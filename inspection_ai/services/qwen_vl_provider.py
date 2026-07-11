"""
QwenVL Provider - Singleton for eager model loading and Redis caching.
"""

import json
import logging
import re
import hashlib
import time
import io
import tempfile
from typing import Optional
from PIL import Image

import redis
import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

from inspection_ai.config import (
    QWEN_MODEL_NAME,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    MAX_IMAGE_SIDE,
    MIN_PIXELS,
    MAX_PIXELS,
    JPEG_QUALITY,
    OOM_RETRY_LEVELS,
    MAX_NEW_TOKENS,
    GPU_MEMORY_FRACTION,
    USE_FLASH_ATTENTION,
)

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

        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(GPU_MEMORY_FRACTION)

        torch_dtype = (
            torch.bfloat16
            if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
            else torch.float16
        )

        model_kwargs = {
            "torch_dtype": torch_dtype,
            "device_map": "auto",
            "low_cpu_mem_usage": True,
        }
        if USE_FLASH_ATTENTION:
            model_kwargs["attn_implementation"] = "flash_attention_2"

        self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            self.model_name, **model_kwargs
        )

        self._processor = AutoProcessor.from_pretrained(
            self.model_name,
            min_pixels=MIN_PIXELS,
            max_pixels=MAX_PIXELS,
        )

        try:
            self._redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
            )
            self._redis_client.ping()
        except Exception:
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

    def _resize_image_if_needed(self, image_path: str) -> str:
        try:
            with Image.open(image_path) as img:
                orig_width, orig_height = img.size

                if max(orig_width, orig_height) <= MAX_IMAGE_SIDE:
                    return image_path

                scale = MAX_IMAGE_SIDE / max(orig_width, orig_height)
                new_width = int(orig_width * scale)
                new_height = int(orig_height * scale)

                img_resized = img.resize(
                    (new_width, new_height), Image.Resampling.LANCZOS
                )
                buffer = io.BytesIO()
                img_resized.save(buffer, format="JPEG", quality=JPEG_QUALITY)
                buffer.seek(0)

                temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                temp_file.write(buffer.read())
                temp_file.close()
                return temp_file.name
        except Exception:
            return image_path

    def _log_gpu_memory(self, stage: str):
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            logger.info(
                f"GPU memory [{stage}]: allocated={allocated:.2f}GB, reserved={reserved:.2f}GB"
            )

    def _run_inference(self, image_path: str, prompt: str) -> dict:
        cache_key = self._get_cache_key(image_path, prompt)

        if self._redis_client:
            cached = self._redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

        start_time = time.time()
        self._log_gpu_memory("before")

        for retry_idx, max_pixels in enumerate(
            [MAX_PIXELS] + [p * 28 * 28 for p in OOM_RETRY_LEVELS]
        ):
            if retry_idx > 0:
                self._processor = AutoProcessor.from_pretrained(
                    self.model_name,
                    min_pixels=MIN_PIXELS,
                    max_pixels=max_pixels,
                )

            try:
                processed_path = self._resize_image_if_needed(image_path)

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": processed_path},
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
                        max_new_tokens=MAX_NEW_TOKENS,
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
                self._log_gpu_memory("after")
                logger.info(f"Inference completed in {duration_ms}ms")

                result = self._parse_response(raw_response)

                if self._redis_client and result.get("success"):
                    self._redis_client.setex(cache_key, 86400, json.dumps(result))

                del inputs, generated_ids, generated_ids_trimmed
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

                return result

            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if retry_idx == len(OOM_RETRY_LEVELS):
                    return {
                        "success": False,
                        "data": None,
                        "raw_response": "",
                        "error": f"CUDA OOM: image too large. Tried max_pixels down to {OOM_RETRY_LEVELS[-1] * 28 * 28}.",
                    }
                continue
            except Exception as e:
                logger.error(f"Inference failed for {image_path}: {e}")
                return {
                    "success": False,
                    "data": None,
                    "raw_response": "",
                    "error": str(e),
                }

        return {
            "success": False,
            "data": None,
            "raw_response": "",
            "error": "Max retries exceeded",
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
