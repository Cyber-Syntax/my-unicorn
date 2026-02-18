"""ID generation module for progress tasks.

Handles generation of unique namespaced task IDs with caching and LRU eviction.
Separates ID generation logic from ProgressDisplay for better SRP compliance.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from contextlib import suppress

from my_unicorn.core.progress.progress_types import (
    ID_CACHE_LIMIT,
    ProgressType,
)


class IDGenerator:
    """Generator for unique namespaced task IDs.

    Maintains counters per progress type for sequential ID generation.
    Caches generated IDs to return consistent values for the same inputs.
    Implements LRU eviction when cache exceeds size limits.

    Attributes:
        _id_cache: Ordered dictionary mapping (type, name) to generated ID
        _task_counters: Counter for each progress type
    """

    def __init__(self) -> None:
        """Initialize ID generator with empty cache and counters."""
        self._task_counters: dict[ProgressType, int] = defaultdict(int)
        self._id_cache: OrderedDict[tuple[ProgressType, str], str] = (
            OrderedDict()
        )

    def generate_namespaced_id(
        self, progress_type: ProgressType, name: str
    ) -> str:
        """Generate a unique namespaced ID for a task with optimized caching.

        For the same (progress_type, name) pair, returns the cached ID.
        For new combinations, generates a new ID using a counter and name.
        Implements LRU cache eviction when limit is exceeded.

        Args:
            progress_type: Type of progress operation
            name: Task name

        Returns:
            Unique namespaced ID in format: {prefix}_{counter}_{sanitized_name}

        Example:
            >>> gen = IDGenerator()
            >>> gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file.zip")
            'dl_1_file.zip'
            >>> gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file.zip")
            'dl_1_file.zip'  # Returns cached value
        """
        cache_key = (progress_type, name)

        # Return cached ID if available
        if cache_key in self._id_cache:
            with suppress(Exception):
                self._id_cache.move_to_end(cache_key)
            return self._id_cache[cache_key]

        # Increment counter for this type
        self._task_counters[progress_type] += 1
        counter = self._task_counters[progress_type]

        # Get type prefix for readable IDs
        type_prefixes = {
            ProgressType.API_FETCHING: "api",
            ProgressType.DOWNLOAD: "dl",
            ProgressType.VERIFICATION: "vf",
            ProgressType.ICON_EXTRACTION: "ic",
            ProgressType.INSTALLATION: "in",
            ProgressType.UPDATE: "up",
        }
        type_prefix = type_prefixes[progress_type]

        # Sanitize name: keep only alphanumeric chars and safe symbols
        clean_name = "".join(c for c in name if c.isalnum() or c in "-_.")[:20]
        if not clean_name:
            clean_name = "unnamed"

        namespaced_id = f"{type_prefix}_{counter}_{clean_name}"

        # Cache the generated ID with LRU eviction
        self._id_cache[cache_key] = namespaced_id
        if len(self._id_cache) > ID_CACHE_LIMIT:
            with suppress(Exception):
                self._id_cache.popitem(last=False)

        return namespaced_id

    def clear_cache(self) -> None:
        """Clear the ID generation cache.

        Note: This clears only the cache, not the counters.
        Subsequent calls with the same inputs will generate new IDs.

        Example:
            >>> gen = IDGenerator()
            >>> id1 = gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file")
            >>> id2 = gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file")
            >>> id1 == id2
            True
            >>> gen.clear_cache()
            >>> id3 = gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file")
            >>> id1 == id3
            False
        """
        self._id_cache.clear()
