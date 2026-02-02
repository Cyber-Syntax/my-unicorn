"""Tests for the ProgressReporter protocol and NullProgressReporter.

These tests verify that:
1. NullProgressReporter implements all ProgressReporter protocol methods
2. NullProgressReporter is runtime-checkable as a ProgressReporter
3. NullProgressReporter methods behave correctly (no-ops, expected returns)
4. ProgressType enum contains all expected values

"""

from __future__ import annotations

import pytest

from my_unicorn.core.protocols import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)


class TestProgressType:
    """Tests for ProgressType enum."""

    def test_progress_type_values_exist(self) -> None:
        """All expected progress types are defined."""
        assert ProgressType.API is not None
        assert ProgressType.DOWNLOAD is not None
        assert ProgressType.VERIFICATION is not None
        assert ProgressType.EXTRACTION is not None
        assert ProgressType.PROCESSING is not None
        assert ProgressType.INSTALLATION is not None
        assert ProgressType.UPDATE is not None

    def test_progress_type_count(self) -> None:
        """Expected number of progress types."""
        assert len(ProgressType) == 7

    def test_progress_types_are_unique(self) -> None:
        """All progress type values are unique."""
        values = [pt.value for pt in ProgressType]
        assert len(values) == len(set(values))


class TestNullProgressReporter:
    """Tests for NullProgressReporter null object implementation."""

    @pytest.fixture
    def reporter(self) -> NullProgressReporter:
        """Create a NullProgressReporter instance."""
        return NullProgressReporter()

    def test_is_protocol_instance(
        self, reporter: NullProgressReporter
    ) -> None:
        """NullProgressReporter is recognized as ProgressReporter."""
        assert isinstance(reporter, ProgressReporter)

    def test_is_active_returns_false(
        self, reporter: NullProgressReporter
    ) -> None:
        """is_active() always returns False."""
        assert reporter.is_active() is False

    def test_add_task_returns_null_task_id(
        self, reporter: NullProgressReporter
    ) -> None:
        """add_task() returns placeholder task ID."""
        task_id = reporter.add_task("Test", ProgressType.DOWNLOAD, total=100.0)
        assert task_id == "null-task"

    def test_add_task_accepts_all_progress_types(
        self, reporter: NullProgressReporter
    ) -> None:
        """add_task() accepts any ProgressType value."""
        for pt in ProgressType:
            task_id = reporter.add_task("Test", pt)
            assert task_id == "null-task"

    def test_add_task_without_total(
        self, reporter: NullProgressReporter
    ) -> None:
        """add_task() works without total (indeterminate progress)."""
        task_id = reporter.add_task("Test", ProgressType.API)
        assert task_id == "null-task"

    def test_update_task_is_noop(self, reporter: NullProgressReporter) -> None:
        """update_task() does nothing and returns None."""
        result = reporter.update_task("task-id", completed=50.0)
        assert result is None

    def test_update_task_with_description(
        self, reporter: NullProgressReporter
    ) -> None:
        """update_task() accepts description parameter."""
        result = reporter.update_task(
            "task-id", completed=50.0, description="Halfway"
        )
        assert result is None

    def test_finish_task_is_noop(self, reporter: NullProgressReporter) -> None:
        """finish_task() does nothing and returns None."""
        result = reporter.finish_task("task-id", success=True)
        assert result is None

    def test_finish_task_failure_case(
        self, reporter: NullProgressReporter
    ) -> None:
        """finish_task() handles success=False."""
        result = reporter.finish_task(
            "task-id", success=False, description="Failed"
        )
        assert result is None

    def test_get_task_info_returns_defaults(
        self, reporter: NullProgressReporter
    ) -> None:
        """get_task_info() returns dict with default values."""
        info = reporter.get_task_info("any-task-id")
        assert info == {"completed": 0.0, "total": None, "description": ""}

    def test_get_task_info_keys(self, reporter: NullProgressReporter) -> None:
        """get_task_info() returns dict with expected keys."""
        info = reporter.get_task_info("task-id")
        assert "completed" in info
        assert "total" in info
        assert "description" in info


class TestProgressReporterProtocol:
    """Tests for ProgressReporter protocol behavior."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """ProgressReporter can be used with isinstance()."""
        reporter = NullProgressReporter()
        assert isinstance(reporter, ProgressReporter)

    def test_custom_implementation_satisfies_protocol(self) -> None:
        """Custom class implementing methods satisfies protocol."""

        class CustomReporter:
            """Custom implementation for testing."""

            def is_active(self) -> bool:
                return True

            def add_task(
                self,
                name: str,
                progress_type: ProgressType,
                total: float | None = None,
            ) -> str:
                return "custom-id"

            def update_task(
                self,
                task_id: str,
                completed: float | None = None,
                description: str | None = None,
            ) -> None:
                pass

            def finish_task(
                self,
                task_id: str,
                *,
                success: bool = True,
                description: str | None = None,
            ) -> None:
                pass

            def get_task_info(self, task_id: str) -> dict[str, object]:
                return {"completed": 0.0, "total": None, "description": ""}

        reporter = CustomReporter()
        assert isinstance(reporter, ProgressReporter)


class TestNullPatternIntegration:
    """Integration tests for null object pattern usage."""

    def test_none_or_pattern(self) -> None:
        """Pattern: progress = reporter or NullProgressReporter()."""
        # When reporter is None
        reporter: ProgressReporter | None = None
        progress = reporter or NullProgressReporter()
        assert isinstance(progress, ProgressReporter)
        assert progress.is_active() is False

    def test_full_lifecycle(self) -> None:
        """Complete task lifecycle with NullProgressReporter."""
        reporter = NullProgressReporter()

        task_id = reporter.add_task(
            name="Download file",
            progress_type=ProgressType.DOWNLOAD,
            total=1024.0,
        )
        assert task_id == "null-task"

        reporter.update_task(task_id, completed=256.0)
        reporter.update_task(task_id, completed=512.0, description="50%")
        reporter.update_task(task_id, completed=1024.0)

        reporter.finish_task(task_id, success=True, description="Complete")

        info = reporter.get_task_info(task_id)
        assert info["completed"] == 0.0  # Null reporter doesn't track state
