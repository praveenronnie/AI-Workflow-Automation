from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init
from backend.core.config import Settings

settings = Settings()

celery_app = Celery(
    "backend",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configure Celery to use JSON as the serializer for both tasks and
# results.  Mongo, Redis and other brokers all support this by default.
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_create_missing_queues=True,
)

celery_app.conf.imports = (
    "backend.tasks.pdf_task",
    "backend.tasks.image_task",
    "backend.tasks.embed_worker",
    "backend.tasks.intent_task",
    "backend.tasks.maintenance",
)

# Celery beat: worker heartbeat + stale-job sweeper (plan item 1.2)
celery_app.conf.beat_schedule = {
    "maintenance-sweep-every-minute": {
        "task": "backend.tasks.maintenance.maintenance_sweep",
        "schedule": 60.0,
    },
}


@worker_process_init.connect
def _warm_services(**kwargs):
    from backend.core.container import warmup_services

    warmup_services()
