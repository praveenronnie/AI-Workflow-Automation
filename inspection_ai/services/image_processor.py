"""
Image Processor - Processes building images in parallel.
Extracts captions, conditions, damage, and other metadata using QwenVL.
"""

import asyncio
import time
from typing import Optional

from inspection_ai.config import MAX_RETRIES, RETRY_BACKOFF_FACTOR
from inspection_ai.services.image_inspection_service import ImageInspectionService
from inspection_ai.services.image_scene_service import ImageSceneService
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
        scene = await ImageSceneService(self.project_manager, self.qwen).analyze(
            image_path
        )
        inspection = await ImageInspectionService(
            self.project_manager, self.qwen
        ).analyze(image_path)

        return {
            "image_name": image_path,
            **scene,
            **inspection,
            "confidence_score": 0.0,
            "evidence": f"Analyzed {image_path}",
        }
