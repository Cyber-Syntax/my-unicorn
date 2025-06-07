#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for UI utility functions.

This module contains tests for the UI utility functions in src/utils/ui_utils.py.
"""

from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from src.utils.ui_utils import select_from_list, get_user_input, confirm_action


class TestSelectFromList:
    """Tests for select_from_list function."""

    def test_empty_list(self) -> None:
        """Test with empty list of items."""
        with pytest.raises(ValueError, match="No items to select from"):
            select_from_list([], "Select an item")

    @patch("builtins.input", return_value="1")
    @patch("builtins.print")
    def test_valid_selection(self, mock_print: MagicMock, mock_input: MagicMock) -> None:
        """
        Test with valid selection.

        Args:
            mock_print: Mocked print function
            mock_input: Mocked input function
        """
        items = [
            {"name": "item1", "value": 1},
            {"name": "item2", "value": 2},
            {"name": "item3", "value": 3},
        ]

        result = select_from_list(items, "Select an item")

        assert result == items[0]
        mock_input.assert_called_once_with("Select an item (1-3): ")

    @patch("builtins.input", side_effect=["4", "invalid", "2"])
    @patch("builtins.print")
    def test_invalid_then_valid_selection(
        self, mock_print: MagicMock, mock_input: MagicMock
    ) -> None:
        """
        Test with invalid selection followed by valid selection.

        Args:
            mock_print: Mocked print function
            mock_input: Mocked input function with multiple return values
        """
        items = [
            {"name": "item1", "value": 1},
            {"name": "item2", "value": 2},
            {"name": "item3", "value": 3},
        ]

        result = select_from_list(items, "Select an item")

        assert result == items[1]  # Should select the 2nd item (index 1)
        assert mock_input.call_count == 3

    @patch("builtins.input", return_value="2")
    @patch("builtins.print")
    def test_custom_display_key(self, mock_print: MagicMock, mock_input: MagicMock) -> None:
        """
        Test with custom display key.

        Args:
            mock_print: Mocked print function
            mock_input: Mocked input function
        """
        items = [
            {"id": "A1", "label": "First item"},
            {"id": "A2", "label": "Second item"},
            {"id": "A3", "label": "Third item"},
        ]

        result = select_from_list(items, "Select an item", display_key="label")

        assert result == items[1]
        mock_input.assert_called_once_with("Select an item (1-3): ")

    @patch("builtins.input", return_value="3")
    @patch("builtins.print")
    def test_with_callback(self, mock_print: MagicMock, mock_input: MagicMock) -> None:
        """
        Test with callback function.

        Args:
            mock_print: Mocked print function
            mock_input: Mocked input function
        """
        items = [
            {"name": "item1", "value": 1},
            {"name": "item2", "value": 2},
            {"name": "item3", "value": 3},
        ]

        callback_called = False
        callback_arg = None

        def test_callback(item: tuple[str, Any]) -> None:
            nonlocal callback_called, callback_arg
            callback_called = True
            callback_arg = item

        result = select_from_list(items, "Select an item", callback=test_callback)

        assert result == items[2]
        assert callback_called is True
        assert callback_arg == items[2]


class TestGetUserInput:
    """Tests for get_user_input function."""

    @patch("builtins.input", return_value="user response")
    def test_basic_input(self, mock_input: MagicMock) -> None:
        """
        Test basic user input.

        Args:
            mock_input: Mocked input function
        """
        result = get_user_input("Enter value")

        assert result == "user response"
        mock_input.assert_called_once_with("Enter value: ")

    @patch("builtins.input", return_value="")
    def test_default_value_with_empty_input(self, mock_input: MagicMock) -> None:
        """
        Test default value with empty input.

        Args:
            mock_input: Mocked input function
        """
        result = get_user_input("Enter value", default="default")

        assert result == "default"
        mock_input.assert_called_once_with("Enter value (default: default): ")

    @patch("builtins.input", return_value="user value")
    def test_override_default(self, mock_input: MagicMock) -> None:
        """
        Test overriding default value.

        Args:
            mock_input: Mocked input function
        """
        result = get_user_input("Enter value", default="default")

        assert result == "user value"
        mock_input.assert_called_once_with("Enter value (default: default): ")

    @patch("builtins.input", return_value="  spaced input  ")
    def test_input_stripping(self, mock_input: MagicMock) -> None:
        """
        Test stripping whitespace from input.

        Args:
            mock_input: Mocked input function
        """
        result = get_user_input("Enter value")

        assert result == "spaced input"
        mock_input.assert_called_once_with("Enter value: ")


class TestConfirmAction:
    """Tests for confirm_action function."""

    @patch("builtins.input", return_value="y")
    def test_confirm_with_y(self, mock_input: MagicMock) -> None:
        """
        Test confirmation with 'y' input.

        Args:
            mock_input: Mocked input function
        """
        result = confirm_action("Proceed?")

        assert result is True
        mock_input.assert_called_once_with("Proceed? [y/N]: ")

    @patch("builtins.input", return_value="yes")
    def test_confirm_with_yes(self, mock_input: MagicMock) -> None:
        """
        Test confirmation with 'yes' input.

        Args:
            mock_input: Mocked input function
        """
        result = confirm_action("Proceed?")

        assert result is True
        mock_input.assert_called_once_with("Proceed? [y/N]: ")

    @patch("builtins.input", return_value="n")
    def test_reject_with_n(self, mock_input: MagicMock) -> None:
        """
        Test rejection with 'n' input.

        Args:
            mock_input: Mocked input function
        """
        result = confirm_action("Proceed?")

        assert result is False
        mock_input.assert_called_once_with("Proceed? [y/N]: ")

    @patch("builtins.input", return_value="no")
    def test_reject_with_no(self, mock_input: MagicMock) -> None:
        """
        Test rejection with 'no' input.

        Args:
            mock_input: Mocked input function
        """
        result = confirm_action("Proceed?")

        assert result is False
        mock_input.assert_called_once_with("Proceed? [y/N]: ")

    @patch("builtins.input", return_value="")
    def test_default_false(self, mock_input: MagicMock) -> None:
        """
        Test default (False) with empty input.

        Args:
            mock_input: Mocked input function
        """
        result = confirm_action("Proceed?")

        assert result is False
        mock_input.assert_called_once_with("Proceed? [y/N]: ")

    @patch("builtins.input", return_value="")
    def test_default_true(self, mock_input: MagicMock) -> None:
        """
        Test default (True) with empty input.

        Args:
            mock_input: Mocked input function
        """
        result = confirm_action("Proceed?", default=True)

        assert result is True
        mock_input.assert_called_once_with("Proceed? [Y/n]: ")

    @patch("builtins.input", return_value="invalid")
    def test_invalid_input(self, mock_input: MagicMock) -> None:
        """
        Test with invalid input.

        Args:
            mock_input: Mocked input function
        """
        result = confirm_action("Proceed?")

        assert result is False
        mock_input.assert_called_once_with("Proceed? [y/N]: ")
