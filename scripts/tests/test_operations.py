"""Test operation functions for my-unicorn testing.

This module contains individual test functions for install, update,
backup, and other operations with optional diagnostic validation.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import logging
from pathlib import Path

import orjson
from benchmark import BenchmarkCollector, BenchmarkTimer
from cli_runner import run_cli
from config import load_app_config, set_version
from diagnostic import DiagnosticValidator

logger = logging.getLogger("my-unicorn-test")

# Configuration constants
CONFIG_DIR = Path.home() / ".config" / "my-unicorn"
TEST_VERSION = "0.1.0"


def test_url_install(app_name: str, url: str) -> bool:
    """Test installing app via URL.

    Args:
        app_name: Name of the app (for logging)
        url: GitHub URL to install from

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing %s URL install", app_name)
    result = run_cli("install", url)
    return result.returncode == 0


def test_catalog_install(*app_names: str) -> bool:
    """Test installing apps from catalog.

    Args:
        *app_names: Names of apps to install

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing catalog install: %s", ", ".join(app_names))
    result = run_cli("install", *app_names)
    return result.returncode == 0


def test_update(*app_names: str) -> bool:
    """Test updating apps.

    Args:
        *app_names: Names of apps to update

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing update for: %s", ", ".join(app_names))

    # Set old versions for update test
    for app_name in app_names:
        set_version(app_name, TEST_VERSION)

    result = run_cli("update", *app_names)
    return result.returncode == 0


def test_backup(app_name: str) -> bool:
    """Test backup creation.

    Args:
        app_name: Name of the app

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing backup for: %s", app_name)
    result = run_cli("backup", app_name)
    return result.returncode == 0


def test_backup_list(app_name: str) -> bool:
    """Test listing backups.

    Args:
        app_name: Name of the app

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing backup list for: %s", app_name)
    result = run_cli("backup", app_name, "--list-backups")
    return result.returncode == 0


def test_backup_restore(app_name: str) -> bool:
    """Test backup restore.

    Args:
        app_name: Name of the app

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing backup restore for: %s", app_name)
    result = run_cli("backup", app_name, "--restore-last")
    return result.returncode == 0


def test_migrate() -> bool:
    """Test configuration migration.

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing migrate command")
    result = run_cli("migrate", "--dry-run")
    return result.returncode == 0


