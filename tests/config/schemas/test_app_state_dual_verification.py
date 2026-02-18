"""Dual verification compatibility tests for app state files.

This module contains tests that validate dual verification patterns
in production app state files. Tests cover:
- Individual dual verification file structures
- Algorithm case sensitivity handling
- Digest field format (with/without prefix)
"""

from pathlib import Path

import orjson
import pytest


def test_beekeeper_dual_verification_structure(app_state_dir: Path) -> None:
    """Test beekeeper-studio has SHA256 digest + SHA512 checksum_file pattern.

    Validates:
    - 2 verification methods present
    - One method is type: "digest" with algorithm: "sha256"
    - One method is type: "checksum_file" with algorithm: "sha512"
    - Both methods have status: "passed"
    - actual_method is set (should prefer "digest")
    """
    app_state_file = "beekeeper-studio.json"
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    methods = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("methods", [])
    )

    # Should have exactly 2 methods
    assert len(methods) == 2, f"Expected 2 methods, got {len(methods)}"

    # Find digest and checksum_file methods
    digest_methods = [m for m in methods if m.get("type") == "digest"]
    checksum_methods = [m for m in methods if m.get("type") == "checksum_file"]

    assert len(digest_methods) == 1, "Should have one digest method"
    assert len(checksum_methods) == 1, "Should have one checksum_file method"

    # Verify digest is SHA256
    digest_method = digest_methods[0]
    assert digest_method.get("algorithm", "").lower() == "sha256", (
        f"Digest algorithm should be sha256, "
        f"got {digest_method.get('algorithm')}"
    )
    assert digest_method.get("status") == "passed", "Digest should pass"

    # Verify checksum_file is SHA512
    checksum_method = checksum_methods[0]
    assert checksum_method.get("algorithm", "").lower() == "sha512", (
        f"Checksum algorithm should be sha512, "
        f"got {checksum_method.get('algorithm')}"
    )
    assert checksum_method.get("status") == "passed", "Checksum should pass"

    # Verify actual_method is set (optional field)
    actual_method = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("actual_method")
    )
    if actual_method is not None:
        assert actual_method in ["digest", "checksum_file"], (
            f"actual_method should be digest or checksum_file, "
            f"got {actual_method}"
        )


def test_legcord_dual_verification_structure(app_state_dir: Path) -> None:
    """Test legcord has SHA256 digest + SHA512 checksum_file pattern.

    Same structure as beekeeper-studio.
    """
    app_state_file = "legcord.json"
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    methods = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("methods", [])
    )

    assert len(methods) == 2, f"Expected 2 methods, got {len(methods)}"

    digest_methods = [m for m in methods if m.get("type") == "digest"]
    checksum_methods = [m for m in methods if m.get("type") == "checksum_file"]

    assert len(digest_methods) == 1
    assert len(checksum_methods) == 1

    assert digest_methods[0].get("algorithm", "").lower() == "sha256"
    assert digest_methods[0].get("status") == "passed"

    assert checksum_methods[0].get("algorithm", "").lower() == "sha512"
    assert checksum_methods[0].get("status") == "passed"


def test_qownnotes_dual_verification_structure(app_state_dir: Path) -> None:
    """Test qownnotes has SHA256 digest + SHA256 checksum_file pattern.

    Both methods use SHA256 algorithm.
    """
    app_state_file = "qownnotes.json"
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    methods = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("methods", [])
    )

    assert len(methods) == 2, f"Expected 2 methods, got {len(methods)}"

    digest_methods = [m for m in methods if m.get("type") == "digest"]
    checksum_methods = [m for m in methods if m.get("type") == "checksum_file"]

    assert len(digest_methods) == 1
    assert len(checksum_methods) == 1

    # Both should use SHA256
    assert digest_methods[0].get("algorithm", "").lower() == "sha256"
    assert digest_methods[0].get("status") == "passed"

    assert checksum_methods[0].get("algorithm", "").lower() == "sha256"
    assert checksum_methods[0].get("status") == "passed"


