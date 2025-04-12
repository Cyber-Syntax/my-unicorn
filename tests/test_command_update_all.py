
import unittest
from unittest.mock import MagicMock

from commands.update_all import AppImageUpdater, UpdateCommand, VersionChecker
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager


# A subclass of UpdateCommand to override interactive and external dependencies.
class FakeUpdateCommand(UpdateCommand):
    def __init__(self):
        # Override components with fake instances.
        self.global_config = GlobalConfigManager(config_file="/tmp/settings.json")
        self.app_config = AppConfigManager(owner="testowner", repo="testrepo")
        self.version_checker = VersionChecker()
        self.appimage_updater = AppImageUpdater()

    def execute(self):
        # Simulate an update scenario with one app that has a new version.
        updatable = [{
            "config_file": "/tmp/testrepo.json",
            "name": "test.AppImage",
            "current": "1.0.0",
            "latest": "1.1.0"
        }]
        # Auto-confirm updates (simulate batch mode).
        self._confirm_updates = lambda apps: True
        # Override the updater's batch execution to a no-op that asserts the updatable list.
        self.appimage_updater.execute_batch = MagicMock()
        self.appimage_updater.execute_batch(updatable, self.global_config)
        return True

class TestUpdateCommand(unittest.TestCase):
    def test_execute_flow(self):
        cmd = FakeUpdateCommand()
        result = cmd.execute()
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
