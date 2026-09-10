import asyncio
import json
import time
from typing import Any

from db.pool import db_pool
from fastapi import APIRouter, Depends, HTTPException
from monitoring.metrics import queue_depth, retrieval_latency
from pydantic import BaseModel
from security.auth import ClientProfile, require_scope
from security.prompt_injection import (
    classify_prompt_injection,
    detect_prompt_injection,
)
from security.validators import validate_query
from sse_starlette.sse import EventSourceResponse

from pipelines.generation.generator import RAGGenerator
from pipelines.retrieval.pipeline import RetrievalPipeline

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    pipeline_id: str | None = None
    stream: bool = False


_active_streams: dict[str, asyncio.Queue] = {}


@router.post("/query")
async def query(
    request: QueryRequest,
    current_user: ClientProfile = Depends(require_scope("query")),
):
    sanitized_query = validate_query(request.query)

    # Layer 1: detect and record, but do not reject.

    # Layer 2: LLM classification for every user query.
    provider = _get_provider()

    if await classify_prompt_injection(
        sanitized_query,
        provider,
    ):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "query_rejected",
                "reason": "potential_prompt_injection",
            },
        )

    request.query = sanitized_query

    db = db_pool.get_pool()

    pipeline_config = None

    if request.pipeline_id:
        pipeline_row = await db.fetchrow(
            """
            SELECT config
            FROM pipelines
            WHERE id = $1::uuid
        """,
            request.pipeline_id,
        )

        if pipeline_row is None:
            raise HTTPException(
                status_code=404,
                detail="Pipeline not found.",
            )

        pipeline_config = pipeline_row["config"]

    retrieval_config = (
        pipeline_config.get("retrieval", {})
        if pipeline_config
        else {}
    )
    generation_config = (
        pipeline_config.get("generation", {})
        if pipeline_config
        else {}
    )

    candidate_k = int(
        retrieval_config.get("candidate_k", 40)
    )
    reranker_candidate_k = int(
        retrieval_config.get(
            "reranker_candidate_k",
            candidate_k,
        )
    )

    retrieval = RetrievalPipeline(
        db=db,
        dense_k=int(
            retrieval_config.get("dense_k", 20)
        ),
        sparse_k=int(
            retrieval_config.get("sparse_k", 20)
        ),
        metadata_k=int(
            retrieval_config.get("metadata_k", 20)
        ),
        candidate_k=candidate_k,
        reranker_candidate_k=reranker_candidate_k,
        query_expansion=bool(
            retrieval_config.get(
                "query_expansion",
                True,
            )
        ),
        fusion_k=int(
            retrieval_config.get("fusion_k", 60)
        ),
        fusion_weights=[
            float(
                retrieval_config.get(
                    "dense_weight",
                    1.0,
                )
            ),
            float(
                retrieval_config.get(
                    "sparse_weight",
                    1.0,
                )
            ),
            float(
                retrieval_config.get(
                    "metadata_weight",
                    1.0,
                )
            ),
        ],
        token_budget=int(
            generation_config.get(
                "max_context_tokens",
                4000,
            )
        ),
    )

    retrieval_start = time.perf_counter()
    context_result = await retrieval.retrieve(
        request.query,
        k=int(
            retrieval_config.get(
                "top_k_after_rerank",
                10,
            )
        ),
    )
    retrieval_latency.labels(strategy="hybrid").observe(
        time.perf_counter() - retrieval_start
    )

    if request.stream:
        run_id = await _create_run(db, request)

        queue: asyncio.Queue = asyncio.Queue()
        _active_streams[run_id] = queue
        queue_depth.set(len(_active_streams))

        asyncio.create_task(
            _run_stream(
                run_id,
                request.query,
                context_result,
                queue,
                db,
            )
        )

        return {"run_id": run_id}

    raise HTTPException(
        status_code=501,
        detail="Non-streaming generation requires a configured LLM provider.",
    )


@router.get("/query/{run_id}/stream")
async def query_stream(run_id: str):
    queue = _active_streams.get(run_id)

    if queue is None:
        raise HTTPException(
            status_code=404,
            detail="Stream not found.",
        )

    async def events():
        try:
            while True:
                event = await queue.get()

                yield {
                    "event": event["type"],
                    "data": json.dumps(event),
                }

                if event["type"] == "done":
                    break
        finally:
            _active_streams.pop(run_id, None)
            queue_depth.set(len(_active_streams))

    return EventSourceResponse(
        events(),
        ping=15,
    )


async def _create_run(
    db,
    request: QueryRequest,
) -> str:
    row = await db.fetchrow(
        """
        INSERT INTO pipeline_runs (
            pipeline_id,
            query,
            status
        )
        VALUES (
            $1::uuid,
            $2,
            'running'
        )
        RETURNING id
        """,
        request.pipeline_id,
        request.query,
    )

    return str(row["id"])


async def _run_stream(
    run_id: str,
    query: str,
    context_result: dict[str, Any],
    queue: asyncio.Queue,
    db,
) -> None:
    try:
        sources = context_result.get("sources", [])

        await queue.put(
            {
                "type": "retrieval_start",
            }
        )

        await queue.put(
            {
                "type": "retrieval_complete",
                "chunk_count": len(
                    context_result.get(
                        "chunks_used",
                        [],
                    )
                ),
                "sources": sources,
            }
        )

        provider = _get_provider()

        generator = RAGGenerator(
            provider=provider,
            db=db,
        )

        async for event in generator.stream(
            query=query,
            context_result=context_result,
            run_id=run_id,
        ):
            await queue.put(event)

    except Exception as exc:
        await queue.put(
            {
                "type": "error",
                "message": str(exc),
            }
        )


_provider = None


def configure_provider(provider):
    global _provider
    _provider = provider


def _get_provider():
    if _provider is None:
        raise RuntimeError(
            "No LLM provider configured for query generation."
        )
    return _provider
