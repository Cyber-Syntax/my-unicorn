"""Tests for AsciiProgressBackend and ProgressDisplay functionality.

This module contains the unique backend tests that were previously in
test_progress.py. These tests cover the interactive/non-interactive
rendering, error handling, and display logic specific to the progress
backend implementation.

Coverage targets: AsciiProgressBackend and ProgressDisplay classes.
"""

import io

import pytest

from my_unicorn.core.progress.progress import (
    AsciiProgressBackend,
    ProgressDisplay,
    ProgressType,
    TaskInfo,
    TaskState,
)


class TestAsciiProgressBackendInitialization:
    """Tests for backend initialization and exception handling."""

    def test_isatty_exception_handling(self) -> None:
        """Ensure backend handles output objects whose isatty raises."""

        class BadOutput(io.StringIO):
            def isatty(self) -> bool:  # type: ignore[override]
                raise RuntimeError("broken isatty")

        out = BadOutput()
        # Should not raise during initialization
        backend = AsciiProgressBackend(output=out, interactive=None)
        assert backend.interactive is False

    def test_update_finish_nonexistent_no_raise(self) -> None:
        """Updating/finishing nonexistent backend tasks should be safe."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        # Should not raise
        backend.update_task("nope", completed=1.0)
        backend.finish_task("nope", success=False)


class TestAsciiProgressBackendClearAndWrite:
    """Tests for clearing and writing output in interactive modes."""

    def test_clear_and_write_paths(self) -> None:
        """Exercise clearing and interactive/non-interactive writes."""
        # interactive clear
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=True)
        backend._last_output_lines = 2
        backend._clear_previous_output()
        assert "\033[" in out.getvalue()

        # write_interactive empty
        backend._write_interactive("")
        assert backend._last_output_lines == 0

        # noninteractive summary write
        out2 = io.StringIO()
        backend2 = AsciiProgressBackend(output=out2, interactive=False)
        backend2._write_noninteractive("Summary: All done")
        assert "Summary: All done" in out2.getvalue()

    def test_clear_previous_output_early_return(self) -> None:
        """_clear_previous_output should return early when non-interactive."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        # With non-interactive, _clear_previous_output should do nothing
        backend._clear_previous_output()

    def test_write_noninteractive_ioerror_is_swallowed(self) -> None:
        """Ensure write errors in noninteractive mode are swallowed."""

        class BadOut:
            def write(self, s: str) -> int:
                raise OSError("broken")

            def flush(self) -> None:
                raise OSError("broken")

        backend = AsciiProgressBackend(output=BadOut(), interactive=False)
        # Should not raise
        backend._write_noninteractive("Some content")

    def test_write_interactive_swallow_ioerror(self) -> None:
        """Ensure _write_interactive swallows IO errors from output."""

        class BadOut:
            def __init__(self):
                self.calls = 0

            def write(self, s: str) -> int:
                # Allow the first two writes (used by _clear_previous_output),
                # then fail on subsequent writes to exercise the exception
                # handling in _write_interactive.
                if self.calls < 2:
                    self.calls += 1
                    return len(s)
                raise OSError("broken")

            def flush(self) -> None:
                # Allow initial flush during clear, then raise afterwards
                if self.calls <= 2:
                    self.calls += 1
                    return
                raise OSError("broken")

        out = BadOut()
        backend = AsciiProgressBackend(output=out, interactive=True)
        backend._last_output_lines = 1
        # Should not raise
        backend._write_interactive("line1\n")

    def test_write_interactive_sync_lock_exception_handled(self) -> None:
        """Ensure _write_interactive handles sync-lock exceptions."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=True)
        # Ensure clear_previous_output returns early (no previous lines)
        backend._last_output_lines = 0

        class BadLock:
            def __enter__(self):
                raise RuntimeError("lock fail")

            def __exit__(self, exc_type, exc, tb):
                return False

        backend._sync_lock = BadLock()  # type: ignore[assignment]
        # Should not raise even though setting _last_output_lines will fail
        backend._write_interactive("hello\n")

    def test_write_noninteractive_no_write_attr_and_empty(self) -> None:
        """_write_noninteractive should handle missing write attribute."""
        # Output without a write attribute
        backend = AsciiProgressBackend(output=object(), interactive=False)
        assert backend._write_noninteractive("anything") == set()

        # Empty/whitespace-only output returns empty set
        out = io.StringIO()
        backend2 = AsciiProgressBackend(output=out, interactive=False)
        assert backend2._write_noninteractive("   ") == set()

    def test_write_noninteractive_writer_raises_is_handled(self) -> None:
        """Writer exceptions are swallowed in non-interactive mode."""

        class BadWriter:
            def write(self, _):
                raise RuntimeError("bork")

            def flush(self):
                pass

        backend = AsciiProgressBackend(output=BadWriter(), interactive=False)
        content = "A\n\nB"
        # Should not raise; returns signatures for sections
        sigs = backend._write_noninteractive(content)
        assert {s.strip() for s in sigs} == {"A", "B"}

    def test_write_noninteractive_summary_writer_raises(self) -> None:
        """Ensure Summary write branch is exercised when writer raises."""

        class BadWriter2:
            def write(self, _):
                raise RuntimeError("fail")

            def flush(self):
                pass

        backend = AsciiProgressBackend(output=BadWriter2(), interactive=False)
        sigs = backend._write_noninteractive("Summary:\nDone")
        assert any("Summary:" in s for s in sigs)

    def test_write_interactive_empty_output_sync_lock_exception_handled(
        self,
    ) -> None:
        """Sync-lock exceptions are swallowed when writing empty output."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=True)

        class BadLock:
            def __enter__(self):
                raise RuntimeError("lock fail")

            def __exit__(self, exc_type, exc, tb):
                return False

        backend._sync_lock = BadLock()  # type: ignore[assignment]
        # Should return 0 and not raise
        assert backend._write_interactive("") == 0

    def test_write_noninteractive_skip_empty_section(self) -> None:
        """Empty sections should be skipped in non-interactive write."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=False)
        sigs = backend._write_noninteractive("\n\nOnly\n\n")
        assert {s.strip() for s in sigs} == {"Only"}

    def test_write_noninteractive_summary_and_section_tracking(self) -> None:
        """Test Summary write and section tracking in non-interactive mode."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=False)

        sigs = backend._write_noninteractive("Summary:\nAll done")
        assert any("Summary:" in s for s in sigs)

        # New sections should be returned
        out2 = io.StringIO()
        backend2 = AsciiProgressBackend(output=out2, interactive=False)
        content = "First section\n\nSecond section"
        added = backend2._write_noninteractive(content)
        assert {s.strip() for s in added} == {
            "First section",
            "Second section",
        }

        # Known sections should produce no additions
        backend2._written_sections.update({"First section", "Second section"})
        assert backend2._write_noninteractive(content) == set()


