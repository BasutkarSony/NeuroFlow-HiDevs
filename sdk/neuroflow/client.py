import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from .models import Document, EvaluationResult, QueryResult


class NeuroFlowClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, headers={"Authorization": f"Bearer {token}"})

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        for attempt in range(4):
            response = await self.client.request(method, path, **kwargs)
            if response.status_code != 429 or attempt == 3:
                response.raise_for_status()
                return response
            await asyncio.sleep(2 ** attempt)
        raise RuntimeError("Request failed")

    async def ingest_file(self, file_path: str, pipeline_id: str | None = None) -> Document:
        path = Path(file_path)
        with path.open("rb") as file:
            response = await self._request("POST", "/ingest/file", data={"source_type": "file", "filename": path.name, "pipeline_id": pipeline_id or "", "metadata": "{}"}, files={"file": (path.name, file, "application/octet-stream")})
        data = response.json()
        return Document(data["ingestion_id"], data["status"], data)

    async def ingest_url(self, url: str, pipeline_id: str | None = None) -> Document:
        response = await self._request("POST", "/ingest", json={"source_type": "url", "source_url": url, "pipeline_id": pipeline_id})
        data = response.json()
        return Document(data["ingestion_id"], data["status"], data)

    def query(self, query: str, pipeline_id: str, stream: bool = False):
        async def run():
            response = await self._request("POST", "/query", json={"query": query, "pipeline_id": pipeline_id, "stream": stream})
            data = response.json()
            run_id = data["run_id"]
            return run_id, data

        if stream:
            async def streaming():
                run_id, _ = await run()
                async for token in self._stream(run_id):
                    yield token
            return streaming()

        async def non_streaming():
            run_id, data = await run()
            return QueryResult(run_id, data.get("answer", ""), data)

        return non_streaming()

    async def _stream(self, run_id: str) -> AsyncIterator[str]:
        async with self.client.stream("GET", f"/query/{run_id}/stream") as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line[5:].strip())
                    if payload.get("type") == "token":
                        yield payload.get("token", "")
                    elif payload.get("type") == "done":
                        break

    async def get_evaluation(self, run_id: str, wait: bool = True) -> EvaluationResult:
        while True:
            response = await self.client.get(f"/evaluations/{run_id}")
            if response.status_code == 404 and wait:
                await asyncio.sleep(2)
                continue
            response.raise_for_status()
            data = response.json()
            return EvaluationResult(data["id"], run_id, data)

    async def list_pipelines(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/pipelines")
        data = response.json()
        return data if isinstance(data, list) else data.get("pipelines", [])

    async def create_pipeline(self, config: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", "/pipelines", json=config)
        return response.json()
