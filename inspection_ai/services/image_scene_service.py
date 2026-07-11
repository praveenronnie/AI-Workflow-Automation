"""
Image Scene Service - Phase 1: Scene Understanding.
Extracts room, category, view, materials, systems using QwenVL.
"""

import os
from typing import Optional

from inspection_ai.services.qwen_vl_provider import QwenVLProvider


class ImageSceneService:
    def __init__(self, project_manager, qwen: Optional[QwenVLProvider] = None):
        self.project_manager = project_manager
        self.qwen = qwen or QwenVLProvider.get_instance()

    async def analyze(self, image_path: str) -> dict:
        prompt = self._load_prompt()
        result = self.qwen.analyze_image(image_path, prompt)

        if not result["success"]:
            return {
                "room": "unknown",
                "category": "unknown",
                "view": "unknown",
                "materials": [],
                "systems": [],
                "confidence_score": 0.0,
                "evidence": f"Error: {result['error']}",
            }

        data = result["data"]
        return {
            "room": data.get("room", "unknown"),
            "category": data.get("category", "unknown"),
            "view": data.get("view", "unknown"),
            "materials": data.get("materials", []),
            "systems": data.get("systems", []),
            "confidence_score": data.get("confidence", 0.0),
            "evidence": f"Analyzed {image_path}",
        }

    def _load_prompt(self) -> str:
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "prompts", "image_analysis.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
