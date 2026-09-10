import asyncio
from neuroflow import NeuroFlowClient

async def main():
    client = NeuroFlowClient("http://localhost:8000", "YOUR_TOKEN")
    try:
        doc = await client.ingest_file("document.pdf", pipeline_id="PIPELINE_ID")
        print("Ingestion:", doc.id, doc.status)
        async for token in client.query("Summarize the document.", "PIPELINE_ID", stream=True):
            print(token, end="", flush=True)
        print()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
