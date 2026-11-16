import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from backend.api import ingest as ingest_api
from backend.security.auth import ClientProfile


class FakeRepository:
    def __init__(self, document_id="11111111-1111-4111-8111-111111111111"):
        self.document_id = document_id
        self.created = []
        self.status_updates = []
        self.lookup_calls = []

    async def create_document(self, **kwargs):
        self.created.append(kwargs)
        return self.document_id

    async def get_document_by_hash(self, content_hash, client_id):
        self.lookup_calls.append((content_hash, client_id))
        return {"id": self.document_id, "status": "queued"}

    async def update_document_status(self, document_id, status, metadata=None):
        self.status_updates.append((document_id, status, metadata))


class FakeQueue:
    def __init__(self, error=None):
        self.error = error
        self.jobs = []

    async def enqueue_job(self, function, *args, **kwargs):
        if self.error:
            raise self.error
        self.jobs.append((function, args, kwargs))
        return object()


def fake_request(queue):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(ingestion_queue=queue)))


@pytest.fixture
def api_dependencies(monkeypatch, tmp_path):
    repository = FakeRepository()
    queue = FakeQueue()
    monkeypatch.setattr(
        ingest_api,
        "get_settings",
        lambda: SimpleNamespace(ingestion_storage_path=str(tmp_path)),
    )
    monkeypatch.setattr(
        ingest_api,
        "DocumentRepository",
        lambda pool: repository,
    )
    monkeypatch.setattr(
        ingest_api,
        "db_pool",
        SimpleNamespace(get_pool=lambda: object()),
    )
    monkeypatch.setattr(
        ingest_api,
        "validate_file_content",
        lambda filename, content, content_type: "text",
    )
    return repository, queue, tmp_path


@pytest.mark.asyncio
async def test_file_ingestion_persists_source_and_enqueues_tenant_scoped_job(
    api_dependencies,
):
    repository, queue, storage_dir = api_dependencies
    upload = UploadFile(
        filename="notes.txt",
        file=io.BytesIO(b"NeuroFlow API ingestion test"),
    )

    result = await ingest_api.ingest_file(
        fake_request(queue),
        source_type="file",
        filename="notes.txt",
        pipeline_id=None,
        metadata=json.dumps({"origin": "api-test"}),
        file=upload,
        current_user=ClientProfile(client_id="tenant-a", scopes=["ingest"]),
    )

    assert result["status"] == "queued"
    assert result["ingestion_id"] == repository.document_id
    assert len(repository.created) == 1
    stored_metadata = repository.created[0]["metadata"]
    assert stored_metadata["client_id"] == "tenant-a"
    source_path = Path(stored_metadata["storage_path"])
    assert source_path.parent == storage_dir
    assert source_path.read_bytes() == b"NeuroFlow API ingestion test"
    assert len(queue.jobs) == 1
    assert queue.jobs[0][0] == "ingest_job"
    assert queue.jobs[0][1][-1] == "tenant-a"
    assert queue.jobs[0][2]["_job_id"] == f"ingest:{repository.document_id}"


@pytest.mark.asyncio
async def test_file_ingestion_marks_document_failed_when_queue_is_unavailable(
    api_dependencies,
):
    repository, queue, storage_dir = api_dependencies
    queue.error = RuntimeError("Redis unavailable")
    upload = UploadFile(filename="notes.txt", file=io.BytesIO(b"content"))

    with pytest.raises(HTTPException) as exc_info:
        await ingest_api.ingest_file(
            fake_request(queue),
            source_type="file",
            filename="notes.txt",
            pipeline_id=None,
            metadata="{}",
            file=upload,
            current_user=ClientProfile(client_id="tenant-a", scopes=["ingest"]),
        )

    assert exc_info.value.status_code == 503
    assert repository.status_updates[0][0] == repository.document_id
    assert repository.status_updates[0][1] == "failed"
    source_path = Path(repository.created[0]["metadata"]["storage_path"])
    assert source_path.exists()


@pytest.mark.asyncio
async def test_ingestion_status_does_not_expose_another_tenants_document(monkeypatch):
    class TenantRepository:
        async def get_document_for_client(self, document_id, client_id):
            assert client_id == "tenant-b"
            return None

    monkeypatch.setattr(
        ingest_api,
        "DocumentRepository",
        lambda pool: TenantRepository(),
    )
    monkeypatch.setattr(
        ingest_api,
        "db_pool",
        SimpleNamespace(get_pool=lambda: object()),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ingest_api.get_ingestion_status(
            "11111111-1111-4111-8111-111111111111",
            current_user=ClientProfile(client_id="tenant-b", scopes=["ingest"]),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"] == "INGESTION_NOT_FOUND"
