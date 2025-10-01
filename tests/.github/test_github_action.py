#!/usr/bin/env python3
"""Test script for GitHub Actions workflow that creates releases from CHANGELOG.md.

This script simulates the bash logic from the workflow to test it locally.
It validates the workflow behavior by extracting version information,
commit messages, and generating release notes.

Example:
    python test_github_action_refactored.py

Environment Variables:
    GITHUB_TOKEN: Optional GitHub API token for username resolution

"""

# Standard library imports
import os
import re
import subprocess
from pathlib import Path
from typing import Any

# Third-party imports
import requests

# Constants
HTTP_OK: int = 200
HTTP_NOT_FOUND: int = 404
PREVIEW_LENGTH: int = 200
EXPECTED_PARTS: int = 3
API_TIMEOUT: int = 10
DEFAULT_VERSION: str = "v1.0.0"
DEFAULT_FALLBACK_VERSION: str = "v0.0.0"
DEFAULT_NOTES: str = "Initial release"
DEFAULT_REPO: str = "test/repo"
FILE_ENCODING: str = "utf-8"
MAX_SEARCH_ITEMS: int = 1


class GitHubActionTester:
    """Test class for GitHub Actions release workflow."""

    def __init__(self, github_token: str | None = None) -> None:
        """Initialize the tester with GitHub token.

        Args:
            github_token: GitHub API token for username resolution, or None to use environment.

        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.repo = self._get_repo_name()
        self.changelog_path = Path("CHANGELOG.md")

    def _get_repo_name(self) -> str:
        """Extract repository name from git remote.

        Returns:
            Repository name in format 'owner/repo' or default fallback.

        """
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
                timeout=API_TIMEOUT,
            )
            url = result.stdout.strip()
            # Extract owner/repo from GitHub URL
            match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
            if match:
                return match.group(1)
            return DEFAULT_REPO
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return DEFAULT_REPO

    def _read_changelog(self) -> str:
        """Read changelog content from file.

        Returns:
            Changelog content or empty string if file not found.

        """
        try:
            return self.changelog_path.read_text(encoding=FILE_ENCODING)
        except FileNotFoundError:
            return ""
        except OSError:
            return ""

    def _extract_version_from_changelog(self) -> str:
        """Extract the first version number from CHANGELOG.md.

        Returns:
            First version found or default version.

        """
        content = self._read_changelog()
        if not content:
            return DEFAULT_VERSION

        # Find first version header
        match = re.search(
            r"^## (v[0-9.]*[0-9](?:-[a-zA-Z0-9]*)*)", content, re.MULTILINE
        )
        if match:
            version = match.group(1)
            return version

        return DEFAULT_FALLBACK_VERSION

    def _extract_notes_from_changelog(self, version: str) -> str:
        """Extract notes for a specific version from CHANGELOG.md.

        Args:
            version: Version string to extract notes for.

        Returns:
            Notes content for the version or default notes.

        """
        content = self._read_changelog()
        if not content:
            return DEFAULT_NOTES

        lines = content.splitlines()
        notes = []
        capturing = False

        for line in lines:
            if line.startswith(f"## {version}"):
                capturing = True
                continue
            elif line.startswith("## v") and capturing:
                break
            elif capturing:
                notes.append(line.rstrip())

        result = "\n".join(notes).strip()
        return result if result else DEFAULT_NOTES

    def _get_previous_tag(self) -> str:
        """Get the previous git tag.

        Returns:
            Previous git tag or empty string if none found.

        """
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0", "--match", "v*"],
                capture_output=True,
                text=True,
                check=True,
                timeout=API_TIMEOUT,
            )
            tag = result.stdout.strip()
            return tag
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""

    def _extract_username_from_noreply_email(self, email: str) -> str | None:
        """Extract username from GitHub noreply email pattern.

        Args:
            email: Email address to check.

        Returns:
            Username if pattern matches, None otherwise.

        """
        noreply_match = re.match(
            r"(?:[0-9]+\+)?([^@]+)@users\.noreply\.github\.com", email
        )
        return noreply_match.group(1) if noreply_match else None

    def _get_user_from_commit_api(self, commit_hash: str) -> str | None:
        """Get username from GitHub commit API.

        Args:
            commit_hash: Git commit hash.

        Returns:
            GitHub username if found, None otherwise.

        """
        if not self.github_token:
            return None

        try:
            headers = {"Authorization": f"token {self.github_token}"}
            url = f"https://api.github.com/repos/{self.repo}/commits/{commit_hash}"
            response = requests.get(url, headers=headers, timeout=API_TIMEOUT)

            if response.status_code == HTTP_OK:
                data = response.json()
                author = data.get("author")
                if author and author.get("login"):
                    return author["login"]
        except requests.RequestException:
            pass

        return None

    def _search_user_by_email(self, email: str) -> str | None:
        """Search for GitHub user by email address.

        Args:
            email: Email address to search for.

        Returns:
            GitHub username if found, None otherwise.

        """
        if not self.github_token:
            return None

        try:
            headers = {"Authorization": f"token {self.github_token}"}
            url = f"https://api.github.com/search/users?q={email}+in:email"
            response = requests.get(url, headers=headers, timeout=API_TIMEOUT)

            if response.status_code == HTTP_OK:
                data = response.json()
                items = data.get("items", [])
                if items and len(items) >= MAX_SEARCH_ITEMS:
                    return items[0]["login"]
        except requests.RequestException:
            pass

        return None

    def _get_github_username(self, email: str, commit_hash: str) -> str:
        """Get GitHub username from email, mimicking the bash function.

        Args:
            email: Email address to resolve.
            commit_hash: Git commit hash for API lookup.

        Returns:
            GitHub username or email prefix as fallback.

        """
        # Try GitHub noreply email pattern first
        username = self._extract_username_from_noreply_email(email)
        if username:
            return username

        # Try GitHub API if token is available
        if self.github_token:
            # Try to get user from commit
            username = self._get_user_from_commit_api(commit_hash)
            if username:
                return username

            # Try to search user by email
            username = self._search_user_by_email(email)
            if username:
                return username

        # Fallback: use part before @
        return email.split("@")[0]

    def _get_commits_with_usernames(
        self, previous_tag: str
    ) -> dict[str, list[str]]:
        """Get commits with GitHub usernames, categorized by type.

        Args:
            previous_tag: Previous git tag for range calculation.

        Returns:
            Dictionary with categorized commit lists.

        """
        # Determine git log range
        git_range = f"{previous_tag}..HEAD" if previous_tag else ""

        # Get commit data with --no-merges to avoid duplicates
        cmd = ["git", "log", "--pretty=format:%H|%ae|%s", "--no-merges"]
        if git_range:
            cmd.append(git_range)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=API_TIMEOUT,
            )
            commit_lines = result.stdout.strip().split("\n")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return {"features": [], "bugfixes": [], "other": []}

        # Initialize categorized lists
        features = []
        bugfixes = []
        other_commits = []

        # Pattern for conventional commits
        conventional_pattern = re.compile(
            r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?:"
        )

        for line in commit_lines:
            if not line.strip():
                continue

            parts = line.split("|", 2)
            if len(parts) == EXPECTED_PARTS:
                commit_hash, email, subject = parts

                # Only process conventional commits
                if not conventional_pattern.match(subject):
                    continue

                username = self._get_github_username(email, commit_hash)

                # Get full commit message to check for PR references
                try:
                    pr_result = subprocess.run(
                        ["git", "show", "-s", "--format=%B", commit_hash],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=API_TIMEOUT,
                    )
                    full_message = pr_result.stdout.strip()

                    # Check for PR reference
                    pr_match = re.search(r"#(\d+)", full_message)
                    pr_num = f" (#{pr_match.group(1)})" if pr_match else ""

                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                ):
                    pr_num = ""

                formatted_commit = f"  - {subject}{pr_num} (@{username})"

                # Categorize based on conventional commit type
                if re.match(r"^feat(\(.+\))?:", subject):
                    features.append(formatted_commit)
                elif re.match(r"^fix(\(.+\))?:", subject):
                    bugfixes.append(formatted_commit)
                else:
                    other_commits.append(formatted_commit)

        return {
            "features": features,
            "bugfixes": bugfixes,
            "other": other_commits,
        }

    def _create_release_notes(self) -> tuple[str, str]:
        """Create full release notes combining CHANGELOG and commits.

        Returns:
            tuple of (version, full_notes).

        """
        version = self._extract_version_from_changelog()
        changelog_notes = self._extract_notes_from_changelog(version)
        previous_tag = self._get_previous_tag()
        commits_dict = self._get_commits_with_usernames(previous_tag)

        # Build categorized commits section
        commits_section = ""
        if commits_dict["features"]:
            commits_section += (
                "#### 🚀 Features\n"
                + "\n".join(commits_dict["features"])
                + "\n\n"
            )
        if commits_dict["bugfixes"]:
            commits_section += (
                "#### 🐛 Bug Fixes\n"
                + "\n".join(commits_dict["bugfixes"])
                + "\n\n"
            )
        if commits_dict["other"]:
            commits_section += (
                "#### 📝 Other Commits\n"
                + "\n".join(commits_dict["other"])
                + "\n\n"
            )

        # Combine notes
        full_notes = changelog_notes
        if commits_section:
            full_notes += "\n\n### Commits\n" + commits_section.rstrip()

        return version, full_notes

    def test_workflow(self) -> dict[str, Any]:
        """Test the complete workflow logic.

        Returns:
            Dictionary containing test results.

        """
        # Test version extraction
        version = self._extract_version_from_changelog()

        # Test changelog notes extraction
        changelog_notes = self._extract_notes_from_changelog(version)

        # Test previous tag
        previous_tag = self._get_previous_tag()

        # Test commit extraction
        commits_dict = self._get_commits_with_usernames(previous_tag)

        # Test full release notes
        version, full_notes = self._create_release_notes()

        return {
            "version": version,
            "previous_tag": previous_tag,
            "changelog_notes": changelog_notes,
            "commits": commits_dict,
            "full_notes": full_notes,
        }


def _write_test_results_to_file(
    results: dict[str, Any], output_path: Path
) -> None:
    """Write test results to markdown file.

    Args:
        results: Test results dictionary.
        output_path: Path to output markdown file.

    """
    try:
        with output_path.open("w", encoding=FILE_ENCODING) as f:
            f.write("# Release Test Output\n\n")
            f.write(f"**Version:** {results['version']}\n\n")
            previous_tag = results["previous_tag"] or "None"
            f.write(f"**Previous Tag:** {previous_tag}\n\n")
            f.write("## Release Notes\n\n")
            f.write(f"{results['full_notes']}\n")
    except OSError:
        pass


def _display_results_summary(results: dict[str, Any]) -> None:
    """Display a summary of test results.

    Args:
        results: Test results dictionary.

    """
    print("Test completed successfully!")
    print(f"Version: {results['version']}")

    commits = results["commits"]
    total_commits = (
        len(commits["features"])
        + len(commits["bugfixes"])
        + len(commits["other"])
    )
    print(
        f"Commits found: {total_commits} "
        f"(Features: {len(commits['features'])}, "
        f"Bug Fixes: {len(commits['bugfixes'])}, "
        f"Other: {len(commits['other'])})"
    )

    # Show preview
    print("Release Notes Preview:")
    print("-" * 30)
    preview = results["full_notes"][:PREVIEW_LENGTH]
    if len(results["full_notes"]) > PREVIEW_LENGTH:
        preview += "..."
    print(preview)


def main() -> None:
    """Run the GitHub Actions workflow test."""
    print("🚀 GitHub Actions Release Workflow Tester")
    print("=" * 50)

    # Initialize tester
    tester = GitHubActionTester()

    # Run tests
    try:
        results = tester.test_workflow()

        # Write results to test file
        output_path = Path("test_github_release_desc.md")
        _write_test_results_to_file(results, output_path)

        # Display summary
        _display_results_summary(results)

    except Exception as e:
        print(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    main()
