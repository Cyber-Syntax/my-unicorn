#!/usr/bin/env python3
"""Test orchestration runner for my-unicorn framework.

This module provides the TestRunner class that orchestrates test execution
with validation and benchmarking using the new modular architecture.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import logging
from pathlib import Path

import orjson
from benchmark import (
    BenchmarkCollector,
    generate_json_report,
    generate_markdown_report,
)
from cli_runner import (
    MY_UNICORN_PROD_VERSION,
    MY_UNICORN_VERSION,
    remove_apps,
    run_cli,
)
from config import set_version
from validators import (
    AppImageValidator,
    ConfigValidator,
    DesktopValidator,
    IconValidator,
)

logger = logging.getLogger("my-unicorn-test")


class TestRunner:
    """Orchestrate test execution with validation and benchmarking."""

    def __init__(self, enable_benchmark: bool = False) -> None:
        """Initialize test runner.

        Args:
            enable_benchmark: Whether to enable benchmarking
        """
        self.enable_benchmark = enable_benchmark
        self.benchmark = (
            BenchmarkCollector(MY_UNICORN_VERSION, MY_UNICORN_PROD_VERSION)
            if enable_benchmark
            else None
        )

        # Config directory path
        self.config_dir = Path.home() / ".config" / "my-unicorn"

        # Track results
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results: list[dict] = []

    def run_quick(self) -> None:
        """Execute quick test suite with qownnotes."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("Running Quick Tests (qownnotes)")
        logger.info("=" * 60)
        logger.info("")

        # Step 1: Test update
        logger.info("Step 1/5: Testing qownnotes update")
        self._test_update("qownnotes")

        # Step 2: Remove for clean state
        logger.info(
            "Step 2/5: Removing qownnotes for clean catalog install test"
        )
        remove_apps("qownnotes")

        # Step 3: Test catalog install
        logger.info("Step 3/5: Testing qownnotes catalog install")
        self._test_install("qownnotes", is_catalog=True)

        # Step 4: Remove for clean URL install test
        logger.info("Step 4/5: Removing qownnotes for clean URL install test")
        remove_apps("qownnotes")

        # Step 5: Test URL install
        logger.info("Step 5/5: Testing qownnotes URL install")
        self._test_install(
            "qownnotes",
            is_catalog=False,
            url="https://github.com/pbek/QOwnNotes",
        )

        logger.info("")
        logger.info("Quick tests completed")

    def run_all(self) -> None:
        """Execute comprehensive test suite."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("Running All Comprehensive Tests")
        logger.info("=" * 60)
        logger.info("")

        # Phase 1: URL Installs
        logger.info("")
        logger.info("-" * 60)
        logger.info("Phase 1: URL Install Tests")
        logger.info("-" * 60)
        logger.info("")

        if self.benchmark:
            phase_id = self.benchmark.start_operation(
                "phase_url_installs",
                metadata={
                    "phase": "url_installs",
                    "apps": ["neovim", "keepassxc"],
                },
            )

        # Clean state for URL installs
        logger.info("Removing neovim and keepassxc for clean state")
        remove_apps("neovim", "keepassxc")

        # Test concurrent URL installs
        logger.info("Testing concurrent URL installs: neovim + keepassxc")
        self._test_install(
            "neovim",
            is_catalog=False,
            url="https://github.com/neovim/neovim",
        )
        self._test_install(
            "keepassxc",
            is_catalog=False,
            url="https://github.com/keepassxreboot/keepassxc",
        )

        if self.benchmark and phase_id:
            self.benchmark.end_operation(phase_id)

        # Phase 2: Catalog Installs
        logger.info("")
        logger.info("-" * 60)
        logger.info("Phase 2: Catalog Install Tests")
        logger.info("-" * 60)
        logger.info("")

        if self.benchmark:
            phase_id = self.benchmark.start_operation(
                "phase_catalog_installs",
                metadata={
                    "phase": "catalog_installs",
                    "apps": [
                        "legcord",
                        "flameshot",
                        "appflowy",
                        "standard-notes",
                    ],
                },
            )

        # Clean state for catalog installs
        logger.info("Removing legcord and flameshot for clean state")
        remove_apps("legcord", "flameshot")

        # Test multiple catalog installs
        logger.info(
            "Testing multiple catalog installs: "
            "legcord, flameshot, appflowy, standard-notes"
        )
        self._test_install("legcord", is_catalog=True)
        self._test_install("flameshot", is_catalog=True)
        self._test_install("appflowy", is_catalog=True)
        self._test_install("standard-notes", is_catalog=True)

        if self.benchmark and phase_id:
            self.benchmark.end_operation(phase_id)

        # Phase 3: Updates
        logger.info("")
        logger.info("-" * 60)
        logger.info("Phase 3: Update Tests")
        logger.info("-" * 60)
        logger.info("")

        if self.benchmark:
            phase_id = self.benchmark.start_operation(
                "phase_updates",
                metadata={
                    "phase": "updates",
                    "apps": [
                        "legcord",
                        "flameshot",
                        "keepassxc",
                        "appflowy",
                        "standard-notes",
                    ],
                },
            )

        # Test updates for all installed apps
        logger.info(
            "Testing updates: "
            "legcord, flameshot, keepassxc, appflowy, standard-notes"
        )
        self._test_update("legcord")
        self._test_update("flameshot")
        self._test_update("keepassxc")
        self._test_update("appflowy")
        self._test_update("standard-notes")

        if self.benchmark and phase_id:
            self.benchmark.end_operation(phase_id)

        logger.info("")
        logger.info("-" * 60)
        logger.info("All comprehensive tests completed")
        logger.info("-" * 60)
        logger.info("")

    def run_slow(self) -> None:
        """Execute slow test suite with large apps."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("Running Slow Tests (large apps)")
        logger.info("=" * 60)
        logger.info("")

        # TODO: Implement slow tests
        logger.warning("Slow tests not yet implemented in new architecture")

    def run_backup_mode(self) -> None:
        """Execute comprehensive backup tests."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("Running Backup Mode Tests")
        logger.info("=" * 60)
        logger.info("")

        # TODO: Implement backup tests
        logger.warning("Backup tests not yet implemented in new architecture")

    def run_remove_mode(self) -> None:
        """Execute comprehensive remove tests."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("Running Remove Mode Tests")
        logger.info("=" * 60)
        logger.info("")

        # TODO: Implement remove tests
        logger.warning("Remove tests not yet implemented in new architecture")

    def run_migrate_mode(self) -> None:
        """Execute migration tests."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("Running Migrate Mode Tests")
        logger.info("=" * 60)
        logger.info("")

        # TODO: Implement migrate tests
        logger.warning("Migrate tests not yet implemented in new architecture")

    def run_upgrade_mode(self) -> None:
        """Execute upgrade functionality tests."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("Running Upgrade Mode Tests")
        logger.info("=" * 60)
        logger.info("")

        # TODO: Implement upgrade tests
        logger.warning("Upgrade tests not yet implemented in new architecture")

    def _test_install(
        self, app_name: str, is_catalog: bool = True, url: str | None = None
    ) -> None:
        """Test app installation with validation.

        Args:
            app_name: Name of app to install
            is_catalog: Whether to install from catalog
            url: GitHub URL if installing from URL
        """
        operation_id = None
        if self.benchmark:
            operation_id = self.benchmark.start_operation(
                f"install_{app_name}",
                metadata={
                    "app": app_name,
                    "source": "catalog" if is_catalog else "url",
                },
            )

        # Execute install
        if is_catalog:
            result = run_cli("install", app_name)
        else:
            result = run_cli("install", url or app_name)

        success = result.returncode == 0

        # End benchmark timing
        if self.benchmark and operation_id:
            self.benchmark.end_operation(operation_id)

        # Validate installation
        errors = []
        if success:
            # Load app config
            config = self._load_app_config(app_name)
            if not config:
                errors.append(f"Failed to load config for {app_name}")
            else:
                # Create validators for this app
                appimage_validator = AppImageValidator(app_name)
                desktop_validator = DesktopValidator(app_name)
                icon_validator = IconValidator(app_name)
                config_validator = ConfigValidator(app_name)

                # Validate AppImage
                appimage_result = appimage_validator.validate(
                    "install", config=config
                )
                if not appimage_result.all_passed():
                    errors.extend(appimage_result.errors)

                # Validate desktop entry
                desktop_result = desktop_validator.validate(
                    "install", config=config
                )
                if not desktop_result.all_passed():
                    errors.extend(desktop_result.errors)

                # Validate icon
                icon_result = icon_validator.validate("install", config=config)
                if not icon_result.all_passed():
                    errors.extend(icon_result.errors)

                # Validate config
                config_result = config_validator.validate("install")
                if not config_result.all_passed():
                    errors.extend(config_result.errors)

        # Record result
        self._record(
            f"{app_name} install", success and len(errors) == 0, errors
        )

    def _test_update(self, app_name: str) -> None:
        """Test app update with validation.

        Args:
            app_name: Name of app to update
        """
        # Set old version to trigger update
        logger.info(
            "Setting %s to old version 0.1.0 for update test", app_name
        )
        set_version(app_name, "0.1.0")

        operation_id = None
        if self.benchmark:
            operation_id = self.benchmark.start_operation(
                f"update_{app_name}", metadata={"app": app_name}
            )

        # Execute update
        result = run_cli("update", app_name)
        success = result.returncode == 0

        # End benchmark timing
        if self.benchmark and operation_id:
            self.benchmark.end_operation(operation_id)

        # Validate update
        errors = []
        if success:
            # Load app config
            config = self._load_app_config(app_name)
            if not config:
                errors.append(f"Failed to load config for {app_name}")
            else:
                # Create validators for this app
                appimage_validator = AppImageValidator(app_name)
                config_validator = ConfigValidator(app_name)

                # Validate AppImage
                appimage_result = appimage_validator.validate(
                    "update", config=config
                )
                if not appimage_result.all_passed():
                    errors.extend(appimage_result.errors)

                # Validate config
                config_result = config_validator.validate("update")
                if not config_result.all_passed():
                    errors.extend(config_result.errors)

        # Record result
        self._record(
            f"{app_name} update", success and len(errors) == 0, errors
        )

    def _record(
        self, test_name: str, success: bool, errors: list[str] | None = None
    ) -> None:
        """Record test result.

        Args:
            test_name: Name of the test
            success: Whether the test passed
            errors: List of error messages
        """
        errors = errors or []

        if success and not errors:
            self.passed += 1
            logger.info("✓ %s - PASSED", test_name)
        else:
            self.failed += 1
            logger.error("✗ %s - FAILED", test_name)
            for error in errors:
                logger.error("  - %s", error)

        self.results.append(
            {"test": test_name, "success": success, "errors": errors}
        )

    def _load_app_config(self, app_name: str) -> dict | None:
        """Load app configuration from JSON file.

        Args:
            app_name: Name of the app

        Returns:
            Config dict or None if not found
        """
        config_path = self.config_dir / "apps" / f"{app_name}.json"
        if not config_path.exists():
            return None

        try:
            return orjson.loads(config_path.read_bytes())
        except Exception as e:
            logger.error("Failed to load config for %s: %s", app_name, e)
            return None

    def print_summary(self) -> None:
        """Print test execution summary."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("Test Summary")
        logger.info("=" * 60)
        logger.info("Total:    %d", self.passed + self.failed)
        logger.info("Passed:   %d", self.passed)
        logger.info("Failed:   %d", self.failed)
        logger.info("Warnings: %d", self.warnings)
        logger.info("=" * 60)

        if self.benchmark:
            logger.info("")
            logger.info("Benchmark statistics available")
            logger.info(
                "Use generate_json_report() or generate_markdown_report() "
                "to export"
            )

    def generate_json_report(self, output_path: Path) -> None:
        """Generate JSON benchmark report.

        Args:
            output_path: Path to save JSON report
        """
        if not self.benchmark:
            logger.warning(
                "Benchmarking was not enabled, cannot generate report"
            )
            return

        report = self.benchmark.generate_report()
        generate_json_report(report, output_path)
        logger.info("JSON report saved to: %s", output_path)

    def generate_markdown_report(self, output_path: Path) -> None:
        """Generate Markdown benchmark report.

        Args:
            output_path: Path to save Markdown report
        """
        if not self.benchmark:
            logger.warning(
                "Benchmarking was not enabled, cannot generate report"
            )
            return

        report = self.benchmark.generate_report()
        generate_markdown_report(report, output_path)
        logger.info("Markdown report saved to: %s", output_path)

    def get_report_status(self, version: str | None = None) -> dict | None:
        """Get report status for a specific version.

        Args:
            version: Version to get status for (None for latest)

        Returns:
            Report status dict or None if not found
        """
        # TODO: Implement report status retrieval
        logger.warning("Report status retrieval not yet implemented")
        return None
