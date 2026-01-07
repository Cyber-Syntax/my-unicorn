"""UI module for presentation and display logic.

This module contains all user interface and presentation components,
including progress displays, formatters, and display utilities.
"""

from my_unicorn.ui.formatters import (
    format_app_status_line,
    format_count_summary,
    format_indented_detail,
    format_section_header,
    format_table_header,
    format_version_string,
    format_version_transition,
)
from my_unicorn.ui.progress import ProgressDisplay

__all__ = [
    "ProgressDisplay",
    "format_app_status_line",
    "format_count_summary",
    "format_indented_detail",
    "format_section_header",
    "format_table_header",
    "format_version_string",
    "format_version_transition",
]
