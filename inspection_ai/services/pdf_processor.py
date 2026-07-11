"""
PDF Processor - Converts PDF pages to images and extracts data using QwenVL.
"""

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from inspection_ai.config import MAX_RETRIES, RETRY_BACKOFF_FACTOR, STORAGE_DIR
from pdf2image import convert_from_path

from inspection_ai.services.docling_processor import DoclingProcessor
from inspection_ai.services.llm_extractor import LLMExtractor
from inspection_ai.services.qwen_vl_provider import QwenVLProvider


class PDFProcessor:
    def __init__(self, project_manager, qwen: Optional[QwenVLProvider] = None):
        self.project_manager = project_manager
        self.qwen = qwen or QwenVLProvider.get_instance()
        self.docling = DoclingProcessor()
        self.llm = LLMExtractor()

    async def process_pdfs(self, handwritten_path: str, scanned_path: str) -> dict:
        results = {}

        tasks = []
        if handwritten_path:
            tasks.append(self._process_single_pdf(handwritten_path, "handwritten"))
        if scanned_path:
            tasks.append(self._process_single_pdf(scanned_path, "scanned"))

        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(task_results):
                if isinstance(result, Exception):
                    results[["handwritten", "scanned"][i]] = {"error": str(result)}
                else:
                    results[["handwritten", "scanned"][i]] = result

        return results

    async def _process_single_pdf(self, pdf_path: str, doc_type: str) -> dict:
        for attempt in range(MAX_RETRIES):
            try:
                if doc_type == "scanned":
                    return await self._extract_with_llm(pdf_path, doc_type)
                return await self._extract_with_retry(pdf_path, doc_type)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait_time = RETRY_BACKOFF_FACTOR**attempt
                await asyncio.sleep(wait_time)

        return {}

    async def _extract_with_llm(self, pdf_path: str, doc_type: str) -> dict:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None, self.docling.convert_pdf_to_text, pdf_path
        )
        extracted_data = await loop.run_in_executor(
            None, self.llm.extract_key_value_pairs, text
        )

        return {
            "document_type": doc_type,
            "pages": 1,
            "fields": [extracted_data],
            "confidence_score": 0.0,
            "evidence": f"Extracted via LLM from {pdf_path}",
        }

    async def _extract_with_retry(self, pdf_path: str, doc_type: str) -> dict:
        loop = asyncio.get_event_loop()
        images = await loop.run_in_executor(
            None, self._convert_pdf_to_images, pdf_path, doc_type
        )
        extracted_data = []

        for img in images:
            field = await self._extract_field_from_image(img, doc_type)
            extracted_data.append(field)

        return {
            "document_type": doc_type,
            "pages": len(images),
            "fields": extracted_data,
            "confidence_score": 0.0,
            "evidence": f"Processed {len(images)} pages",
        }

    def _convert_pdf_to_images(self, pdf_path: str, doc_type: str) -> list:
        output_dir = os.path.join(
            STORAGE_DIR, self.project_manager.project_id, "pdf_images", doc_type
        )
        os.makedirs(output_dir, exist_ok=True)

        images = convert_from_path(pdf_path, dpi=300, fmt="png")
        image_paths = []

        for i, image in enumerate(images):
            image_path = os.path.join(output_dir, f"page_{i + 1}.png")
            image.save(image_path, "PNG")
            image_paths.append(image_path)

        return image_paths

    async def _extract_field_from_image(self, image_path: str, doc_type: str) -> dict:
        prompt = self._load_pdf_prompt()
        result = self.qwen.analyze_document(image_path, prompt)

        if not result["success"]:
            return {
                "image": image_path,
                "type": doc_type,
                "confidence_score": 0.0,
                "evidence": f"Error: {result['error']}",
            }

        data = result["data"]
        return {
            "image": image_path,
            "type": doc_type,
            "owner_name": data.get("owner_name"),
            "property_address": data.get("property_address"),
            "inspection_date": data.get("inspection_date"),
            "inspector_name": data.get("inspector_name"),
            "confidence_score": data.get("confidence", 0.0),
            "evidence": f"Analyzed {image_path}",
        }

    def _load_pdf_prompt(self) -> str:
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "prompts", "pdf_extraction.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
