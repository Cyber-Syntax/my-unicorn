#!/usr/bin/env python3
"""Tests for the extract_changelog.sh script."""

import subprocess
from pathlib import Path

import pytest


class TestExtractChangelog:
    """Test suite for extract_changelog.sh script."""

    @pytest.fixture
    def script_path(self) -> Path:
        """Get path to extract_changelog.sh script.

        Returns:
            Path to the script.

        """
        return Path("scripts/extract_changelog.sh")

    @pytest.fixture
    def temp_changelog(self, tmp_path: Path) -> Path:
        """Create a temporary CHANGELOG.md file.

        Args:
            tmp_path: Pytest temporary directory.

        Returns:
            Path to temporary changelog file.

        """
        return tmp_path / "CHANGELOG.md"

    def _run_script(
        self, script_path: Path, changelog_path: Path
    ) -> tuple[int, str, str]:
        """Run the extract_changelog.sh script.

        Args:
            script_path: Path to script.
            changelog_path: Path to changelog file.

        Returns:
            Tuple of (exit_code, stdout, stderr).

        """
        result = subprocess.run(
            [str(script_path), str(changelog_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr

    def test_valid_bracketed_version(
        self, script_path: Path, temp_changelog: Path
    ) -> None:
        """Test extraction of valid bracketed version format.

        Args:
            script_path: Path to script.
            temp_changelog: Path to temporary changelog.

        """
        temp_changelog.write_text(
            """# Changelog

## [1.2.3] - 2024-01-15

### Added
- New feature A
- New feature B

### Fixed
- Bug fix C

## [1.2.2] - 2024-01-01

### Fixed
- Previous bug fix
""",
            encoding="utf-8",
        )

        exit_code, stdout, _ = self._run_script(script_path, temp_changelog)

        assert exit_code == 0
        assert "version=1.2.3" in stdout
        assert "is_unreleased=false" in stdout
        assert "Detected version: 1.2.3" in stdout
        assert "### Added" in stdout
        assert "New feature A" in stdout

    def test_valid_v_prefixed_version(
        self, script_path: Path, temp_changelog: Path
    ) -> None:
        """Test extraction of v-prefixed version format.

        Args:
            script_path: Path to script.
            temp_changelog: Path to temporary changelog.

        """
        temp_changelog.write_text(
            """# Changelog

## v2.0.0

### Breaking Changes
- Major API refactor

### Added
- New API endpoints
""",
            encoding="utf-8",
        )

        exit_code, stdout, _ = self._run_script(script_path, temp_changelog)

        assert exit_code == 0
        assert "version=v2.0.0" in stdout
        assert "is_unreleased=false" in stdout
        assert "### Breaking Changes" in stdout

    def test_unreleased_version(
        self, script_path: Path, temp_changelog: Path
    ) -> None:
        """Test handling of Unreleased version.

        Args:
            script_path: Path to script.
            temp_changelog: Path to temporary changelog.

        """
        temp_changelog.write_text(
            """# Changelog

## [Unreleased]

### Added
- Work in progress
""",
            encoding="utf-8",
        )

        exit_code, stdout, _ = self._run_script(script_path, temp_changelog)

        assert exit_code == 0
        assert "version=Unreleased" in stdout
        assert "is_unreleased=true" in stdout
        assert "Version is Unreleased, skipping release creation" in stdout

    def test_prerelease_version(
        self, script_path: Path, temp_changelog: Path
    ) -> None:
        """Test extraction of pre-release version.

        Args:
            script_path: Path to script.
            temp_changelog: Path to temporary changelog.

        """
        temp_changelog.write_text(
            """# Changelog

## [1.0.0-beta.1] - 2024-01-10

### Added
- Beta feature
""",
            encoding="utf-8",
        )

        exit_code, stdout, _ = self._run_script(script_path, temp_changelog)

        assert exit_code == 0
        assert "version=1.0.0-beta.1" in stdout
        assert "is_unreleased=false" in stdout

    def test_missing_changelog(
        self, script_path: Path, tmp_path: Path
    ) -> None:
        """Test error handling when CHANGELOG.md is missing.

        Args:
            script_path: Path to script.
            tmp_path: Pytest temporary directory.

        """
        nonexistent = tmp_path / "NONEXISTENT.md"

        exit_code, stdout, _ = self._run_script(script_path, nonexistent)

        assert exit_code == 1
        assert "::error::CHANGELOG.md not found" in stdout

    def test_invalid_version_header(
        self, script_path: Path, temp_changelog: Path
    ) -> None:
        """Test error handling for invalid version header.

        Args:
            script_path: Path to script.
            temp_changelog: Path to temporary changelog.

        """
        temp_changelog.write_text(
            """# Changelog

## Latest Release

### Added
- Some feature
""",
            encoding="utf-8",
        )

        exit_code, stdout, _ = self._run_script(script_path, temp_changelog)

        assert exit_code == 1
        # The script returns "No version header found" for invalid headers
        assert "::error::" in stdout

    def test_no_version_header(
        self, script_path: Path, temp_changelog: Path
    ) -> None:
        """Test error handling when no version header is found.

        Args:
            script_path: Path to script.
            temp_changelog: Path to temporary changelog.

        """
        temp_changelog.write_text(
            """# Changelog

This is just some text without version headers.
""",
            encoding="utf-8",
        )

        exit_code, stdout, _ = self._run_script(script_path, temp_changelog)

        assert exit_code == 1
        assert "::error::No version header found" in stdout

    def test_multiple_versions_extracts_first(
        self, script_path: Path, temp_changelog: Path
    ) -> None:
        """Test that only the first version is extracted.

        Args:
            script_path: Path to script.
            temp_changelog: Path to temporary changelog.

        """
        temp_changelog.write_text(
            """# Changelog

## [2.1.0] - 2024-02-01

### Added
- Latest feature

## [2.0.0] - 2024-01-15

### Added
- Previous feature
""",
            encoding="utf-8",
        )

        exit_code, stdout, _ = self._run_script(script_path, temp_changelog)

        assert exit_code == 0
        assert "version=2.1.0" in stdout
        assert "Latest feature" in stdout
        # Should not include previous version notes
        assert "Previous feature" not in stdout

    def test_notes_stop_at_next_header(
        self, script_path: Path, temp_changelog: Path
    ) -> None:
        """Test that notes extraction stops at next version header.

        Args:
            script_path: Path to script.
            temp_changelog: Path to temporary changelog.

        """
        temp_changelog.write_text(
            """# Changelog

## [1.5.0] - 2024-01-20

### Added
- Feature for 1.5.0

## [1.4.0] - 2024-01-10

### Added
- Feature for 1.4.0
""",
            encoding="utf-8",
        )

        exit_code, stdout, _ = self._run_script(script_path, temp_changelog)

        assert exit_code == 0
        assert "Feature for 1.5.0" in stdout
        assert "Feature for 1.4.0" not in stdout


def test_integration_with_real_changelog(tmp_path: Path) -> None:
    """Integration test using realistic CHANGELOG format.

    Args:
        tmp_path: Pytest temporary directory.

    """
    script_path = Path("scripts/extract_changelog.sh")
    changelog = tmp_path / "CHANGELOG.md"
    # Constants
    eof_marker_length = 20
    base64_chars = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    )

    # Create a realistic changelog
    changelog.write_text(
        """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2024-01-20

### Added
- New command-line option `--verbose` for detailed output
- Support for configuration files in YAML format
- API rate limiting for external service calls

### Changed
- Updated dependencies to latest stable versions
- Improved error messages for better debugging
- Refactored authentication module for better maintainability

### Fixed
- Fixed memory leak in background worker process
- Resolved race condition in concurrent file operations
- Corrected timezone handling for international users

### Security
- Patched CVE-2024-12345 in dependency X
- Updated encryption algorithm to use AES-256

## [1.2.0] - 2024-01-01

### Added
- Initial public release
- Basic CLI interface
- Configuration management
""",
        encoding="utf-8",
    )

    # Run the script
    result = subprocess.run(
        [str(script_path), str(changelog)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "version=1.3.0" in result.stdout
    assert "is_unreleased=false" in result.stdout
    assert "### Added" in result.stdout
    assert "New command-line option" in result.stdout
    assert "### Security" in result.stdout
    assert "Patched CVE-2024-12345" in result.stdout
    # Should not include 1.2.0 notes
    assert "Initial public release" not in result.stdout

    # Write output to markdown file for visual inspection
    output_file = Path("test_github_release_desc.md")
    with output_file.open("w", encoding="utf-8") as f:
        f.write("# Release Extraction Test Results\n\n")
        f.write("## Extracted Version\n\n")
        f.write("```\n")
        # Extract version from stdout
        for line in result.stdout.split("\n"):
            if "version=" in line and not line.startswith("::"):
                f.write(f"{line}\n")
            if "is_unreleased=" in line and not line.startswith("::"):
                f.write(f"{line}\n")
        f.write("```\n\n")
        f.write("## Release Notes Preview\n\n")
        f.write("```markdown\n")
        # Extract notes section
        in_notes = False
        for line in result.stdout.split("\n"):
            if line.startswith("notes<<"):
                in_notes = True
                continue
            if in_notes and line.strip() and not line.startswith("::"):
                # Check if this is the EOF marker (base64 string)
                if len(line) == eof_marker_length and all(
                    c in base64_chars for c in line
                ):
                    break
                f.write(f"{line}\n")
        f.write("```\n\n")
        f.write("## Full Script Output\n\n")
        f.write("```\n")
        f.write(result.stdout)
        f.write("```\n")

    print(f"\n✅ Integration test passed! Results written to {output_file}")
