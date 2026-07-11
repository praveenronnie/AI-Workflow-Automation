"""
Image Inspection Service - Phase 2: Inspection.
Extracts objects, visible_damage, overall_condition, caption, mini_caption, notes using QwenVL.
"""

import os
from typing import Optional

from inspection_ai.services.qwen_vl_provider import QwenVLProvider


class ImageInspectionService:
    def __init__(self, project_manager, qwen: Optional[QwenVLProvider] = None):
        self.project_manager = project_manager
        self.qwen = qwen or QwenVLProvider.get_instance()

    async def analyze(self, image_path: str) -> dict:
        prompt = self._load_prompt()
        result = self.qwen.analyze_image(image_path, prompt)

        if not result["success"]:
            return {
                "objects": [],
                "visible_damage": [],
                "overall_condition": "unknown",
                "caption": "",
                "mini_caption": "",
                "notes": "",
                "confidence_score": 0.0,
                "evidence": f"Error: {result['error']}",
            }

        data = result["data"]
        return {
            "objects": data.get("objects", []),
            "visible_damage": data.get("visible_damage", []),
            "overall_condition": data.get("overall_condition", "unknown"),
            "caption": data.get("caption", ""),
            "mini_caption": data.get("mini_caption", ""),
            "notes": data.get("notes", ""),
            "confidence_score": data.get("confidence", 0.0),
            "evidence": f"Analyzed {image_path}",
        }

    def _load_prompt(self) -> str:
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "prompts", "image_analysis.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
