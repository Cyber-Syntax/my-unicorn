"""Update operation models and data structures."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import ConfigManager
    from ..update import UpdateInfo, UpdateManager


@dataclass
class UpdateContext:
    """Context object containing all data needed for update operations.

    This object is passed to strategies and contains all the dependencies
    and configuration needed to perform update operations.
    """

    app_names: list[str] | None
    check_only: bool
    refresh_cache: bool
    config_manager: "ConfigManager"
    update_manager: "UpdateManager"


@dataclass
class UpdateResult:
    """Result object containing update operation outcomes.

    This standardized result format is returned by all update strategies
    to provide consistent information about what happened during the operation.
    """

    success: bool
    updated_apps: list[str]
    failed_apps: list[str]
    up_to_date_apps: list[str]
    update_infos: list["UpdateInfo"]
    message: str

    @property
    def has_updates(self) -> bool:
        """Check if any apps had updates available."""
        return any(info.has_update for info in self.update_infos)

    @property
    def total_apps(self) -> int:
        """Get total number of apps processed."""
        return len(self.update_infos)
