"""Configuration building utilities for app state management.

This module provides utilities for creating and updating application
configurations in the v2.0.0 format. It centralizes config building logic
used across install and update workflows.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from my_unicorn.constants import APP_CONFIG_VERSION
from my_unicorn.core.github import Asset, Release
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def create_app_config_v2(
    app_name: str,
    app_path: Path,
    app_config: dict[str, Any],
    release: Release,
    verify_result: dict[str, Any] | None,
    icon_result: dict[str, Any],
    source: str,
    config_manager: Any,
) -> dict[str, Any]:
    """Create app configuration in v2.0.0 format.

    Args:
        app_name: Application name
        app_path: Path to installed AppImage
        app_config: App configuration template
        release: Release information
        verify_result: Verification result
        icon_result: Icon extraction result
        source: Install source ("catalog" or "url")
        config_manager: Configuration manager for saving config

    Returns:
        Config creation result with success status and config data

    Example:
        >>> result = create_app_config_v2(
        ...     app_name="myapp",
        ...     app_path=Path("/path/to/myapp.AppImage"),
        ...     app_config={"source": {"owner": "foo", "repo": "bar"}},
        ...     release=release_obj,
        ...     verify_result={"passed": True, "methods": {...}},
        ...     icon_result={"icon_path": "/path/to/icon.png"},
        ...     source="catalog",
        ...     config_manager=config_mgr
        ... )
        >>> result["success"]
        True

    """
    # Determine catalog reference and overrides
    catalog_ref = app_name if source == "catalog" else None
    overrides = (
        None
        if source == "catalog"
        else build_overrides_from_template(app_config)
    )

    # Build verification state
    verification_state = build_verification_state(verify_result)

    # Build state section
    config_data = {
        "config_version": APP_CONFIG_VERSION,
        "source": source,
        "catalog_ref": catalog_ref,
        "state": {
            "version": release.version,
            "installed_date": datetime.now(tz=UTC).isoformat(),
            "installed_path": str(app_path),
            "verification": {
                "passed": verification_state["passed"],
                "methods": verification_state["methods"],
            },
            "icon": {
                "installed": bool(icon_result.get("icon_path")),
                "method": icon_result.get("source", "none"),
                "path": icon_result.get("icon_path", ""),
            },
        },
    }

    # Add overrides for URL installs
    if overrides:
        # Update verification method with actual result
        if "verification" in overrides:
            overrides["verification"]["method"] = verification_state[
                "actual_method"
            ]

        # Update icon filename with actual result
        if icon_result.get("icon_path") and "icon" in overrides:
            icon_path = Path(icon_result["icon_path"])
            overrides["icon"]["filename"] = icon_path.name

        config_data["overrides"] = overrides

    # Save configuration
    try:
        config_manager.save_app_config(
            app_name, config_data, skip_validation=True
        )
        return {
            "success": True,
            "config_path": str(config_manager.apps_dir / f"{app_name}.json"),
            "config": config_data,
        }
    except Exception as error:
        logger.exception("Failed to save config for %s", app_name)
        return {
            "success": False,
            "error": str(error),
        }


def build_verification_state(
    verify_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build verification state from verification result.

    Args:
        verify_result: Verification result dictionary or None

    Returns:
        Dictionary with 'passed', 'methods', and 'actual_method' keys

    Example:
        >>> verify_result = {
        ...     "passed": True,
        ...     "methods": {
        ...         "digest": {"passed": True, "hash_type": "sha256"}
        ...     }
        ... }
        >>> state = build_verification_state(verify_result)
        >>> state["passed"]
        True
        >>> state["actual_method"]
        'digest'

    """
    if not verify_result:
        return {"passed": False, "methods": [], "actual_method": "skip"}

    methods_data = verify_result.get("methods", {})
    if not methods_data:
        return {"passed": False, "methods": [], "actual_method": "skip"}

    verification_passed = verify_result.get("passed", False)
    actual_method = next(iter(methods_data.keys()), "skip")

    verification_methods = [
        build_method_entry(method_type, method_result)
        for method_type, method_result in methods_data.items()
    ]

    return {
        "passed": verification_passed,
        "methods": verification_methods,
        "actual_method": actual_method,
    }


def build_method_entry(method_type: str, method_result: Any) -> dict[str, Any]:
    """Build verification method entry from result.

    Args:
        method_type: Type of verification (digest, checksum_file)
        method_result: Result data (dict or simple bool)

    Returns:
        Method entry dictionary for config

    Example:
        >>> result = {
        ...     "passed": True,
        ...     "hash_type": "sha256",
        ...     "hash": "abc123",
        ...     "computed_hash": "abc123"
        ... }
        >>> entry = build_method_entry("digest", result)
        >>> entry["type"]
        'digest'
        >>> entry["status"]
        'passed'

    """
    method_entry: dict[str, Any] = {"type": method_type}

    if not isinstance(method_result, dict):
        method_entry["status"] = "passed" if method_result else "failed"
        return method_entry

    passed = method_result.get("passed", False)
    hash_type = method_result.get("hash_type", "")
    algorithm = hash_type.upper() if hash_type else "SHA256"

    verification_source = method_result.get("url", "")
    if not verification_source:
        verification_source = "github_api" if method_type == "digest" else ""

    method_entry.update(
        {
            "status": "passed" if passed else "failed",
            "algorithm": algorithm,
            "expected": method_result.get("hash", ""),
            "computed": method_result.get("computed_hash", ""),
            "source": verification_source,
        }
    )
    return method_entry


