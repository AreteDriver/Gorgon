"""Tests for caching module."""

import asyncio
import time
from unittest.mock import patch

import pytest

from test_ai.cache.backends import (
    MemoryCache,
    CacheEntry,
    CacheStats,
    get_cache,
    reset_cache,
    make_cache_key,
)
from test_ai.cache.decorators import cached, async_cached, CacheAside


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_not_expired_when_no_expiry(self):
        """Entry without expiry is never expired."""
        entry = CacheEntry(value="test", expires_at=None)
        assert not entry.is_expired()

    def test_not_expired_before_time(self):
        """Entry is not expired before expiry time."""
        entry = CacheEntry(value="test", expires_at=time.time() + 100)
        assert not entry.is_expired()

    def test_expired_after_time(self):
        """Entry is expired after expiry time."""
        entry = CacheEntry(value="test", expires_at=time.time() - 1)
        assert entry.is_expired()


class TestMemoryCache:
    """Tests for MemoryCache."""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance."""
        return MemoryCache(max_size=10)

    def test_set_and_get(self, cache):
        """Basic set and get operations."""
        cache.set_sync("key", "value")
        assert cache.get_sync("key") == "value"

    def test_get_missing_key(self, cache):
        """Getting missing key returns None."""
        assert cache.get_sync("nonexistent") is None

    def test_set_with_ttl(self, cache):
        """Entry expires after TTL."""
        cache.set_sync("key", "value", ttl=1)
        assert cache.get_sync("key") == "value"

        # Wait for expiration
        time.sleep(1.1)
        assert cache.get_sync("key") is None

    @pytest.mark.asyncio
    async def test_async_operations(self, cache):
        """Async get and set work correctly."""
        await cache.set("async_key", {"data": 123})
        result = await cache.get("async_key")
        assert result == {"data": 123}

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """Delete removes key from cache."""
        await cache.set("key", "value")
        assert await cache.exists("key")

        result = await cache.delete("key")
        assert result is True
        assert not await cache.exists("key")

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache):
        """Deleting nonexistent key returns False."""
        result = await cache.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """Clear removes all entries."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        assert cache.size == 2

        await cache.clear()
        assert cache.size == 0

    def test_max_size_eviction(self, cache):
        """Cache evicts oldest when max size reached."""
        for i in range(15):  # Max size is 10
            cache.set_sync(f"key{i}", f"value{i}")

        assert cache.size <= 10
        # First entries should be evicted
        assert cache.get_sync("key0") is None
        # Recent entries should remain
        assert cache.get_sync("key14") == "value14"

    def test_stats_tracking(self, cache):
        """Cache tracks hit/miss statistics."""
        cache.set_sync("key", "value")

        # Hit
        cache.get_sync("key")
        assert cache.stats.hits == 1
        assert cache.stats.misses == 0

        # Miss
        cache.get_sync("missing")
        assert cache.stats.hits == 1
        assert cache.stats.misses == 1

        assert cache.stats.hit_rate == 50.0


