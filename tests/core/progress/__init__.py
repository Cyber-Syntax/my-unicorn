"""Progress tests package.

This module exists to make ``tests/core/progress`` an explicit Python
package so linters (e.g. ruff) do not report implicit namespace package
issues (INP001).

It intentionally contains no runtime logic; package-level fixtures live in
``conftest.py``.
"""

__all__: list[str] = []
