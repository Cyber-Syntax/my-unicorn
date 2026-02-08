import pytest

from my_unicorn.core.progress.progress import (
    ProgressConfig,
    ProgressType,
    TaskInfo,
    TaskState,
)


class TestTaskState:
    """Test cases for TaskState dataclass."""

    def test_task_state_creation(self) -> None:
        """Test creating a TaskState with required fields."""
        state = TaskState(
            task_id="task_1",
            name="Test Task",
            progress_type=ProgressType.DOWNLOAD,
        )

        assert state.task_id == "task_1"
        assert state.name == "Test Task"
        assert state.progress_type == ProgressType.DOWNLOAD
        assert state.total == 0.0
        assert state.completed == 0.0
        assert state.success is None
        assert not state.is_finished

    def test_task_state_multi_phase(self) -> None:
        """Test TaskState with multi-phase tracking."""
        state = TaskState(
            task_id="task_1",
            name="Multi-phase Task",
            progress_type=ProgressType.VERIFICATION,
            parent_task_id="parent_task",
            phase=1,
            total_phases=2,
        )

        assert state.parent_task_id == "parent_task"
        assert state.phase == 1
        assert state.total_phases == 2


class TestProgressType:
    """Test cases for ProgressType enum."""

    def test_all_progress_types_exist(self) -> None:
        """Test that all expected progress types are defined."""
        expected_types = {
            "API_FETCHING",
            "DOWNLOAD",
            "VERIFICATION",
            "ICON_EXTRACTION",
            "INSTALLATION",
            "UPDATE",
        }

        actual_types = {pt.name for pt in ProgressType}

        assert actual_types == expected_types


class TestTaskInfo:
    """Test cases for TaskInfo dataclass."""

    def test_progress_task_creation(self) -> None:
        """Test creating a TaskInfo with required fields."""
        task_id = "test_task_1"
        task = TaskInfo(
            task_id=task_id,
            namespaced_id="test_1_task",
            name="Test Task",
            progress_type=ProgressType.DOWNLOAD,
        )

        assert task.task_id == task_id
        assert task.namespaced_id == "test_1_task"
        assert task.name == "Test Task"
        assert task.progress_type == ProgressType.DOWNLOAD
        assert task.total == 0.0
        assert task.completed == 0.0
        assert task.success is None
        assert not task.is_finished

    def test_task_info_with_speed_history(self) -> None:
        """Test TaskInfo speed tracking initialization."""
        task = TaskInfo(
            task_id="dl_1",
            namespaced_id="dl_1_file",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
        )

        # Speed history should be initialized in __post_init__
        assert task.speed_history is not None
        assert len(task.speed_history) == 0

    def test_task_info_multi_phase(self) -> None:
        """Test TaskInfo with multi-phase tracking."""
        task = TaskInfo(
            task_id="vf_1",
            namespaced_id="vf_1_app",
            name="MyApp",
            progress_type=ProgressType.VERIFICATION,
            parent_task_id="parent_1",
            phase=1,
            total_phases=2,
        )

        assert task.parent_task_id == "parent_1"
        assert task.phase == 1
        assert task.total_phases == 2


class TestProgressConfig:
    """Test cases for ProgressConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ProgressConfig()

        assert config.refresh_per_second == 4
        assert not config.show_overall
        assert config.show_api_fetching
        assert config.show_downloads
        assert config.show_post_processing
        assert config.batch_ui_updates
        assert config.ui_update_interval == 0.25
        assert config.speed_calculation_interval == 0.5
        assert config.max_speed_history == 10

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = ProgressConfig(
            refresh_per_second=10,
            show_overall=True,
            show_api_fetching=False,
            batch_ui_updates=False,
            ui_update_interval=0.1,
        )

        assert config.refresh_per_second == 10
        assert config.show_overall
        assert not config.show_api_fetching
        assert not config.batch_ui_updates
        assert config.ui_update_interval == 0.1

    def test_invalid_config_validation(self) -> None:
        """ProgressConfig validation should reject invalid values."""
        with pytest.raises(ValueError):
            ProgressConfig(refresh_per_second=0)

        with pytest.raises(ValueError):
            ProgressConfig(bar_width=0)

        with pytest.raises(ValueError):
            ProgressConfig(spinner_fps=0)
