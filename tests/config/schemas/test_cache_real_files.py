"""Test cache validation against real cache files."""

from pathlib import Path

import orjson
import pytest

from my_unicorn.config.schemas import validate_cache_release


def test_all_example_cache_files_validate(cache_examples_dir: Path) -> None:
    """Test that all example cache files validate successfully."""
    if not cache_examples_dir.exists():
        pytest.skip(
            f"Cache examples directory not found: {cache_examples_dir}"
        )

    cache_files = list(cache_examples_dir.glob("*.json"))
    assert len(cache_files) > 0, "No cache files found in examples directory"

    # Validate each cache file
    for cache_file in cache_files:
        cache_data = orjson.loads(cache_file.read_bytes())

        # Should not raise SchemaValidationError
        validate_cache_release(cache_data, cache_file.stem)


@pytest.mark.parametrize(
    "cache_file",
    [
        "beekeeper-studio_beekeeper-studio.json",
        "Legcord_Legcord.json",
        "pbek_QOwnNotes.json",
        "FreeTubeApp_FreeTube_prerelease.json",
        "keepassxreboot_keepassxc.json",
    ],
)
def test_specific_cache_files(
    cache_examples_dir: Path, cache_file: str
) -> None:
    """Test specific well-known cache files."""
    cache_path = cache_examples_dir / cache_file
    if not cache_path.exists():
        pytest.skip(f"Cache file not found: {cache_path}")

    cache_data = orjson.loads(cache_path.read_bytes())

    validate_cache_release(cache_data, cache_path.stem)
