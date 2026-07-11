"""
Project Manager - Single source of truth for project data.
Handles all file I/O and project state management.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Optional

from inspection_ai.config import STORAGE_DIR
from inspection_ai.models.dto import ProcessingStep


class ProjectManager:
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or str(uuid.uuid4())
        self.project_path = os.path.join(STORAGE_DIR, self.project_id)
        self.json_path = os.path.join(self.project_path, "project.json")

    def create_project(self, project_name: str) -> dict:
        os.makedirs(self.project_path, exist_ok=True)
        os.makedirs(os.path.join(self.project_path, "images"), exist_ok=True)

        project = {
            "metadata": {
                "project_id": self.project_id,
                "project_name": project_name,
                "status": "created",
                "created_at": datetime.utcnow().isoformat(),
            },
            "files": {"handwritten_pdf": "", "scanned_pdf": "", "images": []},
            "document_data": {},
            "image_analysis": [],
            "field_mapping": {},
            "automation": {},
            "logs": [],
        }
        self._save_json(self.json_path, project)
        return project

    def load_project(self) -> dict:
        if not os.path.exists(self.json_path):
            raise FileNotFoundError(f"Project {self.project_id} not found")
        return self._load_json(self.json_path)

    def save_project(self, project: dict) -> None:
        self._save_json(self.json_path, project)

    def update_status(self, status: str) -> None:
        project = self.load_project()
        project["metadata"]["status"] = status
        self.save_project(project)

    def add_log(
        self, step: str, status: str, duration_ms: int = 0, error: Optional[str] = None
    ) -> None:
        project = self.load_project()
        log_entry = ProcessingStep(
            step=step,
            status=status,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration_ms,
            error=error,
        )
        project["logs"].append(log_entry.to_dict())
        self.save_project(project)

    def save_document_output(self, data: dict) -> None:
        output_path = os.path.join(self.project_path, "document_output.json")
        self._save_json(output_path, data)

    def save_image_output(self, data: list) -> None:
        output_path = os.path.join(self.project_path, "image_output.json")
        self._save_json(output_path, data)

    def save_mapping_output(self, data: dict) -> None:
        output_path = os.path.join(self.project_path, "mapping.json")
        self._save_json(output_path, data)

    def save_processing_log(self, data: list) -> None:
        log_path = os.path.join(self.project_path, "processing.log.json")
        self._save_json(log_path, data)

    def _load_json(self, path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, path: str, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
