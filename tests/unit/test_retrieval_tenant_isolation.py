import pytest

from pipelines.retrieval.query_processor import ProcessedQuery
from pipelines.retrieval.retriever import HybridRetriever


class FakeDatabase:
    def __init__(self):
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return []


class FakeEmbeddingProvider:
    async def embed(self, texts):
        assert len(texts) == 1
        return [[0.1, 0.2, 0.3]]


def test_retriever_requires_client_id():
    with pytest.raises(ValueError, match="client_id is required"):
        HybridRetriever(db=FakeDatabase(), client_id=" ")


@pytest.mark.asyncio
async def test_dense_retrieval_is_scoped_to_authenticated_tenant():
    db = FakeDatabase()
    retriever = HybridRetriever(
        db=db,
        client_id="tenant-a",
        embedding_provider=FakeEmbeddingProvider(),
    )

    await retriever._dense_retrieval("hybrid retrieval", 7)

    sql, args = db.calls[0]
    assert "JOIN documents AS d ON d.id = c.document_id" in sql
    assert "d.metadata->>'client_id' = $2" in sql
    assert args == ([0.1, 0.2, 0.3], "tenant-a", 7)


@pytest.mark.asyncio
async def test_sparse_retrieval_is_scoped_to_authenticated_tenant():
    db = FakeDatabase()
    retriever = HybridRetriever(db=db, client_id="tenant-a")

    await retriever._sparse_retrieval("hybrid retrieval", 9)

    sql, args = db.calls[0]
    assert "JOIN documents AS d ON d.id = c.document_id" in sql
    assert "d.metadata->>'client_id' = $2" in sql
    assert args == ("hybrid retrieval", "tenant-a", 9)


@pytest.mark.asyncio
async def test_metadata_retrieval_is_scoped_to_authenticated_tenant():
    db = FakeDatabase()
    retriever = HybridRetriever(
        db=db,
        client_id="tenant-a",
        embedding_provider=FakeEmbeddingProvider(),
    )
    processed = ProcessedQuery(
        original="climate change in 2025",
        expansions=["climate change in 2025"],
        filters={"year": 2025, "topic": "climate"},
        query_type="factual",
    )

    await retriever._metadata_retrieval(
        "climate change in 2025",
        processed,
        5,
    )

    sql, args = db.calls[0]
    assert "JOIN documents AS d ON d.id = c.document_id" in sql
    assert "d.metadata->>'client_id' = $3" in sql
    assert args == (
        [0.1, 0.2, 0.3],
        '{"year": 2025, "topic": "climate"}',
        "tenant-a",
        5,
    )
