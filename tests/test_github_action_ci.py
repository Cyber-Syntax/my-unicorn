#!/usr/bin/env python3
"""Pytest for GitHub Actions release workflow test script.

This test runs the local test script and validates the generated markdown
contains the expected version, tag, and release notes, and that it does
not include a commits section.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest


def _extract_version_from_changelog(changelog_path: Path) -> str:
    text = changelog_path.read_text(encoding="utf-8")
    # Prefer bracketed header: ## [1.2.3]
    m = re.search(r"^##\s*\[([^\]]+)\]", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # v-prefixed header: ## v1.2.3
    m = re.search(
        r"^##\s*(v[0-9]+(?:\.[0-9]+)*(?:[-A-Za-z0-9]+)?)", text, re.MULTILINE
    )
    if m:
        return m.group(1).strip()
    # Numeric header: ## 1.2.3
    m = re.search(r"^##\s*([0-9]+\.[0-9]+(?:\.[0-9]+)*)", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    pytest.skip("No version header found in CHANGELOG.md")


def _extract_notes_from_changelog(changelog_path: Path, version: str) -> str:
    text = changelog_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    notes = []
    capturing = False
    core_version = version.removeprefix("v")
    for line in lines:
        if line.startswith("## "):
            if not capturing and core_version in line:
                capturing = True
                continue
            if capturing:
                break
        if capturing:
            notes.append(line.rstrip())
    return "\n".join(notes).strip()


def test_github_action_test_script_generates_expected_markdown() -> None:
    """Run the release workflow test script and validate output.

    This test executes the local script that mimics the GitHub Action and
    verifies the generated markdown contains the expected version and tag,
    and that a commits section is not present.
    """
    repo_root = Path(__file__).resolve().parents[1]
    changelog = repo_root / "CHANGELOG.md"
    script = repo_root / "tests" / ".github" / "test_github_action.py"
    output = repo_root / "test_github_release_desc.md"

    assert changelog.exists(), "CHANGELOG.md not found in repo root"
    assert script.exists(), (
        "Test script not found at tests/.github/test_github_action.py"
    )

    # Remove previous output if present
    if output.exists():
        output.unlink()

    # Run the test script
    proc = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )

    # Provide helpful debug output on failure
    assert proc.returncode == 0, (
        "Test script failed to run:\n\n"
        f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    )

    assert output.exists(), (
        "Expected output file test_github_release_desc.md not created"
    )

    content = output.read_text(encoding="utf-8")

    # Extract expected version and notes from CHANGELOG.md
    version = _extract_version_from_changelog(changelog)
    notes = _extract_notes_from_changelog(changelog, version)

    # Compute expected tag (workflow prefixes with 'v' when needed)
    expected_tag = version if version.startswith("v") else f"v{version}"

    # Assertions: version and tag must appear in generated markdown
    assert f"**Version:** {version}" in content, (
        "Generated markdown does not contain expected version line.\n"
        f"Looking for '**Version:** {version}'.\n"
        "Full content:\n" + content
    )

    # Tag may be printed in different formats; ensure the tag value is present
    assert expected_tag in content, (
        "Generated markdown does not contain the expected tag string.\n"
        f"Expected tag: {expected_tag}\nFull content:\n{content}"
    )

    # Ensure the file does not contain a commits section header
    assert "### Commits" not in content, (
        "Found '### Commits' in output; commits should be omitted"
    )

    # Ensure the changelog notes are present in the output
    if notes:
        # Match a short snippet to avoid brittle exact formatting checks
        snippet = (
            notes.splitlines()[0].strip()
            if notes.splitlines()
            else notes.strip()
        )
        assert snippet and snippet in content, (
            "Release notes from CHANGELOG.md not found in\n"
            "generated markdown.\n"
            f"Expected snippet: {snippet}\n"
            "Full content:\n"
            f"{content}"
        )
