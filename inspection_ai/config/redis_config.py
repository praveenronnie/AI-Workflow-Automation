from redis import Redis
from inspection_ai.config import get_settings

settings = get_settings()

redis_client = Redis(
    host=settings.redis_host, port=settings.redis_port, db=0, decode_responses=True
)
