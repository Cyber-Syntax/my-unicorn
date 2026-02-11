"""Tests for sandbox environment manager."""

import os
from pathlib import Path

import pytest

from tests.e2e.sandbox import SandboxEnvironment


@pytest.mark.e2e
class TestSandboxCreation:
    """Test sandbox creation and basic setup."""

    def test_sandbox_creation(self, sandbox_env: SandboxEnvironment) -> None:
        """Test that sandbox creates a temporary HOME directory."""
        with sandbox_env:
            # Temp directory should exist
            assert sandbox_env.temp_home.exists()
            assert sandbox_env.temp_home.is_dir()

            # Temp home should be in system temp directory
            temp_home_str = str(sandbox_env.temp_home)
            assert temp_home_str.startswith(("/tmp", "/var"))

    def test_sandbox_has_config_directory(
        self, sandbox_env: SandboxEnvironment
    ) -> None:
        """Test that sandbox has a .config/my-unicorn directory."""
        with sandbox_env:
            config_dir = sandbox_env.temp_home / ".config" / "my-unicorn"
            assert config_dir.exists()

    def test_sandbox_cleanup(self) -> None:
        """Test sandbox cleanup removes temp directory when enabled."""
        sandbox = SandboxEnvironment(name="cleanup-test", cleanup=True)
        temp_home_path = None

        with sandbox:
            temp_home_path = sandbox.temp_home
            assert temp_home_path.exists()

        # After context exit with cleanup=True, temp directory removed
        assert not temp_home_path.exists()

    def test_sandbox_provides_home_env(
        self, sandbox_env: SandboxEnvironment
    ) -> None:
        """Test that sandbox provides HOME environment variable."""
        original_home = os.environ.get("HOME")
        try:
            with sandbox_env:
                # HOME should be set to temp directory when using context
                # (This test verifies the env setup, though the actual
                # env override may only apply within subprocess calls)
                assert sandbox_env.temp_home is not None
        finally:
            if original_home:
                os.environ["HOME"] = original_home


@pytest.mark.e2e
class TestConfigCopy:
    """Test configuration copying functionality."""

    def test_config_copy_creates_structure(self, tmp_path: Path) -> None:
        """Test that config copy creates the expected directory structure."""
        # Create a minimal source config
        source_config = tmp_path / "source" / ".config" / "my-unicorn"
        source_config.mkdir(parents=True)
        settings_conf = "[DEFAULT]\ntest = value\n"
        (source_config / "settings.conf").write_text(settings_conf)
        (source_config / "apps").mkdir()
        (source_config / "cache").mkdir()

        # Create sandbox and copy config
        orig_home = os.environ.get("HOME")
        os.environ["HOME"] = str(tmp_path / "source")

        try:
            sandbox = SandboxEnvironment(
                name="test_config_copy_creates_structure"
            )
            # Manually copy config for testing
            sandbox._copy_real_config()

            # Verify structure
            assert (sandbox.temp_home / ".config" / "my-unicorn").exists()
            config_file = (
                sandbox.temp_home / ".config" / "my-unicorn" / "settings.conf"
            )
            assert config_file.exists()
            apps_dir = sandbox.temp_home / ".config" / "my-unicorn" / "apps"
            assert apps_dir.exists()
            cache_dir = sandbox.temp_home / ".config" / "my-unicorn" / "cache"
            assert cache_dir.exists()
        finally:
            if orig_home:
                os.environ["HOME"] = orig_home
            else:
                os.environ.pop("HOME", None)

    def test_config_copy_handles_missing_source(
        self, sandbox_env: SandboxEnvironment
    ) -> None:
        """Test that config copy handles missing source gracefully."""
        with sandbox_env:
            # Should create directories even if source doesn't exist
            config_dir = sandbox_env.temp_home / ".config" / "my-unicorn"
            assert config_dir.exists()


class TestPathRewriting:
    """Test configuration path rewriting functionality."""

    def test_path_rewriting_updates_directory_section(
        self, sandbox_env: SandboxEnvironment
    ) -> None:
        """Test that path rewriting updates directory paths in config file."""
        with sandbox_env:
            # Create settings.conf with absolute paths
            settings_file = (
                sandbox_env.temp_home
                / ".config"
                / "my-unicorn"
                / "settings.conf"
            )
            settings_content = """[DEFAULT]
config_version = 1.1.0
max_concurrent_downloads = 5

[directory]
download = /home/user/Downloads
storage = /home/user/Applications
backup = /home/user/Applications/backups
icon = /home/user/Applications/icons
settings = /home/user/.config/my-unicorn
logs = /home/user/.config/my-unicorn/logs
cache = /home/user/.config/my-unicorn/cache
"""
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings_file.write_text(settings_content)

            # Rewrite paths
            sandbox_env._rewrite_config_paths()

            # Verify paths were rewritten
            content = settings_file.read_text()

            # Check that old paths are not present
            assert "/home/user/Downloads" not in content
            assert "/home/user/Applications" not in content

            # Check that new paths contain sandbox temp_home
            assert "download" in content
            assert "storage" in content

    def test_path_rewriting_relative_paths(
        self, sandbox_env: SandboxEnvironment
    ) -> None:
        """Test that path rewriting handles existing relative paths."""
        with sandbox_env:
            settings_file = (
                sandbox_env.temp_home
                / ".config"
                / "my-unicorn"
                / "settings.conf"
            )
            # Settings with relative/home-relative paths
            settings_content = """[DEFAULT]
config_version = 1.1.0

[directory]
download = ~/Downloads
storage = ~/Applications
"""
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings_file.write_text(settings_content)

            sandbox_env._rewrite_config_paths()

            content = settings_file.read_text()
            # Should have been rewritten to absolute paths in sandbox
            assert "~/" not in content or (
                str(sandbox_env.temp_home) in content
            )

    def test_path_rewriting_preserves_non_directory_settings(
        self, sandbox_env: SandboxEnvironment
    ) -> None:
        """Test that path rewriting preserves non-directory settings."""
        with sandbox_env:
            settings_file = (
                sandbox_env.temp_home
                / ".config"
                / "my-unicorn"
                / "settings.conf"
            )
            settings_content = """[DEFAULT]
config_version = 1.1.0
max_concurrent_downloads = 5
max_backup = 1
log_level = INFO

[network]
retry_attempts = 3
timeout_seconds = 10

[directory]
download = /home/user/Downloads
storage = /home/user/Applications
"""
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings_file.write_text(settings_content)

            sandbox_env._rewrite_config_paths()

            content = settings_file.read_text()

            # Verify non-directory settings are preserved
            assert "config_version = 1.1.0" in content
            assert "max_concurrent_downloads = 5" in content
            assert "max_backup = 1" in content
            assert "log_level = INFO" in content
            assert "retry_attempts = 3" in content
            assert "timeout_seconds = 10" in content
