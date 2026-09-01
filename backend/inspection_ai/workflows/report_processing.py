"""Multi-step orchestration shared by HTTP handlers and Celery tasks.

Only genuinely cross-feature pipelines belong here; single-feature logic
lives in that feature's service module.
"""

import logging

from inspection_ai.core.container import get_universal_services
from inspection_ai.database.repositories.report_repository import ReportRepository
from inspection_ai.features.reports.service import run_mapping

logger = logging.getLogger(__name__)


async def process_report_mapping(report_id: str, user_id: str, db, domain_id: int = 1) -> dict:
    """Full map flow for a report: status updates, mapping, persistence."""
    repo = ReportRepository(db)
    await repo.set_mapping_in_progress(report_id, True)
    try:
        return await run_mapping(report_id, user_id, db, domain_id=domain_id)
    except Exception:
        logger.exception("[WORKFLOW] report mapping failed: report_id=%s", report_id)
        raise
    finally:
        await repo.set_mapping_in_progress(report_id, False)