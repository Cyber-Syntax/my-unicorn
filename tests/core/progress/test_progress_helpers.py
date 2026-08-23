import io

from my_unicorn.core.progress.ascii import format_download_lines
from my_unicorn.core.progress.progress import (
    AsciiProgressBackend,
    Phase,
    ProgressConfig,
    TaskState,
)
from my_unicorn.exceptions import (
    ERROR_MESSAGES,
    ErrorCode,
    ErrorSeverity,
    TaskError,
)


def make_backend():
    cfg = ProgressConfig()
    return AsciiProgressBackend(
        config=cfg, interactive=False, output=io.StringIO()
    )


def test_compute_display_name_strips_appimage():
    from my_unicorn.core.progress.ascii import compute_display_name

    task = TaskState(
        task_id="t1",
        name="example.AppImage",
        progress_type=Phase.DOWNLOAD,
    )
    assert compute_display_name(task) == "example"


def test_format_download_lines_success_and_error():
    # Successful completed download
    total = 10 * 1024 * 1024
    task_ok = TaskState(
        task_id="t_ok",
        name="good.AppImage",
        progress_type=Phase.DOWNLOAD,
        total=total,
        completed=total,
        speed=1024 * 1024,
        is_finished=True,
        success=True,
    )
    lines = format_download_lines(task_ok, max_name_width=20, bar_width=30)
    assert lines
    first = lines[0]
    assert "MiB" in first or "GiB" in first
    # Check for right-aligned format: progress bar and percentage
    assert "[" in first and "]" in first
    assert "100%" in first

    # Failed download with error message
    task_fail = TaskState(
        task_id="t_fail",
        name="bad.AppImage",
        progress_type=Phase.DOWNLOAD,
        total=1024,
        completed=512,
        speed=0,
        is_finished=True,
        success=False,
        errors=[
            TaskError(
                phase="download",
                processing_phase="download",
                app_name="bad.AppImage",
                error_code=ErrorCode.DOWNLOAD_FAILED,
                error_severity=ErrorSeverity.ERROR,
                details=ERROR_MESSAGES.get(ErrorCode.DOWNLOAD_FAILED),
                timestamp="2026-01-01T00:00:00Z",
            )
        ],
    )
    lines = format_download_lines(task_fail, max_name_width=20, bar_width=30)
    assert (
        "error: network error while downloading bad.AppImage : Something went wrong while downloading"
        in lines
    )
