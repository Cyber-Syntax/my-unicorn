"""Tests for UpdateStrategyFactory: create_strategy and get_strategy_name."""

from my_unicorn.strategies.update import UpdateContext
from my_unicorn.strategies.update_all import UpdateAllAppsStrategy
from my_unicorn.strategies.update_check_only import CheckOnlyUpdateStrategy
from my_unicorn.strategies.update_factory import UpdateStrategyFactory
from my_unicorn.strategies.update_specific import UpdateSpecificAppsStrategy


class DummyConfigManager:
    def list_installed_apps(self):
        return ["AppOne", "AppTwo"]


class DummyUpdateManager:
    pass


def make_context(app_names=None, check_only=False):
    return UpdateContext(
        app_names=app_names,
        check_only=check_only,
        config_manager=DummyConfigManager(),
        update_manager=DummyUpdateManager(),
    )


def test_create_strategy_check_only():
    """Test factory returns CheckOnlyUpdateStrategy for check_only context."""
    context = make_context(app_names=None, check_only=True)
    strategy = UpdateStrategyFactory.create_strategy(context)
    assert isinstance(strategy, CheckOnlyUpdateStrategy)


def test_create_strategy_specific_apps():
    """Test factory returns UpdateSpecificAppsStrategy for app_names context."""
    context = make_context(app_names=["AppOne", "AppTwo"], check_only=False)
    strategy = UpdateStrategyFactory.create_strategy(context)
    assert isinstance(strategy, UpdateSpecificAppsStrategy)


def test_create_strategy_all_apps():
    """Test factory returns UpdateAllAppsStrategy for context with neither check_only nor app_names."""
    context = make_context(app_names=None, check_only=False)
    strategy = UpdateStrategyFactory.create_strategy(context)
    assert isinstance(strategy, UpdateAllAppsStrategy)


def test_get_strategy_name_check_only():
    """Test get_strategy_name returns correct name for check_only context."""
    context = make_context(app_names=None, check_only=True)
    name = UpdateStrategyFactory.get_strategy_name(context)
    assert name == "Check Only"


def test_get_strategy_name_specific_apps():
    """Test get_strategy_name returns correct name for app_names context."""
    context = make_context(app_names=["AppOne", "AppTwo"], check_only=False)
    name = UpdateStrategyFactory.get_strategy_name(context)
    assert name == "Update Specific Apps (2 app(s))"


def test_get_strategy_name_all_apps():
    """Test get_strategy_name returns correct name for context with neither check_only nor app_names."""
    context = make_context(app_names=None, check_only=False)
    name = UpdateStrategyFactory.get_strategy_name(context)
    assert name == "Update All Apps"
