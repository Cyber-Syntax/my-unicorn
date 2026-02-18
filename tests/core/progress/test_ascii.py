import io

import pytest

from my_unicorn.core.progress.progress import (
    AsciiProgressBackend,
    ProgressType,
)


@pytest.fixture
def ascii_backend() -> AsciiProgressBackend:
    """Fixture providing an AsciiProgressBackend instance."""
    output = io.StringIO()
    backend = AsciiProgressBackend(output=output, interactive=False)
    return backend


class TestAsciiProgressBackend:
    """Test cases for AsciiProgressBackend."""

    def test_backend_initialization(self) -> None:
        """Test backend initialization with defaults."""
        output = io.StringIO()
        backend = AsciiProgressBackend(output=output)

        assert backend.output == output
        assert backend.bar_width == 30
        assert backend.max_name_width == 20
        assert len(backend.tasks) == 0

    def test_backend_add_task(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test adding a task to the backend."""
        ascii_backend.add_task(
            task_id="dl_1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
        )

        assert "dl_1" in ascii_backend.tasks
        task = ascii_backend.tasks["dl_1"]
        assert task.name == "test.AppImage"
        assert task.total == 1000.0

    def test_backend_update_task(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test updating task progress in backend."""
        ascii_backend.add_task(
            task_id="dl_1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
        )

        ascii_backend.update_task("dl_1", completed=500.0, speed=1024.0)

        task = ascii_backend.tasks["dl_1"]
        assert task.completed == 500.0
        assert task.speed == 1024.0

    def test_backend_finish_task(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test finishing a task in backend."""
        ascii_backend.add_task(
            task_id="dl_1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
        )

        ascii_backend.finish_task("dl_1", success=True, description="Complete")

        task = ascii_backend.tasks["dl_1"]
        assert task.is_finished
        assert task.success
        assert task.description == "Complete"

    def test_backend_multi_phase_task(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test backend handling of multi-phase tasks."""
        ascii_backend.add_task(
            task_id="vf_1",
            name="MyApp",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
        )

        ascii_backend.add_task(
            task_id="in_1",
            name="MyApp",
            progress_type=ProgressType.INSTALLATION,
            parent_task_id="vf_1",
            phase=2,
            total_phases=2,
        )

        verify_task = ascii_backend.tasks["vf_1"]
        install_task = ascii_backend.tasks["in_1"]

        assert verify_task.phase == 1
        assert verify_task.total_phases == 2
        assert install_task.phase == 2
        assert install_task.parent_task_id == "vf_1"

    @pytest.mark.asyncio
    async def test_backend_render_once(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test rendering backend output once."""
        ascii_backend.add_task(
            task_id="dl_1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
        )

        ascii_backend.update_task("dl_1", completed=500.0)

        await ascii_backend.render_once()

        # Check that output was written
        output_value = ascii_backend.output.getvalue()  # type: ignore[attr-defined]
        assert len(output_value) > 0

    def test_backend_interactive_vs_noninteractive(self) -> None:
        """Test interactive vs non-interactive mode detection."""
        output = io.StringIO()

        # Explicit interactive mode
        backend_interactive = AsciiProgressBackend(
            output=output, interactive=True
        )
        assert backend_interactive.interactive

        # Explicit non-interactive mode
        backend_noninteractive = AsciiProgressBackend(
            output=output, interactive=False
        )
        assert not backend_noninteractive.interactive
