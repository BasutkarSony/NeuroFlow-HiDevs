from pathlib import Path

from openai import AsyncOpenAI


async def submit_finetune_job(
    jsonl_path: str,
    base_model: str,
) -> str:
    client = AsyncOpenAI()

    with Path(jsonl_path).open("rb") as handle:
        file_resp = await client.files.create(
            file=handle,
            purpose="fine-tune",
        )

    job = await client.fine_tuning.jobs.create(
        training_file=file_resp.id,
        model=base_model,
    )

    return job.id


async def get_finetune_status(
    provider_job_id: str,
):
    client = AsyncOpenAI()

    return await client.fine_tuning.jobs.retrieve(
        provider_job_id
    )
