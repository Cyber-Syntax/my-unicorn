"""Tests for configuration builder utilities."""

from my_unicorn.utils.config_builders import (
    build_method_entry,
    build_overrides_from_template,
    build_verification_state,
)


class TestBuildMethodEntry:
    """Test build_method_entry function."""

    def test_build_method_entry_with_dict_result_digest(self):
        """Test building method entry from dict result (digest type)."""
        result = {
            "passed": True,
            "hash_type": "sha256",
            "hash": "abc123def456",
            "computed_hash": "abc123def456",
        }
        entry = build_method_entry("digest", result)

        assert entry["type"] == "digest"
        assert entry["status"] == "passed"
        assert entry["algorithm"] == "SHA256"
        assert entry["expected"] == "abc123def456"
        assert entry["computed"] == "abc123def456"
        assert entry["source"] == "github_api"

    def test_build_method_entry_with_dict_result_checksum_file(self):
        """Test building method entry from dict result (checksum_file)."""
        result = {
            "passed": True,
            "hash_type": "sha512",
            "hash": "xyz789",
            "computed_hash": "xyz789",
            "url": "https://example.com/checksums.txt",
        }
        entry = build_method_entry("checksum_file", result)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "passed"
        assert entry["algorithm"] == "SHA512"
        assert entry["expected"] == "xyz789"
        assert entry["computed"] == "xyz789"
        assert entry["source"] == "https://example.com/checksums.txt"

    def test_build_method_entry_with_failed_result(self):
        """Test building method entry from failed verification."""
        result = {
            "passed": False,
            "hash_type": "sha256",
            "hash": "expected123",
            "computed_hash": "actual456",
        }
        entry = build_method_entry("digest", result)

        assert entry["type"] == "digest"
        assert entry["status"] == "failed"
        assert entry["algorithm"] == "SHA256"
        assert entry["expected"] == "expected123"
        assert entry["computed"] == "actual456"

    def test_build_method_entry_with_bool_result_true(self):
        """Test building method entry from simple boolean (True)."""
        entry = build_method_entry("digest", True)

        assert entry["type"] == "digest"
        assert entry["status"] == "passed"
        assert "algorithm" not in entry

    def test_build_method_entry_with_bool_result_false(self):
        """Test building method entry from simple boolean (False)."""
        entry = build_method_entry("checksum_file", False)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "failed"
        assert "algorithm" not in entry

    def test_build_method_entry_with_missing_hash_type(self):
        """Test building method entry when hash_type is missing."""
        result = {
            "passed": True,
            "hash": "abc123",
            "computed_hash": "abc123",
        }
        entry = build_method_entry("digest", result)

        assert entry["algorithm"] == "SHA256"  # Default

    def test_build_method_entry_normalizes_checksum_file_0(self):
        """Test that checksum_file_0 is normalized to checksum_file."""
        result = {
            "passed": True,
            "hash_type": "sha256",
            "hash": "abc123",
            "computed_hash": "abc123",
            "url": "https://example.com/SHA256SUMS",
        }
        entry = build_method_entry("checksum_file_0", result)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "passed"

    def test_build_method_entry_normalizes_checksum_file_1(self):
        """Test that checksum_file_1 is normalized to checksum_file."""
        result = {
            "passed": True,
            "hash_type": "sha512",
            "hash": "def456",
            "computed_hash": "def456",
            "url": "https://example.com/SHA512SUMS",
        }
        entry = build_method_entry("checksum_file_1", result)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "passed"

    def test_build_method_entry_normalizes_checksum_file_with_high_index(self):
        """Test that checksum_file_99 is normalized to checksum_file."""
        entry = build_method_entry("checksum_file_99", True)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "passed"

    def test_build_method_entry_keeps_plain_checksum_file_unchanged(self):
        """Test that plain checksum_file type remains unchanged."""
        result = {
            "passed": True,
            "hash_type": "sha256",
            "hash": "abc123",
            "computed_hash": "abc123",
            "url": "https://example.com/checksums.txt",
        }
        entry = build_method_entry("checksum_file", result)

        assert entry["type"] == "checksum_file"

    def test_build_method_entry_keeps_digest_unchanged(self):
        """Test that digest method type remains unchanged."""
        result = {"passed": True, "hash_type": "sha256"}
        entry = build_method_entry("digest", result)

        assert entry["type"] == "digest"

    def test_build_method_entry_skip_returns_only_type_and_status(self):
        """Skip method returns only type/status without hash fields."""
        entry = build_method_entry(
            "skip", {"passed": False, "status": "skipped"}
        )

        assert entry == {"type": "skip", "status": "skipped"}
        assert "algorithm" not in entry
        assert "expected" not in entry
        assert "computed" not in entry
        assert "source" not in entry

    def test_build_method_entry_skip_ignores_result_content(self):
        """Skip always returns canonical form regardless of input."""
        entry = build_method_entry("skip", {"passed": True, "extra": "data"})

        assert entry == {"type": "skip", "status": "skipped"}

    def test_build_method_entry_keeps_skip_unchanged(self):
        """Test that skip method type remains unchanged."""
        entry = build_method_entry("skip", True)

        assert entry["type"] == "skip"


