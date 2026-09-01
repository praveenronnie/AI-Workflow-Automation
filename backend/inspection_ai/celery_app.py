"""Celery application configuration.

This module exposes a ready‑to‑use :data:`celery_app` instance that can
be imported by both the FastAPI application and the worker executable.

The configuration values are read from :class:`inspection_ai.core.config.Settings`.
Only the minimal set required for the demo is defined – in a real
installation you would likely move these values into environment
variables or a dedicated configuration file.
"""

from __future__ import annotations

from celery import Celery
from inspection_ai.core.config import Settings

settings = Settings()

celery_app = Celery(
    "inspection_ai",
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
    "inspection_ai.tasks.pdf_task",
    "inspection_ai.tasks.image_task",
    "inspection_ai.tasks.embed_worker",
    "inspection_ai.tasks.intent_task",
)
