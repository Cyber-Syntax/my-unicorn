"""Tests for TargetResolver.

This test suite validates the target resolution logic for separating
installation targets into URLs and catalog names.
"""

from unittest.mock import Mock

import pytest

from my_unicorn.core.services.install_service import TargetResolver
from my_unicorn.exceptions import InstallationError


class TestTargetResolver:
    """Test cases for TargetResolver."""

    def test_separate_targets_with_mixed_targets(self) -> None:
        """Test separating mixed URLs and catalog names."""
        config_manager = Mock()
        config_manager.list_catalog_apps.return_value = [
            "qownnotes",
            "appflowy",
            "zen-browser",
        ]

        targets = [
            "qownnotes",
            "https://github.com/user/repo",
            "appflowy",
            "https://github.com/another/app",
        ]

        url_targets, catalog_targets = TargetResolver.separate_targets(
            config_manager, targets
        )

        assert url_targets == [
            "https://github.com/user/repo",
            "https://github.com/another/app",
        ]
        assert catalog_targets == ["qownnotes", "appflowy"]

    def test_separate_targets_only_urls(self) -> None:
        """Test with only URL targets."""
        config_manager = Mock()
        config_manager.list_catalog_apps.return_value = ["qownnotes"]

        targets = [
            "https://github.com/user/repo",
            "https://github.com/another/app",
        ]

        url_targets, catalog_targets = TargetResolver.separate_targets(
            config_manager, targets
        )

        assert url_targets == targets
        assert catalog_targets == []

    def test_separate_targets_only_catalog(self) -> None:
        """Test with only catalog targets."""
        config_manager = Mock()
        config_manager.list_catalog_apps.return_value = [
            "qownnotes",
            "appflowy",
        ]

        targets = ["qownnotes", "appflowy"]

        url_targets, catalog_targets = TargetResolver.separate_targets(
            config_manager, targets
        )

        assert url_targets == []
        assert catalog_targets == targets

    def test_separate_targets_empty_list(self) -> None:
        """Test with empty target list."""
        config_manager = Mock()
        config_manager.list_catalog_apps.return_value = ["qownnotes"]

        targets: list[str] = []

        url_targets, catalog_targets = TargetResolver.separate_targets(
            config_manager, targets
        )

        assert url_targets == []
        assert catalog_targets == []

    def test_separate_targets_unknown_raises_error(self) -> None:
        """Test that unknown targets raise InstallationError."""
        config_manager = Mock()
        config_manager.list_catalog_apps.return_value = ["qownnotes"]

        targets = ["qownnotes", "unknown-app", "another-unknown"]

        with pytest.raises(
            InstallationError, match="Unknown applications or invalid URLs"
        ):
            TargetResolver.separate_targets(config_manager, targets)

    def test_separate_targets_single_unknown_raises_error(self) -> None:
        """Test that a single unknown target raises InstallationError."""
        config_manager = Mock()
        config_manager.list_catalog_apps.return_value = ["qownnotes"]

        targets = ["unknown-app"]

        with pytest.raises(
            InstallationError, match="Unknown applications or invalid URLs"
        ):
            TargetResolver.separate_targets(config_manager, targets)

    def test_separate_targets_preserves_order(self) -> None:
        """Test that target order is preserved."""
        config_manager = Mock()
        config_manager.list_catalog_apps.return_value = [
            "app-a",
            "app-b",
            "app-c",
        ]

        targets = [
            "app-c",
            "https://github.com/user/repo1",
            "app-a",
            "https://github.com/user/repo2",
            "app-b",
        ]

        url_targets, catalog_targets = TargetResolver.separate_targets(
            config_manager, targets
        )

        assert url_targets == [
            "https://github.com/user/repo1",
            "https://github.com/user/repo2",
        ]
        assert catalog_targets == ["app-c", "app-a", "app-b"]

    def test_separate_targets_case_sensitive(self) -> None:
        """Test that catalog name matching is case-sensitive."""
        config_manager = Mock()
        config_manager.list_catalog_apps.return_value = ["QOwnNotes"]

        targets = ["qownnotes"]  # lowercase

        with pytest.raises(
            InstallationError, match="Unknown applications or invalid URLs"
        ):
            TargetResolver.separate_targets(config_manager, targets)
