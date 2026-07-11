"""
Image Processor - Processes building images in parallel.
Extracts scene and inspection data using QwenVL.
"""

import asyncio
import os
from typing import Optional

from inspection_ai.config import (
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    MAX_CONCURRENT_INFERENCES,
)
from inspection_ai.services.qwen_vl_provider import QwenVLProvider


class ImageProcessor:
    def __init__(
        self,
        project_manager,
        max_workers: int = 4,
        qwen: Optional[QwenVLProvider] = None,
    ):
        self.project_manager = project_manager
        self.max_workers = max_workers
        self.qwen = qwen or QwenVLProvider.get_instance()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_INFERENCES)

    async def process_images(self, image_paths: list) -> list:
        tasks = [self._process_single_image(img_path) for img_path in image_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "error": str(result),
                        "confidence_score": 0.0,
                        "evidence": "",
                    }
                )
            else:
                processed_results.append(result)

        return processed_results

    async def _process_single_image(self, image_path: str) -> dict:
        async with self._semaphore:
            for attempt in range(MAX_RETRIES):
                try:
                    return await self._extract_with_retry(image_path)
                except Exception as e:
                    if attempt == MAX_RETRIES - 1:
                        return {
                            "image_name": image_path,
                            "error": str(e),
                            "confidence_score": 0.0,
                            "evidence": "",
                        }
                    wait_time = RETRY_BACKOFF_FACTOR**attempt
                    await asyncio.sleep(wait_time)

        return {}

    async def _extract_with_retry(self, image_path: str) -> dict:
        prompt = self._load_prompt("image_analysis.txt")
        result = self.qwen.analyze_image(image_path, prompt)

        if not result["success"]:
            return {
                "image_name": image_path,
                "room": "unknown",
                "category": "unknown",
                "view": "unknown",
                "materials": [],
                "systems": [],
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
            "image_name": image_path,
            "room": data.get("room", "unknown"),
            "category": data.get("category", "unknown"),
            "view": data.get("view", "unknown"),
            "materials": data.get("materials", []),
            "systems": data.get("systems", []),
            "objects": data.get("objects", []),
            "visible_damage": data.get("visible_damage", []),
            "overall_condition": data.get("overall_condition", "unknown"),
            "caption": data.get("caption", ""),
            "mini_caption": data.get("mini_caption", ""),
            "notes": data.get("notes", ""),
            "confidence_score": data.get("confidence", 0.0),
            "evidence": f"Analyzed {image_path}",
        }

    def _load_prompt(self, filename: str) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
