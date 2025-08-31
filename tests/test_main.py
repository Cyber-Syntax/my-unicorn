import sys
from unittest.mock import patch

import pytest

from my_unicorn import main


def test_main_normal_run():
    """Test main() calls uvloop.install and uvloop.run with async_main."""
    from unittest.mock import ANY

    with (
        patch("my_unicorn.main.uvloop.install") as mock_install,
        patch("my_unicorn.main.uvloop.run") as mock_run,
        patch("my_unicorn.main.async_main") as mock_async_main,
    ):
        mock_run.side_effect = lambda coro: None  # Simulate normal run
        main.main()
        mock_install.assert_called_once()
        mock_run.assert_called_once_with(ANY)
        # Should not print error or exit


def test_main_keyboard_interrupt(monkeypatch):
    """Test main() handles KeyboardInterrupt and prints cancel message."""
    called = {}

    def fake_run(coro):
        # Properly close the coroutine to avoid RuntimeWarning
        coro.close()
        raise KeyboardInterrupt

    monkeypatch.setattr("my_unicorn.main.uvloop.install", lambda: None)
    monkeypatch.setattr("my_unicorn.main.uvloop.run", fake_run)

    def fake_exit(code):
        called["exit"] = code
        raise SystemExit

    monkeypatch.setattr(sys, "exit", fake_exit)

    with patch("builtins.print") as mock_print:
        with pytest.raises(SystemExit):
            main.main()
        mock_print.assert_any_call("\n⏹️  Operation cancelled by user")
        assert called["exit"] == 1


def test_main_exception(monkeypatch):
    """Test main() handles Exception and prints error message."""
    called = {}

    def fake_run(coro):
        # Properly close the coroutine to avoid RuntimeWarning
        coro.close()
        raise RuntimeError("fail")

    monkeypatch.setattr("my_unicorn.main.uvloop.install", lambda: None)
    monkeypatch.setattr("my_unicorn.main.uvloop.run", fake_run)

    def fake_exit(code):
        called["exit"] = code
        raise SystemExit

    monkeypatch.setattr(sys, "exit", fake_exit)

    with patch("builtins.print") as mock_print:
        with pytest.raises(SystemExit):
            main.main()
        mock_print.assert_any_call("❌ Unexpected error: fail")
        assert called["exit"] == 1
