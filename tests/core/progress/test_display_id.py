"""Tests for IDGenerator module.

Tests cover ID generation, caching, and cache clearing functionality.
"""

from __future__ import annotations

from my_unicorn.core.progress.display_id import IDGenerator
from my_unicorn.core.progress.progress_types import (
    ID_CACHE_LIMIT,
    ProgressType,
)


class TestIDGenerationUniqueness:
    """Tests for ID uniqueness within namespaces."""

    def test_id_generation_unique_within_type(self) -> None:
        """IDs generated for the same name are unique per call."""
        generator = IDGenerator()
        id1 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file1")
        id2 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file1")

        assert id1 == id2  # Should be cached, same ID
        assert id1.startswith("dl_")

    def test_id_generation_different_types(self) -> None:
        """IDs are unique across different progress types."""
        generator = IDGenerator()
        dl_id = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "same")
        api_id = generator.generate_namespaced_id(
            ProgressType.API_FETCHING, "same"
        )

        assert dl_id.startswith("dl_")
        assert api_id.startswith("api_")
        assert dl_id != api_id

    def test_id_generation_different_names(self) -> None:
        """IDs are unique for different names in the same type."""
        generator = IDGenerator()
        id1 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file1")
        id2 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file2")

        assert id1 != id2
        assert id1.startswith("dl_1_")
        assert id2.startswith("dl_2_")


class TestIDSequentialNumbering:
    """Tests for sequential counter incrementing."""

    def test_task_counters_increment(self) -> None:
        """Task counters increment for each new name."""
        generator = IDGenerator()

        id1 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file1")
        id2 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file2")
        id3 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file3")

        assert id1.startswith("dl_1_")
        assert id2.startswith("dl_2_")
        assert id3.startswith("dl_3_")

    def test_counters_isolated_per_type(self) -> None:
        """Task counters are isolated per progress type."""
        generator = IDGenerator()

        dl1 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "d1")
        api1 = generator.generate_namespaced_id(
            ProgressType.API_FETCHING, "a1"
        )
        dl2 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "d2")

        assert dl1.startswith("dl_1_")
        assert api1.startswith("api_1_")
        assert dl2.startswith("dl_2_")

    def test_multiple_types_independent_counters(self) -> None:
        """Each progress type maintains independent counters."""
        generator = IDGenerator()

        types_and_names = [
            (ProgressType.DOWNLOAD, "d1"),
            (ProgressType.VERIFICATION, "v1"),
            (ProgressType.API_FETCHING, "a1"),
            (ProgressType.ICON_EXTRACTION, "i1"),
        ]

        ids = {}
        for ptype, name in types_and_names:
            ids[ptype] = generator.generate_namespaced_id(ptype, name)

        assert ids[ProgressType.DOWNLOAD].startswith("dl_1_")
        assert ids[ProgressType.VERIFICATION].startswith("vf_1_")
        assert ids[ProgressType.API_FETCHING].startswith("api_1_")
        assert ids[ProgressType.ICON_EXTRACTION].startswith("ic_1_")


class TestIDCacheClear:
    """Tests for cache clearing functionality."""

    def test_cache_clear_resets_generation(self) -> None:
        """Cache clearing causes same name to get new ID."""
        generator = IDGenerator()

        id1 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "same")
        generator.clear_cache()
        id2 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "same")

        assert id1 != id2
        assert id1.startswith("dl_1_")
        assert id2.startswith("dl_2_")

    def test_cache_clear_only_clears_cache(self) -> None:
        """Cache clearing clears cache but not counters."""
        generator = IDGenerator()

        id1 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file1")
        id2 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file2")

        generator.clear_cache()

        # New ID for same name should use next counter value
        id3 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file1")
        assert id3.startswith("dl_3_")

    def test_clear_all_types_at_once(self) -> None:
        """Clear cache affects all progress types."""
        generator = IDGenerator()

        dl_id1 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "d1")
        api_id1 = generator.generate_namespaced_id(
            ProgressType.API_FETCHING, "a1"
        )

        generator.clear_cache()

        dl_id2 = generator.generate_namespaced_id(ProgressType.DOWNLOAD, "d1")
        api_id2 = generator.generate_namespaced_id(
            ProgressType.API_FETCHING, "a1"
        )

        assert dl_id1 != dl_id2
        assert api_id1 != api_id2


