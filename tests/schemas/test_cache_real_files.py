"""Test cache validation against real cache files."""

import json
from pathlib import Path

import pytest

from my_unicorn.schemas import validate_cache_release


@pytest.fixture
def cache_examples_dir():
    """Return path to cache examples directory."""
    return Path(__file__).parent.parent.parent / "examples" / "cache_releases"


def test_all_example_cache_files_validate(cache_examples_dir):
    """Test that all example cache files validate successfully."""
    if not cache_examples_dir.exists():
        pytest.skip(
            f"Cache examples directory not found: {cache_examples_dir}"
        )

    cache_files = list(cache_examples_dir.glob("*.json"))
    assert len(cache_files) > 0, "No cache files found in examples directory"

    # Validate each cache file
    for cache_file in cache_files:
        with cache_file.open("r") as f:
            cache_data = json.load(f)

        # Should not raise SchemaValidationError
        validate_cache_release(cache_data, cache_file.stem)


@pytest.mark.parametrize(
    "cache_file",
    [
        "obsidianmd_obsidian-releases.json",
        "FreeTubeApp_FreeTube.json",
        "standardnotes_app.json",
    ],
)
def test_specific_cache_files(cache_examples_dir, cache_file):
    """Test specific well-known cache files."""
    cache_path = cache_examples_dir / cache_file
    if not cache_path.exists():
        pytest.skip(f"Cache file not found: {cache_path}")

    with cache_path.open("r") as f:
        cache_data = json.load(f)

    validate_cache_release(cache_data, cache_path.stem)
