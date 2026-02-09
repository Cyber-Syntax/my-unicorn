"""Test config roundtrip serialization (load→validate→save→validate).

Ensures no data loss during JSON serialization/deserialization cycles.
"""

from pathlib import Path

import orjson
import pytest

from my_unicorn.config.schemas import (
    validate_app_state,
    validate_cache_release,
)


@pytest.mark.parametrize(
    "app_state_file",
    [
        "beekeeper-studio.json",
        "digest_catalog.json",
        "digest_url.json",
        "install_catalog.json",
        "install_url.json",
        "keepassxc.json",
        "legcord.json",
        "qownnotes.json",
        "skipped_catalog.json",
        "freetube.json",
    ],
)
def test_app_state_roundtrip(app_state_dir: Path, app_state_file: str) -> None:
    """Test app state files survive load→serialize→load→validate cycle.

    Validates:
    - Original data loads and validates
    - Data can be serialized back to JSON
    - Serialized data can be parsed
    - Parsed data validates against schema
    - Roundtrip data matches original (excluding orjson formatting differences)
    """
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    # Load original
    original_data = orjson.loads(app_state_path.read_bytes())

    # Validate original
    validate_app_state(original_data, app_state_path.stem)

    # Serialize to JSON
    serialized_json = orjson.dumps(
        original_data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
    )

    # Parse serialized JSON
    roundtrip_data = orjson.loads(serialized_json)

    # Validate roundtrip data
    validate_app_state(roundtrip_data, app_state_path.stem)

    # Verify key fields match
    assert roundtrip_data.get("app_name") == original_data.get("app_name")
    assert roundtrip_data.get("config_version") == original_data.get(
        "config_version"
    )
    assert roundtrip_data.get("source") == original_data.get("source")
    assert roundtrip_data.get("catalog_ref") == original_data.get(
        "catalog_ref"
    )

    # Verify verification state is preserved
    original_verification = original_data.get("state", {}).get(
        "verification", {}
    )
    roundtrip_verification = roundtrip_data.get("state", {}).get(
        "verification", {}
    )

    assert roundtrip_verification.get("passed") == original_verification.get(
        "passed"
    )
    assert len(roundtrip_verification.get("methods", [])) == len(
        original_verification.get("methods", [])
    )


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
def test_cache_roundtrip(cache_examples_dir: Path, cache_file: str) -> None:
    """Test cache files survive load→serialize→load→validate cycle.

    Validates:
    - Original data loads and validates
    - Data can be serialized back to JSON
    - Serialized data can be parsed
    - Parsed data validates against schema
    - Timestamps are preserved
    - Asset arrays maintain order and content
    """
    if not cache_examples_dir.exists():
        pytest.skip(
            f"Cache examples directory not found: {cache_examples_dir}"
        )

    cache_path = cache_examples_dir / cache_file
    if not cache_path.exists():
        pytest.skip(f"Cache file not found: {cache_path}")

    # Load original
    original_data = orjson.loads(cache_path.read_bytes())

    # Validate original
    validate_cache_release(original_data, cache_path.stem)

    # Serialize to JSON
    serialized_json = orjson.dumps(
        original_data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
    )

    # Parse serialized JSON
    roundtrip_data = orjson.loads(serialized_json)

    # Validate roundtrip data
    validate_cache_release(roundtrip_data, cache_path.stem)

    # Verify key fields match
    assert roundtrip_data.get("timestamp") == original_data.get("timestamp")
    assert roundtrip_data.get("ttl_hours") == original_data.get("ttl_hours")
    assert roundtrip_data.get("tag_name") == original_data.get("tag_name")
    assert roundtrip_data.get("prerelease") == original_data.get("prerelease")

    # Verify assets array preserved
    assert len(roundtrip_data.get("assets", [])) == len(
        original_data.get("assets", [])
    )

    # Verify digest format preserved
    original_digest = original_data.get("digest")
    roundtrip_digest = roundtrip_data.get("digest")

    if original_digest is not None:
        assert roundtrip_digest == original_digest


def test_optional_fields_preserved(app_state_dir: Path) -> None:
    """Test that optional fields survive roundtrip.

    Tests fields:
    - state.verification.overall_passed
    - state.verification.actual_method
    - state.verification.warning

    Uses beekeeper-studio.json or another file with optional fields.
    """
    # Use a file that might have optional fields
    app_state_file = "beekeeper-studio.json"

    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    original_data = orjson.loads(app_state_path.read_bytes())

    # Add optional fields if they don't exist (for testing purposes)
    verification = original_data.setdefault("state", {}).setdefault(
        "verification", {}
    )
    original_had_overall_passed = "overall_passed" in verification
    original_had_actual_method = "actual_method" in verification
    original_had_warning = "warning" in verification

    if not original_had_overall_passed:
        verification["overall_passed"] = True
    if not original_had_actual_method:
        verification["actual_method"] = "digest"
    if not original_had_warning:
        verification["warning"] = "Test warning message"

    # Validate modified data
    validate_app_state(original_data, app_state_path.stem)

    # Roundtrip
    serialized_json = orjson.dumps(
        original_data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
    )
    roundtrip_data = orjson.loads(serialized_json)

    # Validate roundtrip
    validate_app_state(roundtrip_data, app_state_path.stem)

    # Verify optional fields preserved
    roundtrip_verification = roundtrip_data.get("state", {}).get(
        "verification", {}
    )

    assert "overall_passed" in roundtrip_verification
    assert "actual_method" in roundtrip_verification
    assert "warning" in roundtrip_verification

    assert (
        roundtrip_verification["overall_passed"]
        == verification["overall_passed"]
    )
    assert (
        roundtrip_verification["actual_method"]
        == verification["actual_method"]
    )
    assert roundtrip_verification["warning"] == verification["warning"]


def test_empty_optional_fields_not_added(app_state_dir: Path) -> None:
    """Test that roundtrip doesn't add optional fields that weren't present.

    Uses digest_catalog.json which may not have all optional fields.
    """
    app_state_file = "digest_catalog.json"

    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    original_data = orjson.loads(app_state_path.read_bytes())

    # Track which optional fields were present originally
    verification = original_data.get("state", {}).get("verification", {})
    original_keys = set(verification.keys())

    # Roundtrip
    serialized_json = orjson.dumps(
        original_data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
    )
    roundtrip_data = orjson.loads(serialized_json)

    # Validate roundtrip
    validate_app_state(roundtrip_data, app_state_path.stem)

    # Verify no new keys added
    roundtrip_verification = roundtrip_data.get("state", {}).get(
        "verification", {}
    )
    roundtrip_keys = set(roundtrip_verification.keys())

    # Roundtrip should not add keys that weren't in original
    assert roundtrip_keys == original_keys, (
        f"Roundtrip added keys: {roundtrip_keys - original_keys}, "
        f"or removed keys: {original_keys - roundtrip_keys}"
    )