class TestAsciiProgressBackendBuildOutput:
    """Tests for building and rendering output from task snapshots."""

    def test_build_output_handles_sync_lock_exception(self) -> None:
        """Simulate failing sync lock in _build_output."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        class BadLock:
            def __enter__(self):
                raise RuntimeError("lock failed")

            def __exit__(self, exc_type, exc, tb):
                return False

        # Replace the sync lock with one that raises on enter
        backend._sync_lock = BadLock()  # type: ignore[assignment]
        out = backend._build_output()
        assert isinstance(out, str)

    def test_build_output_from_snapshot_api_downloads_processing_variants(
        self,
    ) -> None:
        """Exercise snapshot builder with various task types."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        # Create TaskState variants for API fetching
        api1 = TaskState(
            task_id="api1",
            name="r1",
            progress_type=ProgressType.API_FETCHING,
            total=10.0,
            completed=3.0,
        )
        api2 = TaskState(
            task_id="api2",
            name="r2",
            progress_type=ProgressType.API_FETCHING,
            total=5.0,
            completed=5.0,
            is_finished=True,
            description="Cached content",
        )
        api3 = TaskState(
            task_id="api3",
            name="r3",
            progress_type=ProgressType.API_FETCHING,
            is_finished=True,
            description="cached",
        )

        # Download task
        dl = TaskState(
            task_id="dl1",
            name="file.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
            completed=50.0,
            speed=100.0,
        )

        # Processing tasks: verification + installation
        vf = TaskState(
            task_id="vf1",
            name="MyApp",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
        )
        inst = TaskState(
            task_id="in1",
            name="MyApp",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
        )

        tasks_snapshot = {
            "api1": api1,
            "api2": api2,
            "api3": api3,
            "dl1": dl,
            "vf1": vf,
            "in1": inst,
        }

        order_snapshot = ["api1", "api2", "api3", "dl1", "vf1", "in1"]

        out = backend._build_output_from_snapshot(
            tasks_snapshot, order_snapshot
        )
        # Check that all major section headers exist
        assert "Fetching from API:" in out
        assert "Downloading" in out
        assert (
            "Verifying:" in out or "Installing:" in out or "Processing:" in out
        )

    def test_build_output_snapshot_api_retrieved_no_cached(self) -> None:
        """Snapshot builder shows 'Retrieved' for finished API tasks."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        ts = {
            "a": TaskState(
                task_id="a",
                name="app",
                progress_type=ProgressType.API_FETCHING,
                total=0,
                completed=0,
                is_finished=True,
                description="done",
            )
        }
        out = backend._build_output_from_snapshot(ts, ["a"])
        assert "Retrieved" in out

    def test_build_output_snapshot_processing_processing_header(self) -> None:
        """Snapshot builder shows 'Processing:' for other post-task types."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        ts = {
            "p1": TaskState(
                task_id="p1",
                name="app",
                progress_type=ProgressType.ICON_EXTRACTION,
                is_finished=False,
            )
        }
        out = backend._build_output_from_snapshot(ts, ["p1"])
        assert "Processing:" in out


