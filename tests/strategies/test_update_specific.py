"""Tests for UpdateSpecificAppsStrategy: validate_inputs and execute logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.strategies.update import UpdateContext, UpdateResult
from my_unicorn.strategies.update_specific import UpdateSpecificAppsStrategy
from my_unicorn.update import UpdateInfo


def make_update_info(app_name, has_update, current_version="1.0", latest_version="1.0"):
    info = MagicMock(spec=UpdateInfo)
    info.app_name = app_name
    info.has_update = has_update
    info.current_version = current_version
    info.latest_version = latest_version
    return info


@pytest.fixture
def context_and_strategy():
    """Fixture for UpdateSpecificAppsStrategy and mocked UpdateContext."""
    config_manager = MagicMock()
    update_manager = MagicMock()
    strategy = UpdateSpecificAppsStrategy()
    return config_manager, update_manager, strategy


def test_validate_inputs_no_apps(context_and_strategy, capsys):
    """Test validate_inputs returns False when no apps specified."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    context = UpdateContext(
        refresh_cache=False,
        app_names=None,
        check_only=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = strategy.validate_inputs(context)
    assert not result
    captured = capsys.readouterr()
    assert "No apps specified for update" in captured.out


def test_validate_inputs_invalid_apps(context_and_strategy, capsys):
    """Test validate_inputs returns False when all apps are invalid."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    context = UpdateContext(
        refresh_cache=False,
        app_names=["MissingApp"],
        check_only=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = strategy.validate_inputs(context)
    assert not result
    captured = capsys.readouterr()
    assert "No valid apps to update." in captured.out


def test_validate_inputs_some_valid(context_and_strategy, capsys):
    """Test validate_inputs returns True and updates app_names with valid apps."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    context = UpdateContext(
        refresh_cache=False,
        app_names=["AppOne", "MissingApp"],
        check_only=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = strategy.validate_inputs(context)
    assert result
    assert context.app_names == ["AppOne"]
    captured = capsys.readouterr()
    assert "MissingApp" in captured.out


def test_validate_inputs_check_only_warns(context_and_strategy, caplog):
    """Test validate_inputs warns if check_only is set."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne"]
    context = UpdateContext(
        refresh_cache=False,
        app_names=["AppOne"],
        check_only=True,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    with caplog.at_level("WARNING"):
        result = strategy.validate_inputs(context)
    assert result
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
        refresh_cache=False,
        app_names=["AppOne", "AppTwo"],
        check_only=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert result.success
    assert result.updated_apps == []
    assert result.up_to_date_apps == ["AppOne", "AppTwo"]
    assert "All specified apps are up to date!" in result.message
    captured = capsys.readouterr()
    assert "already up to date" in captured.out
    assert "All specified apps are up to date!" in captured.out


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
        refresh_cache=False,
        app_names=["AppOne", "AppTwo"],
        check_only=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert result.success
    assert result.updated_apps == ["AppOne"]
    assert result.failed_apps == []
    assert result.up_to_date_apps == ["AppTwo"]
    assert "Successfully updated 1 app(s)" in result.message
    captured = capsys.readouterr()
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
        refresh_cache=False,
        app_names=["AppOne", "AppTwo"],
        check_only=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert not result.success
    assert result.updated_apps == ["AppOne"]
    assert result.failed_apps == ["AppTwo"]
    assert "Updated 1 app(s), 1 failed" in result.message
    captured = capsys.readouterr()
    assert "AppOne: 1.0 → 2.0" in captured.out
    assert "AppTwo: 2.0 → 3.0" in captured.out


@pytest.mark.asyncio
async def test_execute_check_updates_error(context_and_strategy, capsys):
    """Test execute returns error result when check_all_updates returns empty."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne"]
    update_manager.check_all_updates_with_progress = AsyncMock(return_value=[])
    update_manager.update_multiple_apps = AsyncMock(return_value={})
    context = UpdateContext(
        refresh_cache=False,
        app_names=["AppOne"],
        check_only=False,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert not result.success
    assert result.failed_apps == ["AppOne"]
    assert "Failed to check updates for specified apps" in result.message
