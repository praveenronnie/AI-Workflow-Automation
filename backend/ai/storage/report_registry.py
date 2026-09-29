"""Report context and session management."""

import uuid
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class UniversalReportContext:
    """Universal report context."""

    report_id: str
    session_id: str
    evidence_batch_id: str
    source_domain: str
    source_url: Optional[str] = None
    created_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()


class ReportRegistry:
    """Manages report contexts with file-based persistence."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.contexts: dict = {}
        self.load_contexts()

    def create_context(
        self,
        report_id: str,
        source_domain: str = "openquire",
        source_url: Optional[str] = None,
    ) -> UniversalReportContext:
        """Create a new report context."""
        context = UniversalReportContext(
            report_id=report_id,
            session_id=str(uuid.uuid4()),
            evidence_batch_id=str(uuid.uuid4()),
            source_domain=source_domain,
            source_url=source_url or f"https://openquire.com/reports/{report_id}",
        )
        self.contexts[report_id] = context
        self.save_context(context)
        return context

    def get_or_create(
        self,
        report_id: str,
        source_domain: str = "openquire",
        source_url: Optional[str] = None,
    ) -> UniversalReportContext:
        """Get existing context or create a new one."""
        context = self.get_context(report_id)
        if context:
            return context
        return self.create_context(report_id, source_domain, source_url)

    def get_context(self, report_id: str) -> Optional[UniversalReportContext]:
        """Get existing context."""
        return self.contexts.get(report_id)

    def add_batch(self, report_id: str) -> str:
        """Create a new evidence batch id for an existing report."""
        context = self.contexts.get(report_id)
        if not context:
            raise ValueError(f"Report {report_id} not found")
        new_batch_id = str(uuid.uuid4())
        context.evidence_batch_id = new_batch_id
        self.save_context(context)
        return new_batch_id

    def save_context(self, context: UniversalReportContext):
        """Persist a context to disk."""
        context_file = self.storage_dir / f"{context.report_id}_context.json"
        with open(context_file, "w") as f:
            json.dump(context.__dict__, f, indent=2)

    def load_contexts(self):
        """Load all contexts from disk."""
        for context_file in self.storage_dir.glob("*_context.json"):
            with open(context_file, "r") as f:
                data = json.load(f)
                context = UniversalReportContext(**data)
                self.contexts[context.report_id] = context