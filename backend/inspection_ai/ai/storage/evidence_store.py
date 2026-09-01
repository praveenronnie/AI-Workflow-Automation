"""In-memory evidence store with file backup."""

import json
from pathlib import Path
from typing import List, Dict

from ..models.evidence import Evidence


class EvidenceStore:
    """In-memory evidence store with file persistence per report."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.evidence: Dict[str, List[Evidence]] = {}

    def add_evidence(self, report_id: str, evidence: List[Evidence]):
        """Add evidence for a report."""
        if report_id not in self.evidence:
            self.evidence[report_id] = []
        self.evidence[report_id].extend(evidence)
        self.persist(report_id)

    def get_evidence(self, report_id: str) -> List[Evidence]:
        """Get all evidence for a report, loading from disk if needed."""
        if report_id not in self.evidence:
            self.load(report_id)
        return self.evidence.get(report_id, [])

    def get_evidence_by_source(self, report_id: str, source_type: str) -> List[Evidence]:
        """Filter evidence by source type."""
        return [
            e for e in self.get_evidence(report_id)
            if e.source_type == source_type
        ]

    def persist(self, report_id: str):
        """Write evidence to disk."""
        file_path = self.storage_dir / f"{report_id}_evidence.json"
        with open(file_path, "w") as f:
            json.dump([e.dict() for e in self.evidence[report_id]], f, indent=2)

    def load(self, report_id: str):
        """Load evidence from disk."""
        file_path = self.storage_dir / f"{report_id}_evidence.json"
        if file_path.exists():
            with open(file_path, "r") as f:
                data = json.load(f)
                self.evidence[report_id] = [Evidence(**e) for e in data]