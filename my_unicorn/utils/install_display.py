"""Install-specific presentation helpers for CLI output.

This module provides helper functions for printing installation-related
summaries and messages. It intentionally focuses on install flows to be
consistent with other display helpers (e.g., `update_displays.py`).
"""

from typing import Any


def print_install_summary(results: list[dict[str, Any]]) -> None:
    """Print an installation summary to stdout.

    This mirrors the previous `print_installation_summary` behavior but
    the function name better communicates that this is install-specific.
    """
    if not results:
        print("No installations completed")
        return

    already_installed = [
        r for r in results if r.get("status") == "already_installed"
    ]
    newly_installed = [
        r
        for r in results
        if r.get("success", False) and r.get("status") != "already_installed"
    ]
    failed = [r for r in results if not r.get("success", False)]

    total = len(results)

    if len(already_installed) == total:
        print(f"✅ All {total} specified app(s) are already installed:")
        for result in already_installed:
            print(f"   • {result.get('name', 'Unknown')}")
        return

    print("\n📦 Installation Summary:")
    print("-" * 50)

    for result in results:
        app_name = result.get("name", "Unknown")
        if result.get("success", False):
            if result.get("status") == "already_installed":
                print(f"{app_name:<25} ℹ️  Already installed")
            else:
                version = result.get("version", "")
                if version:
                    print(f"{app_name:<25} ✅ {version}")
                else:
                    print(f"{app_name:<25} ✅ Installed")
        else:
            print(f"{app_name:<25} ❌ Installation failed")
            error = result.get("error", "Unknown error")
            print(f"{'':>25}    → {error}")

    print()
    if newly_installed:
        print(f"🎉 Successfully installed {len(newly_installed)} app(s)")
    if already_installed:
        print(f"ℹ️  {len(already_installed)} app(s) already installed")
    if failed:
        print(f"❌ {len(failed)} app(s) failed to install")
