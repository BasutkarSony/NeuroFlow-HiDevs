import asyncio
import logging
from neuroflow import NeuroFlowClient

logging.basicConfig(level=logging.INFO)

async def main():
    client = NeuroFlowClient("http://localhost:8000", "YOUR_TOKEN")
    try:
        doc = await client.ingest_file("document.pdf", pipeline_id="PIPELINE_ID")
        logging.info("Ingestion: %s %s", doc.id, doc.status)
        async for token in client.query("Summarize the document.", "PIPELINE_ID", stream=True):
            logging.info("Token: %s", token)
        logging.info("Streaming complete")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
