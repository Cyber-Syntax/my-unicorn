#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for architecture utility functions.

This module contains tests for the architecture utility functions in src/utils/arch_utils.py.
"""

import platform
from unittest.mock import patch, MagicMock

import pytest

from my_unicorn.utils.arch_utils import (
    get_arch_keywords,
    get_incompatible_archs,
    extract_arch_from_filename,
    get_current_arch,
)


class TestGetArchKeywords:
    """Tests for get_arch_keywords function."""

    def test_with_explicit_keyword(self) -> None:
        """Test with an explicitly provided architecture keyword."""
        result = get_arch_keywords("custom-arch")
        assert result == ["custom-arch"]

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="x86_64")
    def test_linux_x86_64(self, mock_machine: MagicMock, mock_system: MagicMock) -> None:
        """
        Test architecture keywords for Linux x86_64.

        Args:
            mock_machine: Mocked platform.machine function
            mock_system: Mocked platform.system function
        """
        result = get_arch_keywords()
        assert "x86_64" in result
        assert "amd64" in result
        assert "x64" in result
        assert len(result) > 0

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="aarch64")
    def test_linux_arm64(self, mock_machine: MagicMock, mock_system: MagicMock) -> None:
        """
        Test architecture keywords for Linux ARM64.

        Args:
            mock_machine: Mocked platform.machine function
            mock_system: Mocked platform.system function
        """
        result = get_arch_keywords()
        assert "aarch64" in result
        assert "arm64" in result
        assert "arm" in result
        assert len(result) > 0

    @patch("platform.system", return_value="Darwin")
    @patch("platform.machine", return_value="x86_64")
    def test_macos_x86_64(self, mock_machine: MagicMock, mock_system: MagicMock) -> None:
        """
        Test architecture keywords for macOS x86_64.

        Args:
            mock_machine: Mocked platform.machine function
            mock_system: Mocked platform.system function
        """
        result = get_arch_keywords()
        assert "x86_64" in result
        assert "macos" in result
        assert len(result) > 0

    @patch("platform.system", return_value="Windows")
    @patch("platform.machine", return_value="AMD64")
    def test_windows_x86_64(self, mock_machine: MagicMock, mock_system: MagicMock) -> None:
        """
        Test architecture keywords for Windows x86_64.

        Args:
            mock_machine: Mocked platform.machine function
            mock_system: Mocked platform.system function
        """
        result = get_arch_keywords()
        assert "x86_64" in result
        assert "win64" in result
        assert len(result) > 0

    @patch("platform.system", return_value="Unknown")
    @patch("platform.machine", return_value="Unknown")
    def test_unknown_platform(self, mock_machine: MagicMock, mock_system: MagicMock) -> None:
        """
        Test architecture keywords for unknown platform.

        Args:
            mock_machine: Mocked platform.machine function
            mock_system: Mocked platform.system function
        """
        result = get_arch_keywords()
        assert result == ["unknown"]


class TestGetIncompatibleArchs:
    """Tests for get_incompatible_archs function."""

    def test_x86_64_incompatible(self) -> None:
        """Test incompatible architectures for x86_64."""
        result = get_incompatible_archs("x86_64")
        assert "arm64" in result
        assert "aarch64" in result
        assert "i686" in result
        assert "win" in result

    def test_arm64_incompatible(self) -> None:
        """Test incompatible architectures for ARM64."""
        result = get_incompatible_archs("arm64")
        assert "x86_64" in result
        assert "amd64" in result
        assert "win" in result

    def test_i686_incompatible(self) -> None:
        """Test incompatible architectures for i686."""
        result = get_incompatible_archs("i686")
        assert "x86_64" in result
        assert "arm64" in result
        assert "win" in result

    def test_unknown_arch(self) -> None:
        """Test incompatible architectures for unknown architecture."""
        result = get_incompatible_archs("unknown")
        assert result == []


class TestExtractArchFromFilename:
    """Tests for extract_arch_from_filename function."""

    def test_extract_x86_64(self) -> None:
        """Test extracting x86_64 architecture from filename."""
        assert extract_arch_from_filename("app-x86_64.AppImage") == "x86_64"
        assert extract_arch_from_filename("app-amd64.AppImage") == "x86_64"
        assert extract_arch_from_filename("app-x64.AppImage") == "x86_64"

    def test_extract_arm64(self) -> None:
        """Test extracting ARM64 architecture from filename."""
        assert extract_arch_from_filename("app-arm64.AppImage") == "arm64"
        assert extract_arch_from_filename("app-aarch64.AppImage") == "arm64"

    def test_extract_armv7(self) -> None:
        """Test extracting ARMv7 architecture from filename."""
        assert extract_arch_from_filename("app-armv7.AppImage") == "armv7"
        assert extract_arch_from_filename("app-armhf.AppImage") == "armv7"
        assert extract_arch_from_filename("app-arm32.AppImage") == "armv7"

    def test_extract_i386(self) -> None:
        """Test extracting i386 architecture from filename."""
        assert extract_arch_from_filename("app-i386.AppImage") == "i386"
        assert extract_arch_from_filename("app-i686.AppImage") == "i386"
        assert extract_arch_from_filename("app-x86.AppImage") == "i386"

    def test_extract_non_linux(self) -> None:
        """Test extracting non-Linux architectures from filename."""
        assert extract_arch_from_filename("app-mac.dmg") == "mac"
        assert extract_arch_from_filename("app-win.exe") == "win"
        assert extract_arch_from_filename("app-darwin.zip") == "mac"
        assert extract_arch_from_filename("app-windows.msi") == "win"

    def test_no_arch_in_filename(self) -> None:
        """Test with no architecture in filename."""
        assert extract_arch_from_filename("app.AppImage") == ""
        assert extract_arch_from_filename("application.deb") == ""

    def test_none_filename(self) -> None:
        """Test with None filename."""
        assert extract_arch_from_filename(None) == ""


class TestGetCurrentArch:
    """Tests for get_current_arch function."""

    @patch("platform.machine", return_value="x86_64")
    def test_get_current_arch(self, mock_machine: MagicMock) -> None:
        """
        Test getting current architecture.

        Args:
            mock_machine: Mocked platform.machine function
        """
        assert get_current_arch() == "x86_64"

    @patch("platform.machine", return_value="aarch64")
    def test_get_current_arch_arm(self, mock_machine: MagicMock) -> None:
        """
        Test getting current ARM architecture.

        Args:
            mock_machine: Mocked platform.machine function
        """
        assert get_current_arch() == "aarch64"