class TestBuildVerificationState:
    """Test build_verification_state function."""

    def test_build_verification_state_with_valid_result(self):
        """Test building verification state from valid result."""
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash_type": "sha256",
                    "hash": "abc123",
                    "computed_hash": "abc123",
                }
            },
        }
        state = build_verification_state(verify_result)

        assert state["passed"] is True
        assert state["actual_method"] == "digest"
        assert len(state["methods"]) == 1
        assert state["methods"][0]["type"] == "digest"
        assert state["methods"][0]["status"] == "passed"

    def test_build_verification_state_with_multiple_methods(self):
        """Test building verification state with multiple methods."""
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {"passed": True, "hash_type": "sha256"},
                "checksum_file": {
                    "passed": True,
                    "hash_type": "sha512",
                    "url": "https://example.com/sums",
                },
            },
        }
        state = build_verification_state(verify_result)

        assert state["passed"] is True
        assert state["actual_method"] == "digest"  # First method
        assert len(state["methods"]) == 2

    def test_build_verification_state_with_none_result(self):
        """Test building verification state when result is None."""
        state = build_verification_state(None)

        assert state["passed"] is False
        assert state["actual_method"] == "skip"
        assert len(state["methods"]) == 1
        assert state["methods"][0]["type"] == "skip"
        assert state["methods"][0]["status"] == "skipped"

    def test_build_verification_state_with_empty_methods(self):
        """Test building verification state with empty methods dict."""
        verify_result = {"passed": False, "methods": {}}
        state = build_verification_state(verify_result)

        assert state["passed"] is False
        assert state["actual_method"] == "skip"
        assert len(state["methods"]) == 1
        assert state["methods"][0] == {"type": "skip", "status": "skipped"}

    def test_empty_verification_state_has_skip_method(self):
        """Test empty verification state has skip method, not empty list."""
        state = build_verification_state(None)

        assert state["methods"] == [{"type": "skip", "status": "skipped"}]

    def test_build_verification_state_none_input_returns_skip(self):
        """build_verification_state(None) returns exactly one skip entry."""
        state = build_verification_state(None)

        assert len(state["methods"]) == 1
        assert state["methods"][0]["type"] == "skip"
        assert state["methods"][0]["status"] == "skipped"

    def test_build_verification_state_with_failed_verification(self):
        """Test building verification state when verification failed."""
        verify_result = {
            "passed": False,
            "methods": {
                "digest": {
                    "passed": False,
                    "hash_type": "sha256",
                    "hash": "expected",
                    "computed_hash": "actual",
                }
            },
        }
        state = build_verification_state(verify_result)

        assert state["passed"] is False
        assert state["actual_method"] == "digest"
        assert state["methods"][0]["status"] == "failed"

    def test_build_verification_state_includes_overall_passed(self):
        """Test that build_verification_state always includes overall_passed.

        Schema compatibility test: overall_passed is now a valid optional field
        in app_state_v2.schema.json and config_builders must include it.
        """
        verify_result = {
            "passed": True,
            "methods": {"digest": {"passed": True, "hash_type": "sha256"}},
        }
        state = build_verification_state(verify_result)

        assert "overall_passed" in state
        assert state["overall_passed"] is True
        assert state["overall_passed"] == state["passed"]

    def test_build_verification_state_includes_actual_method(self):
        """Test that build_verification_state always includes actual_method.

        Schema compatibility test: actual_method is now a valid optional
        field in app_state_v2.schema.json with enum values: digest,
        checksum_file, skip.
        """
        verify_result = {
            "passed": True,
            "methods": {"digest": {"passed": True, "hash_type": "sha256"}},
        }
        state = build_verification_state(verify_result)

        assert "actual_method" in state
        assert state["actual_method"] in ("digest", "checksum_file", "skip")

    def test_build_verification_state_actual_method_prefers_digest(self):
        """Test actual_method prefers digest over checksum_file."""
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {"passed": True, "hash_type": "sha256"},
                "checksum_file": {
                    "passed": True,
                    "hash_type": "sha512",
                    "url": "https://example.com/SHA512SUMS.txt",
                },
            },
        }
        state = build_verification_state(verify_result)

        assert state["actual_method"] == "digest"

    def test_build_verification_state_empty_returns_skip(self):
        """Test actual_method is 'skip' when no verification data available."""
        state = build_verification_state(None)

        assert state["actual_method"] == "skip"
        assert state["overall_passed"] is False
        assert state["passed"] is False

    def test_build_verification_state_with_warning(self):
        """Test that warnings are included when present in verify result.

        Schema compatibility test: warning is now a valid optional field
        in app_state_v2.schema.json.
        """
        verify_result = {
            "passed": True,
            "warning": "Hash algorithm is deprecated",
            "methods": {"digest": {"passed": True, "hash_type": "sha256"}},
        }
        state = build_verification_state(verify_result)

        assert "warning" in state
        assert state["warning"] == "Hash algorithm is deprecated"


