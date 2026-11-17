import asyncio
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from config import get_settings
from db.pool import db_pool
from pipelines.ingestion.repository import DocumentRepository
from security.auth import ClientProfile, require_scope
from security.secret_detector import redact_secrets
from security.validators import (
    sanitize_text,
    validate_document_url,
    validate_file_content,
)

router = APIRouter()
MAX_FILE_SIZE = 25 * 1024 * 1024


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(description="Ingestion source type.", examples=["url"])
    source_url: str | None = None
    url: str | None = None
    filename: str | None = None
    pipeline_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    return {
        sanitize_text(str(key)).strip(): sanitize_text(str(value)).strip()
        for key, value in metadata.items()
    }


async def _submit_ingestion(
    request: Request,
    *,
    source_type: str,
    filename: str,
    content: bytes,
    pipeline_id: str | None,
    metadata: dict[str, Any],
    client_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    document_uuid = uuid.uuid4()
    storage_dir = Path(settings.ingestion_storage_path)
    file_path = storage_dir / f"{document_uuid}.source"
    content_hash = hashlib.sha256(content).hexdigest()
    document_id = None

    try:
        await asyncio.to_thread(storage_dir.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(file_path.write_bytes, content)

        repository = DocumentRepository(db_pool.get_pool())
        document_id = await repository.create_document(
            filename=filename,
            source_type=source_type,
            content_hash=content_hash,
            pipeline_id=pipeline_id,
            metadata={
                **metadata,
                "client_id": client_id,
                "storage_path": str(file_path),
            },
        )

        if document_id is None:
            await asyncio.to_thread(file_path.unlink, missing_ok=True)
            existing = await repository.get_document_by_hash(content_hash, client_id)
            return {
                "ingestion_id": str(existing["id"]) if existing else None,
                "status": "duplicate",
                "source_type": source_type,
                "duplicate": True,
            }

        queue = request.app.state.ingestion_queue
        job = await queue.enqueue_job(
            "ingest_job",
            document_id,
            str(file_path),
            source_type,
            client_id,
            _job_id=f"ingest:{document_id}",
        )
        if job is None:
            # ARQ returns None when this deterministic job ID already exists.
            return {
                "ingestion_id": document_id,
                "status": "queued",
                "source_type": source_type,
                "duplicate": True,
            }

        return {
            "ingestion_id": document_id,
            "status": "queued",
            "source_type": source_type,
            "filename": filename,
        }
    except HTTPException:
        raise
    except Exception as exc:
        import logging

        logging.getLogger(__name__).exception(
            "Failed to enqueue ingestion for client %s (document %s)",
            client_id,
            document_id,
        )
        try:
            if document_id is None:
                await asyncio.to_thread(file_path.unlink, missing_ok=True)
            else:
                repository = DocumentRepository(db_pool.get_pool())
                await repository.update_document_status(
                    document_id,
                    "failed",
                    metadata={"enqueue_error": str(exc)[:500]},
                )
        except Exception:
            pass
        raise HTTPException(
            status_code=503,
            detail={
                "error": "INGESTION_QUEUE_UNAVAILABLE",
                "message": "The ingestion request could not be queued. Please retry.",
            },
        ) from exc


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    request: Request,
    payload: IngestRequest,
    current_user: ClientProfile = Depends(require_scope("ingest")),
) -> dict[str, Any]:
    if payload.source_type != "url":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_SOURCE_TYPE",
                "message": "source_type must be 'url' for this endpoint",
            },
        )

    source_url = payload.source_url or payload.url
    if not source_url:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_URL", "message": "source_url is required"},
        )

    source_url = validate_document_url(source_url)
    parsed = urlparse(source_url)
    filename = sanitize_text(payload.filename or Path(parsed.path).name or "webpage").strip()
    if not filename:
        filename = "webpage"

    pipeline_id = None
    if payload.pipeline_id:
        try:
            pipeline_id = str(uuid.UUID(payload.pipeline_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="pipeline_id must be a UUID") from exc

    return await _submit_ingestion(
        request,
        source_type="url",
        filename=filename,
        content=source_url.encode("utf-8"),
        pipeline_id=pipeline_id,
        metadata={**_sanitize_metadata(payload.metadata), "source_url": source_url},
        client_id=current_user.client_id,
    )


@router.post("/ingest/file", status_code=status.HTTP_202_ACCEPTED)
async def ingest_file(
    request: Request,
    source_type: str = Form(...),
    filename: str = Form(...),
    pipeline_id: str | None = Form(None),
    metadata: str = Form("{}"),
    file: UploadFile = File(...),
    current_user: ClientProfile = Depends(require_scope("ingest")),
) -> dict[str, Any]:
    if source_type != "file":
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_SOURCE_TYPE", "message": "source_type must be 'file'"},
        )

    safe_filename = sanitize_text(filename).strip()
    if not safe_filename:
        raise HTTPException(status_code=400, detail="filename cannot be empty")

    try:
        metadata_value = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_METADATA", "message": "metadata must be valid JSON"},
        ) from exc
    if not isinstance(metadata_value, dict):
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_METADATA", "message": "metadata must be a JSON object"},
        )

    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={"error": "FILE_TOO_LARGE", "message": "File exceeds the 25 MiB maximum size"},
        )

    detected_type = validate_file_content(safe_filename, content, file.content_type)
    if detected_type in {"jpeg", "jpg", "png", "gif"}:
        detected_type = "image"
    if detected_type == "csv":
        redacted, _ = redact_secrets(content.decode("utf-8"))
        content = redacted.encode("utf-8")

    parsed_pipeline_id = None
    if pipeline_id:
        try:
            parsed_pipeline_id = str(uuid.UUID(pipeline_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="pipeline_id must be a UUID") from exc

    return await _submit_ingestion(
        request,
        source_type=detected_type,
        filename=safe_filename,
        content=content,
        pipeline_id=parsed_pipeline_id,
        metadata=_sanitize_metadata(metadata_value),
        client_id=current_user.client_id,
    )

@router.get("/ingest/{document_id}")
async def get_ingestion_status(
    document_id: str,
    current_user: ClientProfile = Depends(require_scope("ingest")),
) -> dict[str, Any]:
    try:
        parsed_id = str(uuid.UUID(document_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_INGESTION_ID", "message": "ingestion_id must be a UUID"},
        ) from exc

    repository = DocumentRepository(db_pool.get_pool())
    document = await repository.get_document_for_client(
        parsed_id,
        current_user.client_id,
    )
    if document is None:
        # Do not reveal whether another client owns the document.
        raise HTTPException(
            status_code=404,
            detail={"error": "INGESTION_NOT_FOUND", "message": "Ingestion not found"},
        )

    metadata = document["metadata"] or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    safe_metadata = {
        key: metadata[key]
        for key in ("source_url", "page_count", "embedding_count")
        if key in metadata
    }
    return {
        "ingestion_id": str(document["id"]),
        "filename": document["filename"],
        "source_type": document["source_type"],
        "status": document["status"],
        "chunk_count": document["chunk_count"],
        "metadata": safe_metadata,
        "created_at": document["created_at"].isoformat(),
    }