def build_overrides_from_template(
    app_config: dict[str, Any],
) -> dict[str, Any]:
    """Build overrides section from app config template.

    Args:
        app_config: App configuration template (v2 format)

    Returns:
        Overrides dictionary for v2.0.0 config

    Example:
        >>> template = {
        ...     "source": {"owner": "foo", "repo": "bar"},
        ...     "verification": {"method": "digest"}
        ... }
        >>> overrides = build_overrides_from_template(template)
        >>> overrides["source"]["owner"]
        'foo'

    """
    # Extract from v2 format
    source_config = app_config.get("source", {})
    owner = source_config.get("owner", "")
    repo = source_config.get("repo", "")
    prerelease = source_config.get("prerelease", False)

    naming_config = app_config.get("appimage", {}).get("naming", {})
    name_template = naming_config.get("template", "")
    target_name = naming_config.get("target_name", "")

    verification_config = app_config.get("verification", {})
    verification_method = verification_config.get("method", "skip")

    icon_config = app_config.get("icon", {})
    icon_method = icon_config.get("method", "extraction")
    icon_filename = icon_config.get("filename", "")

    overrides = {
        "metadata": {
            "name": repo,
            "display_name": repo,
            "description": "",
        },
        "source": {
            "type": "github",
            "owner": owner,
            "repo": repo,
            "prerelease": prerelease,
        },
        "appimage": {
            "naming": {
                "template": name_template,
                "target_name": target_name,
                "architectures": ["amd64", "x86_64"],
            }
        },
        "verification": {"method": verification_method},
        "icon": {
            "method": icon_method,
            "filename": icon_filename,
        },
    }

    return overrides  # noqa: RET504


def update_app_config(
    app_name: str,
    latest_version: str,
    appimage_path: Path,
    icon_path: Path | None,
    verification_results: dict[str, Any],  # noqa: ARG001
    updated_icon_config: dict[str, Any] | None,
    config_manager: Any,
) -> None:
    """Update app configuration after successful update.

    Args:
        app_name: Name of the app
        latest_version: Latest version string
        appimage_path: Path to installed AppImage
        icon_path: Path to icon or None
        verification_results: Verification results
        updated_icon_config: Updated icon config or None
        config_manager: Configuration manager for loading/saving config

    Raises:
        ValueError: If app config not found

    Example:
        >>> update_app_config(
        ...     app_name="myapp",
        ...     latest_version="1.2.3",
        ...     appimage_path=Path("/path/to/myapp.AppImage"),
        ...     icon_path=Path("/path/to/icon.png"),
        ...     verification_results={"digest": {"passed": True}},
        ...     updated_icon_config={"installed": True},
        ...     config_manager=config_mgr
        ... )

    """
    # Load raw state for modification (not merged effective config)
    raw_state = config_manager.load_raw_app_config(app_name)
    if not raw_state:
        msg = f"Cannot update config: app state not found for {app_name}"
        raise ValueError(msg)

    # Update state fields (v2 format)
    if "state" not in raw_state:
        raw_state["state"] = {}
    raw_state["state"]["version"] = latest_version
    raw_state["state"]["installed_path"] = str(appimage_path)
    raw_state["state"]["installed_date"] = (
        datetime.now().astimezone().isoformat()
    )

    # Update icon configuration in state.icon (v2 format)
    if updated_icon_config:
        # Map workflow utility result to v2 schema format
        # v2 schema only allows: installed, method, path
        raw_state["state"]["icon"] = {
            "installed": updated_icon_config.get("installed", False),
            "method": updated_icon_config.get("source", "none"),
            "path": updated_icon_config.get("path", ""),
        }

        if icon_path:
            logger.debug(
                "🎨 Icon updated for %s: method=%s, installed=%s",
                app_name,
                raw_state["state"]["icon"]["method"],
                raw_state["state"]["icon"]["installed"],
            )

    config_manager.save_app_config(app_name, raw_state, skip_validation=True)


def get_stored_hash(
    verification_results: dict[str, Any],
    appimage_asset: Asset,
) -> str:
    """Get the hash to store from verification results or asset digest.

    Args:
        verification_results: Verification results dictionary
        appimage_asset: AppImage asset with optional digest

    Returns:
        Hash string (SHA256/SHA512) or empty string

    Example:
        >>> results = {"digest": {"passed": True, "hash": "abc123"}}
        >>> asset = Asset(name="app.AppImage", digest="")
        >>> hash_val = get_stored_hash(results, asset)
        >>> hash_val
        'abc123'

    """
    if verification_results.get("digest", {}).get("passed"):
        return str(verification_results["digest"]["hash"])
    if verification_results.get("checksum_file", {}).get("passed"):
        return str(verification_results["checksum_file"]["hash"])
    if appimage_asset.digest:
        return appimage_asset.digest
    return ""
