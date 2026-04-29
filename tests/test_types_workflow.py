"""Tests for domain types.

This test suite validates the dataclass types used in workflow results
and planning.
"""

from my_unicorn.types import InstallPlan


class TestInstallPlan:
    """Test cases for InstallPlan dataclass."""

    def test_install_plan_all_fields(self) -> None:
        """Test InstallPlan with all fields populated."""
        plan = InstallPlan(
            urls_needing_work=["https://github.com/user/repo"],
            catalog_needing_work=["app1", "app2"],
            already_installed=["app3", "app4"],
        )

        assert plan.urls_needing_work == ["https://github.com/user/repo"]
        assert plan.catalog_needing_work == ["app1", "app2"]
        assert plan.already_installed == ["app3", "app4"]

    def test_install_plan_empty_lists(self) -> None:
        """Test InstallPlan with empty lists."""
        plan = InstallPlan(
            urls_needing_work=[],
            catalog_needing_work=[],
            already_installed=[],
        )

        assert plan.urls_needing_work == []
        assert plan.catalog_needing_work == []
        assert plan.already_installed == []

    def test_install_plan_only_urls(self) -> None:
        """Test InstallPlan with only URLs needing work."""
        plan = InstallPlan(
            urls_needing_work=[
                "https://github.com/user/repo1",
                "https://github.com/user/repo2",
            ],
            catalog_needing_work=[],
            already_installed=[],
        )

        assert len(plan.urls_needing_work) == 2
        assert len(plan.catalog_needing_work) == 0
        assert len(plan.already_installed) == 0

    def test_install_plan_only_catalog(self) -> None:
        """Test InstallPlan with only catalog apps needing work."""
        plan = InstallPlan(
            urls_needing_work=[],
            catalog_needing_work=["app1", "app2", "app3"],
            already_installed=[],
        )

        assert len(plan.urls_needing_work) == 0
        assert len(plan.catalog_needing_work) == 3
        assert len(plan.already_installed) == 0

    def test_install_plan_only_installed(self) -> None:
        """Test InstallPlan with only already installed apps."""
        plan = InstallPlan(
            urls_needing_work=[],
            catalog_needing_work=[],
            already_installed=["app1", "app2"],
        )

        assert len(plan.urls_needing_work) == 0
        assert len(plan.catalog_needing_work) == 0
        assert len(plan.already_installed) == 2

    def test_install_plan_immutable(self) -> None:
        """Test that InstallPlan fields can be modified (not frozen)."""
        plan = InstallPlan(
            urls_needing_work=["https://github.com/user/repo"],
            catalog_needing_work=["app1"],
            already_installed=[],
        )

        # Should be able to modify lists
        plan.urls_needing_work.append("https://github.com/user/repo2")
        assert len(plan.urls_needing_work) == 2
