"""Tests for verification detection module."""

import pytest

from my_unicorn.github_client import ChecksumFileInfo
from my_unicorn.verification.detection import (
    ChecksumFilePrioritizationService,
    VerificationDetectionService,
)


class TestVerificationDetectionService:
    """Test VerificationDetectionService."""

    @pytest.fixture
    def detection_service(self):
        """Create detection service instance."""
        return VerificationDetectionService()

    def test_detect_available_methods_with_digest_only(self, detection_service):
        """Test detection when only digest is available."""
        asset = {"digest": "sha256:abc123"}
        config = {"digest": True}

        has_digest, checksum_files = detection_service.detect_available_methods(asset, config)

        assert has_digest is True
        assert len(checksum_files) == 0

    def test_detect_available_methods_no_digest(self, detection_service):
        """Test detection when no digest is available."""
        asset = {"digest": ""}
        config = {"digest": False}

        has_digest, checksum_files = detection_service.detect_available_methods(asset, config)

        assert has_digest is False
        assert len(checksum_files) == 0

    def test_detect_available_methods_with_assets(self, detection_service):
        """Test detection with GitHub assets."""
        asset = {"digest": ""}
        config = {"digest": False}
        assets = [
            {"name": "app.AppImage", "size": 1234},
            {"name": "latest-linux.yml", "size": 567},
            {"name": "SHA256SUMS", "size": 890},
        ]

        has_digest, checksum_files = detection_service.detect_available_methods(
            asset, config, assets, "owner", "repo", "v1.0.0"
        )

        assert has_digest is False
        assert len(checksum_files) == 2  # YAML and SHA256SUMS
        assert any(cf.filename == "latest-linux.yml" for cf in checksum_files)
        assert any(cf.filename == "SHA256SUMS" for cf in checksum_files)

    def test_detect_available_methods_manual_checksum_file(self, detection_service):
        """Test detection with manual checksum file configuration."""
        asset = {"digest": ""}
        config = {"checksum_file": "manual.txt"}

        has_digest, checksum_files = detection_service.detect_available_methods(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert has_digest is False
        assert len(checksum_files) == 1
        assert checksum_files[0].filename == "manual.txt"

    def test_detect_available_methods_digest_and_checksum(self, detection_service):
        """Test detection with both digest and checksum files available."""
        asset = {"digest": "sha256:abc123"}
        config = {"digest": False}  # Don't explicitly enable digest to allow auto-detection
        assets = [
            {"name": "app.AppImage", "size": 1234},
            {"name": "checksums.txt", "size": 567},
        ]

        has_digest, checksum_files = detection_service.detect_available_methods(
            asset, config, assets, "owner", "repo", "v1.0.0"
        )

        assert has_digest is True
        assert len(checksum_files) == 1  # Should find checksum file
        assert checksum_files[0].filename == "checksums.txt"


class TestChecksumFilePrioritizationService:
    """Test ChecksumFilePrioritizationService."""

    @pytest.fixture
    def prioritization_service(self):
        """Create prioritization service instance."""
        return ChecksumFilePrioritizationService()

    @pytest.fixture
    def sample_checksum_files(self):
        """Create sample checksum files for testing."""
        return [
            ChecksumFileInfo(
                filename="SHA256SUMS",
                url="https://example.com/SHA256SUMS",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="latest-linux.yml",
                url="https://example.com/latest-linux.yml",
                format_type="yaml",
            ),
            ChecksumFileInfo(
                filename="app.AppImage.sha256",
                url="https://example.com/app.AppImage.sha256",
                format_type="traditional",
            ),
        ]

    def test_prioritize_checksum_files_yaml_priority(
        self, prioritization_service, sample_checksum_files
    ):
        """Test that YAML files get higher priority."""
        target_filename = "app.AppImage"

        prioritized = prioritization_service.prioritize_checksum_files(
            sample_checksum_files, target_filename
        )

        # Platform-specific should be first priority (highest)
        assert prioritized[0].format_type == "traditional"
        assert prioritized[0].filename == "app.AppImage.sha256"
        # YAML should be second
        assert prioritized[1].format_type == "yaml"
        assert prioritized[1].filename == "latest-linux.yml"

    def test_prioritize_checksum_files_target_specific_priority(self, prioritization_service):
        """Test that target-specific files get highest priority."""
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA256SUMS",
                url="https://example.com/SHA256SUMS",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="app.AppImage.sha256",
                url="https://example.com/app.AppImage.sha256",
                format_type="traditional",
            ),
        ]
        target_filename = "app.AppImage"

        prioritized = prioritization_service.prioritize_checksum_files(
            checksum_files, target_filename
        )

        # Target-specific file should be first
        assert prioritized[0].filename == "app.AppImage.sha256"

    def test_prioritize_checksum_files_empty_list(self, prioritization_service):
        """Test prioritization with empty checksum file list."""
        prioritized = prioritization_service.prioritize_checksum_files([], "app.AppImage")

        assert len(prioritized) == 0

    def test_prioritize_checksum_files_maintains_all_files(
        self, prioritization_service, sample_checksum_files
    ):
        """Test that all files are maintained after prioritization."""
        target_filename = "app.AppImage"

        prioritized = prioritization_service.prioritize_checksum_files(
            sample_checksum_files, target_filename
        )

        assert len(prioritized) == len(sample_checksum_files)
        original_filenames = {cf.filename for cf in sample_checksum_files}
        prioritized_filenames = {cf.filename for cf in prioritized}
        assert original_filenames == prioritized_filenames
