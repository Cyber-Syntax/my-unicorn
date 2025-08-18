"""Tests for CheckOnlyUpdateStrategy: validate_inputs and execute logic."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.strategies.update import UpdateContext, UpdateResult
from my_unicorn.strategies.update_check_only import CheckOnlyUpdateStrategy
from my_unicorn.update import UpdateInfo


@pytest.fixture
def context_and_strategy():
    """Fixture for CheckOnlyUpdateStrategy and mocked UpdateContext."""
    config_manager = MagicMock()
    update_manager = MagicMock()
    strategy = CheckOnlyUpdateStrategy()
    return config_manager, update_manager, strategy


def make_update_info(app_name, has_update, current_version="1.0", latest_version="1.0"):
    """Helper to create UpdateInfo objects."""
    info = MagicMock(spec=UpdateInfo)
    info.app_name = app_name
    info.has_update = has_update
    info.current_version = current_version
    info.latest_version = latest_version
    return info


def test_validate_inputs_all_valid(context_and_strategy):
    """Test validate_inputs with all valid app names."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    context = UpdateContext(
        app_names=["AppOne", "AppTwo"],
        check_only=True,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    assert strategy.validate_inputs(context)
    assert context.app_names == ["AppOne", "AppTwo"]


def test_validate_inputs_some_invalid(context_and_strategy, capsys):
    """Test validate_inputs with some invalid app names."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    context = UpdateContext(
        app_names=["AppOne", "NotInstalled"],
        check_only=True,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    assert strategy.validate_inputs(context)
    assert context.app_names == ["AppOne"]
    captured = capsys.readouterr()
    assert "❌ Apps not installed:" in captured.out
    assert "NotInstalled" in captured.out


def test_validate_inputs_all_invalid(context_and_strategy, capsys):
    """Test validate_inputs with all invalid app names."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    context = UpdateContext(
        app_names=["MissingApp"],
        check_only=True,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    assert not strategy.validate_inputs(context)
    captured = capsys.readouterr()
    assert "No valid apps to check." in captured.out


from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_execute_no_apps(context_and_strategy, capsys):
    """Test execute returns empty result when no apps are installed."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = []
    update_manager.check_all_updates = AsyncMock(return_value=[])
    context = UpdateContext(
        app_names=[],
        check_only=True,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert result.success
    assert result.update_infos == []
    assert result.message == "No apps to check"
    captured = capsys.readouterr()
    assert "No installed apps found to check." in captured.out


@pytest.mark.asyncio
async def test_execute_all_up_to_date(context_and_strategy, capsys):
    """Test execute returns correct result when all apps are up to date."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    update_manager.check_all_updates = AsyncMock(
        return_value=[
            make_update_info("AppOne", False, "1.0", "1.0"),
            make_update_info("AppTwo", False, "2.0", "2.0"),
        ]
    )
    context = UpdateContext(
        app_names=["AppOne", "AppTwo"],
        check_only=True,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert result.success
    assert result.updated_apps == []
    assert result.up_to_date_apps == ["AppOne", "AppTwo"]
    assert result.message == "All 2 app(s) are up to date"
    captured = capsys.readouterr()
    assert "Up to date" in captured.out


@pytest.mark.asyncio
async def test_execute_some_updates(context_and_strategy, capsys):
    """Test execute returns correct result when some apps have updates."""
    config_manager, update_manager, strategy = context_and_strategy
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    update_manager.check_all_updates = AsyncMock(
        return_value=[
            make_update_info("AppOne", True, "1.0", "2.0"),
            make_update_info("AppTwo", False, "2.0", "2.0"),
        ]
    )
    context = UpdateContext(
        app_names=["AppOne", "AppTwo"],
        check_only=True,
        config_manager=config_manager,
        update_manager=update_manager,
    )
    result = await strategy.execute(context)
    assert isinstance(result, UpdateResult)
    assert result.success
    assert result.updated_apps == []
    assert result.up_to_date_apps == ["AppTwo"]
    assert "Found 1 update(s) available out of 2 app(s) checked" in result.message
    captured = capsys.readouterr()
    assert "Update available" in captured.out
    assert "Up to date" in captured.out
    assert "Run 'my-unicorn update' to install updates." in captured.out
