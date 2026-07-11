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
QUIRE_REPORT_URL = "https://app.openquire.com/reports/1762900"

# Redis configuration for caching
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
