"""Tests for AssetSelector filtering methods in github_client.py.

This test module verifies the cache filtering improvements implemented
according to CACHE_FILTERING_IMPROVEMENT_PLAN.md.
"""

from my_unicorn.infrastructure.github import Asset, AssetSelector


class TestAssetSelectorPlatformCompatibility:
    """Test platform compatibility filtering."""

    def test_is_platform_compatible_accepts_linux_x86_64(self):
        """Test that Linux x86_64 AppImages are accepted."""
        # Plain AppImages
        assert AssetSelector.is_platform_compatible("test.AppImage")
        assert AssetSelector.is_platform_compatible("app-1.2.3.AppImage")

        # Explicit x86_64 markers
        assert AssetSelector.is_platform_compatible(
            "QOwnNotes-x86_64.AppImage"
        )
        assert AssetSelector.is_platform_compatible(
            "KeePassXC-2.7.10-x86_64.AppImage"
        )
        assert AssetSelector.is_platform_compatible("app-amd64.AppImage")

        # With version info
        assert AssetSelector.is_platform_compatible("Joplin-3.4.12.AppImage")

    def test_is_platform_compatible_rejects_windows(self):
        """Test that Windows files are rejected."""
        # Windows extensions
        assert not AssetSelector.is_platform_compatible("app-installer.exe")
        assert not AssetSelector.is_platform_compatible("setup.msi")

        # Windows patterns
        assert not AssetSelector.is_platform_compatible("app-Win64.AppImage")
        assert not AssetSelector.is_platform_compatible("app-win32.AppImage")
        assert not AssetSelector.is_platform_compatible("app-Windows.AppImage")
        assert not AssetSelector.is_platform_compatible(
            "LegacyWindows.AppImage"
        )
        assert not AssetSelector.is_platform_compatible(
            "PortableWindows.AppImage"
        )

    def test_is_platform_compatible_rejects_macos(self):
        """Test that macOS files are rejected."""
        # macOS extensions
        assert not AssetSelector.is_platform_compatible("app.dmg")
        assert not AssetSelector.is_platform_compatible("installer.pkg")

        # macOS patterns
        assert not AssetSelector.is_platform_compatible("app-mac.AppImage")
        assert not AssetSelector.is_platform_compatible("app-darwin.AppImage")
        assert not AssetSelector.is_platform_compatible("app-osx.AppImage")
        assert not AssetSelector.is_platform_compatible("app-apple.AppImage")

        # macOS YAML files
        assert not AssetSelector.is_platform_compatible("latest-mac.yml")
        assert not AssetSelector.is_platform_compatible("latest-mac-arm64.yml")
        assert not AssetSelector.is_platform_compatible("mac-latest.yaml")

        # Should not reject "macro" (contains "mac" but not standalone)
        assert AssetSelector.is_platform_compatible("macro-app.AppImage")

    def test_is_platform_compatible_rejects_arm(self):
        """Test that ARM architecture files are rejected."""
        assert not AssetSelector.is_platform_compatible("app-arm64.AppImage")
        assert not AssetSelector.is_platform_compatible("app-aarch64.AppImage")
        assert not AssetSelector.is_platform_compatible("app-armv7l.AppImage")
        assert not AssetSelector.is_platform_compatible("app-armhf.AppImage")
        assert not AssetSelector.is_platform_compatible("app-armv6.AppImage")

    def test_is_platform_compatible_rejects_source(self):
        """Test that source archives are rejected."""
        assert not AssetSelector.is_platform_compatible("app-src-1.0.tar.gz")
        assert not AssetSelector.is_platform_compatible("app_src_1.0.tar.gz")
        assert not AssetSelector.is_platform_compatible("app.src.tar.xz")
        assert not AssetSelector.is_platform_compatible(
            "app-source-code.tar.gz"
        )

    def test_is_platform_compatible_rejects_experimental(self):
        """Test that experimental builds are rejected."""
        assert not AssetSelector.is_platform_compatible(
            "app-experimental.AppImage"
        )
        assert not AssetSelector.is_platform_compatible(
            "app-qt6-experimental.AppImage"
        )

    def test_is_platform_compatible_empty_filename(self):
        """Test handling of empty filename."""
        assert not AssetSelector.is_platform_compatible("")
        assert not AssetSelector.is_platform_compatible(None)


