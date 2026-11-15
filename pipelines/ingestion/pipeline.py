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

    try:
        if not file_path:
            raise ValueError("A persisted file path is required for ingestion")

        file_bytes = await _read_file(file_path)
        content_hash = hashlib.sha256(file_bytes).hexdigest()
        existing = await db.get_document_by_hash(content_hash)

        if existing and str(existing["id"]) != document_id:
            return {"document_id": str(existing["id"]), "duplicate": True}

        await db.update_document_status(document_id, "processing")

        if source_type == "pdf":
            pages = extract_pdf(file_bytes)
        elif source_type == "docx":
            pages = extract_docx(file_bytes)
        elif source_type in {"jpeg", "jpg", "png", "gif", "image"}:
            if provider is None:
                raise ValueError("Vision provider is required for image ingestion")
            pages = await extract_image(file_bytes, provider)
        elif source_type == "csv":
            pages = extract_csv(file_bytes)
        elif source_type == "text":
            from pipelines.ingestion.extractors import ExtractedPage

            pages = [
                ExtractedPage(
                    page_number=1,
                    content=file_bytes.decode("utf-8"),
                    content_type="text",
                    metadata={"source_type": "text"},
                )
            ]
        elif source_type == "url":
            pages = await extract_url(file_bytes.decode("utf-8"))
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

        span_context = (
            tracer.start_as_current_span("ingestion.process") if tracer else None
        )
        if span_context:
            with span_context as span:
                chunks = chunk_pages(pages)
                span.set_attribute("document_id", document_id)
                span.set_attribute("source_type", source_type)
                span.set_attribute("page_count", len(pages))
                span.set_attribute("chunk_count", len(chunks))
        else:
            chunks = chunk_pages(pages)

        if provider is not None and chunks:
            embeddings = await provider.embed([chunk["content"] for chunk in chunks])
            if len(embeddings) != len(chunks):
                raise RuntimeError("Embedding provider returned an unexpected result count")
            for chunk, embedding in zip(chunks, embeddings):
                chunk["embedding"] = embedding

        for chunk in chunks:
            chunk["token_count"] = len(chunk["content"].split())

        await db.insert_chunks(document_id, chunks)
        await db.update_document_status(
            document_id,
            "complete",
            metadata={
                "content_hash": content_hash,
                "page_count": len(pages),
                "chunk_count": len(chunks),
                "embedding_count": sum(
                    1 for chunk in chunks if chunk.get("embedding") is not None
                ),
            },
            chunk_count=len(chunks),
        )

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            json.dumps(
                {
                    "event": "ingestion_complete",
                    "document_id": document_id,
                    "duration_ms": duration_ms,
                    "chunks": len(chunks),
                }
            )
        )
        return {
            "document_id": document_id,
            "duplicate": False,
            "page_count": len(pages),
            "chunk_count": len(chunks),
            "embedding_count": sum(
                1 for chunk in chunks if chunk.get("embedding") is not None
            ),
        }
    except Exception as exc:
        logger.exception("Ingestion failed for document %s", document_id)
        try:
            await db.update_document_status(
                document_id,
                "failed",
                metadata={"error": str(exc)[:500]},
            )
        except Exception:
            logger.exception(
                "Could not persist failed status for document %s",
                document_id,
            )
        raise


async def _read_file(file_path: str) -> bytes:
    import asyncio

    return await asyncio.to_thread(Path(file_path).read_bytes)
