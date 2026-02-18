"""Tests for TokenHandler command."""

from argparse import Namespace
from unittest.mock import MagicMock, patch

import keyring.errors
import pytest

from my_unicorn.cli.commands.token import TokenHandler


@pytest.mark.asyncio
class TestTokenHandler:
    """Test cases for TokenHandler command."""

    @pytest.fixture
    def token_handler(self) -> TokenHandler:
        """Fixture for TokenHandler with mocked dependencies."""
        config_manager = MagicMock()
        auth_manager = MagicMock()
        auth_manager.token_store = MagicMock()
        update_manager = MagicMock()
        return TokenHandler(
            config_manager=config_manager,
            auth_manager=auth_manager,
            update_manager=update_manager,
        )

    async def test_save_token_valid(
        self, token_handler: TokenHandler, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test saving a valid GitHub token."""
        valid_token = "a" * 40  # Valid legacy format token
        monkeypatch.setattr("getpass.getpass", lambda prompt: valid_token)

        args = Namespace(save=True, remove=False)
        await token_handler.execute(args)

        token_handler.auth_manager.token_store.set.assert_called_once_with(
            valid_token
        )

    async def test_save_token_empty(
        self, token_handler: TokenHandler, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test saving empty token exits gracefully."""
        monkeypatch.setattr("getpass.getpass", lambda prompt: "   ")

        args = Namespace(save=True, remove=False)

        with pytest.raises(SystemExit) as exc_info:
            await token_handler.execute(args)
        assert exc_info.value.code == 1

    async def test_save_token_invalid_format(
        self, token_handler: TokenHandler, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test saving invalid token format exits gracefully."""
        invalid_token = "invalid_token_format"  # noqa: S105
        monkeypatch.setattr("getpass.getpass", lambda prompt: invalid_token)

        args = Namespace(save=True, remove=False)

        with pytest.raises(SystemExit) as exc_info:
            await token_handler.execute(args)
        assert exc_info.value.code == 1

    async def test_save_token_confirmation_mismatch(
        self, token_handler: TokenHandler, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test token confirmation mismatch exits gracefully."""
        valid_token = "a" * 40

        # First call returns token, second call returns different confirmation
        calls = [valid_token, "b" * 40]

        def mock_getpass(prompt: str) -> str:
            return calls.pop(0)

        monkeypatch.setattr("getpass.getpass", mock_getpass)

        args = Namespace(save=True, remove=False)

        with pytest.raises(SystemExit) as exc_info:
            await token_handler.execute(args)
        assert exc_info.value.code == 1

    async def test_save_token_keyboard_interrupt(
        self, token_handler: TokenHandler, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test handling KeyboardInterrupt during token input."""

        def mock_getpass(prompt: str) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr("getpass.getpass", mock_getpass)

        args = Namespace(save=True, remove=False)

        with pytest.raises(SystemExit) as exc_info:
            await token_handler.execute(args)
        assert exc_info.value.code == 1

    async def test_save_token_exceeds_max_length(
        self, token_handler: TokenHandler, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test token exceeding maximum length exits gracefully."""
        # Create a token longer than MAX_TOKEN_LENGTH (255)
        long_token = "a" * 300
        monkeypatch.setattr("getpass.getpass", lambda prompt: long_token)

        args = Namespace(save=True, remove=False)

        with pytest.raises(SystemExit) as exc_info:
            await token_handler.execute(args)
        assert exc_info.value.code == 1

    async def test_remove_token_success(
        self, token_handler: TokenHandler
    ) -> None:
        """Test removing token successfully."""
        args = Namespace(save=False, remove=True)

        await token_handler.execute(args)

        token_handler.auth_manager.token_store.delete.assert_called_once()

    async def test_remove_token_not_found(
        self, token_handler: TokenHandler
    ) -> None:
        """Test removing token when none exists handles gracefully."""

        token_handler.auth_manager.token_store.delete.side_effect = (
            keyring.errors.PasswordDeleteError("No such password!")
        )

        args = Namespace(save=False, remove=True)

        # Should not raise exception, just log warning
        await token_handler.execute(args)

        token_handler.auth_manager.token_store.delete.assert_called_once()

    async def test_remove_token_failure(
        self, token_handler: TokenHandler
    ) -> None:
        """Test handling token removal failure."""
        token_handler.auth_manager.token_store.delete.side_effect = Exception(
            "Delete failed"
        )

        args = Namespace(save=False, remove=True)

        with pytest.raises(Exception, match="Delete failed"):
            await token_handler.execute(args)

    async def test_save_token_with_valid_prefixed_token(
        self, token_handler: TokenHandler, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test saving a valid prefixed GitHub token (ghp_)."""
        valid_token = "ghp_" + "a" * 40  # Valid prefixed token
        monkeypatch.setattr("getpass.getpass", lambda prompt: valid_token)

        args = Namespace(save=True, remove=False)
        await token_handler.execute(args)

        token_handler.auth_manager.token_store.set.assert_called_once_with(
            valid_token
        )

    @patch("my_unicorn.cli.commands.token.logger")
    async def test_save_token_logs_success(
        self,
        mock_logger: MagicMock,
        token_handler: TokenHandler,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that successful token save logs appropriate message."""
        valid_token = "a" * 40
        monkeypatch.setattr("getpass.getpass", lambda prompt: valid_token)

        args = Namespace(save=True, remove=False)
        await token_handler.execute(args)

        mock_logger.info.assert_any_call("GitHub token saved successfully.")

    @patch("my_unicorn.cli.commands.token.logger")
    async def test_remove_token_logs_success(
        self, mock_logger: MagicMock, token_handler: TokenHandler
    ) -> None:
        """Test that successful token removal logs appropriate message."""
        args = Namespace(save=False, remove=True)
        await token_handler.execute(args)

        mock_logger.info.assert_any_call("GitHub token removed from keyring.")