class TestCacheStats:
    """Tests for CacheStats."""

    def test_hit_rate_calculation(self):
        """Hit rate calculated correctly."""
        stats = CacheStats(hits=80, misses=20)
        assert stats.hit_rate == 80.0

    def test_hit_rate_no_accesses(self):
        """Hit rate is 0 with no accesses."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0


class TestGetCache:
    """Tests for get_cache factory."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache()

    def teardown_method(self):
        """Reset cache after each test."""
        reset_cache()

    def test_returns_memory_cache_by_default(self):
        """Returns MemoryCache when no Redis URL configured."""
        with patch.dict("os.environ", {}, clear=True):
            cache = get_cache()
            assert isinstance(cache, MemoryCache)

    def test_same_instance_returned(self):
        """Same cache instance returned on subsequent calls."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2


class TestMakeCacheKey:
    """Tests for make_cache_key utility."""

    def test_simple_args(self):
        """Creates key from simple arguments."""
        key = make_cache_key("user", 123)
        assert key == "user:123"

    def test_kwargs(self):
        """Creates key from kwargs."""
        key = make_cache_key(name="test", id=42)
        assert "id=42" in key
        assert "name=test" in key

    def test_complex_objects_hashed(self):
        """Complex objects are hashed."""
        key = make_cache_key({"nested": "data"})
        assert len(key) > 0
        # Hash should be deterministic
        key2 = make_cache_key({"nested": "data"})
        assert key == key2


class TestCachedDecorator:
    """Tests for @cached decorator."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache()

    def test_caches_result(self):
        """Function result is cached."""
        call_count = 0

        @cached()
        def expensive_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call computes
        result1 = expensive_func(5)
        assert result1 == 10
        assert call_count == 1

        # Second call uses cache
        result2 = expensive_func(5)
        assert result2 == 10
        assert call_count == 1  # Not called again

    def test_different_args_different_cache(self):
        """Different arguments use different cache entries."""
        call_count = 0

        @cached()
        def func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x

        func(1)
        func(2)
        func(1)  # Should hit cache

        assert call_count == 2  # Only 2 unique calls

    def test_prefix_namespacing(self):
        """Prefix creates namespace for cache keys."""
        @cached(prefix="ns1")
        def func1(x: int) -> str:
            return f"func1:{x}"

        @cached(prefix="ns2")
        def func2(x: int) -> str:
            return f"func2:{x}"

        result1 = func1(1)
        result2 = func2(1)

        assert result1 == "func1:1"
        assert result2 == "func2:1"

    def test_skip_cache_on_condition(self):
        """Result not cached when skip_cache_on returns True."""
        call_count = 0

        @cached(skip_cache_on=lambda x: x is None)
        def maybe_none(x: int):
            nonlocal call_count
            call_count += 1
            return None if x < 0 else x

        # None result should not be cached
        maybe_none(-1)
        maybe_none(-1)
        assert call_count == 2  # Called twice

        # Non-None result should be cached
        maybe_none(1)
        maybe_none(1)
        assert call_count == 3  # Only called once for x=1

    def test_custom_key_builder(self):
        """Custom key builder used for cache key."""
        @cached(key_builder=lambda x, y: f"custom:{x}:{y}")
        def func(x: int, y: int) -> int:
            return x + y

        result = func(1, 2)
        assert result == 3

        # Verify key was built correctly
        key = func.cache_key(1, 2)
        assert key == "custom:1:2"


class TestAsyncCachedDecorator:
    """Tests for @async_cached decorator."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache()

    @pytest.mark.asyncio
    async def test_caches_async_result(self):
        """Async function result is cached."""
        call_count = 0

        @async_cached()
        async def expensive_async(x: int) -> int:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return x * 2

        # First call computes
        result1 = await expensive_async(5)
        assert result1 == 10
        assert call_count == 1

        # Second call uses cache
        result2 = await expensive_async(5)
        assert result2 == 10
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Cache entry expires after TTL."""
        call_count = 0

        @async_cached(ttl=1)
        async def func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x

        await func(1)
        assert call_count == 1

        # Wait for expiration
        await asyncio.sleep(1.1)

        await func(1)
        assert call_count == 2  # Called again after expiration


class TestCacheAside:
    """Tests for CacheAside pattern helper."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache()

    @pytest.mark.asyncio
    async def test_basic_usage(self):
        """Basic get/set operations work."""
        cache_aside = CacheAside(prefix="test", ttl=60)

        await cache_aside.set("key", {"value": 123})
        result = await cache_aside.get("key")
        assert result == {"value": 123}

    @pytest.mark.asyncio
    async def test_invalidate(self):
        """Invalidate removes cache entry."""
        cache_aside = CacheAside(prefix="test")

        await cache_aside.set("key", "value")
        await cache_aside.invalidate("key")
        result = await cache_aside.get("key")
        assert result is None

    def test_sync_operations(self):
        """Synchronous operations work."""
        cache_aside = CacheAside(prefix="sync")

        cache_aside.set_sync("key", "value")
        result = cache_aside.get_sync("key")
        assert result == "value"
