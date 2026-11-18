import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from backend.api import query as query_api
from backend.security.auth import ClientProfile


@pytest.mark.asyncio
async def test_query_passes_configured_provider_to_retrieval_pipeline(monkeypatch):
    provider = object()
    captured = {}

    async def allow_query(_query, _provider):
        assert _provider is provider
        return False

    class FakeRetrievalPipeline:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def retrieve(self, query, k):
            return {"chunks_used": [], "sources": []}

    monkeypatch.setattr(query_api, "_get_provider", lambda: provider)
    monkeypatch.setattr(query_api, "classify_prompt_injection", allow_query)
    monkeypatch.setattr(
        query_api,
        "db_pool",
        SimpleNamespace(get_pool=lambda: object()),
    )
    monkeypatch.setattr(query_api, "RetrievalPipeline", FakeRetrievalPipeline)

    with pytest.raises(HTTPException) as exc_info:
        await query_api.query(
            query_api.QueryRequest(query="Explain hybrid retrieval."),
            current_user=ClientProfile(client_id="test-client", scopes=["query"]),
        )

    assert exc_info.value.status_code == 501
    assert captured["embedding_provider"] is provider
    assert captured["client_id"] == "test-client"
