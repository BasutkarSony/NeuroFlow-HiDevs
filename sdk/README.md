# NeuroFlow Python SDK

Python client for the NeuroFlow API.

## Install
```bash
pip install ./sdk
```

## Quickstart
```python
from neuroflow import NeuroFlowClient

client = NeuroFlowClient("http://localhost:8000", "YOUR_TOKEN")
doc = await client.ingest_file("document.pdf", pipeline_id="PIPELINE_ID")
async for token in await client.query("Summarize the document.", "PIPELINE_ID", stream=True):
    print(token, end="", flush=True)
```

The SDK uses Bearer authentication, retries rate-limited requests, supports SSE streaming, and polls evaluations until available.
