"""
Review Service - Handles manual review and correction of extracted data.
"""


class ReviewService:
    def __init__(self, project_manager):
        self.project_manager = project_manager

    def get_review_data(self) -> dict:
        project = self.project_manager.load_project()
        return {
            "document_data": project.get("document_data", {}),
            "image_analysis": project.get("image_analysis", []),
            "field_mapping": project.get("field_mapping", {}),
            "approval_status": project.get("metadata", {}).get(
                "approval_status", "pending"
            ),
        }

    def update_field(self, field_name: str, new_value: str) -> None:
        project = self.project_manager.load_project()
        if "document_data" not in project:
            project["document_data"] = {}
        project["document_data"][field_name] = new_value
        self.project_manager.save_project(project)

    def approve_mapping(self) -> None:
        project = self.project_manager.load_project()
        project["metadata"]["approval_status"] = "approved"
        self.project_manager.save_project(project)

    def reject_mapping(self) -> None:
        project = self.project_manager.load_project()
        project["metadata"]["approval_status"] = "rejected"
        self.project_manager.save_project(project)

    def is_approved(self) -> bool:
        project = self.project_manager.load_project()
        return project.get("metadata", {}).get("approval_status") == "approved"
