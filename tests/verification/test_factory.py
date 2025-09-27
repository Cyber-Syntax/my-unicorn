"""Tests for verification factory module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from my_unicorn.download import DownloadService
from my_unicorn.services.progress import ProgressService
from my_unicorn.verification.factory import (
    VerificationServiceFacade,
    VerificationStrategyFactory,
)
from my_unicorn.verification.strategies import (
    ChecksumFileVerificationStrategy,
    DigestVerificationStrategy,
)


class TestVerificationStrategyFactory:
    """Tests for VerificationStrategyFactory."""

    @pytest.fixture
    def download_service(self):
        """Mock download service."""
        return MagicMock(spec=DownloadService)

    @pytest.fixture
    def factory(self, download_service):
        """Factory instance for testing."""
        return VerificationStrategyFactory(download_service)

    def test_factory_initialization(self, factory, download_service):
        """Test factory initialization."""
        assert factory.download_service is download_service

    def test_create_digest_strategy(self, factory):
        """Test digest strategy creation."""
        strategy = factory.create_digest_strategy()
        assert isinstance(strategy, DigestVerificationStrategy)

    def test_create_checksum_file_strategy(self, factory):
        """Test checksum file strategy creation."""
        strategy = factory.create_checksum_file_strategy()
        assert isinstance(strategy, ChecksumFileVerificationStrategy)
        assert strategy.download_service is factory.download_service

    def test_get_available_strategies(self, factory):
        """Test getting all available strategies."""
        strategies = factory.get_available_strategies()
        assert "digest" in strategies
        assert "checksum_file" in strategies
        assert isinstance(strategies["digest"], DigestVerificationStrategy)
        assert isinstance(strategies["checksum_file"], ChecksumFileVerificationStrategy)


class TestVerificationServiceFacade:
    """Tests for VerificationServiceFacade."""

    @pytest.fixture
    def download_service(self):
        """Mock download service."""
        return MagicMock(spec=DownloadService)

    @pytest.fixture
    def progress_service(self):
        """Mock progress service."""
        return MagicMock(spec=ProgressService)

    @pytest.fixture
    def facade(self, download_service):
        """Facade instance for testing."""
        return VerificationServiceFacade(download_service)

    @pytest.fixture
    def facade_with_progress(self, download_service, progress_service):
        """Facade instance with progress service."""
        return VerificationServiceFacade(download_service, progress_service)

    def test_facade_initialization(self, facade, download_service):
        """Test facade initialization."""
        assert facade.factory.download_service is download_service
        assert facade.detection_service is not None
        assert facade.prioritization_service is not None
        assert facade.progress_service is None

    def test_facade_initialization_without_progress_service(self, facade_with_progress, progress_service):
        """Test facade initialization with progress service."""
        assert facade_with_progress.progress_service is progress_service

    def test_should_skip_verification_no_strong_methods(self, facade):
        """Test skip logic when no strong verification methods available."""
        config = {"skip": True}  # Must be True to test the skip logic
        has_digest = False
        has_checksum_files = False

        should_skip, updated_config = facade.should_skip_verification(
            config, has_digest, has_checksum_files
        )

        assert should_skip is True
        assert updated_config["skip"] is True  # Should remain True when skipping

    def test_should_skip_verification_explicitly_skipped(self, facade):
        """Test skip logic when explicitly skipped but strong methods available."""
        config = {"skip": True}
        has_digest = True
        has_checksum_files = True

        should_skip, updated_config = facade.should_skip_verification(
            config, has_digest, has_checksum_files
        )

        assert should_skip is False  # Should not skip when strong methods available
        assert updated_config["skip"] is False  # Should override skip setting

    def test_should_skip_verification_with_strong_methods(self, facade):
        """Test skip logic when strong methods available."""
        config = {"skip": False}
        has_digest = True
        has_checksum_files = False

        should_skip, updated_config = facade.should_skip_verification(
            config, has_digest, has_checksum_files
        )

        assert should_skip is False
        assert updated_config["skip"] is False

    def test_should_skip_verification_override_skip_setting(self, facade):
        """Test that skip setting is overridden when strong methods available."""
        config = {"skip": True}
        has_digest = False
        has_checksum_files = True

        should_skip, updated_config = facade.should_skip_verification(
            config, has_digest, has_checksum_files
        )

        assert should_skip is False
        assert updated_config["skip"] is False  # Should be overridden
