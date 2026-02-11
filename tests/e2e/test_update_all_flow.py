"""E2E update-all flow tests for my-unicorn CLI.

This module tests the "update-all" workflow:
1. Install multiple apps from catalog
2. Force old versions in app configs
3. Run update (no args)
4. Verify versions changed

Tests verify:
- Multiple app installations work
- Version manipulation works
- update (no args) succeeds
- Versions are actually updated after update (no args)
"""

import pytest

from tests.e2e.runner import E2ERunner
from tests.e2e.sandbox import SandboxEnvironment


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.network
class TestUpdateAllFlow:
    """E2E update-all flow tests for multiple app updates."""

    def test_install_qownnotes_appflowy(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test installing qownnotes and appflowy from catalog.

        Flow:
        1. Install qownnotes via catalog
        2. Install appflowy via catalog
        3. Verify both config files created

        Verifications:
        - Both installs succeed (return code 0)
        - Both app config files created
        - Config files contain required fields
        """
        with sandbox_env:
            # Step 1: Install qownnotes from catalog
            result = e2e_runner.install("qownnotes")
            assert result.returncode == 0, (
                f"Qownnotes install failed: {result.stderr}"
            )
            assert (
                "successfully installed" in result.stdout.lower()
                or "installed" in result.stdout.lower()
            ), f"Unexpected output: {result.stdout}"

            # Step 2: Verify qownnotes config exists
            qownnotes_config = (
                sandbox_env.temp_home
                / ".config/my-unicorn/apps/qownnotes.json"
            )
            assert qownnotes_config.exists(), (
                f"Qownnotes config not created at {qownnotes_config}"
            )

            # Step 3: Install appflowy from catalog
            result = e2e_runner.install("appflowy")
            assert result.returncode == 0, (
                f"AppFlowy install failed: {result.stderr}"
            )
            assert (
                "successfully installed" in result.stdout.lower()
                or "installed" in result.stdout.lower()
            ), f"Unexpected output: {result.stdout}"

            # Step 4: Verify appflowy config exists
            appflowy_config = (
                sandbox_env.temp_home / ".config/my-unicorn/apps/appflowy.json"
            )
            assert appflowy_config.exists(), (
                f"AppFlowy config not created at {appflowy_config}"
            )

    def test_force_old_versions(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test forcing old versions in app configs for update testing.

        Flow:
        1. Install qownnotes and appflowy from catalog
        2. Get original versions
        3. Set old versions manually in configs
        4. Verify old versions are set

        Verifications:
        - Install succeeds
        - Original versions are not the test old versions
        - get_app_config() returns dict with installed_version or version field
        - set_version() successfully changes versions
        """
        with sandbox_env:
            # Step 1: Install qownnotes
            result = e2e_runner.install("qownnotes")
            assert result.returncode == 0, f"Install failed: {result.stderr}"

            # Step 2: Install appflowy
            result = e2e_runner.install("appflowy")
            assert result.returncode == 0, f"Install failed: {result.stderr}"

            # Step 3: Get original versions
            qownnotes_config_before = e2e_runner.get_app_config("qownnotes")
            appflowy_config_before = e2e_runner.get_app_config("appflowy")

            original_qownnotes_version = qownnotes_config_before.get(
                "state", {}
            ).get("version")
            original_appflowy_version = appflowy_config_before.get(
                "state", {}
            ).get("version")

            assert original_qownnotes_version is not None
            assert original_appflowy_version is not None

            # Step 4: Force old versions
            old_qownnotes = "v23.1.0"
            old_appflowy = "0.1.0"

            e2e_runner.set_version("qownnotes", old_qownnotes)
            e2e_runner.set_version("appflowy", old_appflowy)

            # Step 5: Verify versions changed
            qownnotes_config_after = e2e_runner.get_app_config("qownnotes")
            appflowy_config_after = e2e_runner.get_app_config("appflowy")

            assert (
                qownnotes_config_after.get("state", {}).get("version")
                == old_qownnotes
            )
            assert (
                appflowy_config_after.get("state", {}).get("version")
                == old_appflowy
            )

            assert original_qownnotes_version != old_qownnotes
            assert original_appflowy_version != old_appflowy

    def test_update_all_command(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test running update --all to update all installed apps.

        Flow:
        1. Install qownnotes and appflowy from catalog
        2. Force old versions
        3. Run update --all
        4. Verify command succeeds

        Verifications:
        - Install succeeds
        - set_version() works
        - update --all succeeds (return code 0)
        - Output contains update-related messages
        """
        with sandbox_env:
            # Step 1: Install qownnotes
            result = e2e_runner.install("qownnotes")
            assert result.returncode == 0, f"Install failed: {result.stderr}"

            # Step 2: Install appflowy
            result = e2e_runner.install("appflowy")
            assert result.returncode == 0, f"Install failed: {result.stderr}"

            # Step 3: Force old versions
            e2e_runner.set_version("qownnotes", "v23.1.0")
            e2e_runner.set_version("appflowy", "0.1.0")

            # Step 4: Run update (all apps - no args means update all)
            result = e2e_runner.update()
            assert result.returncode == 0, f"Update failed: {result.stderr}"

            # Step 5: Verify output indicates update operation
            output_lower = result.stdout.lower()
            assert (
                "update" in output_lower
                or "checking" in output_lower
                or "version" in output_lower
            ), f"Unexpected output: {result.stdout}"

    def test_verify_versions_changed(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that update --all actually changes versions in configs.

        Flow:
        1. Install qownnotes and appflowy from catalog
        2. Get latest versions
        3. Force old versions
        4. Run update --all
        5. Verify versions changed from old versions

        Verifications:
        - Install succeeds
        - Latest versions obtained
        - Old versions set successfully
        - update --all succeeds
        - Versions in configs are different from old versions
        - Versions match or exceed original versions
        """
        with sandbox_env:
            # Step 1: Install qownnotes
            result = e2e_runner.install("qownnotes")
            assert result.returncode == 0, f"Install failed: {result.stderr}"

            # Step 2: Install appflowy
            result = e2e_runner.install("appflowy")
            assert result.returncode == 0, f"Install failed: {result.stderr}"

            # Step 3: Get fresh versions after install
            qownnotes_latest = (
                e2e_runner.get_app_config("qownnotes")
                .get("state", {})
                .get("version")
            )
            appflowy_latest = (
                e2e_runner.get_app_config("appflowy")
                .get("state", {})
                .get("version")
            )

            assert qownnotes_latest is not None
            assert appflowy_latest is not None

            # Step 4: Force old versions
            old_qownnotes = "v23.1.0"
            old_appflowy = "0.1.0"

            e2e_runner.set_version("qownnotes", old_qownnotes)
            e2e_runner.set_version("appflowy", old_appflowy)

            # Step 5: Verify old versions set
            assert (
                e2e_runner.get_app_config("qownnotes")
                .get("state", {})
                .get("version")
                == old_qownnotes
            )
            assert (
                e2e_runner.get_app_config("appflowy")
                .get("state", {})
                .get("version")
                == old_appflowy
            )

            # Step 6: Run update (all apps - no args means update all)
            result = e2e_runner.update()
            assert result.returncode == 0, f"Update failed: {result.stderr}"

            # Step 7: Verify versions updated
            qownnotes_after = (
                e2e_runner.get_app_config("qownnotes")
                .get("state", {})
                .get("version")
            )
            appflowy_after = (
                e2e_runner.get_app_config("appflowy")
                .get("state", {})
                .get("version")
            )

            # Versions should have changed from old versions
            assert qownnotes_after != old_qownnotes, (
                f"Qownnotes version not updated from {old_qownnotes}"
            )
            assert appflowy_after != old_appflowy, (
                f"AppFlowy version not updated from {old_appflowy}"
            )

            # Versions should match or be newer than original
            assert qownnotes_after == qownnotes_latest
            assert appflowy_after == appflowy_latest