def test_upgrade_check() -> bool:
    """Test upgrade check functionality.

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing upgrade --check-only")
    result = run_cli("upgrade", "--check-only")
    return result.returncode == 0


def test_remove_with_verification(
    app_name: str, validator: DiagnosticValidator
) -> tuple[bool, list[str]]:
    """Test removing app with diagnostic verification.

    Args:
        app_name: Name of the app to remove
        validator: DiagnosticValidator instance

    Returns:
        Tuple of (success, errors)
    """
    logger.info("Testing remove for: %s", app_name)

    # Get owner/repo before removal for cache validation (v2 structure)
    config = load_app_config(app_name)
    owner = None
    repo = None
    if config:
        source_type = config.get("source")  # String in v2
        if source_type == "url":
            # Get from overrides.source
            overrides_source = config.get("overrides", {}).get("source", {})
            if (
                isinstance(overrides_source, dict)
                and overrides_source.get("type") == "github"
            ):
                owner = overrides_source.get("owner")
                repo = overrides_source.get("repo")
        elif source_type == "catalog":
            # Get from catalog file
            catalog_ref = config.get("catalog_ref")
            if catalog_ref:
                catalog_file = (
                    CONFIG_DIR.parent / "catalog" / f"{catalog_ref}.json"
                )
                if catalog_file.exists():
                    try:
                        catalog_data = orjson.loads(catalog_file.read_bytes())
                        catalog_source = catalog_data.get("source", {})
                        if (
                            isinstance(catalog_source, dict)
                            and catalog_source.get("type") == "github"
                        ):
                            owner = catalog_source.get("owner")
                            repo = catalog_source.get("repo")
                    except Exception:
                        logger.exception(
                            "Failed to load catalog for cache validation"
                        )

    # Execute remove
    result = run_cli("remove", app_name)
    success = result.returncode == 0

    # Run removal diagnostics
    removal_report = validator.validate_removal(app_name, owner, repo)

    errors = removal_report.errors.copy()
    if removal_report.warnings:
        logger.warning(
            "Warnings during removal validation: %s",
            ", ".join(removal_report.warnings),
        )

    return success and removal_report.all_passed(), errors


def test_install_with_diagnostics(
    app_name: str,
    url_or_name: str,
    validator: DiagnosticValidator,
    is_catalog: bool = False,
    benchmark: BenchmarkCollector | None = None,
    operation_name: str | None = None,
) -> tuple[bool, list[str]]:
    """Install app and validate complete system state.

    Args:
        app_name: Name of the app
        url_or_name: GitHub URL or catalog name
        validator: DiagnosticValidator instance
        is_catalog: True if installing from catalog
        benchmark: Optional benchmark collector
        operation_name: Optional custom operation name for benchmarking

    Returns:
        Tuple of (success, errors)
    """
    install_type = "catalog" if is_catalog else "URL"
    logger.info("Testing %s %s install", app_name, install_type)

    # Execute install with optional benchmarking
    if benchmark:
        bench_name = operation_name or f"install_{app_name}"
        with BenchmarkTimer(benchmark, bench_name) as timer:
            result, net_stats = run_cli(
                "install", url_or_name, track_network=True
            )
            # Record network time and breakdown
            if net_stats.get("network_time_ms", 0) > 0:
                timer.record_network(
                    net_stats["network_time_ms"],
                    net_stats.get("total_bytes", 0),
                )
            timer.record_breakdown("cli_execution", result.returncode)
    else:
        result = run_cli("install", url_or_name)

    success = result.returncode == 0

    # Run diagnostics
    app_report = validator.validate_app_state(app_name)
    cache_report = validator.validate_cache_state(app_name)

    errors = app_report.errors + cache_report.errors

    if app_report.warnings:
        logger.warning(
            "App validation warnings: %s", ", ".join(app_report.warnings)
        )

    if cache_report.warnings:
        logger.warning(
            "Cache validation warnings: %s", ", ".join(cache_report.warnings)
        )

    return success and app_report.all_passed(), errors


def test_update_with_diagnostics(
    app_names: list[str],
    validator: DiagnosticValidator,
    benchmark: BenchmarkCollector | None = None,
    operation_name: str | None = None,
) -> tuple[bool, list[str]]:
    """Update apps and validate system state.

    Args:
        app_names: Names of apps to update
        validator: DiagnosticValidator instance
        benchmark: Optional benchmark collector
        operation_name: Optional custom operation name for benchmarking

    Returns:
        Tuple of (success, errors)
    """
    logger.info("Testing update for: %s", ", ".join(app_names))

    # Set old versions
    for app_name in app_names:
        set_version(app_name, TEST_VERSION)

    # Execute update
    if benchmark:
        bench_name = operation_name or "update_multiple"
        with BenchmarkTimer(benchmark, bench_name) as timer:
            result, net_stats = run_cli(
                "update", *app_names, track_network=True
            )
            # Record network time and breakdown
            if net_stats.get("network_time_ms", 0) > 0:
                timer.record_network(
                    net_stats["network_time_ms"],
                    net_stats.get("total_bytes", 0),
                )
            timer.record_breakdown("cli_execution", result.returncode)
    else:
        result = run_cli("update", *app_names)

    success = result.returncode == 0

    # Validate each updated app
    all_errors = []
    for app_name in app_names:
        app_report = validator.validate_app_state(app_name)
        all_errors.extend(app_report.errors)

    return success and len(all_errors) == 0, all_errors