class TestAssetSelectorChecksumFiltering:
    """Test checksum file relevance filtering."""

    def test_is_relevant_checksum_accepts_compatible_checksums(self):
        """Test that checksums for compatible AppImages are accepted."""
        # Standard checksum extensions
        assert AssetSelector.is_relevant_checksum(
            "QOwnNotes-x86_64.AppImage.sha256sum"
        )
        assert AssetSelector.is_relevant_checksum(
            "KeePassXC-2.7.10-x86_64.AppImage.DIGEST"
        )
        assert AssetSelector.is_relevant_checksum(
            "Joplin-3.4.12.AppImage.sha512"
        )
        assert AssetSelector.is_relevant_checksum("app.AppImage.sha256")
        assert AssetSelector.is_relevant_checksum("app.AppImage.md5sum")

    def test_is_relevant_checksum_rejects_windows_checksums(self):
        """Test that checksums for Windows files are rejected."""
        assert not AssetSelector.is_relevant_checksum(
            "KeePassXC-2.7.10-Win64.msi.DIGEST"
        )
        assert not AssetSelector.is_relevant_checksum("app-windows.exe.sha256")
        assert not AssetSelector.is_relevant_checksum(
            "installer-win32.msi.sha512sum"
        )

    def test_is_relevant_checksum_rejects_arm_checksums(self):
        """Test that checksums for ARM AppImages are rejected."""
        assert not AssetSelector.is_relevant_checksum(
            "Obsidian-1.9.14-arm64.AppImage.sha256"
        )
        assert not AssetSelector.is_relevant_checksum(
            "app-aarch64.AppImage.sha512sum"
        )

    def test_is_relevant_checksum_rejects_macos_checksums(self):
        """Test that checksums for macOS files are rejected."""
        assert not AssetSelector.is_relevant_checksum("latest-mac-arm64.yml")
        assert not AssetSelector.is_relevant_checksum("app-darwin.dmg.sha256")

    def test_is_relevant_checksum_requires_appimage_base(self):
        """Test that non-AppImage checksums are rejected."""
        assert not AssetSelector.is_relevant_checksum("archive.tar.gz.sha256")
        assert not AssetSelector.is_relevant_checksum("source.zip.sha512sum")
        assert not AssetSelector.is_relevant_checksum("README.md.sha256")

    def test_is_relevant_checksum_not_a_checksum(self):
        """Test that non-checksum files are rejected."""
        assert not AssetSelector.is_relevant_checksum("app.AppImage")
        assert not AssetSelector.is_relevant_checksum("README.md")

    def test_is_relevant_checksum_empty_filename(self):
        """Test handling of empty filename."""
        assert not AssetSelector.is_relevant_checksum("")
        assert not AssetSelector.is_relevant_checksum(None)


class TestAssetSelectorFilterForCache:
    """Test complete cache filtering logic."""

    def create_asset(self, name: str) -> Asset:
        """Create a mock Asset for testing."""
        return Asset(
            name=name,
            size=1024,
            digest="",
            browser_download_url=f"https://example.com/{name}",
        )

    def test_filter_for_cache_keeps_compatible_appimages(self):
        """Test that compatible AppImages are kept."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("tool-amd64.AppImage"),
            self.create_asset("program.AppImage"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 3
        assert all(a.name.endswith(".AppImage") for a in filtered)

    def test_filter_for_cache_removes_windows_appimages(self):
        """Test that Windows AppImages are filtered out."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app-Win64.AppImage"),
            self.create_asset("app-windows.AppImage"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 1
        assert filtered[0].name == "app-x86_64.AppImage"

    def test_filter_for_cache_removes_macos_files(self):
        """Test that macOS files are filtered out."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app.dmg"),
            self.create_asset("installer.pkg"),
            self.create_asset("app-darwin.AppImage"),
            self.create_asset("latest-mac.yml"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 1
        assert filtered[0].name == "app-x86_64.AppImage"

    def test_filter_for_cache_removes_arm_appimages(self):
        """Test that ARM AppImages are filtered out."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app-arm64.AppImage"),
            self.create_asset("app-aarch64.AppImage"),
            self.create_asset("app-armhf.AppImage"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 1
        assert filtered[0].name == "app-x86_64.AppImage"

    def test_filter_for_cache_keeps_relevant_checksums(self):
        """Test that relevant checksum files are kept."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app-x86_64.AppImage.sha256sum"),
            self.create_asset("app-x86_64.AppImage.DIGEST"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 3
        assert "app-x86_64.AppImage" in [a.name for a in filtered]
        assert "app-x86_64.AppImage.sha256sum" in [a.name for a in filtered]
        assert "app-x86_64.AppImage.DIGEST" in [a.name for a in filtered]

    def test_filter_for_cache_removes_irrelevant_checksums(self):
        """Test that checksums for incompatible files are filtered out."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app-x86_64.AppImage.sha256sum"),
            self.create_asset("app-Win64.msi.DIGEST"),
            self.create_asset("app-arm64.AppImage.sha256"),
            self.create_asset("latest-mac.yml"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 2
        assert filtered[0].name == "app-x86_64.AppImage"
        assert filtered[1].name == "app-x86_64.AppImage.sha256sum"

    def test_filter_for_cache_real_world_keepassxc(self):
        """Test with real KeePassXC release assets."""
        assets = [
            # Keep these
            self.create_asset("KeePassXC-2.7.10-x86_64.AppImage"),
            self.create_asset("KeePassXC-2.7.10-x86_64.AppImage.DIGEST"),
            # Filter these out (.sig files are GPG signatures, not checksums)
            self.create_asset("KeePassXC-2.7.10-x86_64.AppImage.sig"),
            self.create_asset("KeePassXC-2.7.10-Win64.msi"),
            self.create_asset("KeePassXC-2.7.10-Win64.msi.DIGEST"),
            self.create_asset("KeePassXC-2.7.10.dmg"),
            self.create_asset("KeePassXC-2.7.10.dmg.DIGEST"),
            self.create_asset("KeePassXC-2.7.10-src.tar.xz"),
            self.create_asset("KeePassXC-2.7.10-src.tar.xz.DIGEST"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        # Should only keep x86_64 AppImage and its DIGEST checksum
        # Note: .sig files are GPG signatures, not checksums, so filtered
        assert len(filtered) == 2
        filtered_names = [a.name for a in filtered]
        assert "KeePassXC-2.7.10-x86_64.AppImage" in filtered_names
        assert "KeePassXC-2.7.10-x86_64.AppImage.DIGEST" in filtered_names

    def test_filter_for_cache_empty_list(self):
        """Test filtering an empty asset list."""
        assets = []
        filtered = AssetSelector.filter_for_cache(assets)
        assert len(filtered) == 0

    def test_filter_for_cache_no_compatible_assets(self):
        """Test when no assets are compatible."""
        assets = [
            self.create_asset("app.dmg"),
            self.create_asset("installer.exe"),
            self.create_asset("app-arm64.AppImage"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 0
