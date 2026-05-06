"""Integration tests for tag-based upgrade functionality.

Tests cover:
- normalize_version: semver -> PEP 440 conversion
- _is_candidate_newer: version comparison logic
- perform_self_update: uv execvp with tagged git URL
- should_perform_self_update: dev-install and version-check logic
- check_for_self_update: public async entry point
- Error paths: OSError on execvp, uv not found on PATH
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from my_unicorn.cli.upgrade import (
    GITHUB_GIT_URL,
    _is_candidate_newer,
    check_for_self_update,
    normalize_version,
    perform_self_update,
    should_perform_self_update,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_install_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create a minimal temporary directory structure for upgrade tests.

    Args:
        tmp_path: pytest-provided temporary path.

    Returns:
        Dictionary of labelled paths used by upgrade tests.

    """
    package_dir = tmp_path / "my-unicorn"
    venv_bin = package_dir / "venv" / "bin"
    venv_bin.mkdir(parents=True)

    return {
        "repo": tmp_path / "my-unicorn-repo",
        "package": package_dir,
        "venv": venv_bin,
        "tmp_root": tmp_path,
    }


# ---------------------------------------------------------------------------
# normalize_version
# ---------------------------------------------------------------------------


class TestNormalizeVersion:
    """Unit tests for normalize_version."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("v1.2.3", "1.2.3"),
            ("1.2.3", "1.2.3"),
            ("1.0.0-alpha", "1.0.0a0"),
            ("2.0.0-beta1", "2.0.0b1"),
            ("3.0.0-rc2", "3.0.0rc2"),
            ("1.9.2-alpha1", "1.9.2a1"),
            # Label with no trailing number -> num defaults to "0"
            ("1.0.0-rc", "1.0.0rc0"),
        ],
    )
    def test_normalizes_correctly(self, raw: str, expected: str) -> None:
        """normalize_version converts semver prerelease labels to PEP 440.

        Args:
            raw: Input version string.
            expected: Expected PEP 440 output.

        """
        assert normalize_version(raw) == expected

    def test_strips_v_prefix(self) -> None:
        """Leading 'v' is stripped before normalisation."""
        assert normalize_version("v2.3.4") == "2.3.4"

    def test_unknown_format_returned_as_is(self) -> None:
        """Strings that do not match the semver regex are returned unchanged."""
        assert normalize_version("nightly") == "nightly"


# ---------------------------------------------------------------------------
# _is_candidate_newer
# ---------------------------------------------------------------------------


class TestIsCandidateNewer:
    """Unit tests for _is_candidate_newer."""

    def test_newer_patch(self) -> None:
        """Bumping the patch version is detected as newer."""
        assert _is_candidate_newer("1.9.1", "1.9.2") is True

    def test_newer_minor(self) -> None:
        """Bumping the minor version is detected as newer."""
        assert _is_candidate_newer("1.9.2", "2.0.0") is True

    def test_same_version_not_newer(self) -> None:
        """Identical versions are not considered newer."""
        assert _is_candidate_newer("2.0.0", "2.0.0") is False

    def test_older_candidate_not_newer(self) -> None:
        """A lower version is not newer than current."""
        assert _is_candidate_newer("2.0.0", "1.9.9") is False

    def test_prerelease_vs_stable(self) -> None:
        """A stable release is newer than an alpha of the same base version."""
        assert _is_candidate_newer("2.0.0-alpha", "2.0.0") is True

    def test_invalid_current_upgrades_when_candidate_valid(self) -> None:
        """Unparseable current version: upgrade when candidate parses fine."""
        assert _is_candidate_newer("unknown", "1.0.0") is True

    def test_both_invalid_falls_back_to_string_compare(self) -> None:
        """Both versions unparseable: lexicographic fallback is used."""
        assert _is_candidate_newer("a", "z") is True
        assert _is_candidate_newer("z", "a") is False


# ---------------------------------------------------------------------------
# perform_self_update
# ---------------------------------------------------------------------------


class TestPerformSelfUpdate:
    """Integration tests for perform_self_update with tag-based git URL."""

    def _expected_argv(self, version: str) -> list[str]:
        """Build the expected uv argument list for a given version.

        Args:
            version: Raw version string passed to perform_self_update.

        Returns:
            Expected argv list passed to os.execvp.

        """
        tag = version if version.startswith("v") else f"v{version}"
        return [
            "uv",
            "tool",
            "install",
            "--upgrade",
            f"{GITHUB_GIT_URL}@{tag}",
        ]

    @pytest.mark.integration
    def test_execvp_called_with_tagged_url(self) -> None:
        """os.execvp receives the correct tagged git URL.

        A plain version string (no leading 'v') must have 'v' prepended
        before being appended to the git URL.

        """
        version = "2.3.0"
        with (
            patch("my_unicorn.cli.upgrade.os.execvp") as mock_execvp,
            patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
        ):
            mock_execvp.side_effect = SystemExit(0)
            with contextlib.suppress(SystemExit):
                perform_self_update(version)

            mock_execvp.assert_called_once_with(
                "uv", self._expected_argv(version)
            )

    @pytest.mark.integration
    def test_version_with_v_prefix_not_doubled(self) -> None:
        """A version already prefixed with 'v' must not become 'vv<version>'.

        Ensures perform_self_update passes '@v2.3.0', not '@vv2.3.0'.

        """
        version = "v2.3.0"
        with (
            patch("my_unicorn.cli.upgrade.os.execvp") as mock_execvp,
            patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
        ):
            mock_execvp.side_effect = SystemExit(0)
            with contextlib.suppress(SystemExit):
                perform_self_update(version)

            argv: list[str] = mock_execvp.call_args[0][1]
            install_target = argv[-1]
            assert "@vv" not in install_target, (
                "Version prefix was doubled: " + install_target
            )
            assert "@v2.3.0" in install_target

    @pytest.mark.integration
    def test_prerelease_version_tag(self) -> None:
        """Alpha prerelease versions are passed through to the git tag."""
        version = "2.0.0-alpha1"
        with (
            patch("my_unicorn.cli.upgrade.os.execvp") as mock_execvp,
            patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
        ):
            mock_execvp.side_effect = SystemExit(0)
            with contextlib.suppress(SystemExit):
                perform_self_update(version)

            mock_execvp.assert_called_once_with(
                "uv", self._expected_argv(version)
            )

    @pytest.mark.integration
    def test_uv_not_on_path_falls_back_to_bare_uv(self) -> None:
        """When shutil.which returns None, the bare string 'uv' is used.

        perform_self_update should still attempt execvp rather than raising.

        """
        version = "1.9.2"
        with (
            patch("my_unicorn.cli.upgrade.os.execvp") as mock_execvp,
            patch("my_unicorn.cli.upgrade.shutil.which", return_value=None),
        ):
            mock_execvp.side_effect = SystemExit(0)
            with contextlib.suppress(SystemExit):
                perform_self_update(version)

            executable_used: str = mock_execvp.call_args[0][0]
            assert executable_used == "uv"

    @pytest.mark.integration
    def test_oserror_on_execvp_returns_false(self) -> None:
        """An OSError raised by execvp is caught; False is returned."""
        with (
            patch(
                "my_unicorn.cli.upgrade.os.execvp",
                side_effect=OSError("uv not found"),
            ),
            patch("my_unicorn.cli.upgrade.shutil.which", return_value=None),
        ):
            result = perform_self_update("2.0.0")

        assert result is False

    @pytest.mark.integration
    def test_file_not_found_on_execvp_returns_false(self) -> None:
        """A FileNotFoundError raised by execvp is caught; False is returned."""
        with (
            patch(
                "my_unicorn.cli.upgrade.os.execvp",
                side_effect=FileNotFoundError("uv missing"),
            ),
            patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
        ):
            result = perform_self_update("2.0.0")

        assert result is False


# ---------------------------------------------------------------------------
# should_perform_self_update
# ---------------------------------------------------------------------------


class TestShouldPerformSelfUpdate:
    """Tests for the async version-check orchestration logic."""

    @pytest.mark.asyncio
    async def test_dev_install_always_upgrades(self) -> None:
        """A dev (file://) installation always triggers an upgrade.

        Even if version numbers match, a dev install must be replaced
        with the tagged production release.

        """
        with (
            patch(
                "my_unicorn.cli.upgrade._run_uv_tool_list",
                new_callable=AsyncMock,
                return_value=True,  # file:// URI -> dev install
            ),
            patch(
                "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
                new_callable=AsyncMock,
                return_value="2.0.0",
            ),
        ):
            should_upgrade, latest = await should_perform_self_update("1.9.9")

        assert should_upgrade is True
        assert latest == "2.0.0"

    @pytest.mark.asyncio
    async def test_newer_version_triggers_upgrade(self) -> None:
        """A newer available version returns should_upgrade=True."""
        with (
            patch(
                "my_unicorn.cli.upgrade._run_uv_tool_list",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
                new_callable=AsyncMock,
                return_value="2.0.1",
            ),
        ):
            should_upgrade, latest = await should_perform_self_update("2.0.0")

        assert should_upgrade is True
        assert latest == "2.0.1"

    @pytest.mark.asyncio
    async def test_same_version_no_upgrade(self) -> None:
        """Already at the latest version: should_upgrade is False."""
        with (
            patch(
                "my_unicorn.cli.upgrade._run_uv_tool_list",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
                new_callable=AsyncMock,
                return_value="2.0.0",
            ),
        ):
            should_upgrade, latest = await should_perform_self_update("2.0.0")

        assert should_upgrade is False
        assert latest == "2.0.0"

    @pytest.mark.asyncio
    async def test_older_latest_means_no_upgrade(self) -> None:
        """If latest < current (e.g. after a rollback), no upgrade occurs."""
        with (
            patch(
                "my_unicorn.cli.upgrade._run_uv_tool_list",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
                new_callable=AsyncMock,
                return_value="1.0.0",
            ),
        ):
            should_upgrade, _ = await should_perform_self_update("2.0.0")

        assert should_upgrade is False

    @pytest.mark.asyncio
    async def test_fetch_returns_none_yields_none(self) -> None:
        """When _fetch_latest_prerelease_version returns None, (None, None)."""
        with (
            patch(
                "my_unicorn.cli.upgrade._run_uv_tool_list",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            should_upgrade, latest = await should_perform_self_update("2.0.0")

        assert should_upgrade is None
        assert latest is None

    @pytest.mark.asyncio
    async def test_empty_version_string_treated_as_failure(self) -> None:
        """An empty string from the API must not trigger a blind upgrade."""
        with (
            patch(
                "my_unicorn.cli.upgrade._run_uv_tool_list",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
                new_callable=AsyncMock,
                return_value="",
            ),
        ):
            should_upgrade, _ = await should_perform_self_update("2.0.0")

        assert should_upgrade is None


# ---------------------------------------------------------------------------
# check_for_self_update
# ---------------------------------------------------------------------------


class TestCheckForSelfUpdate:
    """Tests for the public check_for_self_update entry point."""

    @pytest.mark.asyncio
    async def test_delegates_using_package_version(self) -> None:
        """check_for_self_update passes the package __version__ as current."""
        with patch(
            "my_unicorn.cli.upgrade.should_perform_self_update",
            new_callable=AsyncMock,
            return_value=(True, "3.0.0"),
        ) as mock_check:
            result = await check_for_self_update()

        assert result == (True, "3.0.0")
        mock_check.assert_awaited_once()

        # The argument must be the live __version__ string, not hardcoded.
        called_version: str = mock_check.call_args[0][0]
        assert isinstance(called_version, str)
        assert called_version, "Expected a non-empty __version__ string"

    @pytest.mark.asyncio
    async def test_returns_false_when_up_to_date(self) -> None:
        """Returns (False, version) when already on the latest version."""
        with patch(
            "my_unicorn.cli.upgrade.should_perform_self_update",
            new_callable=AsyncMock,
            return_value=(False, "2.0.0"),
        ):
            should_upgrade, latest = await check_for_self_update()

        assert should_upgrade is False
        assert latest == "2.0.0"

    @pytest.mark.asyncio
    async def test_propagates_none_on_fetch_failure(self) -> None:
        """Propagates (None, None) transparently when the check itself fails."""
        with patch(
            "my_unicorn.cli.upgrade.should_perform_self_update",
            new_callable=AsyncMock,
            return_value=(None, None),
        ):
            should_upgrade, latest = await check_for_self_update()

        assert should_upgrade is None
        assert latest is None
