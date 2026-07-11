"""
QwenVL Provider - Singleton for eager model loading and Redis caching.
Ensures model is loaded once and reused across all services.
"""

import json
import logging
import re
import hashlib
import time
from typing import Optional, Dict, Any

import redis
import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

from inspection_ai.config import QWEN_MODEL_NAME, REDIS_HOST, REDIS_PORT, REDIS_DB

logger = logging.getLogger(__name__)


class QwenVLProvider:
    _instance: Optional["QwenVLProvider"] = None
    _model: Optional[Qwen2_5_VLForConditionalGeneration] = None
    _processor: Optional[AutoProcessor] = None
    _redis_client: Optional[redis.Redis] = None

    def __new__(cls, model_name: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.model_name = model_name or QWEN_MODEL_NAME
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        logger.info(f"Loading QwenVL model: {self.model_name}")
        self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            self.model_name, torch_dtype="auto", device_map="auto"
        )
        self._processor = AutoProcessor.from_pretrained(self.model_name)
        logger.info("QwenVL model loaded successfully")

        try:
            self._redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
            )
            self._redis_client.ping()
            logger.info("Redis cache connected successfully")
        except Exception as e:
            logger.warning(f"Redis not available, caching disabled: {e}")
            self._redis_client = None

    @classmethod
    def get_instance(cls) -> "QwenVLProvider":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def analyze_image(self, image_path: str, prompt: str) -> dict:
        return self._run_inference(image_path, prompt)

    def analyze_document(self, image_path: str, prompt: str) -> dict:
        return self._run_inference(image_path, prompt)

    def _get_cache_key(self, image_path: str, prompt: str) -> str:
        content = f"{image_path}:{prompt}"
        return f"qwen_vl:{hashlib.md5(content.encode()).hexdigest()}"

    def _run_inference(self, image_path: str, prompt: str) -> dict:
        cache_key = self._get_cache_key(image_path, prompt)

        if self._redis_client:
            cached = self._redis_client.get(cache_key)
            if cached:
                logger.info(f"Cache hit for {image_path}")
                return json.loads(cached)

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

            text = self._processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            image_inputs, video_inputs = process_vision_info(messages)

            inputs = self._processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            ).to(self._model.device)

            with torch.inference_mode():
                generated_ids = self._model.generate(
                    **inputs,
                    max_new_tokens=512,
                    do_sample=False,
                    temperature=0.0,
                )

            generated_ids_trimmed = [
                out_ids[len(in_ids) :]
                for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            raw_response = self._processor.batch_decode(
                generated_ids_trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0]

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Inference completed in {duration_ms}ms")

            result = self._parse_response(raw_response)

            if self._redis_client and result.get("success"):
                self._redis_client.setex(cache_key, 86400, json.dumps(result))
                logger.info(f"Cached result for {image_path}")

            return result

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
