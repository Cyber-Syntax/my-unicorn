"""Tests for UpdateStrategy base class and helpers."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.strategies.update import UpdateContext, UpdateStrategy


class DummyUpdateStrategy(UpdateStrategy):
    """Minimal concrete subclass for testing."""

    async def execute(self, context: UpdateContext):
        return "executed"

    def validate_inputs(self, context: UpdateContext) -> bool:
        return True


def test_validate_installed_apps_case_insensitive():
    """Test _validate_installed_apps matches installed apps case-insensitively."""
    config_manager = MagicMock()
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo", "AnotherApp"]
    strategy = DummyUpdateStrategy()
    valid, invalid = strategy._validate_installed_apps(
        ["appone", "APPtwo", "missing"], config_manager
    )
    assert set(valid) == {"AppOne", "AppTwo"}
    assert invalid == ["missing"]


def test_validate_installed_apps_all_invalid():
    """Test _validate_installed_apps returns all invalid if none match."""
    config_manager = MagicMock()
    config_manager.list_installed_apps.return_value = ["AppOne", "AppTwo"]
    strategy = DummyUpdateStrategy()
    valid, invalid = strategy._validate_installed_apps(["notfound", "missing"], config_manager)
    assert valid == []
    assert set(invalid) == {"notfound", "missing"}


def test_print_invalid_apps_suggestions(capsys):
    """Test _print_invalid_apps prints suggestions for similar installed apps."""
    strategy = DummyUpdateStrategy()
    invalid_apps = ["AppOn", "AppTw"]
    installed_apps = ["AppOne", "AppTwo", "AnotherApp"]
    strategy._print_invalid_apps(invalid_apps, installed_apps)
    captured = capsys.readouterr()
    assert "❌ Apps not installed:" in captured.out
    assert "AppOn (did you mean: AppOne?)" in captured.out
    assert "AppTw (did you mean: AppTwo?)" in captured.out


def test_print_invalid_apps_no_suggestions(capsys):
    """Test _print_invalid_apps prints without suggestions if none found."""
    strategy = DummyUpdateStrategy()
    invalid_apps = ["Xyz"]
    installed_apps = ["AppOne", "AppTwo"]
    strategy._print_invalid_apps(invalid_apps, installed_apps)
    captured = capsys.readouterr()
    assert "❌ Apps not installed:" in captured.out
    assert "Xyz" in captured.out
    assert "(did you mean:" not in captured.out


def test_abstract_methods_raise():
    """Test abstract methods must be implemented."""

    class IncompleteStrategy(UpdateStrategy):
        pass

    with pytest.raises(TypeError):
        IncompleteStrategy()
