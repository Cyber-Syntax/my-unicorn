"""E2E full flow tests for my-unicorn CLI.

This module tests the "full" workflow combining:
- URL installs (neovim, keepassxc)
- Catalog installs (legcord, flameshot, appflowy, standard-notes)
- Updates for all apps

Tests verify:
- CLI command execution success
- App config file creation and structure
- Config contains expected fields (app_name, state, etc.)
- All operations complete without errors in sequence
"""

import orjson
import pytest

from tests.e2e.runner import E2ERunner
from tests.e2e.sandbox import SandboxEnvironment


@pytest.mark.slow
@pytest.mark.network
class TestFullFlow:
    """E2E full flow tests for comprehensive CLI operations."""

    def test_url_installs_neovim_keepassxc(self) -> None:
        """Test neovim and keepassxc URL direct installs.

        Flow:
        1. Install neovim via direct GitHub URL
        2. Install keepassxc via direct GitHub URL
        3. Verify both config files created

        Verifications:
        - Install via URL succeeds (return code 0)
        - Both app config files created
        - Configs contain required fields (source, state)
        - state contains version field
        """
        with SandboxEnvironment(
            name="test_url_installs_neovim_keepassxc"
        ) as sandbox:
            runner = E2ERunner(sandbox)

            # Step 1: Install neovim via GitHub URL
            result = runner.install("https://github.com/neovim/neovim")
            assert result.returncode == 0, (
                f"Neovim URL install failed: {result.stderr}"
            )

            # Step 2: Verify neovim config created
            neovim_config_path = (
                sandbox.temp_home
                / ".config"
                / "my-unicorn"
                / "apps"
                / "neovim.json"
            )
            assert neovim_config_path.exists(), (
                f"Neovim config not created at {neovim_config_path}"
            )

            # Step 3: Verify neovim config structure
            neovim_config_text = neovim_config_path.read_text()
            neovim_config = orjson.loads(neovim_config_text)
            assert "source" in neovim_config, (
                "Neovim config missing source field"
            )
            assert "state" in neovim_config, (
                "Neovim config missing state field"
            )
            assert "version" in neovim_config.get("state", {}), (
                "Neovim config missing state.version field"
            )

            # Step 4: Install keepassxc via GitHub URL
            result = runner.install(
                "https://github.com/keepassxreboot/keepassxc"
            )
            assert result.returncode == 0, (
                f"KeePassXC URL install failed: {result.stderr}"
            )

            # Step 5: Verify keepassxc config created
            keepassxc_config_path = (
                sandbox.temp_home
                / ".config"
                / "my-unicorn"
                / "apps"
                / "keepassxc.json"
            )
            assert keepassxc_config_path.exists(), (
                f"KeePassXC config not created at {keepassxc_config_path}"
            )

            # Step 6: Verify keepassxc config structure
            keepassxc_config_text = keepassxc_config_path.read_text()
            keepassxc_config = orjson.loads(keepassxc_config_text)
            assert "source" in keepassxc_config, (
                "KeePassXC config missing source field"
            )
            assert "state" in keepassxc_config, (
                "KeePassXC config missing state field"
            )
            assert "version" in keepassxc_config.get("state", {}), (
                "KeePassXC config missing state.version field"
            )

    def test_catalog_installs_multiple_apps(self) -> None:
        """Test catalog installs for multiple apps.

        Flow:
        1. Install legcord from catalog
        2. Install flameshot from catalog
        3. Install appflowy from catalog
        4. Install standard-notes from catalog
        5. Verify all config files created

        Verifications:
        - Each install succeeds (return code 0)
        - All app config files created
        - Configs contain required fields (source, state)
        - state contains version field
        """
        with SandboxEnvironment(
            name="test_catalog_installs_multiple_apps"
        ) as sandbox:
            runner = E2ERunner(sandbox)

            app_names = ["legcord", "flameshot", "appflowy", "standard-notes"]

            # Step 1: Install multiple apps from catalog
            result = runner.install(*app_names)
            assert result.returncode == 0, (
                f"Catalog install failed: {result.stderr}"
            )

            # Step 2: Verify all config files were created
            for app_name in app_names:
                config_path = (
                    sandbox.temp_home
                    / ".config"
                    / "my-unicorn"
                    / "apps"
                    / f"{app_name}.json"
                )
                assert config_path.exists(), (
                    f"{app_name} config not created at {config_path}"
                )

                # Step 3: Verify each config structure
                config_text = config_path.read_text()
                config = orjson.loads(config_text)
                assert "source" in config, (
                    f"{app_name} config missing source field"
                )
                assert "state" in config, (
                    f"{app_name} config missing state field"
                )
                assert "version" in config.get("state", {}), (
                    f"{app_name} config missing state.version field"
                )

    def test_updates_multiple_apps(self) -> None:
        """Test updating multiple installed apps.

        Flow:
        1. Install multiple apps
        2. Set old version for each app
        3. Run update command for each app
        4. Verify versions changed from test version

        Verifications:
        - Install succeeds (return code 0)
        - Update succeeds (return code 0)
        - Version changed from test version (0.1.0)
        """
        with SandboxEnvironment(name="test_updates_multiple_apps") as sandbox:
            runner = E2ERunner(sandbox)

            app_names = ["legcord", "flameshot", "appflowy", "standard-notes"]

            # Step 1: Install multiple apps
            result = runner.install(*app_names)
            assert result.returncode == 0, f"Install failed: {result.stderr}"

            # Step 2: Set old version for each app
            for app_name in app_names:
                runner.set_version(app_name, "0.1.0")

            # Step 3: Run update
            result = runner.update(*app_names)
            assert result.returncode == 0, f"Update failed: {result.stderr}"

            # Step 4: Verify versions changed
            for app_name in app_names:
                config_path = (
                    sandbox.temp_home
                    / ".config"
                    / "my-unicorn"
                    / "apps"
                    / f"{app_name}.json"
                )
                assert config_path.exists(), (
                    f"{app_name} config missing after update"
                )

                config_text = config_path.read_text()
                config = orjson.loads(config_text)
                updated_version = config.get("state", {}).get("version")
                assert updated_version is not None, (
                    f"{app_name} missing state.version after update"
                )
                assert updated_version != "0.1.0", (
                    f"{app_name} version not updated from test version"
                )

    def test_full_workflow_complete(self) -> None:
        """Test complete full workflow in sequence.

        Flow (mirrors scripts/test.py all test):
        1. Install neovim and keepassxc via GitHub URLs
        2. Install legcord, flameshot, appflowy, standard-notes via catalog
        3. Set old versions for all apps
        4. Run updates for all apps
        5. Verify all apps configured properly

        Verifications:
        - All operations succeed (return code 0)
        - Config files exist and are valid JSON
        - All configs contain required fields
        - Versions updated from test version
        """
        with SandboxEnvironment(name="test_full_workflow_complete") as sandbox:
            runner = E2ERunner(sandbox)

            # Phase 1: URL installs
            result = runner.install(
                "https://github.com/neovim/neovim",
                "https://github.com/keepassxreboot/keepassxc",
            )
            assert result.returncode == 0, (
                f"URL installs failed: {result.stderr}"
            )

            # Verify URL installs
            for app_name in ["neovim", "keepassxc"]:
                config_path = (
                    sandbox.temp_home
                    / ".config"
                    / "my-unicorn"
                    / "apps"
                    / f"{app_name}.json"
                )
                assert config_path.exists(), (
                    f"{app_name} config not created after URL install"
                )
                config_text = config_path.read_text()
                config = orjson.loads(config_text)
                assert "source" in config, (
                    f"{app_name} config missing source field"
                )

            # Phase 2: Catalog installs
            catalog_apps = [
                "legcord",
                "flameshot",
                "appflowy",
                "standard-notes",
            ]
            result = runner.install(*catalog_apps)
            assert result.returncode == 0, (
                f"Catalog installs failed: {result.stderr}"
            )

            # Verify catalog installs
            for app_name in catalog_apps:
                config_path = (
                    sandbox.temp_home
                    / ".config"
                    / "my-unicorn"
                    / "apps"
                    / f"{app_name}.json"
                )
                assert config_path.exists(), (
                    f"{app_name} config not created after catalog install"
                )
                config_text = config_path.read_text()
                config = orjson.loads(config_text)
                assert "state" in config, (
                    f"{app_name} config missing state field"
                )

            # Phase 3: Set old versions and update
            all_apps = [
                "legcord",
                "flameshot",
                "keepassxc",
                "appflowy",
                "standard-notes",
            ]
            for app_name in all_apps:
                runner.set_version(app_name, "0.1.0")

            result = runner.update(*all_apps)
            assert result.returncode == 0, f"Updates failed: {result.stderr}"

            # Phase 4: Verify all versions updated
            for app_name in all_apps:
                config_path = (
                    sandbox.temp_home
                    / ".config"
                    / "my-unicorn"
                    / "apps"
                    / f"{app_name}.json"
                )
                assert config_path.exists(), (
                    f"{app_name} config missing after update"
                )
                config_text = config_path.read_text()
                config = orjson.loads(config_text)
                updated_version = config.get("state", {}).get("version")
                assert updated_version is not None, (
                    f"{app_name} missing state.version after update"
                )
                assert updated_version != "0.1.0", (
                    f"{app_name} version not updated from test version"
                )
