import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict

from security.auth import ClientProfile, require_scope
from security.secret_detector import redact_secrets
from security.validators import (
    sanitize_text,
    validate_document_url,
    validate_file_content,
)


router = APIRouter()

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MiB


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_url: str | None = None
    url: str | None = None
    filename: str | None = None
    pipeline_id: str | None = None
    metadata: dict[str, Any] = {}


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    return {
        sanitize_text(str(key)).strip(): sanitize_text(str(value)).strip()
        for key, value in metadata.items()
    }


def _queued_response(
    source_type: str,
    pipeline_id: str | None,
    current_user: ClientProfile,
    *,
    source_url: str | None = None,
    filename: str | None = None,
    metadata: dict[str, Any] | None = None,
    redacted_content: str | None = None,
) -> dict[str, Any]:
    response = {
        "ingestion_id": f"ing_{uuid.uuid4().hex}",
        "status": "queued",
        "source_type": source_type,
        "pipeline_id": pipeline_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if source_url is not None:
        response["source_url"] = source_url

    if filename is not None:
        response["filename"] = filename

    if metadata is not None:
        response["metadata"] = metadata

    # Internal processing receives redacted content only.
    # Do not return document content to the API caller.
    if redacted_content is not None:
        response["content_redacted"] = True

    response["client_id"] = current_user.client_id

    return response


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    request: IngestRequest,
    current_user: ClientProfile = Depends(require_scope("ingest")),
) -> dict[str, Any]:
    if request.source_type not in {"url", "file"}:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_SOURCE_TYPE",
                "message": "source_type must be 'file' or 'url'",
            },
        )

    if request.source_type == "url":
        source_url = request.source_url or request.url

        if not source_url:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_URL",
                    "message": "source_url is required for URL ingestion",
                },
            )

        source_url = validate_document_url(source_url)

        filename = (
            sanitize_text(request.filename).strip()
            if request.filename
            else None
        )

        metadata = _sanitize_metadata(request.metadata)

        return _queued_response(
            "url",
            request.pipeline_id,
            current_user,
            source_url=source_url,
            filename=filename,
            metadata=metadata,
        )

    if not request.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_FILE",
                "message": "filename is required for file ingestion",
            },
        )

    raise HTTPException(
        status_code=400,
        detail={
            "error": "INVALID_FILE",
            "message": "File uploads must use multipart/form-data",
        },
    )


@router.post("/ingest/file", status_code=status.HTTP_202_ACCEPTED)
async def ingest_file(
    source_type: str = Form(...),
    filename: str = Form(...),
    pipeline_id: str | None = Form(None),
    metadata: str = Form("{}"),
    file: UploadFile = File(...),
    current_user: ClientProfile = Depends(require_scope("ingest")),
) -> dict[str, Any]:
    import json

    if source_type != "file":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_SOURCE_TYPE",
                "message": "source_type must be 'file' for file uploads",
            },
        )

    safe_filename = sanitize_text(filename).strip()

    try:
        metadata_value = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_METADATA",
                "message": "metadata must be valid JSON",
            },
        ) from exc

    if not isinstance(metadata_value, dict):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_METADATA",
                "message": "metadata must be a JSON object",
            },
        )

    sanitized_metadata = _sanitize_metadata(metadata_value)

    content = await file.read(MAX_FILE_SIZE + 1)

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "FILE_TOO_LARGE",
                "message": "File exceeds the 25 MiB maximum size",
            },
        )

    detected_type = validate_file_content(
        safe_filename,
        content,
        file.content_type,
    )

    # Decode text-like content where possible so secrets can be removed
    # before downstream persistence/embedding.
    redacted_content = None

    if detected_type == "csv":
        text = content.decode("utf-8")
        redacted_content, _ = redact_secrets(text)

    return _queued_response(
        detected_type,
        pipeline_id,
        current_user,
        filename=safe_filename,
        metadata=sanitized_metadata,
        redacted_content=redacted_content,
    )
