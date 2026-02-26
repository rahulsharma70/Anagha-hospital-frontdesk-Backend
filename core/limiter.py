from fastapi import Request
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter
from core.config import settings

import logging

logger = logging.getLogger(__name__)

async def init_redis():
    try:
        redis_conn = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        # Ping to check connection
        await redis_conn.ping()
        await FastAPILimiter.init(redis_conn)
        logger.info("✅ Redis Limiter initialized")
        return redis_conn
    except Exception as e:
        logger.warning(f"⚠️ Redis not available at {settings.REDIS_URL}: {e}. Rate limiting will be disabled.")
        return None

async def get_real_ip(request: Request):
    """Dependency to extract real IP even behind a proxy/nginx"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0]
    return request.client.host
