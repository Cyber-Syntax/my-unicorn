"""Shared types and constants for progress tracking and display."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum, auto

# caps the size of cached generated IDs to avoid unbounded growth.
ID_CACHE_LIMIT = 1000


class Phase(Enum):
    """Main operation types for progress tracking.

    Example:
    - API_FETCHING: Querying upstream releases for all apps.
    - DOWNLOAD: Downloading appimages for all apps.
    - PROCESSING: Verifying, installing, and performing post-processing for all apps.
    """

    API_FETCHING = auto()
    DOWNLOAD = auto()
    PROCESSING = auto()


class ProcessingPhase(Enum):
    """Sub processing types for PROCESSING phase.

    Example:
    - VERIFICATION: Verifying the integrity of a downloaded appimage.
    - INSTALLATION: Installing an appimage to the system.
    - UPDATE: Updating an already installed appimage to a new version.
    - ICON_EXTRACTION: Extracting the app icon from the appimage.
    - DESKTOP_ENTRY_CREATION: Creating a .desktop entry for the installed app.
    """

    VERIFICATION = auto()
    INSTALLATION = auto()
    UPDATE = auto()
    ICON_EXTRACTION = auto()
    DESKTOP_ENTRY_CREATION = auto()


# Section headers for each main operation type
PHASE_SECTION_LABELS: dict[Phase, str] = {
    Phase.API_FETCHING: ":: Querying upstream releases...",
    Phase.DOWNLOAD: ":: Retrieving appimages...",
    Phase.PROCESSING: ":: Processing package changes...",
}

TRANSACTION_SUMMARY_HEADER: str = ":: Creating transaction summary..."

# Per-task verbs
PROCESSING_LABELS: dict[ProcessingPhase, str] = {
    ProcessingPhase.VERIFICATION: "verifying",
    ProcessingPhase.INSTALLATION: "installing",
    ProcessingPhase.UPDATE: "upgrading",
    ProcessingPhase.ICON_EXTRACTION: "extracting icon",
    ProcessingPhase.DESKTOP_ENTRY_CREATION: "creating desktop entry",
}

# Small tunables exposed for easier testing
DEFAULT_MIN_NAME_WIDTH: int = 15
DEFAULT_SPINNER_FPS: int = 4
DEFAULT_MAX_SPEED_HISTORY: int = 10
DEFAULT_BAR_WIDTH: int = 30

# Spinner frames for in-progress tasks
SPINNER_FRAMES: list[str] = [
    "⠋",
    "⠙",
    "⠹",
    "⠸",
    "⠼",
    "⠴",
    "⠦",
    "⠧",
    "⠇",
    "⠏",
]


@dataclass(slots=True)
class TaskState:
    """State information for a single task in the backend."""

    task_id: str
    name: str
    progress_type: Phase
    sub_type: ProcessingPhase | None = None
    total: float = 0.0
    completed: float = 0.0
    description: str = ""
    speed: float = 0.0  # bytes per second
    success: bool | None = None
    is_finished: bool = False
    created_at: float = 0.0
    last_update: float = 0.0
    error_message: str = ""
    # Multi-phase task tracking
    parent_task_id: str | None = None  # For tracking related tasks
    phase: int = 1  # Current phase (1 for verify, 2 for install)
    total_phases: int = 1  # Total number of phases


@dataclass(frozen=True, slots=True)
class TaskConfig:
    """Configuration for creating a new progress task."""

    name: str
    progress_type: Phase
    sub_type: ProcessingPhase | None = None
    total: float = 0.0
    description: str | None = None
    parent_task_id: str | None = None
    phase: int = 1
    total_phases: int = 1


@dataclass(frozen=True, slots=True)
class ProgressConfig:
    """Configuration for progress display."""

    refresh_per_second: int = 4
    show_overall: bool = False
    show_api_fetching: bool = True
    show_downloads: bool = True
    show_post_processing: bool = True
    batch_ui_updates: bool = True
    ui_update_interval: float = 0.25  # Seconds between batched UI updates
    speed_calculation_interval: float = (
        0.5  # Minimum interval for speed recalculation
    )
    max_speed_history: int = DEFAULT_MAX_SPEED_HISTORY

    # Display tuning
    bar_width: int = 30
    min_name_width: int = DEFAULT_MIN_NAME_WIDTH
    spinner_fps: int = DEFAULT_SPINNER_FPS
    max_name_width: int = 20

    def __post_init__(self) -> None:
        """Validate config fields to prevent invalid runtime values."""
        if self.refresh_per_second < 1:
            raise ValueError("refresh_per_second must be >= 1")
        if self.bar_width < 1:
            raise ValueError("bar_width must be >= 1")
        if self.spinner_fps < 1:
            raise ValueError("spinner_fps must be >= 1")
        if self.ui_update_interval <= 0:
            raise ValueError("ui_update_interval must be > 0")
        if self.speed_calculation_interval <= 0:
            raise ValueError("speed_calculation_interval must be > 0")
        if self.max_speed_history < 1:
            raise ValueError("max_speed_history must be >= 1")


@dataclass(slots=True)
class TaskInfo:
    """Task information with all metadata in one structure."""

    # Core task data
    task_id: str
    namespaced_id: str
    name: str
    progress_type: Phase
    sub_type: ProcessingPhase | None = None
    total: float = 0.0
    completed: float = 0.0
    description: str = ""
    success: bool | None = None
    is_finished: bool = False

    # Timing data
    created_at: float = 0.0
    last_update: float = 0.0
    last_speed_update: float = 0.0

    # Speed tracking for downloads
    current_speed_mbps: float = 0.0
    # (timestamp, speed) pairs
    speed_history: deque[tuple[float, float]] | None = None

    # Carries the max number of speed history size from the ProgressConfig
    # so the deque is created with the correct maxlen in __post_init__
    max_speed_history: int = DEFAULT_MAX_SPEED_HISTORY

    # Multi-phase task tracking
    parent_task_id: str | None = None
    phase: int = 1
    total_phases: int = 1

    def __post_init__(self) -> None:
        """Initialize speed history deque."""
        if self.completed < 0:
            raise ValueError("completed must be >= 0")
        if self.total < 0:
            raise ValueError("total must be >= 0")
        if self.speed_history is None:
            # use the instance-level value so ProgressConfig.max_speed_history
            # is actually respected at runtime.
            self.speed_history = deque(maxlen=self.max_speed_history)
