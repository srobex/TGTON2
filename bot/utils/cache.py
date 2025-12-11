"""Единая точка настройки aiocache."""

from __future__ import annotations

from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from aiocache import SimpleMemoryCache, caches
from aiocache.base import BaseCache

try:
    from aiocache import RedisCache
except (ImportError, AttributeError):  # pragma: no cover - optional dependency
    RedisCache = None  # type: ignore[assignment]

from config.settings import get_settings

settings = get_settings()
_configured = False


def configure_cache() -> None:
    """Настраивает aiocache в зависимости от backend (memory/redis)."""

    global _configured
    if _configured:
        return

    if settings.cache.backend == "redis":
        if RedisCache is None:
            raise RuntimeError(
                "Для использования RedisCache установите пакет 'redis' и aiocache[redis]"
            )
        config = _build_redis_config(settings.cache.redis_dsn)
        caches.set_config(
            {
                "default": {
                    "cache": RedisCache,
                    **config,
                    "ttl": settings.cache.ttl_seconds,
                }
            }
        )
    else:
        caches.set_config(
            {
                "default": {
                    "cache": SimpleMemoryCache,
                    "ttl": settings.cache.ttl_seconds,
                }
            }
        )
    _configured = True


def get_cache(alias: str = "default") -> BaseCache:
    """Возвращает кеш по алиасу (предварительно гарантирует конфиг)."""

    configure_cache()
    return caches.get(alias)


async def cached_call(key: str, ttl: int, factory: Callable[[], Awaitable[Any]]) -> Any:
    """Мини-хелпер: если значение отсутствует – вызывает factory."""

    cache = get_cache()
    value = await cache.get(key)
    if value is not None:
        return value
    value = await factory()
    await cache.set(key, value, ttl=ttl)
    return value


def _build_redis_config(dsn: str | None) -> dict[str, Any]:
    if not dsn:
        raise RuntimeError("CACHE_BACKEND=redis, но redis_dsn не указан")
    parsed = urlparse(dsn)
    if parsed.scheme not in {"redis", "rediss"}:
        raise ValueError(f"Неподдерживаемая схема Redis DSN: {parsed.scheme}")
    db = 0
    if parsed.path and parsed.path != "/":
        try:
            db = int(parsed.path.lstrip("/"))
        except ValueError:
            db = 0
    return {
        "endpoint": parsed.hostname or "localhost",
        "port": parsed.port or 6379,
        "password": parsed.password,
        "db": db,
        "ssl": parsed.scheme == "rediss",
    }


__all__ = ["configure_cache", "get_cache", "cached_call"]

