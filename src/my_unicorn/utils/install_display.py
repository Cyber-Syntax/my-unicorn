"""Install-specific presentation helpers for CLI output.

This module provides helper functions for printing installation-related
summaries and messages. It intentionally focuses on install flows to be
consistent with other display helpers (e.g., `update_displays.py`).
"""

from typing import Any

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def _categorize_results(results: list[dict[str, Any]]) -> dict[str, list]:
    """Categorize installation results by status."""
    already_installed = [
        r for r in results if r.get("status") == "already_installed"
    ]
    newly_installed = [
        r
        for r in results
        if r.get("success", False) and r.get("status") != "already_installed"
    ]
    failed = [r for r in results if not r.get("success", False)]
    with_warnings = [r for r in newly_installed if r.get("warning")]

    return {
        "already_installed": already_installed,
        "newly_installed": newly_installed,
        "failed": failed,
        "with_warnings": with_warnings,
    }


def _print_all_already_installed(results: list[dict[str, Any]]) -> None:
    """Print message when all apps are already installed."""
    logger.info(
        "✅ All %s specified app(s) are already installed:", len(results)
    )
    for result in results:
        logger.info("   • %s", result.get("name", "Unknown"))


def _print_result_line(result: dict[str, Any]) -> None:
    """Print a single installation result line."""
    app_name = result.get("name", "Unknown")

    if not result.get("success", False):
        logger.info("%-25s ❌ Installation failed", app_name)
        error = result.get("error", "Unknown error")
        logger.info("%-25s    → %s", "", error)
        return

    if result.get("status") == "already_installed":
        logger.info("%-25s ℹ️  Already installed", app_name)  # noqa: RUF001
        return

    version = result.get("version", "")
    status_msg = f"✅ {version}" if version else "✅ Installed"
    logger.info("%-25s %s", app_name, status_msg)

    if result.get("warning"):
        logger.info("%-25s    ⚠️  %s", "", result["warning"])


def _print_statistics(categories: dict[str, list]) -> None:
    """Print final installation statistics."""
    logger.info("")
    if categories["newly_installed"]:
        count = len(categories["newly_installed"])
        logger.info("🎉 Successfully installed %s app(s)", count)
    if categories["with_warnings"]:
        count = len(categories["with_warnings"])
        logger.info("⚠️  %s app(s) installed with warnings", count)
    if categories["already_installed"]:
        count = len(categories["already_installed"])
        logger.info("ℹ️  %s app(s) already installed", count)  # noqa: RUF001
    if categories["failed"]:
        logger.info(
            "❌ %s app(s) failed to install", len(categories["failed"])
        )


def print_install_summary(results: list[dict[str, Any]]) -> None:
    """Print an installation summary to stdout.

    This mirrors the previous `print_installation_summary` behavior but
    the function name better communicates that this is install-specific.
    """
    if not results:
        logger.info("No installations completed")
        return

    categories = _categorize_results(results)

    if len(categories["already_installed"]) == len(results):
        _print_all_already_installed(results)
        return

    logger.info("")
    logger.info("📦 Installation Summary:")
    logger.info("-" * 50)

    for result in results:
        _print_result_line(result)

    _print_statistics(categories)
