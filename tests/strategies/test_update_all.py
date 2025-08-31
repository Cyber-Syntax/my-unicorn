"""Tests for UpdateAllAppsStrategy: validate_inputs and execute logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.strategies.update import UpdateContext, UpdateResult
from my_unicorn.strategies.update_all import UpdateAllAppsStrategy
from my_unicorn.update import UpdateInfo


@pytest.fixture
def context_and_strategy():
    """Fixture for UpdateAllAppsStrategy and mocked UpdateContext."""
    config_manager = MagicMock()
    update_manager = MagicMock()
    strategy = UpdateAllAppsStrategy()
    return config_manager, update_manager, strategy


def make_update_info(app_name, has_update, current_version="1.0", latest_version="1.0"):
    """Helper to create UpdateInfo objects."""
    info = MagicMock(spec=UpdateInfo)
    info.app_name = app_name
    info.has_update = has_update
    info.current_version = current_version
    info.latest_version = latest_version
    return info


def test_validate_inputs_no_installed_apps(context_and_strategy, capsys):
    """Test validate_inputs returns False when no apps are installed."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = []
    context = UpdateContext(
        app_names=None,
        check_only=False,
        refresh_cache=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = strategy.validate_inputs(context)
    assert not result
    captured = capsys.readouterr()
    assert "No installed apps found to update." in captured.out


def test_validate_inputs_with_installed_apps(context_and_strategy):
    """Test validate_inputs returns True when apps are installed."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    context = UpdateContext(
        app_names=None,
        check_only=False,
        refresh_cache=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = strategy.validate_inputs(context)
    assert result


def test_validate_inputs_warns_on_app_names_and_check_only(context_and_strategy, caplog):
    """Test validate_inputs warns if app_names or check_only are set."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne"]
    context = UpdateContext(
        app_names=["AppOne"],
        check_only=True,
        refresh_cache=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    with caplog.at_level("WARNING"):
        result = strategy.validate_inputs(context)
    assert result
    assert "app_names specified but will be ignored" in caplog.text
    assert "check_only flag should not be used" in caplog.text


@pytest.mark.asyncio
async def test_execute_all_up_to_date(context_and_strategy, capsys):
    """Test execute returns correct result when all apps are up to date."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    update_manager.check_all_updates_with_progress = AsyncMock(
        return_value=[
            make_update_info("AppOne", False, "1.0", "1.0"),
            make_update_info("AppTwo", False, "2.0", "2.0"),
        ]
    )
    update_manager.update_multiple_apps = AsyncMock(return_value={})
    context = UpdateContext(
        app_names=None,
        check_only=False,
        refresh_cache=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert result.success
    assert result.updated_apps == []
    assert result.up_to_date_apps == ["AppOne", "AppTwo"]
    assert "All apps are up to date!" in result.message
    captured = capsys.readouterr()
    assert "already up to date" in captured.out
    assert "All apps are up to date!" in captured.out


@pytest.mark.asyncio
async def test_execute_some_updated(context_and_strategy, capsys):
    """Test execute returns correct result when some apps are updated."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    update_manager.check_all_updates_with_progress = AsyncMock(
        return_value=[
            make_update_info("AppOne", True, "1.0", "2.0"),
            make_update_info("AppTwo", False, "2.0", "2.0"),
        ]
    )
    update_manager.update_multiple_apps = AsyncMock(return_value={"AppOne": True})
    context = UpdateContext(
        app_names=None,
        check_only=False,
        refresh_cache=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert result.success
    assert result.updated_apps == ["AppOne"]
    assert result.failed_apps == []
    assert result.up_to_date_apps == ["AppTwo"]
    assert "Successfully updated 1 out of 2 app(s)" in result.message
    captured = capsys.readouterr()
    assert "Successfully updated 1 out of 2 app(s)" in result.message
    assert "✅ 1 app(s) already up to date" in captured.out
    assert "AppOne: 1.0 → 2.0" in captured.out


@pytest.mark.asyncio
async def test_execute_some_failed(context_and_strategy, capsys):
    """Test execute returns correct result when some apps fail to update."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    update_manager.check_all_updates_with_progress = AsyncMock(
        return_value=[
            make_update_info("AppOne", True, "1.0", "2.0"),
            make_update_info("AppTwo", True, "2.0", "3.0"),
        ]
    )
    update_manager.update_multiple_apps = AsyncMock(
        return_value={"AppOne": True, "AppTwo": False}
    )
    context = UpdateContext(
        app_names=None,
        check_only=False,
        refresh_cache=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert not result.success
    assert result.updated_apps == ["AppOne"]
    assert result.failed_apps == ["AppTwo"]
    assert "Updated 1 app(s), 1 failed out of 2 checked" in result.message
    captured = capsys.readouterr()
    assert "AppOne: 1.0 → 2.0" in captured.out
    assert "AppTwo: 2.0 → 3.0" in captured.out
