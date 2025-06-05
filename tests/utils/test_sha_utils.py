#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for SHA utility functions.

This module contains tests for the SHA utility functions in src/utils/sha_utils.py.
"""


import pytest

from src.utils.sha_utils import is_sha_file, detect_hash_type


class TestIsShaFile:
    """Tests for is_sha_file function."""

    def test_standard_sha_files(self) -> None:
        """Test standard SHA file extensions."""
        assert is_sha_file("app.sha256") is True
        assert is_sha_file("app.SHA256") is True
        assert is_sha_file("app.sha512") is True
        assert is_sha_file("app.sha") is True
        assert is_sha_file("app.sum") is True

    def test_yaml_files(self) -> None:
        """Test YAML files that may contain SHA information."""
        assert is_sha_file("app.yml") is True
        assert is_sha_file("app.yaml") is True
        assert is_sha_file("latest-linux.yml") is True

    def test_text_files_with_sha_keywords(self) -> None:
        """Test text files with SHA-related keywords."""
        assert is_sha_file("checksum.txt") is True
        assert is_sha_file("sha256sums") is True
        assert is_sha_file("sha256.txt") is True
        assert is_sha_file("sha512.txt") is True

    def test_non_sha_files(self) -> None:
        """Test files that are not SHA files."""
        assert is_sha_file("app.AppImage") is False
        assert is_sha_file("app.exe") is False
        assert is_sha_file("app.png") is False
        assert is_sha_file("app.json") is False
        assert is_sha_file("readme.md") is False

    def test_edge_cases(self) -> None:
        """Test edge cases for SHA file detection."""
        assert is_sha_file("app.txt") is False  # No SHA keyword
        assert is_sha_file("checksums") is True  # Contains "checksum"
        assert is_sha_file("SHA256") is True  # Contains "sha256"
        assert is_sha_file("SHA512") is True  # Contains "sha512"


class TestDetectHashType:
    """Tests for detect_hash_type function."""

    def test_sha256_detection(self) -> None:
        """Test detection of SHA256 hash type."""
        assert detect_hash_type("app.sha256") == "sha256"
        assert detect_hash_type("SHA256SUMS") == "sha256"
        assert detect_hash_type("app-sha256.txt") == "sha256"
        assert detect_hash_type("checksum-sha256.txt") == "sha256"

    def test_sha512_detection(self) -> None:
        """Test detection of SHA512 hash type."""
        assert detect_hash_type("app.sha512") == "sha512"
        assert detect_hash_type("SHA512SUMS") == "sha512"
        assert detect_hash_type("app-sha512.txt") == "sha512"
        assert detect_hash_type("checksum-sha512.txt") == "sha512"

    def test_yml_files(self) -> None:
        """Test hash type detection for YAML files."""
        assert detect_hash_type("latest-linux.yml") == "sha512"
        assert detect_hash_type("app.yml") == "sha512"
        assert detect_hash_type("app.yaml") == "sha512"

    def test_default_fallback(self) -> None:
        """Test default fallback when hash type cannot be determined."""
        assert detect_hash_type("checksum.txt") == "sha256"
        assert detect_hash_type("hashes.txt") == "sha256"
        assert detect_hash_type("unknown.sum") == "sha256"
