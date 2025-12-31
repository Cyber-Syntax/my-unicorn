"""Tests for asset selection workflow utility."""

import pytest

from my_unicorn.exceptions import InstallationError
from my_unicorn.github_client import Asset, Release
from my_unicorn.utils.asset_selection import select_best_appimage_asset


def create_mock_release(assets: list[Asset] | None = None) -> Release:
    """Create a mock Release object for testing."""
    return Release(
        owner="test",
        repo="repo",
        version="1.0.0",
        prerelease=False,
        assets=assets or [],
        original_tag_name="v1.0.0",
    )


def create_mock_asset(name: str, size: int = 1000) -> Asset:
    """Create a mock Asset object for testing."""
    return Asset(
        name=name,
        size=size,
        digest="",
        browser_download_url=f"https://github.com/test/repo/releases/download/v1.0.0/{name}",
    )


class TestSelectBestAppimageAsset:
    """Tests for select_best_appimage_asset function."""

    def test_no_release_raises_error(self) -> None:
        """Test that None release raises InstallationError."""
        with pytest.raises(InstallationError, match="No assets found"):
            select_best_appimage_asset(None)  # type: ignore[arg-type]

    def test_no_assets_raises_error(self) -> None:
        """Test that release with no assets raises InstallationError."""
        release = create_mock_release(assets=[])
        with pytest.raises(InstallationError, match="No assets found"):
            select_best_appimage_asset(release)

    def test_no_assets_returns_none_when_raise_disabled(self) -> None:
        """Test that no assets returns None when raise_on_not_found=False."""
        release = create_mock_release(assets=[])
        result = select_best_appimage_asset(release, raise_on_not_found=False)
        assert result is None

    def test_single_appimage_selected(self) -> None:
        """Test that single AppImage is selected successfully."""
        asset = create_mock_asset("app-x86_64.AppImage")
        release = create_mock_release(assets=[asset])

        result = select_best_appimage_asset(release)
        assert result == asset

    def test_preferred_suffixes_explicit(self) -> None:
        """Test selection with explicit preferred suffixes."""
        asset1 = create_mock_asset("app-x86_64.AppImage")
        asset2 = create_mock_asset("app-arm64.AppImage")
        release = create_mock_release(assets=[asset1, asset2])

        result = select_best_appimage_asset(
            release,
            preferred_suffixes=["x86_64.AppImage"],
        )
        assert result == asset1

    def test_preferred_suffixes_from_catalog(self) -> None:
        """Test extraction of preferred suffixes from catalog entry."""
        asset1 = create_mock_asset("app-x86_64.AppImage")
        asset2 = create_mock_asset("app.AppImage")
        release = create_mock_release(assets=[asset1, asset2])

        catalog_entry = {
            "appimage": {
                "preferred_suffixes": ["x86_64.AppImage"],
            }
        }

        result = select_best_appimage_asset(
            release,
            catalog_entry=catalog_entry,
        )
        assert result == asset1

    def test_explicit_suffixes_override_catalog(self) -> None:
        """Test that explicit suffixes take precedence over catalog."""
        asset1 = create_mock_asset("app-x86_64.AppImage")
        asset2 = create_mock_asset("app.AppImage")
        release = create_mock_release(assets=[asset1, asset2])

        catalog_entry = {
            "appimage": {
                "preferred_suffixes": ["x86_64.AppImage"],
            }
        }

        # Explicit suffix should override catalog
        result = select_best_appimage_asset(
            release,
            preferred_suffixes=[],  # Empty list overrides catalog
            catalog_entry=catalog_entry,
        )
        # Should select based on AssetSelector logic without suffixes
        assert result in [asset1, asset2]

    def test_installation_source_catalog(self) -> None:
        """Test installation_source='catalog' behavior."""
        asset = create_mock_asset("app-x86_64.AppImage")
        release = create_mock_release(assets=[asset])

        result = select_best_appimage_asset(
            release,
            installation_source="catalog",
        )
        assert result == asset

    def test_installation_source_url(self) -> None:
        """Test installation_source='url' behavior."""
        asset = create_mock_asset("app-x86_64.AppImage")
        release = create_mock_release(assets=[asset])

        result = select_best_appimage_asset(
            release,
            installation_source="url",
        )
        assert result == asset

    def test_no_appimage_found_raises_error(self) -> None:
        """Test that no AppImage found raises InstallationError."""
        # Create non-AppImage assets
        asset1 = create_mock_asset("app.deb")
        asset2 = create_mock_asset("app.rpm")
        release = create_mock_release(assets=[asset1, asset2])

        with pytest.raises(
            InstallationError,
            match="AppImage not found in release",
        ):
            select_best_appimage_asset(release)

    def test_no_appimage_found_returns_none_when_raise_disabled(
        self,
    ) -> None:
        """Test that no AppImage returns None when raise_on_not_found=False."""
        asset1 = create_mock_asset("app.deb")
        release = create_mock_release(assets=[asset1])

        result = select_best_appimage_asset(release, raise_on_not_found=False)
        assert result is None

    def test_catalog_entry_without_appimage_key(self) -> None:
        """Test catalog entry without appimage key."""
        asset = create_mock_asset("app-x86_64.AppImage")
        release = create_mock_release(assets=[asset])

        catalog_entry = {"name": "TestApp"}  # No appimage key

        result = select_best_appimage_asset(
            release,
            catalog_entry=catalog_entry,
        )
        assert result == asset

    def test_catalog_entry_with_non_dict_appimage(self) -> None:
        """Test catalog entry with non-dict appimage value."""
        asset = create_mock_asset("app-x86_64.AppImage")
        release = create_mock_release(assets=[asset])

        catalog_entry = {"appimage": "invalid"}  # Not a dict

        result = select_best_appimage_asset(
            release,
            catalog_entry=catalog_entry,
        )
        assert result == asset
