"""Test backward compatibility with v1.0.0 configs."""

import json

import pytest

from my_unicorn.config import (
    AppConfigManager,
    CatalogManager,
    DirectoryManager,
)


@pytest.fixture
def test_config_dir(tmp_path):
    """Create test config directory structure."""
    config_dir = tmp_path / "config"
    catalog_dir = tmp_path / "catalog"
    apps_dir = config_dir / "apps"

    config_dir.mkdir()
    catalog_dir.mkdir()
    apps_dir.mkdir()

    return config_dir, catalog_dir, apps_dir


def test_load_old_config_requires_migration(test_config_dir):
    """Test that loading v1.0.0 config raises error requiring migration."""
    config_dir, catalog_dir, apps_dir = test_config_dir

    # Create v1.0.0 config file
    old_config = {
        "config_version": "1.0.0",
        "source": "catalog",
        "owner": "owner",
        "repo": "test-app",
        "appimage": {
            "version": "1.0.0",
            "name": "test-app.AppImage",
            "rename": "test-app",
            "name_template": "{rename}-{latest_version}.AppImage",
            "characteristic_suffix": ["x86_64"],
            "installed_date": "2025-01-01T00:00:00",
            "digest": "sha256:abc123",
        },
        "github": {"repo": True, "prerelease": False},
        "verification": {"skip": False, "digest": True},
        "icon": {
            "extraction": True,
            "name": "test-app.png",
            "installed": False,
            "path": "",
        },
    }

    old_config_path = apps_dir / "test-app.json"
    with open(old_config_path, "w", encoding="utf-8") as f:
        json.dump(old_config, f, indent=2)

    # Attempt to load config (should fail with helpful message)
    dm = DirectoryManager(config_dir=config_dir, catalog_dir=catalog_dir)
    cm = CatalogManager(dm)
    acm = AppConfigManager(dm, cm)

    # Verify that loading v1 config raises error with migration message
    with pytest.raises(ValueError) as exc_info:
        acm.load_app_config("test-app")

    error_message = str(exc_info.value)
    assert "version 1.0.0" in error_message
    assert "expected 2.0.0" in error_message
    assert "my-unicorn migrate" in error_message


def test_save_and_load_v2_config(test_config_dir):
    """Test saving and loading v2 config."""
    config_dir, catalog_dir, apps_dir = test_config_dir

    # Create v2 config
    v2_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test-app",
        "state": {
            "version": "1.0.0",
            "installed_date": "2025-01-01T00:00:00",
            "installed_path": "/path/to/app.AppImage",
            "verification": {"passed": True, "methods": []},
            "icon": {"installed": False, "method": "extraction", "path": ""},
        },
    }

    # Save config
    dm = DirectoryManager(config_dir=config_dir, catalog_dir=catalog_dir)
    cm = CatalogManager(dm)
    acm = AppConfigManager(dm, cm)

    acm.save_app_config("test-app", v2_config)

    # Load it back
    loaded_config = acm.load_app_config("test-app")

    # Verify
    assert loaded_config is not None
    assert loaded_config["config_version"] == "2.0.0"
    assert loaded_config["source"] == "catalog"
    assert loaded_config["catalog_ref"] == "test-app"


def test_effective_config_url_install(test_config_dir):
    """Test effective config for URL install with overrides."""
    config_dir, catalog_dir, apps_dir = test_config_dir

    # Create v2 URL install config with overrides
    url_config = {
        "config_version": "2.0.0",
        "source": "url",
        "catalog_ref": None,
        "state": {
            "version": "1.0.0",
            "installed_date": "2025-01-01T00:00:00",
            "installed_path": "/path/to/app.AppImage",
            "verification": {"passed": True, "methods": []},
            "icon": {"installed": False, "method": "extraction", "path": ""},
        },
        "overrides": {
            "metadata": {"name": "test-app", "display_name": "Test App"},
            "source": {
                "type": "github",
                "owner": "owner",
                "repo": "test-app",
                "prerelease": False,
            },
            "verification": {"method": "digest"},
        },
    }

    # Save config
    dm = DirectoryManager(config_dir=config_dir, catalog_dir=catalog_dir)
    cm = CatalogManager(dm)
    acm = AppConfigManager(dm, cm)

    acm.save_app_config("test-app", url_config)

    # Get effective config
    effective = acm.get_effective_config("test-app")

    # Verify effective config has overrides applied
    assert effective["source"]["owner"] == "owner"
    assert effective["source"]["repo"] == "test-app"
    assert effective["source"]["prerelease"] is False
    assert effective["state"]["version"] == "1.0.0"