class TestIDSanitization:
    """Tests for name sanitization in ID generation."""

    def test_sanitize_removes_special_chars(self) -> None:
        """Special characters are removed from name."""
        generator = IDGenerator()

        id_clean = generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "myfile.zip"
        )
        id_special = generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "my@file#$%"
        )

        assert id_clean.endswith("myfile.zip")
        assert "#" not in id_special
        assert "@" not in id_special
        assert "$" not in id_special
        assert "%" not in id_special

    def test_sanitize_keeps_allowed_chars(self) -> None:
        """Alphanumerics and allowed symbols are kept."""
        generator = IDGenerator()

        id1 = generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "file-name_123.zip"
        )

        assert "file-name_123.zip" in id1

    def test_sanitize_truncates_long_names(self) -> None:
        """Names longer than 20 chars are truncated."""
        generator = IDGenerator()

        long_name = "this_is_a_very_long_filename_that_exceeds_limit"
        id_long = generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, long_name
        )

        # ID should be: dl_counter_truncated_name
        # Truncated name should be max 20 chars
        parts = id_long.split("_", 2)
        if len(parts) >= 3:
            truncated = parts[2]
            assert len(truncated) <= 20

    def test_sanitize_fallback_to_unnamed(self) -> None:
        """Empty name after sanitization falls back to 'unnamed'."""
        generator = IDGenerator()

        id_empty = generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "!!!!"
        )
        id_num_only = generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "@#$%^&*()"
        )

        assert "unnamed" in id_empty
        assert "unnamed" in id_num_only


class TestIDCacheLimit:
    """Tests for LRU cache eviction when limit exceeded."""

    def test_cache_size_respects_limit(self) -> None:
        """Cache size does not exceed ID_CACHE_LIMIT."""
        generator = IDGenerator()

        # Generate more IDs than the limit
        for i in range(ID_CACHE_LIMIT + 100):
            generator.generate_namespaced_id(
                ProgressType.DOWNLOAD, f"file_{i}"
            )

        # Verify cache size does not exceed limit
        assert len(generator._id_cache) <= ID_CACHE_LIMIT

    def test_lru_eviction_removes_oldest(self) -> None:
        """Oldest entries are evicted when cache exceeds limit."""
        generator = IDGenerator()

        # Create a few entries
        key1 = (ProgressType.DOWNLOAD, "file1")
        key2 = (ProgressType.DOWNLOAD, "file2")

        generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file1")
        generator.generate_namespaced_id(ProgressType.DOWNLOAD, "file2")

        # Both should be in cache initially
        assert key1 in generator._id_cache
        assert key2 in generator._id_cache


class TestIDTypePrefix:
    """Tests for correct type prefixes in generated IDs."""

    def test_all_progress_types_have_prefixes(self) -> None:
        """All progress types produce correct prefixes."""
        generator = IDGenerator()

        test_cases = [
            (ProgressType.API_FETCHING, "api"),
            (ProgressType.DOWNLOAD, "dl"),
            (ProgressType.VERIFICATION, "vf"),
            (ProgressType.ICON_EXTRACTION, "ic"),
            (ProgressType.INSTALLATION, "in"),
            (ProgressType.UPDATE, "up"),
        ]

        for ptype, expected_prefix in test_cases:
            generated_id = generator.generate_namespaced_id(
                ptype, f"test_{ptype.name}"
            )
            assert generated_id.startswith(f"{expected_prefix}_")
