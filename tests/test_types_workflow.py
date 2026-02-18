"""Tests for domain types.

This test suite validates the dataclass types used in workflow results
and planning.
"""

from my_unicorn.types import InstallPlan, InstallResult, UpdateResult


class TestInstallResult:
    """Test cases for InstallResult dataclass."""

    def test_install_result_success(self) -> None:
        """Test successful installation result."""
        result = InstallResult(
            success=True,
            app_name="test-app",
            version="1.0.0",
            message="Installation successful",
            source="catalog",
            installed_path="/tmp/test-app.AppImage",
            desktop_entry="/tmp/test-app.desktop",
            icon_path="/tmp/test-app.png",
        )

        assert result.success is True
        assert result.app_name == "test-app"
        assert result.version == "1.0.0"
        assert result.source == "catalog"
        assert result.error is None

    def test_install_result_failure(self) -> None:
        """Test failed installation result."""
        result = InstallResult(
            success=False,
            app_name="test-app",
            version="1.0.0",
            message="Installation failed",
            source="url",
            error="Download failed",
        )

        assert result.success is False
        assert result.error == "Download failed"
        assert result.installed_path is None

    def test_install_result_to_dict_full(self) -> None:
        """Test conversion to dict with all fields."""
        result = InstallResult(
            success=True,
            app_name="test-app",
            version="1.0.0",
            message="Installation successful",
            source="catalog",
            installed_path="/tmp/test-app.AppImage",
            desktop_entry="/tmp/test-app.desktop",
            icon_path="/tmp/test-app.png",
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["app_name"] == "test-app"
        assert result_dict["version"] == "1.0.0"
        assert result_dict["message"] == "Installation successful"
        assert result_dict["source"] == "catalog"
        assert result_dict["installed_path"] == "/tmp/test-app.AppImage"
        assert result_dict["desktop"] == "/tmp/test-app.desktop"
        assert result_dict["icon"] == "/tmp/test-app.png"
        assert "error" not in result_dict

    def test_install_result_to_dict_minimal(self) -> None:
        """Test conversion to dict with minimal fields."""
        result = InstallResult(
            success=False,
            app_name="test-app",
            version="1.0.0",
            message="Installation failed",
            source="url",
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is False
        assert result_dict["app_name"] == "test-app"
        assert "installed_path" not in result_dict
        assert "desktop" not in result_dict
        assert "icon" not in result_dict
        assert "error" not in result_dict

    def test_install_result_to_dict_with_error(self) -> None:
        """Test conversion to dict with error field."""
        result = InstallResult(
            success=False,
            app_name="test-app",
            version="1.0.0",
            message="Installation failed",
            source="catalog",
            error="Verification failed",
        )

        result_dict = result.to_dict()

        assert result_dict["error"] == "Verification failed"


class TestUpdateResult:
    """Test cases for UpdateResult dataclass."""

    def test_update_result_success(self) -> None:
        """Test successful update result."""
        result = UpdateResult(
            success=True,
            app_name="test-app",
            old_version="1.0.0",
            new_version="2.0.0",
            message="Update successful",
            updated_path="/tmp/test-app.AppImage",
            backup_path="/tmp/test-app-1.0.0.AppImage.backup",
        )

        assert result.success is True
        assert result.old_version == "1.0.0"
        assert result.new_version == "2.0.0"
        assert result.error is None

    def test_update_result_failure(self) -> None:
        """Test failed update result."""
        result = UpdateResult(
            success=False,
            app_name="test-app",
            old_version="1.0.0",
            new_version="2.0.0",
            message="Update failed",
            error="Download failed",
        )

        assert result.success is False
        assert result.error == "Download failed"
        assert result.updated_path is None
        assert result.backup_path is None

    def test_update_result_to_dict_full(self) -> None:
        """Test conversion to dict with all fields."""
        result = UpdateResult(
            success=True,
            app_name="test-app",
            old_version="1.0.0",
            new_version="2.0.0",
            message="Update successful",
            updated_path="/tmp/test-app.AppImage",
            backup_path="/tmp/test-app-1.0.0.AppImage.backup",
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["app_name"] == "test-app"
        assert result_dict["old_version"] == "1.0.0"
        assert result_dict["new_version"] == "2.0.0"
        assert result_dict["message"] == "Update successful"
        assert result_dict["updated_path"] == "/tmp/test-app.AppImage"
        assert (
            result_dict["backup_path"] == "/tmp/test-app-1.0.0.AppImage.backup"
        )
        assert "error" not in result_dict

    def test_update_result_to_dict_minimal(self) -> None:
        """Test conversion to dict with minimal fields."""
        result = UpdateResult(
            success=False,
            app_name="test-app",
            old_version="1.0.0",
            new_version="2.0.0",
            message="Update failed",
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is False
        assert "updated_path" not in result_dict
        assert "backup_path" not in result_dict
        assert "error" not in result_dict

    def test_update_result_to_dict_with_error(self) -> None:
        """Test conversion to dict with error field."""
        result = UpdateResult(
            success=False,
            app_name="test-app",
            old_version="1.0.0",
            new_version="2.0.0",
            message="Update failed",
            error="Verification failed",
        )

        result_dict = result.to_dict()

        assert result_dict["error"] == "Verification failed"


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
