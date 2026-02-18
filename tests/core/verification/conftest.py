"""Shared test fixtures for verification module tests.

This module provides common fixtures used across all verification test files:
- mock_download_service: Mocked DownloadService dependency
- verification_service: VerificationService instance with mocked dependencies
- test_file_path: Temporary test file with known content for hash verification
- sample_assets: GitHub assets for integration tests
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from my_unicorn.core.github import Asset
from my_unicorn.core.verification.service import VerificationService


@pytest.fixture
def mock_download_service() -> MagicMock:
    """Create a mock download service.

    Returns:
        MagicMock: A mocked download service for testing verification logic.
    """
    return MagicMock()


@pytest.fixture
def verification_service(
    mock_download_service: MagicMock,
) -> VerificationService:
    """Create a VerificationService instance with mock dependencies.

    Args:
        mock_download_service: Mocked download service fixture.

    Returns:
        VerificationService: Service instance for verification testing.
    """
    return VerificationService(mock_download_service)


@pytest.fixture
def test_file_path(tmp_path: Path) -> Path:
    """Create a temporary test file with known content for hash verification.

    The file contains "test content" which can be used to verify hash
    calculations.
    SHA256: 6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863
            140143ff72
    SHA512: DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzj
            AuwlC4IcwAHkbMl6cEmIKXGFpN9+mWAg==

    Args:
        tmp_path: pytest temporary path fixture.

    Returns:
        Path: Path to the temporary test file.
    """
    file_path = tmp_path / "test.AppImage"
    file_path.write_bytes(b"test content")
    return file_path


@pytest.fixture
def sample_assets() -> list[Asset]:
    """Sample GitHub assets for testing with YAML checksum file.

    Returns:
        list[Asset]: List containing an AppImage and a YAML checksum
        file.
    """
    return [
        Asset(
            name="Legcord-1.1.5-linux-x86_64.AppImage",
            browser_download_url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/Legcord-1.1.5-linux-x86_64.AppImage",
            size=124457255,
            digest="",
        ),
        Asset(
            name="latest-linux.yml",
            browser_download_url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/latest-linux.yml",
            size=1234,
            digest="",
        ),
    ]


@pytest.fixture
def sample_assets_with_both() -> list[Asset]:
    """Sample GitHub assets with YAML and traditional checksum files.

    Returns:
        list[Asset]: List containing AppImage, YAML, and SHA256SUMS.txt
        files.
    """
    return [
        Asset(
            name="app.AppImage",
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/app.AppImage",
            size=12345,
            digest="",
        ),
        Asset(
            name="latest-linux.yml",
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/latest-linux.yml",
            size=1234,
            digest="",
        ),
        Asset(
            name="SHA256SUMS.txt",
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/SHA256SUMS.txt",
            size=567,
            digest="",
        ),
    ]


# Test data constants for verification_methods tests
LEGCORD_YAML_CONTENT = """version: 1.1.5  # noqa: E501
files:
  - url: test.AppImage
    sha512: DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzjAuwlC4IcwAHkbMl6cEmIKXGFpN9+mWAg==  # noqa: E501
    size: 12
  - url: Legcord-1.1.5-linux-x86_64.AppImage
    sha512: JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw==  # noqa: E501
    size: 124457255
    blockMapSize: 131387
  - url: Legcord-1.1.5-linux-x86_64.rpm
    sha512: 3j2/BdKHypZrIQ0qDzJk9WjyXJwCfPfbQ7la8i+YFSHZwzOBdWDrkLPh16ZhTa3zRbQ13/XyeN76HwrRzCJIRg==  # noqa: E501
    size: 82429221
  - url: Legcord-1.1.5-linux-amd64.deb
    sha512: UjNfkg1xSME7aa7bRo4wcNz3bWMvVpcdUv08BNDCrrQ9Z/sx1nZo6FqByUd7GEZyJfgVaWYIfdQtcQaTV7Di6Q==  # noqa: E501
    size: 82572182
path: test.AppImage
sha512: DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzjAuwlC4IcwAHkbMl6cEmIKXGFpN9+mWAg==  # noqa: E501
releaseDate: '2025-05-26T17:26:48.710Z'"""

SIYUAN_SHA256SUMS_CONTENT = """6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72 test.AppImage  # noqa: E501
81529d6af7327f3468e13fe3aa226f378029aeca832336ef69af05438ef9146e siyuan-3.2.1-linux-arm64.AppImage  # noqa: E501
d0f6e2b796c730f077335a4661e712363512b911adfdb5cc419b7e02c4075c0a siyuan-3.2.1-linux-arm64.deb  # noqa: E501
dda94a3cf4b3a91a0240d4cbb70c7583f7611da92f9ed33713bb86530f2010a9 siyuan-3.2.1-linux-arm64.tar.gz  # noqa: E501
3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef siyuan-3.2.1-linux.AppImage  # noqa: E501
b39f78905a55bab8f16b82e90d784e4838c05b1605166d9cb3824a612cf6fc71 siyuan-3.2.1-linux.deb  # noqa: E501
70964f1e981a2aec0d7334cf49ee536fb592e7d19b2fccdffb005fd25a55f092 siyuan-3.2.1-linux.tar.gz  # noqa: E501
6153d6189302135f39c836e160a4a036ff495df81c3af1492d219d0d7818cb04 siyuan-3.2.1-mac-arm64.dmg  # noqa: E501
fbe6115ef044d451623c8885078172d6adc1318db6baf88e6b1fe379630a2da9 siyuan-3.2.1-mac.dmg  # noqa: E501
b75303038e40c0fcee7942bb47e9c8f853e8801fa87d63e0ab54d559837ffb03 siyuan-3.2.1-win-arm64.exe  # noqa: E501
ecfd14da398507452307bdb7671b57715a44a02ac7fdfb47e8afbe4f3b20e45f siyuan-3.2.1-win.exe  # noqa: E501
d9ad0f257893f6f2d25b948422257a938b03e6362ab638ad1a74e9bab1c0e755 siyuan-3.2.1.apk  # noqa: E501
6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72 app.AppImage"""  # noqa: E501

LEGCORD_EXPECTED_HEX = "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"  # noqa: E501
EXPECTED_SHA1_HEX = "abc123def4567890abcdef1234567890abcdef12"
EXPECTED_MD5_HEX = "abc123def4567890abcdef1234567890"
