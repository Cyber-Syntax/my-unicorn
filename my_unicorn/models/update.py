"""Update operation models and data structures."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..update import UpdateInfo


@dataclass
class UpdateResult:
    """Result object containing update operation outcomes."""

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
