import hashlib
import json
import uuid
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from config import get_settings
from db.pool import db_pool


router = APIRouter()

MAX_FILE_SIZE = 100 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".webp": "image",
    ".csv": "csv",
}


class URLRequest(BaseModel):
    url: str


def _source_type(filename: str) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type",
        )

    return ALLOWED_EXTENSIONS[extension]


async def _find_duplicate(pool, content_hash: str):
    return await pool.fetchrow(
        """
        SELECT id, status
        FROM documents
        WHERE content_hash = $1
        """,
        content_hash,
    )


async def _create_document(
    pool,
    document_id,
    filename,
    source_type,
    content_hash,
    metadata,
):
    await pool.execute(
        """
        INSERT INTO documents (
            id,
            filename,
            source_type,
            content_hash,
            metadata,
            status
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        document_id,
        filename,
        source_type,
        content_hash,
        json.dumps(metadata),
        "queued",
    )


async def _enqueue_ingestion(
    document_id: str,
    file_path: str | None,
    source_type: str,
):
    settings = get_settings()

    redis = await create_pool(
        RedisSettings(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            database=0,
        )
    )

    try:
        await redis.enqueue_job(
            "ingest_job",
            document_id,
            file_path,
            source_type,
        )
    finally:
        await redis.close()


@router.post("/ingest")
async def ingest(
    file: UploadFile | None = File(default=None),
):
    if file is None:
        raise HTTPException(
            status_code=400,
            detail="File upload is required",
        )

    filename = file.filename or ""
    source_type = _source_type(filename)

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File exceeds 100MB limit",
        )

    content_hash = hashlib.sha256(content).hexdigest()

    pool = db_pool.get_pool()

    duplicate = await _find_duplicate(
        pool,
        content_hash,
    )

    if duplicate:
        return {
            "document_id": str(duplicate["id"]),
            "status": duplicate["status"],
            "duplicate": True,
        }

    document_id = uuid.uuid4()

    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)

    file_path = upload_dir / f"{document_id}_{filename}"
    file_path.write_bytes(content)

    await _create_document(
        pool,
        document_id,
        filename,
        source_type,
        content_hash,
        {
            "file_path": str(file_path),
        },
    )

    await _enqueue_ingestion(
        str(document_id),
        str(file_path),
        source_type,
    )

    return {
        "document_id": str(document_id),
        "status": "queued",
        "duplicate": False,
    }


@router.post("/ingest/url")
async def ingest_url(request: URLRequest):
    if not request.url.startswith(
        ("http://", "https://")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL",
        )

    content_hash = hashlib.sha256(
        request.url.encode()
    ).hexdigest()

    pool = db_pool.get_pool()

    duplicate = await _find_duplicate(
        pool,
        content_hash,
    )

    if duplicate:
        return {
            "document_id": str(duplicate["id"]),
            "status": duplicate["status"],
            "duplicate": True,
        }

    document_id = uuid.uuid4()

    await _create_document(
        pool,
        document_id,
        request.url,
        "url",
        content_hash,
        {
            "url": request.url,
        },
    )

    await _enqueue_ingestion(
        str(document_id),
        None,
        "url",
    )

    return {
        "document_id": str(document_id),
        "status": "queued",
        "duplicate": False,
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: uuid.UUID,
):
    pool = db_pool.get_pool()

    document = await pool.fetchrow(
        """
        SELECT
            id,
            filename,
            source_type,
            status,
            chunk_count,
            metadata,
            created_at
        FROM documents
        WHERE id = $1
        """,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return {
        "document_id": str(document["id"]),
        "filename": document["filename"],
        "source_type": document["source_type"],
        "status": document["status"],
        "chunk_count": document["chunk_count"] or 0,
        "metadata": document["metadata"],
        "created_at": document["created_at"].isoformat(),
    }