class TestProgressDisplayIDGenerator:
    """Tests for ID generation and caching in ProgressDisplay."""

    def test_generate_namespaced_id_cache_hit_and_clear(self) -> None:
        """Verify ID caching and cache clearing in ProgressDisplay."""
        pd = ProgressDisplay()
        id1 = pd._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "same"
        )
        id2 = pd._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "same"
        )
        assert id1 == id2
        pd._id_generator.clear_cache()
        id3 = pd._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "same"
        )
        assert id3 != id1

    def test_generate_namespaced_id_unnamed(
        self, progress_service: ProgressDisplay
    ) -> None:
        """ID generator falls back to 'unnamed' for empty names."""
        # Use name with only non-allowed chars for empty sanitized result
        nid = progress_service._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "!!!   $$$"
        )
        assert "unnamed" in nid


class TestProgressDisplaySpeedCalculation:
    """Tests for speed calculation and cache management in ProgressDisplay."""

    def test_calculate_speed_returns_current_when_no_time(self) -> None:
        """_calculate_speed returns current speed with no time delta."""
        pd = ProgressDisplay()
        ti = TaskInfo(
            task_id="t",
            namespaced_id="t",
            name="n",
            progress_type=ProgressType.DOWNLOAD,
        )
        ti.current_speed_mbps = 2.0
        ti.last_speed_update = 100.0
        ti.completed = 100.0
        # time equals last update and completed unchanged
        res = pd._calculate_speed(ti, completed=100.0, current_time=100.0)
        assert res == 2.0 * 1024 * 1024

    def test_id_cache_eviction_and_calculate_speed_zero(self) -> None:
        """Force ID cache eviction and test zero speed calculation."""
        pd = ProgressDisplay()
        # Verify that cache respects size limits via IDGenerator
        # Generate IDs and verify cache doesn't exceed limit
        for i in range(100):
            pd._id_generator.generate_namespaced_id(
                ProgressType.DOWNLOAD, f"file_{i}"
            )
        # Cache should not exceed ID_CACHE_LIMIT
        assert len(pd._id_generator._id_cache) <= 1000

        # _calculate_speed returns 0.0 when avg_speed==0 and no previous speed
        ti = TaskInfo(
            task_id="t",
            namespaced_id="t",
            name="n",
            progress_type=ProgressType.DOWNLOAD,
        )
        ti.current_speed_mbps = 0.0
        ti.last_speed_update = 100.0
        ti.completed = 100.0
        res = pd._calculate_speed(ti, completed=100.0, current_time=100.0)
        assert res == 0.0


class TestAsciiProgressBackendAsync:
    """Async tests for backend rendering and cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_interactive_writes_final_output(self) -> None:
        """Interactive cleanup writes final output and resets line count."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=True)
        # Add a finished task so _build_output has content
        backend.add_task("t1", "app", ProgressType.DOWNLOAD, total=10.0)
        backend.finish_task("t1", success=True)
        # Should write final output without error
        backend._last_output_lines = 2
        await backend.cleanup()
        assert backend._last_output_lines == 0

    @pytest.mark.asyncio
    async def test_render_once_interactive_branch(self) -> None:
        """Exercise render_once in interactive mode."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=True)
        # Add a task so output is non-empty
        backend.add_task(
            "d1", "file.AppImage", ProgressType.DOWNLOAD, total=10.0
        )
        backend.update_task("d1", completed=5.0)
        await backend.render_once()
        # Should have written something
        assert out.getvalue()


class TestProgressDisplayAsync:
    """Async tests for ProgressDisplay functionality."""

    @pytest.mark.asyncio
    async def test_render_loop_logs_and_continues_on_exception(self) -> None:
        """Render loop catches exceptions from backend.render_once."""
        pd = ProgressDisplay()

        class BrokenBackend:
            def __init__(self, session_manager):
                self.session_manager = session_manager
                self.called = 0

            async def render_once(self):
                # Raise on first call, then stop the loop on second
                self.called += 1
                if self.called == 1:
                    raise RuntimeError("boom")
                # Stop the loop so the test completes
                self.session_manager._stop_rendering.set()

        # Replace backend on SessionManager since render loop delegates
        pd._session_manager._backend = BrokenBackend(pd._session_manager)
        # Ensure stop flag is cleared
        pd._session_manager._stop_rendering.clear()

        # Run the render loop until it stops (should handle one exception)
        await pd._render_loop()

    @pytest.mark.asyncio
    async def test_finish_nonexistent_task_no_raise(
        self, progress_service: ProgressDisplay
    ) -> None:
        """finish_task on non-existent task logs and does not raise."""
        await progress_service.start_session()
        # Should not raise
        await progress_service.finish_task(
            "this_does_not_exist", success=False
        )
        await progress_service.stop_session()
