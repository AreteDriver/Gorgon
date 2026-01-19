"""Caching layer with pluggable backends.

Provides a unified caching interface with:
- In-memory cache (default, no dependencies)
- Redis cache (optional, for distributed deployments)
- Decorator-based caching for functions
- TTL support for all backends

Usage:
    from test_ai.cache import cache, cached

    # Get cache instance (auto-detects backend)
    await cache.set("key", "value", ttl=300)
    value = await cache.get("key")

    # Decorator for function caching
    @cached(ttl=60, prefix="user")
    async def get_user(user_id: str) -> dict:
        ...
"""

from test_ai.cache.backends import Cache, get_cache
from test_ai.cache.decorators import cached, async_cached

__all__ = [
    "Cache",
    "get_cache",
    "cached",
    "async_cached",
]

# Convenience access to global cache instance
cache = get_cache()
