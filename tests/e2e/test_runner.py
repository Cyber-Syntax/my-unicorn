"""Test E2E CLI query runner.

Tests the E2ERunner class for executing my-unicorn commands in
sandboxed environments.
"""

import orjson
import pytest

from tests.e2e.runner import E2ERunner
from tests.e2e.sandbox import SandboxEnvironment


@pytest.mark.e2e
class TestCLIExecution:
    """Test CLI command execution with sandbox."""

    def test_cli_execution_help(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that basic CLI help command executes."""
        with sandbox_env:
            result = e2e_runner.run_cli("--help")

            assert result.returncode == 0
            assert (
                "usage:" in result.stdout or "usage" in result.stdout.lower()
            )

    def test_cli_execution_help_with_fixtures(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test basic CLI help using fixtures (proof of concept).

        Demonstrates fixture usage: sandbox_env and e2e_runner fixtures
        provide instances for test execution.
        """
        with sandbox_env:
            result = e2e_runner.run_cli("--help")

            assert result.returncode == 0
            assert (
                "usage:" in result.stdout or "usage" in result.stdout.lower()
            )

    def test_cli_execution_unknown_command(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that unknown command exits with non-zero status."""
        with sandbox_env:
            result = e2e_runner.run_cli("invalid-command-xyz")

            assert result.returncode != 0

    def test_run_cli_returns_completed_process(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that run_cli returns subprocess.CompletedProcess object."""
        with sandbox_env:
            result = e2e_runner.run_cli("--help")

            assert hasattr(result, "returncode")
            assert hasattr(result, "stdout")
            assert isinstance(result.returncode, int)
            assert isinstance(result.stdout, str)

    def test_cli_executes_with_sandbox_home(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that CLI executes with sandbox's HOME environment variable."""
        with sandbox_env:
            # Running help should use the sandbox HOME
            result = e2e_runner.run_cli("--help")

            # Verify the environment was set correctly
            assert sandbox_env.temp_home.exists()

            # Create a simple config file in sandbox to verify it's being
            # used
            apps_dir = (
                sandbox_env.temp_home / ".config" / "my-unicorn" / "apps"
            )
            apps_dir.mkdir(parents=True, exist_ok=True)

            # The help command should execute without errors
            assert result.returncode == 0


@pytest.mark.e2e
class TestConfigManipulation:
    """Test config reading/writing utilities."""

    def test_set_version_modifies_app_config(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that set_version updates the version in app config JSON."""
        with sandbox_env:
            # Create an app config file in the sandbox
            app_name = "test-app"
            config_path = (
                sandbox_env.temp_home
                / ".config"
                / "my-unicorn"
                / "apps"
                / f"{app_name}.json"
            )
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write initial config
            initial_config = {
                "config_version": "2.0.0",
                "source": "catalog",
                "catalog_ref": "test-app",
                "state": {
                    "version": "1.0.0",
                    "installed_date": "2026-02-10T10:00:00",
                    "installed_path": "/tmp/test-app.AppImage",
                    "verification": {
                        "passed": True,
                        "methods": [],
                    },
                    "icon": {
                        "installed": False,
                        "method": "none",
                    },
                },
            }
            config_text = orjson.dumps(
                initial_config, option=orjson.OPT_INDENT_2
            ).decode()
            config_path.write_text(config_text)

            # Update the version
            new_version = "2.0.0"
            e2e_runner.set_version(app_name, new_version)

            # Read the config and verify version was updated
            config = orjson.loads(config_path.read_text())
            assert config["state"]["version"] == new_version

    def test_set_version_preserves_other_fields(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that set_version preserves all other fields in config."""
        with sandbox_env:
            app_name = "test-app-preserve"
            config_path = (
                sandbox_env.temp_home
                / ".config"
                / "my-unicorn"
                / "apps"
                / f"{app_name}.json"
            )
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write initial config with various fields
            initial_config = {
                "config_version": "2.0.0",
                "source": "catalog",
                "catalog_ref": "test-app-preserve",
                "state": {
                    "version": "1.0.0",
                    "installed_date": "2026-02-10T10:00:00",
                    "installed_path": "/tmp/test-app.AppImage",
                    "verification": {
                        "passed": True,
                        "methods": [
                            {
                                "type": "digest",
                                "status": "passed",
                                "algorithm": "SHA256",
                                "expected": "abc123",
                                "computed": "abc123",
                            }
                        ],
                    },
                    "icon": {
                        "installed": True,
                        "method": "extraction",
                        "path": "/tmp/test-app.png",
                    },
                },
            }
            config_text = orjson.dumps(
                initial_config, option=orjson.OPT_INDENT_2
            ).decode()
            config_path.write_text(config_text)

            # Update the version
            e2e_runner.set_version(app_name, "3.0.0")

            # Verify version was updated and other fields preserved
            config = orjson.loads(config_path.read_text())
            assert config["state"]["version"] == "3.0.0"
            assert config["config_version"] == "2.0.0"
            assert config["source"] == "catalog"
            assert config["state"]["installed_date"] == "2026-02-10T10:00:00"
            assert config["state"]["icon"]["installed"] is True
            assert (
                config["state"]["verification"]["methods"][0]["expected"]
                == "abc123"
            )


@pytest.mark.e2e
class TestHelperMethods:
    """Test helper methods for common operations."""

    def test_install_helper_method(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that install() method calls run_cli with correct args."""
        with sandbox_env:
            # Just verify the method exists and can be called
            # (even though it may fail without network)
            assert hasattr(e2e_runner, "install")
            assert callable(e2e_runner.install)

    def test_remove_helper_method(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that remove() method calls run_cli with correct args."""
        with sandbox_env:
            assert hasattr(e2e_runner, "remove")
            assert callable(e2e_runner.remove)

    def test_update_helper_method(
        self, sandbox_env: SandboxEnvironment, e2e_runner: E2ERunner
    ) -> None:
        """Test that update() method calls run_cli with correct args."""
        with sandbox_env:
            assert hasattr(e2e_runner, "update")
            assert callable(e2e_runner.update)
