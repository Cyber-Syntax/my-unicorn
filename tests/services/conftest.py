"""Common fixtures for services tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.download import DownloadService, IconAsset
from my_unicorn.services.icon_service import IconConfig, IconService
from my_unicorn.verification.verification_service import VerificationService


@pytest.fixture
def mock_download_service():
    """Create a mock DownloadService for testing."""
    service = MagicMock(spec=DownloadService)
    service.download_icon = AsyncMock()
    service.verify_file_size = MagicMock(return_value=True)
    return service


@pytest.fixture
def icon_service(mock_download_service):
    """Create an IconService instance with mock dependencies."""
    return IconService(mock_download_service)


@pytest.fixture
def verification_service(mock_download_service):
    """Create a VerificationService instance with mock dependencies."""
    return VerificationService(mock_download_service)


@pytest.fixture
def sample_icon_config():
    """Create a sample IconConfig for testing."""
    return IconConfig(
        extraction_enabled=True,
        icon_url="https://github.com/test/repo/raw/main/icon.png",
        icon_filename="testapp.png",
    )


@pytest.fixture
def sample_icon_asset():
    """Create a sample IconAsset for testing."""
    return IconAsset(
        icon_filename="testapp.png",
        icon_url="https://github.com/test/repo/raw/main/icon.png",
    )


@pytest.fixture
def sample_verification_config():
    """Create a sample verification config."""
    return {
        "skip": False,
        "checksum_file": "checksums.txt",
        "checksum_hash_type": "sha256",
    }


@pytest.fixture
def sample_asset_with_digest():
    """Create a sample asset with digest for verification testing."""
    return {
        "digest": "sha256:abc123def456",
        "size": 1024,
        "name": "test.AppImage",
    }


@pytest.fixture
def mock_paths(tmp_path):
    """Create mock paths for testing file operations."""
    icon_dir = tmp_path / "icons"
    icon_dir.mkdir()

    appimage_path = tmp_path / "testapp.AppImage"
    appimage_path.write_bytes(b"mock appimage content")
    appimage_path.chmod(0o755)

    return {
        "icon_dir": icon_dir,
        "appimage_path": appimage_path,
        "dest_path": icon_dir / "testapp.png",
        "tmp_dir": tmp_path,
    }


@pytest.fixture
def mock_catalog_entry():
    """Create a mock catalog entry for testing."""
    return {
        "icon": {
            "extraction": True,
            "url": "https://github.com/test/repo/raw/main/icon.png",
            "name": "testapp.png",
        },
        "verification": {
            "skip": False,
            "checksum_file": "checksums.txt",
        },
    }


@pytest.fixture
def mock_app_config():
    """Create a mock app configuration for testing."""
    return {
        "name": "testapp",
        "repo": "test/repo",
        "owner": "test",
        "icon": {
            "extraction": False,
            "url": "https://github.com/test/repo/raw/main/icon.png",
            "installed": False,
        },
        "verification": {
            "skip": True,
        },
    }


@pytest.fixture
def mock_logger():
    """Mock logger to avoid log output during tests."""
    from unittest.mock import patch

    with (
        patch("my_unicorn.services.icon_service.logger"),
        patch("my_unicorn.verification_service.logger"),
    ):
        yield
