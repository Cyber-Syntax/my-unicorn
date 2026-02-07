import io

from my_unicorn.core.progress.progress import (
    AsciiProgressBackend,
    ProgressConfig,
    ProgressType,
    TaskState,
)


def make_backend():
    cfg = ProgressConfig()
    return AsciiProgressBackend(
        config=cfg, interactive=False, output=io.StringIO()
    )


def test_compute_display_name_strips_appimage():
    backend = make_backend()
    task = TaskState(
        task_id="t1",
        name="example.AppImage",
        progress_type=ProgressType.DOWNLOAD,
    )
    assert backend._compute_display_name(task) == "example"


def test_format_download_lines_success_and_error():
    backend = make_backend()

    # Successful completed download
    total = 10 * 1024 * 1024
    task_ok = TaskState(
        task_id="t_ok",
        name="good.AppImage",
        progress_type=ProgressType.DOWNLOAD,
        total=total,
        completed=total,
        speed=1024 * 1024,
        is_finished=True,
        success=True,
    )
    lines = backend._format_download_lines(task_ok, max_name_width=20)
    assert lines
    first = lines[0]
    assert "MiB" in first or "GiB" in first
    assert "✓" in first

    # Failed download with error message
    task_fail = TaskState(
        task_id="t_fail",
        name="bad.AppImage",
        progress_type=ProgressType.DOWNLOAD,
        total=1024,
        completed=512,
        speed=0,
        is_finished=True,
        success=False,
        error_message="Something went wrong while downloading",
    )
    lines = backend._format_download_lines(task_fail, max_name_width=20)
    assert any("Error:" in l for l in lines)
