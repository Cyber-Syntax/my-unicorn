"""Install-specific presentation helpers for CLI output.

This module provides helper functions for printing installation-related
summaries and messages. It intentionally focuses on install flows to be
consistent with other display helpers (e.g., `display_update.py`).

Uses print() directly to avoid conflicts with logger context managers
and progress display systems.
"""
# ruff: noqa: T201

from typing import Any


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
    print(f"✅ All {len(results)} specified app(s) are already installed:")
    for result in results:
        print(f"   • {result.get('name', 'Unknown')}")


def _print_result_line(result: dict[str, Any]) -> None:
    """Print a single installation result line."""
    app_name = result.get("name", "Unknown")

    if not result.get("success", False):
        print(f"{app_name:<25} ❌ Installation failed")
        error = result.get("error", "Unknown error")
        print(f"{'':25}    → {error}")
        return

    if result.get("status") == "already_installed":
        print(f"{app_name:<25} ℹ️  Already installed")  # noqa: RUF001
        return

    version = result.get("version", "")
    status_msg = f"✅ {version}" if version else "✅ Installed"
    print(f"{app_name:<25} {status_msg}")

    if result.get("warning"):
        print(f"{'':25}    ⚠️  {result['warning']}")


def _print_statistics(categories: dict[str, list]) -> None:
    """Print final installation statistics."""
    print()
    if categories["newly_installed"]:
        count = len(categories["newly_installed"])
        print(f"🎉 Successfully installed {count} app(s)")
    if categories["with_warnings"]:
        count = len(categories["with_warnings"])
        print(f"⚠️  {count} app(s) installed with warnings")
    if categories["already_installed"]:
        count = len(categories["already_installed"])
        print(f"ℹ️  {count} app(s) already installed")  # noqa: RUF001
    if categories["failed"]:
        print(f"❌ {len(categories['failed'])} app(s) failed to install")


def print_install_summary(results: list[dict[str, Any]]) -> None:
    """Print an installation summary to stdout.

    This mirrors the previous `print_installation_summary` behavior but
    the function name better communicates that this is install-specific.
    """
    if not results:
        print("No installations completed")
        return

    categories = _categorize_results(results)

    if len(categories["already_installed"]) == len(results):
        _print_all_already_installed(results)
        return

    print()
    print("📦 Installation Summary:")
    print("-" * 50)

    for result in results:
        _print_result_line(result)

    _print_statistics(categories)
