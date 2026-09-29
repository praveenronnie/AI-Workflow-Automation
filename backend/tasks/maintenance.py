"""Maintenance task: worker heartbeat + stale-job sweeper.

Runs via Celery beat every minute. Two responsibilities:
1. Write a short-TTL ``worker:heartbeat`` Redis key so ``/ready`` can report
   whether any worker/beat is alive (distinguishes "queued" from "worker dead").
2. Fail jobs stuck in ``queued``/``processing`` beyond a threshold — a worker
   crash otherwise leaves them (and the report's ``mapping_in_progress`` flag)
   stuck forever.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update

from backend.celery_app import celery_app
from backend.database.base import AsyncSessionLocal
from backend.database.models.job import Job

logger = logging.getLogger(__name__)

STALE_AFTER_MINUTES = 15
HEARTBEAT_TTL_SECONDS = 120
HEARTBEAT_KEY = "worker:heartbeat"


def _write_heartbeat() -> None:
    from backend.ai.storage.cache import RedisCache

    cache = RedisCache()
    if cache.client is not None:
        cache.client.set(
            HEARTBEAT_KEY, datetime.utcnow().isoformat(), ex=HEARTBEAT_TTL_SECONDS
        )


async def _sweep() -> int:
    cutoff = datetime.utcnow() - timedelta(minutes=STALE_AFTER_MINUTES)
    failed = 0
    async with AsyncSessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(Job).where(
                        Job.status.in_(["queued", "processing"]),
                        Job.created_at < cutoff,
                    )
                )
            )
            .scalars()
            .all()
        )
        for job in rows:
            await db.execute(
                update(Job)
                .where(Job.id == job.id)
                .values(
                    status="failed",
                    error=f"Stale job: no worker progress for {STALE_AFTER_MINUTES}m",
                    completed_at=datetime.utcnow(),
                )
            )
            failed += 1
            logger.error(
                "[SWEEP] failed stale job: job=%s report=%s type=%s created=%s",
                job.id,
                job.report_id,
                job.job_type,
                job.created_at,
            )
        if failed:
            await db.commit()
    return failed


@celery_app.task(name="backend.tasks.maintenance.maintenance_sweep")
def maintenance_sweep() -> dict:
    """Heartbeat + stale-job sweep. Scheduled every minute via Celery beat."""
    _write_heartbeat()
    try:
        failed = asyncio.run(_sweep())
    except Exception:  # noqa: BLE001 — beat task must never crash the worker
        logger.exception("[SWEEP] maintenance sweep failed")
        failed = -1
    return {"heartbeat": True, "failed_stale_jobs": failed}
