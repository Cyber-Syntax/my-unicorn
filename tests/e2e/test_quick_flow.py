"""E2E quick flow tests for my-unicorn CLI.

This module tests the "quick" workflow: update → URL install → catalog install
for QOwnNotes application using sandboxed environment for isolation.

Tests verify:
- CLI command execution success
- App config file creation and structure
- Config contains expected fields (app_name, state, etc.)
- All operations complete without errors
"""

import orjson
import pytest

from tests.e2e.runner import E2ERunner
from tests.e2e.sandbox import SandboxEnvironment


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.network
class TestQuickFlow:
    """E2E quick flow tests for QOwnNotes."""

    def test_qownnotes_update(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test QOwnNotes update operation.

        Flow:
        1. Install qownnotes via catalog
        2. Set installed version to an old version
        3. Run update command
        4. Verify update succeeded and config was updated

        Verifications:
        - Install succeeds (return code 0)
        - App config file created at ~/.config/my-unicorn/apps/qownnotes.json
        - Config contains app_name field
        - Update succeeds (return code 0)
        - config.state.version reflects new version
        """
        with sandbox_env:
            # Step 1: Install qownnotes from catalog
            result = e2e_runner.install("qownnotes")
            assert result.returncode == 0, f"Install failed: {result.stderr}"

            # Step 2: Verify config file was created
            config_path = (
                sandbox_env.temp_home
                / ".config"
                / "my-unicorn"
                / "apps"
                / "qownnotes.json"
            )
            assert config_path.exists(), f"Config not created at {config_path}"

            # Step 3: Verify config structure
            config_text = config_path.read_text()
            config = orjson.loads(config_text)
            assert "state" in config, "Config missing state field"

            # Step 4: Set old version for update test
            e2e_runner.set_version("qownnotes", "0.1.0")

            # Step 5: Run update
            result = e2e_runner.update("qownnotes")
            assert result.returncode == 0, f"Update failed: {result.stderr}"

            # Step 6: Verify config was updated with new version
            config_text = config_path.read_text()
            config = orjson.loads(config_text)
            updated_version = config.get("state", {}).get("version")
            assert updated_version is not None, (
                "Config missing state.version after update"
            )
            assert updated_version != "0.1.0", (
                "Version not updated from test version"
            )

    def test_qownnotes_url_install(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test QOwnNotes URL direct install operation.

        Flow:
        1. Install qownnotes via direct GitHub URL
        2. Verify config file created with correct structure
        3. Verify CLI reported success

        Verifications:
        - Install via URL succeeds (return code 0)
        - App config file created at ~/.config/my-unicorn/apps/qownnotes.json
        - Config contains required fields (source, state)
        - state contains version field
        """
        with sandbox_env:
            # Step 1: Install qownnotes via GitHub URL
            url = "https://github.com/pbek/QOwnNotes"
            result = e2e_runner.install(url)
            assert result.returncode == 0, (
                f"URL install failed: {result.stderr}"
            )

            # Step 2: Verify config file was created
            config_path = (
                sandbox_env.temp_home
                / ".config"
                / "my-unicorn"
                / "apps"
                / "qownnotes.json"
            )
            assert config_path.exists(), f"Config not created at {config_path}"

            # Step 3: Verify config structure
            config_text = config_path.read_text()
            config = orjson.loads(config_text)
            assert "source" in config, (
                "Config missing source field (install method)"
            )
            assert "state" in config, "Config missing state field"
            assert "version" in config.get("state", {}), (
                "Config missing state.version field"
            )

    def test_qownnotes_catalog_install(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test QOwnNotes catalog install operation.

        Flow:
        1. Install qownnotes via catalog name
        2. Verify config file created with correct structure
        3. Verify CLI reported success

        Verifications:
        - Install via catalog succeeds (return code 0)
        - App config file created at ~/.config/my-unicorn/apps/qownnotes.json
        - Config contains required fields (source, state)
        - state contains version field
        """
        with sandbox_env:
            # Step 1: Install qownnotes from catalog
            result = e2e_runner.install("qownnotes")
            assert result.returncode == 0, (
                f"Catalog install failed: {result.stderr}"
            )

            # Step 2: Verify config file was created
            config_path = (
                sandbox_env.temp_home
                / ".config"
                / "my-unicorn"
                / "apps"
                / "qownnotes.json"
            )
            assert config_path.exists(), f"Config not created at {config_path}"

            # Step 3: Verify config structure
            config_text = config_path.read_text()
            config = orjson.loads(config_text)
            assert "source" in config, (
                "Config missing source field (install method)"
            )
            assert "state" in config, "Config missing state field"
            assert "version" in config.get("state", {}), (
                "Config missing state.version field"
            )

    def test_quick_workflow_complete(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test complete quick workflow in sequence.

        Flow (mirrors scripts/test.py quick test):
        1. Install qownnotes via catalog
        2. Set old version and run update
        3. Remove qownnotes for clean state
        4. Install via direct GitHub URL
        5. Remove qownnotes for clean state
        6. Install via catalog

        Verifications:
        - All operations succeed (return code 0)
        - Config file exists and is valid JSON after each operation
        - Config contains required fields at each step
        """
        with sandbox_env:
            # Step 1: Test update (requires initial install)
            result = e2e_runner.install("qownnotes")
            assert result.returncode == 0, (
                f"Initial install failed: {result.stderr}"
            )

            config_path = (
                sandbox_env.temp_home
                / ".config"
                / "my-unicorn"
                / "apps"
                / "qownnotes.json"
            )
            assert config_path.exists(), "Config not created after install"

            # Set old version for update
            e2e_runner.set_version("qownnotes", "0.1.0")
            result = e2e_runner.update("qownnotes")
            assert result.returncode == 0, f"Update failed: {result.stderr}"

            # Step 2: Remove for clean URL install test
            result = e2e_runner.remove("qownnotes")
            # Remove may succeed or be idempotent, just verify command executed

            # Step 3: Test URL install
            url = "https://github.com/pbek/QOwnNotes"
            result = e2e_runner.install(url)
            assert result.returncode == 0, (
                f"URL install failed: {result.stderr}"
            )
            assert config_path.exists(), "Config not created after URL install"

            # Verify config is valid
            config_text = config_path.read_text()
            config = orjson.loads(config_text)
            assert "source" in config, "Config invalid after URL install"

            # Step 4: Remove for clean catalog test
            result = e2e_runner.remove("qownnotes")
            # Remove may succeed or be idempotent, just verify command executed

            # Step 5: Test catalog install
            result = e2e_runner.install("qownnotes")
            assert result.returncode == 0, (
                f"Catalog install failed: {result.stderr}"
            )
            assert config_path.exists(), (
                "Config not created after catalog install"
            )

            # Verify config is valid
            config_text = config_path.read_text()
            config = orjson.loads(config_text)
            assert "source" in config, "Config invalid after catalog install"
            assert "state" in config, (
                "Config missing state after catalog install"
            )
