"""Tests for VerificationConfig and VerificationContext dataclasses."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from my_unicorn.constants import VerificationMethod
from my_unicorn.core.github import Asset, ChecksumFileInfo
from my_unicorn.core.verification.context import (
    VerificationConfig,
    VerificationContext,
)
from my_unicorn.core.verification.verifier import Verifier


class TestVerificationConfig:
    """Test VerificationConfig dataclass."""

    def test_verification_config_defaults(self) -> None:
        """Test VerificationConfig with default values."""
        config = VerificationConfig()
        assert config.skip is False
        assert config.checksum_file is None
        assert config.checksum_hash_type == "sha256"
        assert config.digest_enabled is False

    def test_verification_config_custom_values(self) -> None:
        """Test VerificationConfig with custom values."""
        config = VerificationConfig(
            skip=True,
            checksum_file="checksums.txt",
            checksum_hash_type="sha512",
            digest_enabled=True,
        )
        assert config.skip is True
        assert config.checksum_file == "checksums.txt"
        assert config.checksum_hash_type == "sha512"
        assert config.digest_enabled is True

    def test_verification_config_immutable(self) -> None:
        """Test that VerificationConfig is frozen/immutable."""
        config = VerificationConfig()
        with pytest.raises(AttributeError):
            config.skip = True

    def test_verification_config_from_dict_defaults(self) -> None:
        """Test VerificationConfig.from_dict with minimal dictionary."""
        config_dict: dict[str, bool | str | None] = {}
        config = VerificationConfig.from_dict(config_dict)

        assert config.skip is False
        assert config.checksum_file is None
        assert config.checksum_hash_type == "sha256"
        assert config.digest_enabled is False

    def test_verification_config_from_dict_custom_values(self) -> None:
        """Test VerificationConfig.from_dict with custom values."""
        config_dict: dict[str, bool | str] = {
            "skip": True,
            "checksum_file": "SHA256SUMS",
            "checksum_hash_type": "sha512",
            VerificationMethod.DIGEST: True,
        }
        config = VerificationConfig.from_dict(config_dict)

        assert config.skip is True
        assert config.checksum_file == "SHA256SUMS"
        assert config.checksum_hash_type == "sha512"
        assert config.digest_enabled is True

    def test_verification_config_from_dict_partial_values(self) -> None:
        """Test VerificationConfig.from_dict with partial dictionary."""
        config_dict: dict[str, str] = {"checksum_hash_type": "sha512"}
        config = VerificationConfig.from_dict(config_dict)

        assert config.skip is False
        assert config.checksum_file is None
        assert config.checksum_hash_type == "sha512"
        assert config.digest_enabled is False

    def test_verification_config_to_dict(self) -> None:
        """Test VerificationConfig.to_dict conversion."""
        config = VerificationConfig(
            skip=True,
            checksum_file="SHA256SUMS.txt",
            checksum_hash_type="sha512",
            digest_enabled=True,
        )
        result = config.to_dict()

        assert result["skip"] is True
        assert result["checksum_file"] == "SHA256SUMS.txt"
        assert result["checksum_hash_type"] == "sha512"
        assert result[VerificationMethod.DIGEST] is True

    def test_verification_config_to_dict_defaults(self) -> None:
        """Test VerificationConfig.to_dict with default values."""
        config = VerificationConfig()
        result = config.to_dict()

        assert result["skip"] is False
        assert result["checksum_file"] is None
        assert result["checksum_hash_type"] == "sha256"
        assert result[VerificationMethod.DIGEST] is False

    def test_verification_config_from_dict_to_dict_roundtrip(self) -> None:
        """Test that from_dict and to_dict are inverse operations."""
        original_dict: dict[str, bool | str | None] = {
            "skip": True,
            "checksum_file": "checksums.txt",
            "checksum_hash_type": "sha512",
            VerificationMethod.DIGEST: True,
        }
        config = VerificationConfig.from_dict(original_dict)
        result_dict = config.to_dict()

        assert result_dict == original_dict


class TestVerificationContext:
    """Test VerificationContext dataclass."""

    @pytest.fixture
    def sample_asset(self) -> Asset:
        """Create a sample asset for testing."""
        return Asset(
            name="app-1.0.0.AppImage",
            browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/app-1.0.0.AppImage",
            size=1024000,
            digest=None,
        )

    @pytest.fixture
    def verification_context(
        self, tmp_path: Path, sample_asset: Asset
    ) -> VerificationContext:
        """Create a VerificationContext instance for testing."""
        file_path = tmp_path / "app-1.0.0.AppImage"
        config: dict[str, bool | str | None] = {
            "skip": False,
            "checksum_hash_type": "sha256",
        }

        return VerificationContext(
            file_path=file_path,
            asset=sample_asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="app",
            assets=None,
            progress_task_id=None,
        )

    def test_verification_context_initialization(
        self, tmp_path: Path, sample_asset: Asset
    ) -> None:
        """Test VerificationContext basic initialization."""
        file_path = tmp_path / "test.AppImage"
        config: dict[str, bool | str | None] = {"skip": False}

        context = VerificationContext(
            file_path=file_path,
            asset=sample_asset,
            config=config,
            owner="owner",
            repo="repo",
            tag_name="v1.0.0",
            app_name="app",
            assets=None,
            progress_task_id=None,
        )

        assert context.file_path == file_path
        assert context.asset == sample_asset
        assert context.config == config
        assert context.owner == "owner"
        assert context.repo == "repo"
        assert context.tag_name == "v1.0.0"
        assert context.app_name == "app"
        assert context.assets is None
        assert context.progress_task_id is None

    def test_verification_context_default_values(
        self, verification_context: VerificationContext
    ) -> None:
        """Test that VerificationContext has correct default values."""
        assert verification_context.has_digest is False
        assert verification_context.checksum_files is None
        assert verification_context.verifier is None
        assert verification_context.updated_config is not None
        assert verification_context.verification_passed is False
        assert verification_context.verification_methods == {}
        assert verification_context.verification_warning is None

    def test_verification_context_post_init_copies_config(
        self, verification_context: VerificationContext
    ) -> None:
        """Test that __post_init__ copies config to updated_config."""
        assert verification_context.updated_config is not None
        assert (
            verification_context.updated_config == verification_context.config
        )
        # Verify it's a copy, not the same object
        assert (
            verification_context.updated_config
            is not verification_context.config
        )

    def test_verification_context_with_assets(
        self, tmp_path: Path, sample_asset: Asset
    ) -> None:
        """Test VerificationContext with multiple assets."""
        file_path = tmp_path / "app.AppImage"
        config: dict[str, bool | str | None] = {}
        assets = [
            sample_asset,
            Asset(
                name="SHA256SUMS.txt",
                browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/SHA256SUMS.txt",
                size=256,
                digest=None,
            ),
        ]

        context = VerificationContext(
            file_path=file_path,
            asset=sample_asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="app",
            assets=assets,
            progress_task_id=None,
        )

        assert context.assets == assets
        assert len(context.assets) == 2

    def test_verification_context_with_initial_checksum_files(
        self, tmp_path: Path, sample_asset: Asset
    ) -> None:
        """Test VerificationContext initialized with checksum_files."""
        file_path = tmp_path / "app.AppImage"
        config: dict[str, bool | str | None] = {}
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA256SUMS.txt",
                url="https://example.com/SHA256SUMS.txt",
                format_type="traditional",
            ),
        ]

        context = VerificationContext(
            file_path=file_path,
            asset=sample_asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="app",
            assets=None,
            progress_task_id=None,
            checksum_files=checksum_files,
        )

        assert context.checksum_files == checksum_files
        assert len(context.checksum_files) == 1

    def test_verification_context_with_verifier(
        self, tmp_path: Path, sample_asset: Asset
    ) -> None:
        """Test VerificationContext with Verifier instance."""
        file_path = tmp_path / "app.AppImage"
        config: dict[str, bool | str | None] = {}
        mock_verifier = MagicMock(spec=Verifier)

        context = VerificationContext(
            file_path=file_path,
            asset=sample_asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="app",
            assets=None,
            progress_task_id=None,
            verifier=mock_verifier,
        )

        assert context.verifier is mock_verifier

    def test_verification_context_state_management(
        self, verification_context: VerificationContext
    ) -> None:
        """Test VerificationContext state management through mutable attrs."""
        # Initially, verification should not be passed
        assert verification_context.verification_passed is False

        # Simulate state updates (these are mutable fields in the dataclass)
        object.__setattr__(verification_context, "verification_passed", True)
        object.__setattr__(
            verification_context,
            "verification_methods",
            {"digest": {"passed": True, "hash": "abc123"}},
        )
        object.__setattr__(
            verification_context, "verification_warning", "Minor warning"
        )

        # Verify updates
        assert verification_context.verification_passed is True
        assert verification_context.verification_methods == {  # type: ignore[unreachable]
            "digest": {"passed": True, "hash": "abc123"}
        }
        assert verification_context.verification_warning == "Minor warning"

    def test_verification_context_has_digest_state(
        self, verification_context: VerificationContext
    ) -> None:
        """Test VerificationContext has_digest state management."""
        assert verification_context.has_digest is False

        object.__setattr__(verification_context, "has_digest", True)

        assert verification_context.has_digest is True

    def test_verification_context_updated_config_independence(
        self, tmp_path: Path, sample_asset: Asset
    ) -> None:
        """Test that updated_config is independent from config."""
        file_path = tmp_path / "app.AppImage"
        original_config: dict[str, bool | str | None] = {"skip": False}

        context = VerificationContext(
            file_path=file_path,
            asset=sample_asset,
            config=original_config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="app",
            assets=None,
            progress_task_id=None,
        )

        # Modify original config
        original_config["skip"] = True

        # Verify updated_config was not affected
        assert context.updated_config["skip"] is False
        assert context.config["skip"] is True

    def test_verification_context_with_progress_task_id(
        self, tmp_path: Path, sample_asset: Asset
    ) -> None:
        """Test VerificationContext with progress task ID."""
        file_path = tmp_path / "app.AppImage"
        config: dict[str, bool | str | None] = {}
        task_id = 42

        context = VerificationContext(
            file_path=file_path,
            asset=sample_asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="app",
            assets=None,
            progress_task_id=task_id,
        )

        assert context.progress_task_id == task_id

    def test_verification_context_with_all_fields(
        self, tmp_path: Path, sample_asset: Asset
    ) -> None:
        """Test VerificationContext with all fields populated."""
        file_path = tmp_path / "app.AppImage"
        config: dict[str, bool | str | None] = {"skip": False}
        assets = [sample_asset]
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA256SUMS.txt",
                url="https://example.com/SHA256SUMS.txt",
                format_type="yaml",
            ),
        ]
        mock_verifier = MagicMock(spec=Verifier)
        task_id = 1

        context = VerificationContext(
            file_path=file_path,
            asset=sample_asset,
            config=config,
            owner="myowner",
            repo="myrepo",
            tag_name="v2.0.0",
            app_name="myapp",
            assets=assets,
            progress_task_id=task_id,
            has_digest=True,
            checksum_files=checksum_files,
            verifier=mock_verifier,
            verification_passed=True,
            verification_methods={"sha256": {"passed": True, "hash": "abc"}},
            verification_warning="Test warning",
        )

        assert context.file_path == file_path
        assert context.asset == sample_asset
        assert context.config == config
        assert context.owner == "myowner"
        assert context.repo == "myrepo"
        assert context.tag_name == "v2.0.0"
        assert context.app_name == "myapp"
        assert context.assets == assets
        assert context.progress_task_id == task_id
        assert context.has_digest is True
        assert context.checksum_files == checksum_files
        assert context.verifier == mock_verifier
        assert context.verification_passed is True
        assert context.verification_methods == {
            "sha256": {"passed": True, "hash": "abc"}
        }
        assert context.verification_warning == "Test warning"
