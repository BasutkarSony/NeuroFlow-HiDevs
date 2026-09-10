from apscheduler.schedulers.asyncio import AsyncIOScheduler
import structlog

log = structlog.get_logger()


async def run_retention(db):
    completed_runs = await db.execute("""
        DELETE FROM pipeline_runs
        WHERE created_at < NOW() - INTERVAL '90 days'
          AND status = 'complete'
          AND NOT EXISTS (SELECT 1 FROM evaluations e WHERE e.run_id = pipeline_runs.id)
    """)
    evaluations = await db.execute("""
        DELETE FROM evaluations
        WHERE evaluated_at < NOW() - INTERVAL '180 days'
    """)
    chunks = await db.execute("""
        DELETE FROM chunks c
        USING documents d
        WHERE c.document_id = d.id AND d.status = 'archived'
    """)
    log.info(
        "retention_completed", pipeline_runs=completed_runs, evaluations=evaluations, chunks=chunks
    )
    return {"pipeline_runs": completed_runs, "evaluations": evaluations, "chunks": chunks}


def create_scheduler(db):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_retention, "interval", days=1, args=[db], id="data-retention", replace_existing=True
    )
    return scheduler
