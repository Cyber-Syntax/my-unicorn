"""Tests for update result class."""

from unittest.mock import Mock

from my_unicorn.models.update import UpdateResult

# UpdateContext has been removed as part of simplification
# The update command now directly uses UpdateManager without context wrapper


class TestUpdateResult:
    """Test UpdateResult class."""

    def test_initialization_minimal(self):
        """Test UpdateResult initialization with minimal data."""
        result = UpdateResult(
            success=True,
            updated_apps=["app1"],
            failed_apps=[],
            up_to_date_apps=["app2"],
            update_infos=[],
            message="Update completed",
        )

        assert result.success is True
        assert result.updated_apps == ["app1"]
        assert result.failed_apps == []
        assert result.up_to_date_apps == ["app2"]
        assert result.update_infos == []
        assert result.message == "Update completed"

    def test_initialization_with_failures(self):
        """Test UpdateResult initialization with failed apps."""
        result = UpdateResult(
            success=False,
            updated_apps=[],
            failed_apps=["app1", "app2"],
            up_to_date_apps=[],
            update_infos=[],
            message="Update failed for some apps",
        )

        assert result.success is False
        assert result.updated_apps == []
        assert result.failed_apps == ["app1", "app2"]
        assert result.up_to_date_apps == []

    def test_has_updates_property_with_updates(self):
        """Test has_updates property when updates are available."""
        mock_update_info1 = Mock()
        mock_update_info1.has_update = True

        mock_update_info2 = Mock()
        mock_update_info2.has_update = False

        result = UpdateResult(
            success=True,
            updated_apps=["app1"],
            failed_apps=[],
            up_to_date_apps=["app2"],
            update_infos=[mock_update_info1, mock_update_info2],
            message="Update completed",
        )

        assert result.has_updates is True

    def test_has_updates_property_without_updates(self):
        """Test has_updates property when no updates are available."""
        mock_update_info1 = Mock()
        mock_update_info1.has_update = False

        mock_update_info2 = Mock()
        mock_update_info2.has_update = False

        result = UpdateResult(
            success=True,
            updated_apps=[],
            failed_apps=[],
            up_to_date_apps=["app1", "app2"],
            update_infos=[mock_update_info1, mock_update_info2],
            message="All apps up to date",
        )

        assert result.has_updates is False

    def test_has_updates_property_empty_infos(self):
        """Test has_updates property with empty update_infos."""
        result = UpdateResult(
            success=True,
            updated_apps=[],
            failed_apps=[],
            up_to_date_apps=[],
            update_infos=[],
            message="No apps processed",
        )

        assert result.has_updates is False

    def test_total_apps_property(self):
        """Test total_apps property."""
        mock_update_info1 = Mock()
        mock_update_info2 = Mock()
        mock_update_info3 = Mock()

        result = UpdateResult(
            success=True,
            updated_apps=["app1"],
            failed_apps=["app2"],
            up_to_date_apps=["app3"],
            update_infos=[
                mock_update_info1,
                mock_update_info2,
                mock_update_info3,
            ],
            message="Update completed",
        )

        assert result.total_apps == 3

    def test_total_apps_property_empty(self):
        """Test total_apps property with empty update_infos."""
        result = UpdateResult(
            success=True,
            updated_apps=[],
            failed_apps=[],
            up_to_date_apps=[],
            update_infos=[],
            message="No apps processed",
        )

        assert result.total_apps == 0

    def test_equality(self):
        """Test UpdateResult equality comparison."""
        mock_update_info = Mock()

        result1 = UpdateResult(
            success=True,
            updated_apps=["app1"],
            failed_apps=[],
            up_to_date_apps=["app2"],
            update_infos=[mock_update_info],
            message="Update completed",
        )

        result2 = UpdateResult(
            success=True,
            updated_apps=["app1"],
            failed_apps=[],
            up_to_date_apps=["app2"],
            update_infos=[mock_update_info],
            message="Update completed",
        )

        assert result1 == result2

    def test_mixed_scenario(self):
        """Test result with mixed update outcomes."""
        mock_update_info1 = Mock()
        mock_update_info1.has_update = True

        mock_update_info2 = Mock()
        mock_update_info2.has_update = False

        mock_update_info3 = Mock()
        mock_update_info3.has_update = True

        result = UpdateResult(
            success=True,  # Overall success despite one failure
            updated_apps=["app1"],
            failed_apps=["app3"],
            up_to_date_apps=["app2"],
            update_infos=[
                mock_update_info1,
                mock_update_info2,
                mock_update_info3,
            ],
            message="Partially completed",
        )

        assert result.success is True
        assert result.has_updates is True
        assert result.total_apps == 3
        assert len(result.updated_apps) == 1
        assert len(result.failed_apps) == 1
        assert len(result.up_to_date_apps) == 1