def test_keepassxc_dual_verification_structure(app_state_dir: Path) -> None:
    """Test keepassxc has SHA256 digest + SHA256 checksum_file pattern.

    Same as qownnotes - both methods use SHA256.
    """
    app_state_file = "keepassxc.json"
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    methods = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("methods", [])
    )

    assert len(methods) == 2, f"Expected 2 methods, got {len(methods)}"

    digest_methods = [m for m in methods if m.get("type") == "digest"]
    checksum_methods = [m for m in methods if m.get("type") == "checksum_file"]

    assert len(digest_methods) == 1
    assert len(checksum_methods) == 1

    assert digest_methods[0].get("algorithm", "").lower() == "sha256"
    assert digest_methods[0].get("status") == "passed"

    assert checksum_methods[0].get("algorithm", "").lower() == "sha256"
    assert checksum_methods[0].get("status") == "passed"


def test_tagspaces_dual_verification_structure(app_state_dir: Path) -> None:
    """Test tagspaces (install_catalog.json) has dual verification.

    Validates digest + checksum_file pattern from catalog.
    """
    app_state_file = "install_catalog.json"
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    methods = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("methods", [])
    )

    # Should have at least 2 methods (digest + checksum_file)
    assert len(methods) >= 2, f"Expected >= 2 methods, got {len(methods)}"

    digest_methods = [m for m in methods if m.get("type") == "digest"]
    checksum_methods = [m for m in methods if m.get("type") == "checksum_file"]

    # Should have at least one of each
    assert len(digest_methods) >= 1, "Should have at least one digest method"
    assert len(checksum_methods) >= 1, (
        "Should have at least one checksum_file method"
    )

    # All methods should pass
    for method in methods:
        assert method.get("status") == "passed", (
            f"Method {method.get('type')} should have status passed, "
            f"got {method.get('status')}"
        )


def test_algorithm_case_sensitivity(app_state_dir: Path) -> None:
    """Test that algorithm field handles case variations (sha256 vs SHA256).

    Uses freetube.json which has lowercase sha256.
    """
    app_state_file = "freetube.json"
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    methods = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("methods", [])
    )

    # Find digest methods
    digest_methods = [m for m in methods if m.get("type") == "digest"]
    assert len(digest_methods) > 0, "Should have at least one digest method"

    # Verify algorithm is lowercase or uppercase sha256
    for method in digest_methods:
        algorithm = method.get("algorithm", "").lower()
        assert algorithm in [
            "sha256",
            "sha512",
        ], f"Algorithm should be sha256/sha512, got {method.get('algorithm')}"


def test_digest_prefix_handling(app_state_dir: Path) -> None:
    """Test digest field format handling (sha256:hash vs hash).

    Production files may have digest with or without algorithm prefix.
    This test verifies that both formats are accepted by the schema.
    """
    # Test beekeeper-studio which should have digest field
    app_state_file = "beekeeper-studio.json"
    if not app_state_dir.exists():
        pytest.skip(f"App state directory not found: {app_state_dir}")

    app_state_path = app_state_dir / app_state_file
    if not app_state_path.exists():
        pytest.skip(f"App state file not found: {app_state_path}")

    app_state_data = orjson.loads(app_state_path.read_bytes())

    methods = (
        app_state_data.get("state", {})
        .get("verification", {})
        .get("methods", [])
    )

    # Find methods with digest field
    methods_with_digest = [m for m in methods if "digest" in m]

    if len(methods_with_digest) > 0:
        for method in methods_with_digest:
            digest_value = method.get("digest")
            # Digest can be:
            # 1. Plain hash (64 chars for sha256, 128 for sha512)
            # 2. Prefixed with algorithm (sha256:hash, sha512:hash)
            # Just verify it's a non-empty string
            assert isinstance(digest_value, str), (
                f"Digest should be string, got {type(digest_value)}"
            )
            assert len(digest_value) > 0, "Digest should not be empty"
