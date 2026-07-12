"""
Configuration settings for AI Inspection Report Automation.
All settings are centralized for easy modification.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "projects")

QWEN_MODEL_NAME = "Qwen/Qwen2.5-VL-3B-Instruct"
QWEN_API_URL = "http://localhost:8000/v1/chat/completions"

DEFAULT_TIMEOUT = 60000
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2

CONFIDENCE_THRESHOLD = 0.80

QUIRE_LOGIN_URL = "https://app.openquire.com/login"
QUIRE_REPORT_URL = os.getenv("QUIRE_URL", "https://app.openquire.com/reports/1762900")
QUIRE_EMAIL = os.getenv("QUIRE_EMAIL", "")
QUIRE_PASSWORD = os.getenv("QUIRE_PASSWORD", "")

# Redis configuration for caching
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# GPU / Image preprocessing configuration
MAX_IMAGE_SIDE = int(os.getenv("MAX_IMAGE_SIDE", "1280"))
MIN_PIXELS = int(os.getenv("MIN_PIXELS", str(256 * 28 * 28)))
MAX_PIXELS = int(os.getenv("MAX_PIXELS", str(512 * 28 * 28)))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "90"))
OOM_RETRY_LEVELS = [512, 384, 256]  # pixel counts for adaptive OOM recovery
MAX_CONCURRENT_INFERENCES = int(os.getenv("MAX_CONCURRENT_INFERENCES", "2"))
USE_FLASH_ATTENTION = os.getenv("USE_FLASH_ATTENTION", "false").lower() == "true"
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "256"))
GPU_MEMORY_FRACTION = float(os.getenv("GPU_MEMORY_FRACTION", "0.8"))
