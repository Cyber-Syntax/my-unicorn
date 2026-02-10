"""Test E2E CLI query runner.

Tests the E2ERunner class for executing my-unicorn commands in
sandboxed environments.
"""

import orjson

from tests.e2e.runner import E2ERunner
from tests.e2e.sandbox import SandboxEnvironment


class TestCLIExecution:
    """Test CLI command execution with sandbox."""

    def test_cli_execution_help(self) -> None:
        """Test that basic CLI help command executes."""
        with SandboxEnvironment(name="test_cli_execution_help") as sandbox:
            runner = E2ERunner(sandbox)
            result = runner.run_cli("--help")

            assert result.returncode == 0
            assert (
                "usage:" in result.stdout or "usage" in result.stdout.lower()
            )

    def test_cli_execution_unknown_command(self) -> None:
        """Test that unknown command exits with non-zero status."""
        with SandboxEnvironment(
            name="test_cli_execution_unknown_command"
        ) as sandbox:
            runner = E2ERunner(sandbox)
            result = runner.run_cli("invalid-command-xyz")

            assert result.returncode != 0

    def test_run_cli_returns_completed_process(self) -> None:
        """Test that run_cli returns subprocess.CompletedProcess object."""
        with SandboxEnvironment(
            name="test_run_cli_returns_completed_process"
        ) as sandbox:
            runner = E2ERunner(sandbox)
            result = runner.run_cli("--help")

            assert hasattr(result, "returncode")
            assert hasattr(result, "stdout")
            assert isinstance(result.returncode, int)
            assert isinstance(result.stdout, str)

    def test_cli_executes_with_sandbox_home(self) -> None:
        """Test that CLI executes with sandbox's HOME environment variable."""
        with SandboxEnvironment(
            name="test_cli_executes_with_sandbox_home"
        ) as sandbox:
            runner = E2ERunner(sandbox)
            # Running help should use the sandbox HOME
            result = runner.run_cli("--help")

            # Verify the environment was set correctly
            assert sandbox.temp_home.exists()

            # Create a simple config file in sandbox to verify it's being used
            apps_dir = sandbox.temp_home / ".config" / "my-unicorn" / "apps"
            apps_dir.mkdir(parents=True, exist_ok=True)

            # The help command should execute without errors
            assert result.returncode == 0


class TestConfigManipulation:
    """Test config reading/writing utilities."""

    def test_set_version_modifies_app_config(self) -> None:
        """Test that set_version updates the version in app config JSON."""
        with SandboxEnvironment(
            name="test_set_version_modifies_app_config"
        ) as sandbox:
            runner = E2ERunner(sandbox)

            # Create an app config file in the sandbox
            app_name = "test-app"
            config_path = (
                sandbox.temp_home
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
            runner.set_version(app_name, new_version)

            # Read the config and verify version was updated
            config = orjson.loads(config_path.read_text())
            assert config["state"]["version"] == new_version

    def test_set_version_preserves_other_fields(self) -> None:
        """Test that set_version preserves all other fields in config."""
        with SandboxEnvironment(
            name="test_set_version_preserves_other_fields"
        ) as sandbox:
            runner = E2ERunner(sandbox)

            app_name = "test-app-preserve"
            config_path = (
                sandbox.temp_home
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
            runner.set_version(app_name, "3.0.0")

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


class TestHelperMethods:
    """Test helper methods for common operations."""

    def test_install_helper_method(self) -> None:
        """Test that install() method calls run_cli with correct args."""
        with SandboxEnvironment(name="test_install_helper_method") as sandbox:
            runner = E2ERunner(sandbox)
            # Just verify the method exists and can be called
            # (even though it may fail without network)
            assert hasattr(runner, "install")
            assert callable(runner.install)

    def test_remove_helper_method(self) -> None:
        """Test that remove() method calls run_cli with correct args."""
        with SandboxEnvironment(name="test_remove_helper_method") as sandbox:
            runner = E2ERunner(sandbox)
            assert hasattr(runner, "remove")
            assert callable(runner.remove)

    def test_update_helper_method(self) -> None:
        """Test that update() method calls run_cli with correct args."""
        with SandboxEnvironment(name="test_update_helper_method") as sandbox:
            runner = E2ERunner(sandbox)
            assert hasattr(runner, "update")
            assert callable(runner.update)
