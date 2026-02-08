"""Comprehensive tests for the progress service module.

Tests cover all major functionality including edge cases for network errors,
verification failures, icon extraction errors, and other progress bar issues.
"""

import asyncio
import io
from unittest.mock import patch

import pytest

from my_unicorn.core.progress.ascii_sections import (
    SectionRenderConfig,
    calculate_dynamic_name_width,
    format_download_lines,
    format_processing_task_lines,
    render_api_section,
    render_downloads_section,
    render_processing_section,
    select_current_task,
)
from my_unicorn.core.progress.progress import (
    AsciiProgressBackend,
    ProgressConfig,
    ProgressDisplay,
    ProgressType,
    TaskInfo,
    TaskState,
)


class TestProgressCoverageExtras:
    """Additional tests targeting branches flagged by coverage annotate."""

    def test_isatty_exception_handling(self) -> None:
        """Ensure backend handles output objects whose isatty raises."""

        class BadOutput(io.StringIO):
            def isatty(self) -> bool:  # type: ignore[override]
                raise RuntimeError("broken isatty")

        out = BadOutput()
        # Should not raise during initialization
        backend = AsciiProgressBackend(output=out, interactive=None)
        assert backend.interactive is False

    def test_format_download_lines_variations(self) -> None:
        """Cover branches in format_download_lines (sizes, speeds, eta, errors)."""

        # Case: no total, no speed
        t1 = TaskState(
            task_id="a", name="no_size", progress_type=ProgressType.DOWNLOAD
        )
        lines = format_download_lines(t1, max_name_width=10, bar_width=30)
        assert any("--" in l or "00:00" in l for l in lines)

        # Case: total and speed present, unfinished
        t2 = TaskState(
            task_id="b",
            name="big.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
            completed=200.0,
            speed=100.0,
            is_finished=False,
        )
        lines2 = format_download_lines(t2, max_name_width=15, bar_width=30)
        assert any("00:00" not in l for l in lines2)

        # Case: finished with error message
        t3 = TaskState(
            task_id="c",
            name="err.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
            completed=100.0,
            speed=0.0,
            is_finished=True,
            success=False,
            error_message="Something went wrong while downloading",
        )
        lines3 = format_download_lines(t3, max_name_width=15, bar_width=30)
        assert any("Error:" in l for l in lines3)

    def test_update_finish_nonexistent_no_raise(self) -> None:
        """Updating/finishing nonexistent backend tasks should be safe."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        # Should not raise
        backend.update_task("nope", completed=1.0)
        backend.finish_task("nope", success=False)

    def test_api_rendering_status_variations(self) -> None:
        """Cover API fetching status formatting permutations."""
        # in-progress with total
        api_task1 = TaskState(
            task_id="api1",
            name="repo",
            progress_type=ProgressType.API_FETCHING,
            total=10.0,
            completed=3.0,
            is_finished=False,
        )
        api_lines = render_api_section(
            tasks={"api1": api_task1}, order=["api1"]
        )
        assert any("Fetching..." in l or "Retrieved" in l for l in api_lines)

        # finished and cached
        api_task2 = TaskState(
            task_id="api2",
            name="repo2",
            progress_type=ProgressType.API_FETCHING,
            total=5.0,
            completed=5.0,
            is_finished=True,
            success=True,
            description="Cached content",
        )
        api_lines2 = render_api_section(
            tasks={"api2": api_task2}, order=["api2"]
        )
        assert any("Retrieved" in l for l in api_lines2)

    def test_calculate_dynamic_name_width_and_spinner_header(self) -> None:
        """Trigger terminal-size exception and spinner/header helpers."""
        # Force shutil.get_terminal_size to raise by monkeypatching
        import shutil

        orig = shutil.get_terminal_size

        def bad_getter():
            raise OSError("no tty")

        shutil.get_terminal_size = bad_getter  # type: ignore[assignment]
        try:
            name_w = calculate_dynamic_name_width(
                interactive=True, min_name_width=10
            )
            assert isinstance(name_w, int)
        finally:
            shutil.get_terminal_size = orig

        # Spinner deterministic value
        with patch("time.monotonic", return_value=0.25):
            from my_unicorn.core.progress.ascii_format import compute_spinner

            spin = compute_spinner(4)  # 4 FPS
            assert isinstance(spin, str) and len(spin) > 0

        # header
        from my_unicorn.core.progress.ascii_format import (
            compute_download_header,
        )

        assert compute_download_header(2).startswith("Downloading")

    def test_format_processing_task_lines(self) -> None:
        """Cover processing task formatting (spinner, finished, errors)."""
        t = TaskState(
            task_id="p1",
            name="MyApp",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=False,
        )
        lines = format_processing_task_lines(t, name_width=10, spinner="*")
        assert any(
            "Processing" in l or "Verifying" in l or "*" in l for l in lines
        )

        # finished with error
        t2 = TaskState(
            task_id="p2",
            name="MyApp",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=False,
            error_message="boom",
        )
        lines2 = format_processing_task_lines(t2, name_width=10, spinner="~")
        assert any("Error:" in l for l in lines2)

    def test_clear_and_write_paths(self) -> None:
        """Exercise clear previous output and interactive/noninteractive writes."""
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

    def test_format_api_task_status_all_cases(self) -> None:
        """Exercise different status outputs from format_api_task_status."""
        from my_unicorn.core.progress.ascii_format import (
            format_api_task_status,
        )

        # total > 0, unfinished
        t = TaskState(
            task_id="a",
            name="x",
            progress_type=ProgressType.API_FETCHING,
            total=10.0,
            completed=2.0,
        )
        assert "Fetching" in format_api_task_status(t)

        # total >0 finished, cached
        t2 = TaskState(
            task_id="b",
            name="y",
            progress_type=ProgressType.API_FETCHING,
            total=5.0,
            completed=5.0,
            is_finished=True,
            description="Cached result",
        )
        assert "Retrieved" in format_api_task_status(t2)

        # no total, finished cached
        t3 = TaskState(
            task_id="c",
            name="z",
            progress_type=ProgressType.API_FETCHING,
            is_finished=True,
            description="cached",
        )
        assert format_api_task_status(t3).startswith("Retrieved")

    def test_select_current_task_variants(self) -> None:
        """Select current task from list with various finished/failed states."""
        t1 = TaskState(
            task_id="1",
            name="a",
            progress_type=ProgressType.VERIFICATION,
            is_finished=True,
            success=True,
            phase=1,
        )
        t2 = TaskState(
            task_id="2",
            name="a",
            progress_type=ProgressType.VERIFICATION,
            is_finished=True,
            success=False,
            phase=2,
        )
        t3 = TaskState(
            task_id="3",
            name="a",
            progress_type=ProgressType.VERIFICATION,
            is_finished=False,
            success=None,
            phase=3,
        )

        sel = select_current_task([t1, t2, t3])
        # According to selection logic, first failing phase is preferred
        assert sel is t2

    def test_generate_namespaced_id_cache_hit_and_clear(self) -> None:
        """Ensure ProgressDisplay caches generated namespaced ids and can clear cache."""
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
        """When sanitization produces an empty name, fallback to 'unnamed'."""
        # Use a name containing only non-allowed chars so sanitization yields empty
        nid = progress_service._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "!!!   $$$"
        )
        assert "unnamed" in nid

    def test_calculate_speed_returns_current_when_no_time(self) -> None:
        """_calculate_speed should return current_speed when no time/progress delta."""
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

    @pytest.mark.asyncio
    async def test_cleanup_interactive_writes_final_output(self) -> None:
        """Interactive cleanup should write final output and reset last lines."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=True)
        # Add a finished task so _build_output has content
        backend.add_task("t1", "app", ProgressType.DOWNLOAD, total=10.0)
        backend.finish_task("t1", success=True)
        # Should write final output without error
        backend._last_output_lines = 2
        await backend.cleanup()
        assert backend._last_output_lines == 0

    def test_render_api_section_no_tasks(self) -> None:
        """API section should return empty list when there are no API tasks."""
        assert render_api_section(tasks={}, order=[]) == []

    def test_render_downloads_and_processing_sections(self) -> None:
        """Ensure downloads and processing renderers handle empty and populated lists."""
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # No downloads initially
        assert (
            render_downloads_section(tasks={}, order=[], config=config) == []
        )

        # Add a download and ensure section renders
        dl_task = TaskState(
            task_id="dl_a",
            name="file.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
            completed=10.0,
            speed=50.0,
        )
        dl_lines = render_downloads_section(
            tasks={"dl_a": dl_task}, order=["dl_a"], config=config
        )
        assert any(
            "Downloading" in l or "00:00" in l or "Error:" in l
            for l in dl_lines
        )

        # Processing: no post tasks
        assert (
            render_processing_section(tasks={}, order=[], config=config) == []
        )

        # Add a verification task to trigger 'Verifying' header
        vf_task = TaskState(
            task_id="vf_a",
            name="MyApp",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
        )
        proc_lines = render_processing_section(
            tasks={"vf_a": vf_task}, order=["vf_a"], config=config
        )
        assert any(
            l.startswith("Verifying")
            or l.startswith("Installing")
            or l.startswith("Processing")
            for l in proc_lines
        )

    def test_build_output_handles_sync_lock_exception(self) -> None:
        """Simulate a failing sync lock to hit the except branch in _build_output."""
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
        """Call _build_output_from_snapshot with crafted snapshots to exercise branches."""
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

    def test_write_interactive_swallow_ioerror(self) -> None:
        """Ensure _write_interactive swallows IO errors from output.write/flush."""

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

    @pytest.mark.asyncio
    async def test_render_loop_logs_and_continues_on_exception(self) -> None:
        """Ensure the render loop catches exceptions from backend.render_once and continues."""
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

        # Replace backend on SessionManager (not ProgressDisplay) since render loop now delegates
        pd._session_manager._backend = BrokenBackend(pd._session_manager)
        # Ensure stop flag is cleared
        pd._session_manager._stop_rendering.clear()

        # Run the render loop until it stops (should handle one exception)
        await pd._render_loop()

    def test_api_status_branches_snapshot_and_nonsnapshot(self) -> None:
        """Exercise all API status branches in both snapshot and non-snapshot renderers."""
        # total >0 unfinished
        api_a = TaskState(
            task_id="a",
            name="a",
            progress_type=ProgressType.API_FETCHING,
            total=10.0,
            completed=2.0,
        )
        # total >0 finished cached
        api_b = TaskState(
            task_id="b",
            name="b",
            progress_type=ProgressType.API_FETCHING,
            total=5.0,
            completed=5.0,
            is_finished=True,
            description="cached copy",
        )
        # total >0 finished not cached
        api_c = TaskState(
            task_id="c",
            name="c",
            progress_type=ProgressType.API_FETCHING,
            total=3.0,
            completed=3.0,
            is_finished=True,
            description="ok",
        )
        # no total finished cached
        api_d = TaskState(
            task_id="d",
            name="d",
            progress_type=ProgressType.API_FETCHING,
            is_finished=True,
            description="CACHED",
        )
        # no total not finished
        api_e = TaskState(
            task_id="e", name="e", progress_type=ProgressType.API_FETCHING
        )

        tasks = {t.task_id: t for t in (api_a, api_b, api_c, api_d, api_e)}
        order = ["a", "b", "c", "d", "e"]

        api_lines = render_api_section(tasks, order)
        assert any("Fetching from API:" in l for l in api_lines)
        assert any(
            "Retrieved from cache" in l or "cached" in l.lower()
            for l in api_lines
        )
        assert any("Retrieved" in l or "Fetching" in l for l in api_lines)

    def test_processing_section_installing_header(self) -> None:
        """Ensure processing renderer emits 'Installing:' when installation tasks exist."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        # Only installation tasks
        inst1 = TaskState(
            task_id="i1",
            name="App",
            progress_type=ProgressType.INSTALLATION,
            phase=1,
            total_phases=1,
        )
        tasks = {"i1": inst1}
        order = ["i1"]

        out = backend._build_output_from_snapshot(tasks, order)
        assert "Installing:" in out

    def test_clear_previous_output_early_return(self) -> None:
        """_clear_previous_output should return early when non-interactive or no lines."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        # With non-interactive, _clear_previous_output should do nothing
        backend._clear_previous_output()

    def test_write_interactive_sync_lock_exception_handled(self) -> None:
        """Ensure _write_interactive swallows exceptions when sync-lock fails to set state."""
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
        """_write_noninteractive should handle outputs without write and empty content."""
        # Output without a write attribute
        backend = AsciiProgressBackend(output=object(), interactive=False)
        assert backend._write_noninteractive("anything") == set()

        # Empty/whitespace-only output returns empty set
        out = io.StringIO()
        backend2 = AsciiProgressBackend(output=out, interactive=False)
        assert backend2._write_noninteractive("   ") == set()

    @pytest.mark.asyncio
    async def test_render_once_interactive_branch(self) -> None:
        """Run render_once in interactive mode to exercise interactive branch."""
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

    def test_format_api_task_status_variants(self) -> None:
        """Explicitly exercise all branches of format_api_task_status."""
        from my_unicorn.core.progress.ascii_format import (
            format_api_task_status,
        )

        # total > 0, finished, cached
        t1 = TaskState(
            task_id="a",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=2,
            completed=2,
            is_finished=True,
            description="Cached result",
        )
        assert "Retrieved from cache" in format_api_task_status(t1)

        # total > 0, finished, not cached
        t2 = TaskState(
            task_id="b",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=3,
            completed=3,
            is_finished=True,
            description="OK",
        )
        assert "Retrieved" in format_api_task_status(t2)

        # total > 0, not finished
        t3 = TaskState(
            task_id="c",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=4,
            completed=1,
            is_finished=False,
            description="",
        )
        assert "Fetching" in format_api_task_status(t3)

        # total == 0, finished, cached
        t4 = TaskState(
            task_id="d",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=0,
            completed=0,
            is_finished=True,
            description="cached",
        )
        assert format_api_task_status(t4) == "Retrieved from cache"

        # total == 0, not finished
        t5 = TaskState(
            task_id="e",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=0,
            completed=0,
            is_finished=False,
            description="",
        )
        assert format_api_task_status(t5) == "Fetching..."

    def test_format_api_task_status_exact_retrieved(self) -> None:
        """Ensure exact formatting for total/total Retrieved branch."""
        from my_unicorn.core.progress.ascii_format import (
            format_api_task_status,
        )

        t = TaskState(
            task_id="x",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=7,
            completed=7,
            is_finished=True,
            description="ok",
        )
        assert format_api_task_status(t) == "7/7        Retrieved"

    def test_processing_section_verifying_header(self) -> None:
        """When only verification tasks exist, header should be 'Verifying:'"""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        ts = {
            "v1": TaskState(
                task_id="v1",
                name="app",
                progress_type=ProgressType.VERIFICATION,
                is_finished=False,
            )
        }
        out = backend._build_output_from_snapshot(ts, ["v1"])
        assert "Verifying:" in out

    def test_write_noninteractive_writer_raises_is_handled(self) -> None:
        """If writer raises during non-interactive write, exception is swallowed and signatures returned."""

        class BadWriter:
            def write(self, _):
                raise RuntimeError("bork")

            def flush(self):
                pass

        backend = AsciiProgressBackend(output=BadWriter(), interactive=False)
        content = "A\n\nB"
        # Should not raise despite writer failing; returns signatures for sections
        sigs = backend._write_noninteractive(content)
        assert {s.strip() for s in sigs} == {"A", "B"}

    def test_build_output_snapshot_api_retrieved_no_cached(self) -> None:
        """_snapshot builder: API task with total==0 and finished should show 'Retrieved'"""
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

    def test_render_api_section_retrieved_no_cached(self) -> None:
        """API rendering should show 'Retrieved' for finished non-cached tasks."""
        task = TaskState(
            task_id="a",
            name="app",
            progress_type=ProgressType.API_FETCHING,
            total=0,
            completed=0,
            is_finished=True,
            success=True,
            description="done",
        )
        lines = render_api_section(tasks={"a": task}, order=["a"])
        assert any("Retrieved" in l for l in lines)

    def test_format_api_task_status_return_retrieved(self) -> None:
        from my_unicorn.core.progress.ascii_format import (
            format_api_task_status,
        )

        t = TaskState(
            task_id="x",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=0,
            completed=0,
            is_finished=True,
            description="done",
        )
        assert format_api_task_status(t) == "Retrieved"

    def test_render_processing_section_headers_non_snapshot(self) -> None:
        """Verify all processing header branches."""
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Verifying only
        v_task = TaskState(
            task_id="v",
            name="app",
            progress_type=ProgressType.VERIFICATION,
        )
        v_lines = render_processing_section(
            tasks={"v": v_task}, order=["v"], config=config
        )
        assert any("Verifying:" in l for l in v_lines)

        # Installation present
        i_task = TaskState(
            task_id="i",
            name="app",
            progress_type=ProgressType.INSTALLATION,
        )
        i_lines = render_processing_section(
            tasks={"i": i_task}, order=["i"], config=config
        )
        assert any("Installing:" in l for l in i_lines)

        # Other post-task (processing)
        p_task = TaskState(
            task_id="p",
            name="app",
            progress_type=ProgressType.ICON_EXTRACTION,
        )
        p_lines = render_processing_section(
            tasks={"p": p_task}, order=["p"], config=config
        )
        assert any("Processing:" in l for l in p_lines)

    def test_build_output_snapshot_processing_processing_header(self) -> None:
        """When only non-verification/non-installation post-tasks exist, header is 'Processing:'"""
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

    def test_write_noninteractive_summary_writer_raises(self) -> None:
        """Ensure Summary write except branch is exercised when writer raises."""

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
        """When writing nothing, setting _last_output_lines under sync lock may fail; ensure it's swallowed."""
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
        """Empty sections produced by split should be skipped (continue executed)."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=False)
        sigs = backend._write_noninteractive("\n\nOnly\n\n")
        assert {s.strip() for s in sigs} == {"Only"}

    def test_write_noninteractive_summary_and_section_tracking(self) -> None:
        """Test Summary immediate write, new sections detection, and no-change behavior."""
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

    def test_id_cache_eviction_and_calculate_speed_zero(self) -> None:
        """Force ID cache eviction and ensure _calculate_speed returns 0 when no current speed."""
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

    @pytest.mark.asyncio
    async def test_finish_nonexistent_task_no_raise(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Calling finish_task on a non-existent task should log and return without raising."""
        await progress_service.start_session()
        # Should not raise
        await progress_service.finish_task(
            "this_does_not_exist", success=False
        )
        await progress_service.stop_session()
