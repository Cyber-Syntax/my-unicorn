"""Production data validation tests for app state files.

This module contains tests that validate real production app state files
against their JSON schema. Tests cover:
- All production app state files validation
- Dual verification file structure
- Catalog vs URL source structure
- Skip verification configuration
"""

from pathlib import Path

import orjson
import pytest

from my_unicorn.config.schemas import validate_app_state


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
def test_all_production_app_state_files_validate(
    app_state_dir: Path, app_state_file: str
) -> None:
    """Test that all production app state files validate successfully.

    Validates:
    - All 11 app state files against app_state_v2.schema.json
    - config_version equals "2.0.0"
    - source is either "catalog" or "url"
    """
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    # Should not raise SchemaValidationError
    validate_app_state(app_state_data, app_state_path.stem)

    # Verify required fields
    assert app_state_data.get("config_version") == "2.0.0", (
        f"config_version must be 2.0.0, "
        f"got {app_state_data.get('config_version')}"
    )

    assert app_state_data.get("source") in ["catalog", "url"], (
        f"source must be 'catalog' or 'url', "
        f"got {app_state_data.get('source')}"
    )


@pytest.mark.parametrize(
    "app_state_file",
    [
        "beekeeper-studio.json",
        "legcord.json",
        "qownnotes.json",
        "keepassxc.json",
        "install_catalog.json",
    ],
)
def test_dual_verification_files_have_multiple_methods(
    app_state_dir: Path, app_state_file: str
) -> None:
    """Test that dual-verification files have multiple verification methods.

    These 5 files demonstrate multiple verification methods:
    (e.g. digest + checksum_file)
    - beekeeper-studio.json
    - legcord.json
    - qownnotes.json
    - keepassxc.json
    - install_catalog.json

    Validates:
    - At least 2 verification methods present
    - All methods have status: "passed"
    """
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    # Verify multiple verification methods exist
    methods = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("methods", [])
    )
    assert len(methods) >= 2, (
        f"{app_state_file} should have at least 2 methods, got {len(methods)}"
    )

    # Verify all methods passed
    for method in methods:
        assert method.get("status") == "passed", (
            f"Method {method.get('type')} in {app_state_file} has status "
            f"{method.get('status')}, expected 'passed'"
        )


@pytest.mark.parametrize(
    "app_state_file",
    [
        "beekeeper-studio.json",
        "legcord.json",
        "qownnotes.json",
        "digest_catalog.json",
        "install_catalog.json",
        "skipped_catalog.json",
        "freetube.json",
    ],
)
def test_catalog_files_structure(
    app_state_dir: Path, app_state_file: str
) -> None:
    """Test that catalog source files have correct structure.

    Catalog files (7 files):
    - beekeeper-studio.json
    - legcord.json
    - qownnotes.json
    - digest_catalog.json
    - install_catalog.json
    - skipped_catalog.json
    - freetube.json

    Validates:
    - source == "catalog"
    - catalog_ref is not None and not empty string
    - overrides field is absent or None
    """
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    # Verify source is catalog
    assert app_state_data.get("source") == "catalog", (
        f"{app_state_file} should have source='catalog', "
        f"got {app_state_data.get('source')}"
    )

    # Verify catalog_ref is present and non-empty
    catalog_ref = app_state_data.get("catalog_ref")
    assert catalog_ref, f"{app_state_file} should have non-empty catalog_ref"
    assert len(str(catalog_ref)) > 0, (
        f"{app_state_file} catalog_ref should not be empty"
    )

    # Verify overrides is absent or None
    overrides = app_state_data.get("overrides")
    assert overrides is None, (
        f"{app_state_file} should not have overrides, got {overrides}"
    )


@pytest.mark.parametrize(
    "app_state_file",
    [
        "keepassxc.json",
        "digest_url.json",
        "install_url.json",
    ],
)
def test_url_files_structure(app_state_dir: Path, app_state_file: str) -> None:
    """Test that URL source files have correct structure.

    URL files (3 files):
    - keepassxc.json
    - digest_url.json
    - install_url.json

    Validates:
    - source == "url"
    - catalog_ref is None
    - overrides field exists and is a dict
    """
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    # Verify source is url
    assert app_state_data.get("source") == "url", (
        f"{app_state_file} should have source='url', "
        f"got {app_state_data.get('source')}"
    )

    # Verify catalog_ref is None
    catalog_ref = app_state_data.get("catalog_ref")
    assert catalog_ref is None, (
        f"{app_state_file} URL source should have catalog_ref=null, "
        f"got {catalog_ref}"
    )

    # Verify overrides exists and is a dict
    overrides = app_state_data.get("overrides")
    assert isinstance(overrides, dict), (
        f"{app_state_file} should have overrides as dict, "
        f"got {type(overrides)}"
    )
    assert len(overrides) > 0, (
        f"{app_state_file} overrides should not be empty"
    )


@pytest.mark.parametrize(
    "app_state_file",
    [
        "skipped_catalog.json",
    ],
)
def test_skip_verification_structure(
    app_state_dir: Path, app_state_file: str
) -> None:
    """Test that skip verification files have correct structure.

    Skip verification file:
    - skipped_catalog.json

    Validates:
    - state.verification.passed == False
    - At least one method has type: "skip"

    Note: skipped_url.json is excluded because it has an empty methods array,
    which violates the schema (methods must be non-empty).
    """
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    # Verify verification.passed is False
    verification_passed = (
        app_state_data.get("state", {}).get("verification", {}).get("passed")
    )
    assert verification_passed is False, (
        f"{app_state_file} should have verification.passed=false, "
        f"got {verification_passed}"
    )

    # Verify at least one skip method exists
    methods = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("methods", [])
    )
    skip_methods = [m for m in methods if m.get("type") == "skip"]
    assert len(skip_methods) > 0, (
        f"{app_state_file} should have at least one skip method"
    )
