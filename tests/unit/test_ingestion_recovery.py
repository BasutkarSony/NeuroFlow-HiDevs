import pytest

from pipelines.ingestion.worker import recover_ingestion_documents


class RecoveryRepository:
    def __init__(self, documents):
        self.documents = documents
        self.failed = []

    async def recoverable_ingestion_documents(self):
        return self.documents

    async def update_document_status(self, document_id, status, metadata=None):
        self.failed.append((document_id, status, metadata))


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_job(self, function, *args, **kwargs):
        self.jobs.append((function, args, kwargs))
        return object()


@pytest.mark.asyncio
async def test_recovery_reuses_original_job_id_for_abandoned_processing_document():
    repository = RecoveryRepository(
        [
            {
                "document_id": "doc-123",
                "source_type": "text",
                "metadata": {
                    "client_id": "client-1",
                    "storage_path": "/data/doc-123.source",
                    "processing_started_at": "2026-11-16T10:00:00+00:00",
                },
            }
        ]
    )
    queue = FakeQueue()

    await recover_ingestion_documents({"db": repository, "redis": queue})

    assert len(queue.jobs) == 1
    function, args, kwargs = queue.jobs[0]
    assert function == "ingest_job"
    assert args == (
        "doc-123",
        "/data/doc-123.source",
        "text",
        "client-1",
    )
    assert kwargs["_job_id"] == "ingest:doc-123"
    assert repository.failed == []


@pytest.mark.asyncio
async def test_recovery_uses_same_job_id_for_queued_document_without_processing_timestamp():
    repository = RecoveryRepository(
        [
            {
                "document_id": "doc-789",
                "source_type": "text",
                "metadata": {
                    "client_id": "client-1",
                    "storage_path": "/data/doc-789.source",
                },
            }
        ]
    )
    queue = FakeQueue()

    await recover_ingestion_documents({"db": repository, "redis": queue})

    assert len(queue.jobs) == 1
    assert queue.jobs[0][2]["_job_id"] == "ingest:doc-789"
    assert repository.failed == []


@pytest.mark.asyncio
async def test_recovery_marks_records_with_missing_storage_metadata_failed():
    repository = RecoveryRepository(
        [
            {
                "document_id": "doc-456",
                "source_type": "text",
                "metadata": {"client_id": "client-1"},
            }
        ]
    )
    queue = FakeQueue()

    await recover_ingestion_documents({"db": repository, "redis": queue})

    assert queue.jobs == []
    assert repository.failed == [
        (
            "doc-456",
            "failed",
            {"error": "Recovery metadata is missing storage_path or client_id"},
        )
    ]
