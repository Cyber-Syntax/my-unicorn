"""Tests for CatalogCache - in-memory catalog caching.

This module tests the CatalogCache class that provides thread-safe
in-memory catalog caching using asyncio.Lock for concurrent access.
"""

import asyncio
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from my_unicorn.core.update.catalog_cache import CatalogCache
from my_unicorn.exceptions import UpdateError


class TestCatalogCacheInitialization:
    """Tests for CatalogCache initialization."""

    def test_catalog_cache_initialization(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test CatalogCache initializes with empty cache and lock.

        Verifies that when a CatalogCache instance is created with a
        ConfigManager, it initializes with an empty cache dictionary,
        a valid asyncio.Lock for thread safety, and a reference to the
        provided ConfigManager instance.
        """
        cache = CatalogCache(mock_config_manager)

        assert cache.config_manager is mock_config_manager
        assert isinstance(cache._cache, dict)
        assert len(cache._cache) == 0
        assert isinstance(cache._lock, asyncio.Lock)


class TestCatalogCacheLoadCatalog:
    """Tests for CatalogCache.load_catalog method."""

    @pytest.mark.asyncio
    async def test_load_catalog_cache_miss(
        self, mock_config_manager: MagicMock, sample_catalog: dict[str, Any]
    ) -> None:
        """Test load_catalog retrieves from config_manager on cache miss.

        Verifies that when a catalog reference is not in the cache,
        load_catalog fetches it from config_manager.load_catalog() and
        stores the result in the cache for future access.
        """
        mock_config_manager.load_catalog.return_value = sample_catalog
        cache = CatalogCache(mock_config_manager)

        result = await cache.load_catalog("test-app")

        assert result == sample_catalog
        mock_config_manager.load_catalog.assert_called_once_with("test-app")

    @pytest.mark.asyncio
    async def test_load_catalog_cache_hit(
        self, mock_config_manager: MagicMock, sample_catalog: dict[str, Any]
    ) -> None:
        """Test load_catalog returns cached result on cache hit.

        Verifies that when a catalog reference is already in the cache,
        load_catalog returns the cached value without calling
        config_manager.load_catalog() again.
        """
        mock_config_manager.load_catalog.return_value = sample_catalog
        cache = CatalogCache(mock_config_manager)

        # First call - cache miss
        result1 = await cache.load_catalog("test-app")
        # Second call - cache hit
        result2 = await cache.load_catalog("test-app")

        assert result1 == sample_catalog
        assert result2 == sample_catalog
        # Should only be called once (cache hit on second call)
        mock_config_manager.load_catalog.assert_called_once_with("test-app")

    @pytest.mark.asyncio
    async def test_load_catalog_concurrent_access_single_load(
        self, mock_config_manager: MagicMock, sample_catalog: dict[str, Any]
    ) -> None:
        """Test concurrent access to same catalog only loads once.

        Verifies that when multiple concurrent tasks request the same
        catalog reference, the asyncio.Lock ensures that load_catalog
        is only called once, and subsequent concurrent tasks receive
        the cached result.
        """
        call_count = 0

        def mock_load_with_tracking(ref: str) -> dict[str, Any]:
            """Track calls to config_manager.load_catalog."""
            nonlocal call_count
            call_count += 1
            return sample_catalog

        mock_config_manager.load_catalog.side_effect = mock_load_with_tracking

        cache = CatalogCache(mock_config_manager)

        # Launch multiple concurrent tasks requesting same catalog
        results = await asyncio.gather(
            cache.load_catalog("test-app"),
            cache.load_catalog("test-app"),
            cache.load_catalog("test-app"),
        )

        # All results should be identical
        assert len(results) == 3
        assert all(r == sample_catalog for r in results)
        # Load called only once despite concurrent access (due to lock)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_load_catalog_stores_none_for_missing(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test load_catalog caches None result to avoid repeated lookups.

        Verifies that when a catalog reference is not found and
        config_manager.load_catalog() returns None, the None value is
        cached to prevent repeated lookups on subsequent requests.
        """
        mock_config_manager.load_catalog.return_value = None
        cache = CatalogCache(mock_config_manager)

        # First call - cache miss, returns None
        result1 = await cache.load_catalog("missing-app")
        # Second call - cache hit for None value
        result2 = await cache.load_catalog("missing-app")

        assert result1 is None
        assert result2 is None
        # Should only be called once (None is cached)
        mock_config_manager.load_catalog.assert_called_once_with("missing-app")


class TestCatalogCacheLoadCatalogIfNeeded:
    """Tests for CatalogCache.load_catalog_if_needed method."""

    @pytest.mark.asyncio
    async def test_load_catalog_if_needed_no_catalog_ref(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test load_catalog_if_needed returns None when catalog_ref is None.

        Verifies that when catalog_ref is None, load_catalog_if_needed
        returns None immediately without attempting to load any catalog
        or calling config_manager at all.
        """
        cache = CatalogCache(mock_config_manager)

        result = await cache.load_catalog_if_needed("test-app", None)

        assert result is None
        mock_config_manager.load_catalog.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_catalog_if_needed_with_catalog_ref_success(
        self, mock_config_manager: MagicMock, sample_catalog: dict[str, Any]
    ) -> None:
        """Test load_catalog_if_needed loads catalog when ref is provided.

        Verifies that when catalog_ref is provided and valid,
        load_catalog_if_needed successfully loads the catalog from
        config_manager and returns the catalog data.
        """
        mock_config_manager.load_catalog.return_value = sample_catalog
        cache = CatalogCache(mock_config_manager)

        result = await cache.load_catalog_if_needed("test-app", "test-app")

        assert result == sample_catalog
        mock_config_manager.load_catalog.assert_called_once_with("test-app")

    @pytest.mark.asyncio
    async def test_load_catalog_if_needed_catalog_not_found_raises_error(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test load_catalog_if_needed raises UpdateError on missing catalog.

        Verifies that when catalog_ref is provided but the catalog is not
        found (FileNotFoundError raised by config_manager),
        load_catalog_if_needed wraps the error in an UpdateError with
        appropriate context including app_name and catalog_ref.
        """
        mock_config_manager.load_catalog.side_effect = FileNotFoundError(
            "Catalog not found"
        )
        cache = CatalogCache(mock_config_manager)

        with pytest.raises(UpdateError) as exc_info:
            await cache.load_catalog_if_needed("my-app", "missing-catalog")

        error = exc_info.value
        assert error.context["app_name"] == "my-app"
        assert error.context["catalog_ref"] == "missing-catalog"
        assert "missing-catalog" in error.message.lower()
        assert "my-app" in error.message.lower()


class TestCatalogCacheClear:
    """Tests for CatalogCache.clear method."""

    @pytest.mark.asyncio
    async def test_clear_cache(
        self, mock_config_manager: MagicMock, sample_catalog: dict[str, Any]
    ) -> None:
        """Test clear() empties the cache.

        Verifies that after loading catalogs into the cache, calling
        clear() removes all cached entries, forcing subsequent load
        operations to fetch from config_manager again.
        """
        mock_config_manager.load_catalog.return_value = sample_catalog
        cache = CatalogCache(mock_config_manager)

        # Load catalog into cache
        result1 = await cache.load_catalog("test-app")
        assert result1 == sample_catalog
        assert len(cache._cache) > 0

        # Clear cache
        cache.clear()
        assert len(cache._cache) == 0

        # Reset mock to count new call
        mock_config_manager.load_catalog.reset_mock()
        mock_config_manager.load_catalog.return_value = sample_catalog

        # Load again - should call config_manager
        result2 = await cache.load_catalog("test-app")
        assert result2 == sample_catalog
        mock_config_manager.load_catalog.assert_called_once_with("test-app")


class TestCatalogCachePerformance:
    """Tests for CatalogCache performance characteristics."""

    @pytest.mark.asyncio
    async def test_cache_performance_improvement(
        self, mock_config_manager: MagicMock, sample_catalog: dict[str, Any]
    ) -> None:
        """Test that cached access is faster than initial load.

        Verifies that cache hits are significantly faster than cache misses
        by measuring execution time. This demonstrates the performance
        benefit of caching: ~0.01ms for cached vs ~1-2ms for initial load.

        This is a performance/integration test showing the practical benefit:
        for shared catalogs, caching provides 100x+ speedup.
        """
        call_count = 0

        def mock_load_with_delay(ref: str) -> dict[str, Any]:
            """Simulate I/O delay in config_manager."""
            nonlocal call_count
            call_count += 1
            # Simulate minimal I/O delay
            time.sleep(0.001)
            return sample_catalog

        mock_config_manager.load_catalog.side_effect = mock_load_with_delay
        cache = CatalogCache(mock_config_manager)

        # Measure cache miss (first load)
        start = time.perf_counter()
        result1 = await cache.load_catalog("test-app")
        miss_time = time.perf_counter() - start

        # Measure cache hit (second load)
        start = time.perf_counter()
        result2 = await cache.load_catalog("test-app")
        hit_time = time.perf_counter() - start

        # Verify results are correct
        assert result1 == sample_catalog
        assert result2 == sample_catalog
        assert call_count == 1  # Only called once due to caching

        # Cache hit should be significantly faster
        assert hit_time < miss_time, (
            f"Cache hit ({hit_time:.6f}s) should be faster than "
            f"miss ({miss_time:.6f}s)"
        )
