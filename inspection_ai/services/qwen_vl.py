"""
QwenVL Wrapper - Production-ready wrapper for Qwen2.5-VL model.
Handles model loading, inference, and response parsing.
"""

import json
import logging
import re
import time
from typing import Optional

import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

from inspection_ai.config import QWEN_MODEL_NAME

logger = logging.getLogger(__name__)


class QwenVL:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or QWEN_MODEL_NAME
        logger.info(f"Loading QwenVL model: {self.model_name}")
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            self.model_name, torch_dtype="auto", device_map="auto"
        )
        self.processor = AutoProcessor.from_pretrained(self.model_name)
        logger.info("QwenVL model loaded successfully")

    def analyze_image(self, image_path: str, prompt: str) -> dict:
        return self._run_inference(image_path, prompt)

    def analyze_document(self, image_path: str, prompt: str) -> dict:
        return self._run_inference(image_path, prompt)

    def _run_inference(self, image_path: str, prompt: str) -> dict:
        start_time = time.time()
        logger.info(f"Starting inference for: {image_path}")

        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image_path},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            image_inputs, video_inputs = process_vision_info(messages)

            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            ).to(self.model.device)

            with torch.inference_mode():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    do_sample=False,
                    temperature=0.0,
                )

            generated_ids_trimmed = [
                out_ids[len(in_ids) :]
                for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            raw_response = self.processor.batch_decode(
                generated_ids_trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0]

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Inference completed in {duration_ms}ms")

            return self._parse_response(raw_response)

        except Exception as e:
            logger.error(f"Inference failed for {image_path}: {e}")
            return {
                "success": False,
                "data": None,
                "raw_response": "",
                "error": str(e),
            }

    def _parse_response(self, raw_response: str) -> dict:
        normalized = self._normalize_response(raw_response)

        try:
            data = json.loads(normalized)
            return {
                "success": True,
                "data": data,
                "raw_response": raw_response,
                "error": None,
            }
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            return {
                "success": False,
                "data": None,
                "raw_response": raw_response,
                "error": f"JSON parsing failed: {e}",
            }

    def _normalize_response(self, response: str) -> str:
        response = re.sub(r"^```json\s*", "", response)
        response = re.sub(r"\s*```$", "", response)
        response = response.strip()

        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            return json_match.group(0)
        return response
