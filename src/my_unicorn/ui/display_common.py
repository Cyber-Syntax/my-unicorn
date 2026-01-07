"""Shared display utilities for UI modules.

This module provides common display functions used across different
display modules (install, update, etc.).

Note:
    These functions use print() for direct console output to ensure
    messages are always visible to users regardless of logger configuration.
"""
# ruff: noqa: T201


def print_section_divider(width: int = 50) -> None:
    """Print a visual section divider.

    Args:
        width: Width of the divider line.

    """
    print("-" * width)


def print_empty_line() -> None:
    """Print an empty line for spacing."""
    print()


def print_info_message(message: str) -> None:
    """Print an informational message with icon.

    Args:
        message: Information message to display.

    """
    print(f"ℹ️  {message}")  # noqa: RUF001


def print_success_message(message: str) -> None:
    """Print a success message with icon.

    Args:
        message: Success message to display.

    """
    print(f"✅ {message}")


def print_error_message(message: str) -> None:
    """Print an error message with icon.

    Args:
        message: Error message to display.

    """
    print(f"❌ {message}")


def print_warning_message(message: str) -> None:
    """Print a warning message with icon.

    Args:
        message: Warning message to display.

    """
    print(f"⚠️  {message}")


def print_progress_message(message: str) -> None:
    """Print a progress/activity message with icon.

    Args:
        message: Progress message to display.

    """
    print(f"🔄 {message}")


def print_celebration_message(message: str) -> None:
    """Print a celebratory message with icon.

    Args:
        message: Celebration message to display.

    """
    print(f"🎉 {message}")


def print_list_item(item: str, indent: int = 0) -> None:
    """Print a bullet point list item.

    Args:
        item: Item text to display.
        indent: Number of spaces to indent.

    """
    prefix = " " * indent
    print(f"{prefix}• {item}")


def print_numbered_item(number: int, item: str, indent: int = 0) -> None:
    """Print a numbered list item.

    Args:
        number: Item number.
        item: Item text to display.
        indent: Number of spaces to indent.

    """
    prefix = " " * indent
    print(f"{prefix}{number}. {item}")


def print_key_value(
    key: str,
    value: str,
    key_width: int = 20,
    indent: int = 0,
) -> None:
    """Print a key-value pair with aligned formatting.

    Args:
        key: Key name.
        value: Value to display.
        key_width: Width for the key column.
        indent: Number of spaces to indent.

    """
    prefix = " " * indent
    print(f"{prefix}{key:<{key_width}} {value}")


def print_table_row(
    columns: list[tuple[str, int]],
    indent: int = 0,
) -> None:
    """Print a formatted table row.

    Args:
        columns: List of (value, width) tuples for each column.
        indent: Number of spaces to indent.

    """
    prefix = " " * indent
    row_parts = [f"{value:<{width}}" for value, width in columns]
    row_line = " ".join(row_parts)
    print(f"{prefix}{row_line}")


def print_centered_text(text: str, width: int = 50) -> None:
    """Print centered text.

    Args:
        text: Text to center.
        width: Total width for centering.

    """
    print(text.center(width))
