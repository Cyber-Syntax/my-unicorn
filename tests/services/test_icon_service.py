"""Comprehensive tests for IconService with high coverage and edge cases."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.download import DownloadService, IconAsset
from my_unicorn.services.icon_service import IconConfig, IconResult, IconService


class TestIconConfig:
    """Test cases for IconConfig dataclass."""

    def test_icon_config_creation(self):
        """Test IconConfig can be created with required parameters."""
        config = IconConfig(
            extraction_enabled=True,
            icon_url="https://example.com/icon.png",
            icon_filename="test.png",
        )

        assert config.extraction_enabled is True
        assert config.icon_url == "https://example.com/icon.png"
        assert config.icon_filename == "test.png"
        assert config.preserve_url_on_extraction is False  # Default value

    def test_icon_config_with_preserve_url(self):
        """Test IconConfig with preserve_url_on_extraction set to True."""
        config = IconConfig(
            extraction_enabled=False,
            icon_url="https://example.com/icon.png",
            icon_filename="test.png",
            preserve_url_on_extraction=True,
        )

        assert config.preserve_url_on_extraction is True

    def test_icon_config_immutable(self):
        """Test that IconConfig is immutable (frozen)."""
        config = IconConfig(
            extraction_enabled=True,
            icon_url="https://example.com/icon.png",
            icon_filename="test.png",
        )

        with pytest.raises(AttributeError):
            config.extraction_enabled = False

    def test_icon_config_none_url(self):
        """Test IconConfig with None URL."""
        config = IconConfig(
            extraction_enabled=True,
            icon_url=None,
            icon_filename="test.png",
        )

        assert config.icon_url is None


class TestIconResult:
    """Test cases for IconResult dataclass."""

    def test_icon_result_creation(self):
        """Test IconResult can be created with all parameters."""
        result = IconResult(
            icon_path=Path("/test/icon.png"),
            source="extraction",
            config={"installed": True, "extraction": True},
        )

        assert result.icon_path == Path("/test/icon.png")
        assert result.source == "extraction"
        assert result.config == {"installed": True, "extraction": True}

    def test_icon_result_none_path(self):
        """Test IconResult with None icon_path."""
        result = IconResult(
            icon_path=None,
            source="none",
            config={"installed": False},
        )

        assert result.icon_path is None
        assert result.source == "none"

    def test_icon_result_immutable(self):
        """Test that IconResult is immutable (frozen)."""
        result = IconResult(
            icon_path=Path("/test/icon.png"),
            source="extraction",
            config={"test": True},
        )

        with pytest.raises(AttributeError):
            result.source = "github"


class TestIconService:
    """Test cases for IconService."""

    @pytest.fixture
    def mock_download_service(self):
        """Create a mock DownloadService."""
        return MagicMock(spec=DownloadService)

    @pytest.fixture
    def icon_service(self, mock_download_service):
        """Create an IconService instance with mock dependencies."""
        return IconService(mock_download_service)

    @pytest.fixture
    def sample_icon_config(self):
        """Create a sample IconConfig for testing."""
        return IconConfig(
            extraction_enabled=True,
            icon_url="https://github.com/test/repo/raw/main/icon.png",
            icon_filename="testapp.png",
        )

    @pytest.fixture
    def mock_paths(self, tmp_path):
        """Create mock paths for testing."""
        icon_dir = tmp_path / "icons"
        icon_dir.mkdir()
        appimage_path = tmp_path / "testapp.AppImage"
        appimage_path.write_bytes(b"mock appimage content")

        return {
            "icon_dir": icon_dir,
            "appimage_path": appimage_path,
            "dest_path": icon_dir / "testapp.png",
        }

    def test_determine_extraction_preference_from_current_config(self, icon_service):
        """Test extraction preference detection from current config."""
        current_config = {"extraction": False}
        catalog_entry = {"icon": {"extraction": True}}

        result = icon_service._determine_extraction_preference(current_config, catalog_entry)

        assert result is False  # Current config takes priority

    def test_determine_extraction_preference_from_catalog(self, icon_service):
        """Test extraction preference detection from catalog entry."""
        current_config = {}
        catalog_entry = {"icon": {"extraction": False}}

        result = icon_service._determine_extraction_preference(current_config, catalog_entry)

        assert result is False

    def test_determine_extraction_preference_default(self, icon_service):
        """Test extraction preference defaults to True."""
        current_config = {}
        catalog_entry = None

        result = icon_service._determine_extraction_preference(current_config, catalog_entry)

        assert result is True

    def test_determine_extraction_preference_catalog_none_extraction(self, icon_service):
        """Test extraction preference when catalog has None extraction value."""
        current_config = {}
        catalog_entry = {"icon": {"extraction": None}}

        result = icon_service._determine_extraction_preference(current_config, catalog_entry)

        assert result is True  # Should use default

    def test_generate_icon_filename_default_extension(self, icon_service):
        """Test icon filename generation with default extension."""
        filename = icon_service._generate_icon_filename("testapp")

        assert filename == "testapp.png"

    def test_generate_icon_filename_from_url_svg(self, icon_service):
        """Test icon filename generation with SVG extension from URL."""
        filename = icon_service._generate_icon_filename(
            "testapp", "https://example.com/icon.svg"
        )

        assert filename == "testapp.svg"

    def test_generate_icon_filename_from_url_ico(self, icon_service):
        """Test icon filename generation with ICO extension from URL."""
        filename = icon_service._generate_icon_filename(
            "testapp", "https://example.com/icon.ico"
        )

        assert filename == "testapp.ico"

    def test_generate_icon_filename_unsupported_extension(self, icon_service):
        """Test icon filename generation with unsupported extension."""
        filename = icon_service._generate_icon_filename(
            "testapp", "https://example.com/icon.jpeg"
        )

        assert filename == "testapp.png"  # Falls back to default

    def test_generate_icon_filename_no_extension(self, icon_service):
        """Test icon filename generation with URL without extension."""
        filename = icon_service._generate_icon_filename("testapp", "https://example.com/icon")

        assert filename == "testapp.png"

    @pytest.mark.asyncio
    async def test_attempt_extraction_success(self, icon_service, mock_paths):
        """Test successful icon extraction."""
        mock_icon_path = mock_paths["dest_path"]

        with patch("my_unicorn.services.icon_service.IconManager") as mock_icon_manager_class:
            mock_icon_manager = AsyncMock()
            mock_icon_manager_class.return_value = mock_icon_manager
            mock_icon_manager.extract_icon_only.return_value = mock_icon_path

            result = await icon_service._attempt_extraction(
                mock_paths["appimage_path"],
                mock_paths["dest_path"],
                "testapp",
            )

            assert result == mock_icon_path
            mock_icon_manager_class.assert_called_once_with(enable_extraction=True)
            mock_icon_manager.extract_icon_only.assert_called_once_with(
                appimage_path=mock_paths["appimage_path"],
                dest_path=mock_paths["dest_path"],
                app_name="testapp",
            )

    @pytest.mark.asyncio
    async def test_attempt_extraction_failure(self, icon_service, mock_paths):
        """Test failed icon extraction."""
        with patch("my_unicorn.services.icon_service.IconManager") as mock_icon_manager_class:
            mock_icon_manager = AsyncMock()
            mock_icon_manager_class.return_value = mock_icon_manager
            mock_icon_manager.extract_icon_only.side_effect = Exception("Extraction failed")

            result = await icon_service._attempt_extraction(
                mock_paths["appimage_path"],
                mock_paths["dest_path"],
                "testapp",
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_attempt_extraction_no_icon_found(self, icon_service, mock_paths):
        """Test extraction when no icon is found."""
        with patch("my_unicorn.services.icon_service.IconManager") as mock_icon_manager_class:
            mock_icon_manager = AsyncMock()
            mock_icon_manager_class.return_value = mock_icon_manager
            mock_icon_manager.extract_icon_only.return_value = None

            result = await icon_service._attempt_extraction(
                mock_paths["appimage_path"],
                mock_paths["dest_path"],
                "testapp",
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_attempt_github_download_success(self, icon_service, mock_paths):
        """Test successful GitHub icon download."""
        icon_asset = IconAsset(
            icon_filename="testapp.png",
            icon_url="https://github.com/test/repo/raw/main/icon.png",
        )
        mock_icon_path = mock_paths["dest_path"]

        icon_service.download_service.download_icon.return_value = mock_icon_path

        result = await icon_service._attempt_github_download(
            icon_asset,
            mock_paths["dest_path"],
            "testapp",
        )

        assert result == mock_icon_path
        icon_service.download_service.download_icon.assert_called_once_with(
            icon_asset, mock_paths["dest_path"]
        )

    @pytest.mark.asyncio
    async def test_attempt_github_download_failure(self, icon_service, mock_paths):
        """Test failed GitHub icon download."""
        icon_asset = IconAsset(
            icon_filename="testapp.png",
            icon_url="https://github.com/test/repo/raw/main/icon.png",
        )

        icon_service.download_service.download_icon.side_effect = Exception("Download failed")

        result = await icon_service._attempt_github_download(
            icon_asset,
            mock_paths["dest_path"],
            "testapp",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_attempt_github_download_no_icon_returned(self, icon_service, mock_paths):
        """Test GitHub download when no icon is returned."""
        icon_asset = IconAsset(
            icon_filename="testapp.png",
            icon_url="https://github.com/test/repo/raw/main/icon.png",
        )

        icon_service.download_service.download_icon.return_value = None

        result = await icon_service._attempt_github_download(
            icon_asset,
            mock_paths["dest_path"],
            "testapp",
        )

        assert result is None

    def test_build_updated_config_extraction_success(self, icon_service, mock_paths):
        """Test config building for successful extraction."""
        base_config = {"old_key": "old_value"}

        result = icon_service._build_updated_config(
            base_config=base_config,
            icon_source="extraction",
            icon_path=mock_paths["dest_path"],
            icon_filename="testapp.png",
            icon_url="https://example.com/icon.png",
            extraction_enabled=True,
            preserve_url_on_extraction=True,
        )

        expected = {
            "old_key": "old_value",
            "source": "extraction",
            "name": "testapp.png",
            "installed": True,
            "path": str(mock_paths["dest_path"]),
            "extraction": True,
            "url": "https://example.com/icon.png",
        }

        assert result == expected

    def test_build_updated_config_github_success(self, icon_service, mock_paths):
        """Test config building for successful GitHub download."""
        base_config = {}

        result = icon_service._build_updated_config(
            base_config=base_config,
            icon_source="github",
            icon_path=mock_paths["dest_path"],
            icon_filename="testapp.png",
            icon_url="https://example.com/icon.png",
            extraction_enabled=True,
            preserve_url_on_extraction=False,
        )

        expected = {
            "source": "github",
            "name": "testapp.png",
            "installed": True,
            "path": str(mock_paths["dest_path"]),
            "extraction": False,
            "url": "https://example.com/icon.png",
        }

        assert result == expected

    def test_build_updated_config_no_icon_acquired(self, icon_service):
        """Test config building when no icon was acquired."""
        base_config = {"existing": "value"}

        result = icon_service._build_updated_config(
            base_config=base_config,
            icon_source="none",
            icon_path=None,
            icon_filename="testapp.png",
            icon_url="https://example.com/icon.png",
            extraction_enabled=False,
            preserve_url_on_extraction=False,
        )

        expected = {
            "existing": "value",
            "source": "none",
            "name": "testapp.png",
            "installed": False,
            "path": None,
            "extraction": False,
            "url": "https://example.com/icon.png",
        }

        assert result == expected

    def test_build_updated_config_extraction_clear_url(self, icon_service, mock_paths):
        """Test config building for extraction without preserving URL."""
        result = icon_service._build_updated_config(
            base_config={},
            icon_source="extraction",
            icon_path=mock_paths["dest_path"],
            icon_filename="testapp.png",
            icon_url="https://example.com/icon.png",
            extraction_enabled=True,
            preserve_url_on_extraction=False,
        )

        assert result["url"] == ""

    def test_build_updated_config_none_url(self, icon_service):
        """Test config building with None URL."""
        result = icon_service._build_updated_config(
            base_config={},
            icon_source="none",
            icon_path=None,
            icon_filename="testapp.png",
            icon_url=None,
            extraction_enabled=True,
            preserve_url_on_extraction=False,
        )

        assert result["url"] == ""

    @pytest.mark.asyncio
    async def test_acquire_icon_extraction_success(
        self, icon_service, sample_icon_config, mock_paths
    ):
        """Test successful icon acquisition via extraction."""
        mock_icon_path = mock_paths["dest_path"]

        with patch.object(icon_service, "_attempt_extraction") as mock_extract:
            mock_extract.return_value = mock_icon_path

            result = await icon_service.acquire_icon(
                icon_config=sample_icon_config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
            )

            assert result.icon_path == mock_icon_path
            assert result.source == "extraction"
            assert result.config["installed"] is True
            assert result.config["extraction"] is True
            assert result.config["source"] == "extraction"

            mock_extract.assert_called_once_with(
                mock_paths["appimage_path"],
                mock_paths["dest_path"],
                "testapp",
            )

    @pytest.mark.asyncio
    async def test_acquire_icon_github_fallback(
        self, icon_service, sample_icon_config, mock_paths
    ):
        """Test icon acquisition falling back to GitHub download."""
        mock_icon_path = mock_paths["dest_path"]

        with (
            patch.object(icon_service, "_attempt_extraction") as mock_extract,
            patch.object(icon_service, "_attempt_github_download") as mock_github,
        ):
            mock_extract.return_value = None  # Extraction fails
            mock_github.return_value = mock_icon_path

            result = await icon_service.acquire_icon(
                icon_config=sample_icon_config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
            )

            assert result.icon_path == mock_icon_path
            assert result.source == "github"
            assert result.config["installed"] is True
            assert result.config["extraction"] is False

            mock_extract.assert_called_once()
            mock_github.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_icon_extraction_disabled(self, icon_service, mock_paths):
        """Test icon acquisition with extraction disabled."""
        config = IconConfig(
            extraction_enabled=False,
            icon_url="https://example.com/icon.png",
            icon_filename="testapp.png",
        )
        mock_icon_path = mock_paths["dest_path"]

        with (
            patch.object(icon_service, "_attempt_extraction") as mock_extract,
            patch.object(icon_service, "_attempt_github_download") as mock_github,
        ):
            mock_github.return_value = mock_icon_path

            result = await icon_service.acquire_icon(
                icon_config=config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
            )

            assert result.source == "github"
            mock_extract.assert_not_called()  # Should skip extraction
            mock_github.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_icon_no_url(self, icon_service, mock_paths):
        """Test icon acquisition with no URL provided."""
        config = IconConfig(
            extraction_enabled=True,
            icon_url=None,
            icon_filename="testapp.png",
        )

        with (
            patch.object(icon_service, "_attempt_extraction") as mock_extract,
            patch.object(icon_service, "_attempt_github_download") as mock_github,
        ):
            mock_extract.return_value = None  # Extraction fails

            result = await icon_service.acquire_icon(
                icon_config=config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
            )

            assert result.icon_path is None
            assert result.source == "none"
            assert result.config["installed"] is False

            mock_extract.assert_called_once()
            mock_github.assert_not_called()  # Should skip GitHub download

    @pytest.mark.asyncio
    async def test_acquire_icon_both_methods_fail(
        self, icon_service, sample_icon_config, mock_paths
    ):
        """Test icon acquisition when both extraction and GitHub download fail."""
        with (
            patch.object(icon_service, "_attempt_extraction") as mock_extract,
            patch.object(icon_service, "_attempt_github_download") as mock_github,
        ):
            mock_extract.return_value = None
            mock_github.return_value = None

            result = await icon_service.acquire_icon(
                icon_config=sample_icon_config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
            )

            assert result.icon_path is None
            assert result.source == "none"
            assert result.config["installed"] is False

    @pytest.mark.asyncio
    async def test_acquire_icon_with_catalog_entry(self, icon_service, mock_paths):
        """Test icon acquisition with catalog entry for preference detection."""
        config = IconConfig(
            extraction_enabled=True,  # Will be overridden
            icon_url="https://example.com/icon.png",
            icon_filename="testapp.png",
        )

        catalog_entry = {"icon": {"extraction": False}}
        current_config = {}

        mock_icon_path = mock_paths["dest_path"]

        with (
            patch.object(icon_service, "_attempt_extraction") as mock_extract,
            patch.object(icon_service, "_attempt_github_download") as mock_github,
        ):
            mock_github.return_value = mock_icon_path

            result = await icon_service.acquire_icon(
                icon_config=config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
                current_config=current_config,
                catalog_entry=catalog_entry,
            )

            assert result.source == "github"
            # Should skip extraction due to catalog preference
            mock_extract.assert_not_called()
            mock_github.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_icon_preserve_url_on_extraction(self, icon_service, mock_paths):
        """Test icon acquisition preserving URL on extraction."""
        config = IconConfig(
            extraction_enabled=True,
            icon_url="https://example.com/icon.png",
            icon_filename="testapp.png",
            preserve_url_on_extraction=True,
        )

        mock_icon_path = mock_paths["dest_path"]

        with patch.object(icon_service, "_attempt_extraction") as mock_extract:
            mock_extract.return_value = mock_icon_path

            result = await icon_service.acquire_icon(
                icon_config=config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
            )

            assert result.config["url"] == "https://example.com/icon.png"

    @pytest.mark.asyncio
    async def test_acquire_icon_logging_calls(
        self, icon_service, sample_icon_config, mock_paths
    ):
        """Test that appropriate logging calls are made."""
        mock_icon_path = mock_paths["dest_path"]

        with (
            patch.object(icon_service, "_attempt_extraction") as mock_extract,
            patch("my_unicorn.services.icon_service.logger") as mock_logger,
        ):
            mock_extract.return_value = mock_icon_path

            await icon_service.acquire_icon(
                icon_config=sample_icon_config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
            )

            # Check that debug logging was called at least once
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_acquire_icon_edge_case_empty_filename(self, icon_service, mock_paths):
        """Test icon acquisition with empty filename."""
        config = IconConfig(
            extraction_enabled=True,
            icon_url="https://example.com/icon.png",
            icon_filename="",  # Edge case: empty filename
        )

        with patch.object(icon_service, "_attempt_extraction") as mock_extract:
            mock_extract.return_value = None

            result = await icon_service.acquire_icon(
                icon_config=config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
            )

            # Should handle empty filename gracefully
            assert result.config["name"] == ""

    @pytest.mark.asyncio
    async def test_acquire_icon_path_creation(self, icon_service, mock_paths):
        """Test that destination path is created correctly."""
        config = IconConfig(
            extraction_enabled=True,
            icon_url="https://example.com/icon.png",
            icon_filename="custom_name.svg",
        )

        expected_dest = mock_paths["icon_dir"] / "custom_name.svg"

        with patch.object(icon_service, "_attempt_extraction") as mock_extract:
            mock_extract.return_value = expected_dest

            result = await icon_service.acquire_icon(
                icon_config=config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
            )

            mock_extract.assert_called_once_with(
                mock_paths["appimage_path"],
                expected_dest,
                "testapp",
            )

    def test_icon_service_initialization(self, mock_download_service):
        """Test that IconService initializes correctly."""
        service = IconService(mock_download_service)

        assert service.download_service is mock_download_service

    @pytest.mark.asyncio
    async def test_acquire_icon_complex_workflow(self, icon_service, mock_paths):
        """Test complex workflow with multiple configurations and scenarios."""
        # Test scenario: catalog prefers extraction, but extraction fails,
        # then GitHub succeeds, and config should reflect the actual outcome

        config = IconConfig(
            extraction_enabled=False,  # App config says no extraction
            icon_url="https://example.com/icon.png",
            icon_filename="testapp.png",
            preserve_url_on_extraction=True,
        )

        catalog_entry = {"icon": {"extraction": True}}  # Catalog wants extraction
        current_config = {"old_setting": "value"}
        mock_icon_path = mock_paths["dest_path"]

        with (
            patch.object(icon_service, "_attempt_extraction") as mock_extract,
            patch.object(icon_service, "_attempt_github_download") as mock_github,
        ):
            mock_extract.return_value = None  # Extraction fails
            mock_github.return_value = mock_icon_path  # GitHub succeeds

            result = await icon_service.acquire_icon(
                icon_config=config,
                app_name="testapp",
                icon_dir=mock_paths["icon_dir"],
                appimage_path=mock_paths["appimage_path"],
                current_config=current_config,
                catalog_entry=catalog_entry,
            )

            # Should attempt extraction due to catalog preference
            mock_extract.assert_called_once()
            mock_github.assert_called_once()

            # Result should reflect actual outcome
            assert result.source == "github"
            assert result.config["extraction"] is False
            assert result.config["old_setting"] == "value"  # Preserves existing config
            assert result.config["installed"] is True
            assert result.config["url"] == "https://example.com/icon.png"
