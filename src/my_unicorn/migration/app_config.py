"""App configuration migration module.

Handles migration of app state files (apps/*.json) from v1 to v2 format.

v1 Format (flat structure):
    - All fields in one level
    - Catalog and URL installs stored identically

v2 Format (hybrid structure):
    - Catalog apps: state + catalog_ref only
    - URL apps: state + full config in overrides
    - Clear source field distinguishes types
"""

from typing import TYPE_CHECKING, Any

from my_unicorn.constants import APP_CONFIG_VERSION
from my_unicorn.migration import base

if TYPE_CHECKING:
    from my_unicorn.config import ConfigManager

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class AppConfigMigrator:
    """Migrate app configs from v1 to v2 format."""

    def __init__(self, config_manager: "ConfigManager") -> None:
        """Initialize app config migrator.

        Args:
            config_manager: Config manager instance for directory access

        """
        self.config_manager = config_manager

    def migrate_app(self, app_name: str) -> dict[str, Any]:
        """Migrate single app config.

        Args:
            app_name: Name of app to migrate

        Returns:
            dict: {"migrated": bool, "from": str, "to": str}

        Raises:
            FileNotFoundError: If app config not found
            ValueError: If unsupported config version

        """
        # Load config file directly (bypass version validation)
        app_file = (
            self.config_manager.directory_manager.apps_dir / f"{app_name}.json"
        )
        config = base.load_json_file(app_file)

        current_version = config.get("config_version", "1.0.0")

        # Check if migration needed
        if not base.needs_migration(current_version, APP_CONFIG_VERSION):
            return {
                "migrated": False,
                "from": current_version,
                "to": APP_CONFIG_VERSION,
            }

        # Create backup before migration
        backup_dir = self.config_manager.directory_manager.apps_dir / "backups"
        base.create_backup(app_file, backup_dir)

        # Migrate based on version
        if current_version.startswith("1."):
            migrated_config = self._migrate_v1_to_v2(config, app_name)
        else:
            msg = f"Unsupported config version: {current_version}"
            raise ValueError(msg)

        # Save migrated config
        self.config_manager.app_config_manager.save_app_config(
            app_name, migrated_config
        )

        logger.info(
            "Migrated %s from v%s to v%s",
            app_name,
            current_version,
            APP_CONFIG_VERSION,
        )

        return {
            "migrated": True,
            "from": current_version,
            "to": APP_CONFIG_VERSION,
        }

    def _migrate_v1_to_v2(self, old_config: dict, app_name: str) -> dict:
        """Migrate v1 flat structure to v2 hybrid structure.

        Args:
            old_config: v1.x config data
            app_name: Name of the app being migrated

        Returns:
            v2.0.0 config data

        """
        source = old_config.get("source", "catalog")
        catalog_ref = app_name if source == "catalog" else None

        # Build new config with state section
        new_config = {
            "config_version": APP_CONFIG_VERSION,
            "source": source,
            "catalog_ref": catalog_ref,
            "state": self._build_state_section(old_config, app_name, source),
        }

        # Add overrides only for URL installs
        if source == "url":
            new_config["overrides"] = self._build_overrides_section(old_config)

        return new_config

    def _build_state_section(
        self, old_config: dict, app_name: str, source: str
    ) -> dict:
        """Build state section from v1 config.

        Args:
            old_config: v1 config data
            app_name: Name of the app being migrated
            source: Source type (catalog or url)

        Returns:
            State section for v2 config

        """
        appimage_old = old_config.get("appimage", {})
        icon_old = old_config.get("icon", {})

        return {
            "version": appimage_old.get("version", "unknown"),
            "installed_date": appimage_old.get("installed_date", ""),
            "installed_path": old_config.get("installed_path", ""),
            "verification": self._build_verification_state(
                old_config, appimage_old, app_name, source
            ),
            "icon": self._build_icon_state(icon_old),
        }

    def _build_verification_state(
        self, old_config: dict, appimage_old: dict, app_name: str, source: str
    ) -> dict:
        """Build verification state from v1 config.

        Prioritizes actual verification data from v1 app state over catalog.
        Catalog method="skip" doesn't prevent using digest if available.

        Args:
            old_config: v1 config data
            appimage_old: v1 appimage section
            app_name: Name of the app being migrated
            source: Source type (catalog or url)

        Returns:
            Verification state for v2 config

        """
        verification_old = old_config.get("verification", {})
        methods = []

        # Handle explicit skip in v1 app state
        if verification_old.get("skip", False):
            methods.append({"type": "skip", "status": "skipped"})
            return {
                "passed": False,
                "methods": methods,
            }

        # Check if v1 app state has actual verification data
        has_digest = bool(appimage_old.get("digest"))
        has_checksum = bool(verification_old.get("checksum_file"))
        digest_verified = verification_old.get("digest", False)

        # Priority 1: Use checksum file if available in v1 state
        if has_checksum:
            checksum_file = verification_old["checksum_file"]
            algorithm = verification_old.get("checksum_hash_type", "sha256")
            methods.append(
                {
                    "type": "checksum_file",
                    "status": "passed",
                    "algorithm": algorithm,
                    "filename": checksum_file,
                }
            )
        # Priority 2: Use digest if available in v1 state
        elif has_digest and digest_verified:
            # Parse digest string (e.g., "sha256:hash")
            digest_str = appimage_old["digest"]
            algorithm = "sha256"
            digest_hash = digest_str

            if ":" in digest_str:
                algorithm, digest_hash = digest_str.split(":", 1)

            methods.append(
                {
                    "type": "digest",
                    "status": "passed",
                    "algorithm": algorithm,
                    "expected": digest_hash,
                    "computed": digest_hash,
                    "source": "github_api",
                }
            )
        # Priority 3: Catalog says skip but no actual verification in v1
        # For catalog apps, check if catalog method is skip
        elif source == "catalog":
            catalog_entry = (
                self.config_manager.catalog_manager.load_catalog_entry(
                    app_name
                )
            )
            if catalog_entry:
                catalog_verification = catalog_entry.get("verification", {})
                method = catalog_verification.get("method", "digest")

                if method == "skip":
                    methods.append({"type": "skip", "status": "skipped"})

        # Ensure at least one method exists (required by v2 schema)
        if not methods:
            # Default to skip if no verification data available
            methods.append({"type": "skip", "status": "skipped"})

        return {
            "passed": len([m for m in methods if m["status"] == "passed"]) > 0,
            "methods": methods,
        }

    def _build_verification_config(self, verification_old: dict) -> dict:
        """Build verification config from v1 verification section.

        Args:
            verification_old: v1 verification section

        Returns:
            Verification config for v2 overrides

        """
        if verification_old.get("skip"):
            return {"method": "skip"}
        if verification_old.get("checksum_file"):
            return {
                "method": "checksum_file",
                "checksum_file": {
                    "filename": verification_old["checksum_file"],
                    "algorithm": verification_old.get(
                        "checksum_hash_type", "sha256"
                    ),
                },
            }
        if verification_old.get("digest"):
            return {"method": "digest"}
        return {"method": "skip"}

    def _build_icon_state(self, icon_old: dict) -> dict:
        """Build icon state from v1 config.

        Args:
            icon_old: v1 icon section

        Returns:
            Icon state for v2 config

        """
        # Determine icon method from v1 config
        # Priority: source field > extraction boolean > default to extraction
        # Note: v1 "download" method is mapped to "extraction" in v2
        # since v2 only supports extraction or none
        source = icon_old.get("source", "")
        if source == "download":
            # Map deprecated download method to extraction
            method = "extraction"
        elif source == "extraction" or icon_old.get("extraction"):
            method = "extraction"
        else:
            method = "extraction"  # Default to extraction for safety

        return {
            "installed": icon_old.get("installed", False),
            "method": method,
            "path": icon_old.get("path", ""),
        }

    def _build_overrides_section(self, old_config: dict) -> dict:
        """Build overrides section for URL installs.

        Args:
            old_config: v1 config data

        Returns:
            Overrides section for v2 config

        """
        github_old = old_config.get("github", {})
        appimage_old = old_config.get("appimage", {})
        icon_old = old_config.get("icon", {})
        verification_old = old_config.get("verification", {})

        # Determine verification method
        verification_config = self._build_verification_config(verification_old)

        overrides = {
            "metadata": {
                "name": old_config.get("repo", ""),
                "display_name": old_config.get("repo", ""),
                "description": "",
            },
            "source": {
                "type": "github",
                "owner": old_config.get("owner", ""),
                "repo": old_config.get("repo", ""),
                "prerelease": github_old.get("prerelease", False),
            },
            "appimage": {
                "naming": {
                    "template": appimage_old.get("name_template", ""),
                    "target_name": appimage_old.get("rename", ""),
                    "architectures": ["amd64", "x86_64"],
                }
            },
            "verification": verification_config,
            "icon": {
                "method": "extraction",
                "filename": icon_old.get("name", ""),
            },
        }

        return overrides
