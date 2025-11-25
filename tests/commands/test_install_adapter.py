"""Tests for using CatalogManagerAdapter with install helpers."""

from typing import Any

import pytest

from my_unicorn.commands.install import CatalogManagerAdapter
from my_unicorn.config import config_manager
from my_unicorn.install import InstallHandler


@pytest.mark.asyncio
async def test_check_apps_needing_work_with_adapter():
    """Ensure InstallHandler static check works with CatalogManagerAdapter.

    This guards against passing a CatalogManagerAdapter incorrectly into
    instance methods (which would bind the adapter as self and cause
    attribute errors).
    """
    catalog_adapter = CatalogManagerAdapter(config_manager)

    url_targets = [
        "https://github.com/some/repo/releases/download/app.AppImage"
    ]
    catalog_targets = ["appflowy"]
    install_options: dict[str, Any] = {"force": False}

    # The static impl should accept the adapter directly without raising
    (
        urls_needing,
        catalog_needing,
        already_installed,
    ) = await InstallHandler.check_apps_needing_work_impl(
        catalog_adapter, url_targets, catalog_targets, install_options
    )

    assert isinstance(urls_needing, list)
    assert isinstance(catalog_needing, list)
    assert isinstance(already_installed, list)
