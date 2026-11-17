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
async def test_recovery_requeues_abandoned_processing_document_with_stable_job_id():
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
    assert kwargs["_job_id"] == "ingest-recovery:doc-123:2026-11-16T10:00:00+00:00"
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
