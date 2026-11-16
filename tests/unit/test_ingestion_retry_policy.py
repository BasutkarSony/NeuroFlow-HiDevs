import pytest
from arq.worker import Retry

from pipelines.ingestion import worker


class FakeRepository:
    def __init__(self):
        self.status_updates = []

    async def update_document_status(self, document_id, status, metadata=None, **kwargs):
        self.status_updates.append((document_id, status, metadata or {}))


@pytest.mark.asyncio
async def test_transient_ingestion_error_is_retried_without_marking_failed(monkeypatch):
    repository = FakeRepository()

    async def fail_transiently(**kwargs):
        raise RuntimeError("temporary provider outage")

    monkeypatch.setattr(worker, "process_document", fail_transiently)

    with pytest.raises(Retry) as retry:
        await worker.ingest_job(
            {"db": repository, "job_try": 1},
            "document-1",
            "/tmp/source.txt",
            "text",
            "client-1",
        )

    assert retry.value.defer_score == 1000
    assert repository.status_updates == []


@pytest.mark.asyncio
async def test_final_transient_failure_is_persisted(monkeypatch):
    repository = FakeRepository()

    async def fail_transiently(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(worker, "process_document", fail_transiently)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await worker.ingest_job(
            {"db": repository, "job_try": worker.MAX_INGESTION_TRIES},
            "document-2",
            "/tmp/source.txt",
            "text",
            "client-1",
        )

    assert repository.status_updates == [
        (
            "document-2",
            "failed",
            {"error": "provider unavailable", "attempts": worker.MAX_INGESTION_TRIES},
        )
    ]


@pytest.mark.asyncio
async def test_permanent_ingestion_error_is_not_retried(monkeypatch):
    repository = FakeRepository()

    async def fail_permanently(**kwargs):
        raise ValueError("unsupported source type")

    monkeypatch.setattr(worker, "process_document", fail_permanently)

    with pytest.raises(ValueError, match="unsupported source type"):
        await worker.ingest_job(
            {"db": repository, "job_try": 1},
            "document-3",
            "/tmp/source.txt",
            "unknown",
            "client-1",
        )

    assert repository.status_updates[0][1] == "failed"
    assert repository.status_updates[0][2]["attempts"] == 1
