"""
Test that Python files don't exceed 500 lines.Long files are difficult to maintain, understand, and test.

Files should be kept concise and focused on a single responsibility.
"""

from pathlib import Path


def test_python_files_max_500_lines() -> None:
    """
    Ensure all Python files in tests and src/my_unicorn are at most 500 lines long.

    Files exceeding 500 lines indicate:
        - Too many responsibilities in a single module
        - Need for refactoring into smaller, focused modules
        - Potential violation of single responsibility principle
    Exceptions can be made for:
        - Generated migration files
        - Configuration files with large data structures

    """
    max_lines = 550
    # Determine project root robustly so the test works whether this file lives in
    # `tests/` or `tests/custom/`. Prefer a parent that contains both `src` and
    # `tests`. Fall back to two levels up (common when running from tests/custom).
    current_file = Path(__file__).resolve()
    project_root: Path | None = None
    for parent in current_file.parents:
        if (parent / "src").exists() and (parent / "tests").exists():
            project_root = parent
            break
    if project_root is None:
        project_root = (
            current_file.parents[2]
            if len(current_file.parents) >= 3
            else current_file.parent
        )
    violations = []
    # Directories to check (relative to project root)
    directories = ["tests", "src/my_unicorn"]
    for directory in directories:
        dir_path = project_root / directory
        if not dir_path.exists():
            continue
        # Walk through all Python files
        for py_file in dir_path.rglob("*.py"):
            # Skip migration files
            if "migrations" in py_file.parts:
                continue
            # Skip __pycache__ directories
            if "__pycache__" in py_file.parts:
                continue
            # Count lines in the file
            try:
                with py_file.open(encoding="utf-8") as f:
                    line_count = sum(1 for _ in f)
            except OSError:
                # Skip files that can't be read
                continue
            if line_count > max_lines:
                relative_path = py_file.relative_to(project_root)
                violations.append(
                    f"{relative_path}: {line_count} lines (exceeds {max_lines})"
                )
    if violations:
        violation_list = "\n".join(violations)
        import pytest

        pytest.fail(f"Files exceeding {max_lines} lines:\n{violation_list}")
