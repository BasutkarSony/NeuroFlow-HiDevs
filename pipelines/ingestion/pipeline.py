import hashlib
import json
import logging
import time
from pathlib import Path

from pipelines.ingestion.chunker import chunk_pages
from pipelines.ingestion.extractors.csv_extractor import extract_csv
from pipelines.ingestion.extractors.docx_extractor import extract_docx
from pipelines.ingestion.extractors.image_extractor import extract_image
from pipelines.ingestion.extractors.pdf_extractor import extract_pdf
from pipelines.ingestion.extractors.url_extractor import extract_url


logger = logging.getLogger(__name__)


async def process_document(
    document_id: str,
    file_path: str | None,
    source_type: str,
    db,
    provider=None,
    tracer=None,
):
    start_time = time.perf_counter()

    file_bytes = b""

    if file_path:
        file_bytes = Path(file_path).read_bytes()

    content_hash = hashlib.sha256(file_bytes).hexdigest()

    existing = await db.get_document_by_hash(content_hash)

    if existing:
        return {
            "document_id": existing["id"],
            "duplicate": True,
        }

    await db.update_document_status(
        document_id,
        "processing",
    )

    if tracer:
        span_context = tracer.start_as_current_span(
            "ingestion.process"
        )
    else:
        span_context = None

    if span_context:
        with span_context as span:
            result = await _extract_and_chunk(
                document_id=document_id,
                file_bytes=file_bytes,
                source_type=source_type,
                provider=provider,
            )

            _set_span_attributes(
                span,
                document_id,
                source_type,
                result,
            )
    else:
        result = await _extract_and_chunk(
            document_id=document_id,
            file_bytes=file_bytes,
            source_type=source_type,
            provider=provider,
        )

    await db.update_document_status(
        document_id,
        "complete",
        metadata={
            "content_hash": content_hash,
            "page_count": result["page_count"],
            "chunk_count": result["chunk_count"],
        },
    )

    duration_ms = (
        time.perf_counter() - start_time
    ) * 1000

    logger.info(
        json.dumps(
            {
                "event": "ingestion_complete",
                "document_id": document_id,
                "duration_ms": duration_ms,
                "chunks": result["chunk_count"],
                "tokens": result["tokens"],
            }
        )
    )

    return {
        "document_id": document_id,
        "duplicate": False,
        **result,
    }


async def _extract_and_chunk(
    document_id: str,
    file_bytes: bytes,
    source_type: str,
    provider=None,
):
    if source_type == "pdf":
        pages = extract_pdf(file_bytes)

    elif source_type == "docx":
        pages = extract_docx(file_bytes)

    elif source_type in {"jpg", "jpeg", "png", "webp", "image"}:
        if provider is None:
            raise ValueError(
                "Vision provider is required for images"
            )

        pages = await extract_image(
            file_bytes,
            provider,
        )

    elif source_type == "csv":
        pages = extract_csv(file_bytes)

    elif source_type == "url":
        pages = await extract_url(
            file_bytes.decode("utf-8")
        )

    else:
        raise ValueError(
            f"Unsupported source type: {source_type}"
        )

    chunks = chunk_pages(
        pages,
        embedding_provider=provider,
    )

    tokens = sum(
        len(chunk["content"].split())
        for chunk in chunks
    )

    return {
        "page_count": len(pages),
        "chunk_count": len(chunks),
        "tokens": tokens,
        "embedding_calls": 0,
    }


def _set_span_attributes(
    span,
    document_id,
    source_type,
    result,
):
    span.set_attribute(
        "document_id",
        document_id,
    )

    span.set_attribute(
        "source_type",
        source_type,
    )

    span.set_attribute(
        "page_count",
        result["page_count"],
    )

    span.set_attribute(
        "chunk_count",
        result["chunk_count"],
    )

    span.set_attribute(
        "embedding_calls",
        result["embedding_calls"],
    )