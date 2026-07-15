import redis

from app.core.config import get_settings

# redis-py's client is connection-pooled and thread-safe internally, so a single
# module-level instance is the right pattern.
_redis_client = redis.from_url(get_settings().redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    return _redis_client