class TestBuildOverridesFromTemplate:
    """Test build_overrides_from_template function."""

    def test_build_overrides_with_complete_template(self):
        """Test building overrides from complete app config template."""
        template = {
            "source": {
                "owner": "myowner",
                "repo": "myrepo",
                "prerelease": True,
            },
            "appimage": {
                "naming": {
                    "template": "{repo}-{version}.AppImage",
                    "target_name": "MyApp.AppImage",
                }
            },
            "verification": {"method": "digest"},
            "icon": {"method": "extraction", "filename": "app.png"},
        }
        overrides = build_overrides_from_template(template)

        assert overrides["metadata"]["name"] == "myrepo"
        assert overrides["source"]["owner"] == "myowner"
        assert overrides["source"]["repo"] == "myrepo"
        assert overrides["source"]["prerelease"] is True
        assert (
            overrides["appimage"]["naming"]["template"]
            == "{repo}-{version}.AppImage"
        )
        assert overrides["verification"]["method"] == "digest"
        assert overrides["icon"]["method"] == "extraction"
        assert overrides["icon"]["filename"] == "app.png"

    def test_build_overrides_with_minimal_template(self):
        """Test building overrides from minimal template with defaults."""
        template = {"source": {"owner": "foo", "repo": "bar"}}
        overrides = build_overrides_from_template(template)

        assert overrides["source"]["owner"] == "foo"
        assert overrides["source"]["repo"] == "bar"
        assert overrides["source"]["prerelease"] is False  # Default
        assert overrides["verification"]["method"] == "skip"  # Default
        assert overrides["icon"]["method"] == "extraction"  # Default

    def test_build_overrides_with_empty_template(self):
        """Test building overrides from empty template."""
        template = {}
        overrides = build_overrides_from_template(template)

        assert overrides["source"]["owner"] == ""
        assert overrides["source"]["repo"] == ""
        assert overrides["metadata"]["name"] == ""
