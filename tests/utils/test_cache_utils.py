#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for cache utility functions.

This module contains tests for the cache utility functions in src/utils/cache_utils.py.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import pytest
from pytest import fixture

from src.utils.cache_utils import ensure_directory_exists, load_json_cache, save_json_cache


@fixture
def temp_dir() -> str:
    """
    Create a temporary directory for testing.

    Returns:
        str: Path to the temporary directory
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@fixture
def temp_cache_file() -> str:
    """
    Create a temporary cache file path for testing.

    Returns:
        str: Path to the temporary cache file
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        temp_path = temp_file.name
        yield temp_path
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@fixture
def sample_cache_data() -> tuple[str, Any]:
    """
    Create sample cache data for testing.

    Returns:
        tuple[str, Any]: Sample cache data
    """
    return {
        "timestamp": time.time(),
        "request_count": 5,
        "data": {"item1": "value1", "item2": "value2"},
    }


class TestEnsureDirectoryExists:
    """Tests for ensure_directory_exists function."""

    def test_create_nonexistent_directory(self, temp_dir: str) -> None:
        """
        Test creating a non-existent directory.

        Args:
            temp_dir: Temporary directory fixture
        """
        test_dir = os.path.join(temp_dir, "new_directory")

        # Ensure directory doesn't exist
        assert not os.path.exists(test_dir)

        # Create directory using function
        result = ensure_directory_exists(test_dir)

        # Verify directory was created
        assert os.path.exists(test_dir)
        assert os.path.isdir(test_dir)
        assert result == test_dir

    def test_existing_directory(self, temp_dir: str) -> None:
        """
        Test with an existing directory.

        Args:
            temp_dir: Temporary directory fixture
        """
        # Directory already exists
        assert os.path.exists(temp_dir)

        # Function should return the path without error
        result = ensure_directory_exists(temp_dir)

        assert result == temp_dir
        assert os.path.exists(temp_dir)
        assert os.path.isdir(temp_dir)


class TestLoadJsonCache:
    """Tests for load_json_cache function."""

    def test_load_valid_cache(
        self, temp_cache_file: str, sample_cache_data: tuple[str, Any]
    ) -> None:
        """
        Test loading a valid cache file.

        Args:
            temp_cache_file: Temporary cache file path
            sample_cache_data: Sample cache data
        """
        # Create valid cache file
        with open(temp_cache_file, "w") as f:
            json.dump(sample_cache_data, f)

        # Load cache with default TTL (1 hour)
        result = load_json_cache(temp_cache_file)

        # Verify contents match
        assert result == sample_cache_data

    def test_load_expired_cache(self, temp_cache_file: str) -> None:
        """
        Test loading an expired cache file.

        Args:
            temp_cache_file: Temporary cache file path
        """
        # Create expired cache file (2 hours old)
        expired_data = {
            "timestamp": time.time() - 7200,  # 2 hours ago
            "data": {"item": "value"},
        }
        with open(temp_cache_file, "w") as f:
            json.dump(expired_data, f)

        # Load cache with 1 hour TTL
        result = load_json_cache(temp_cache_file, ttl_seconds=3600)

        # Should return empty dict for expired cache
        assert result == {}

    def test_load_with_hard_refresh(self, temp_cache_file: str) -> None:
        """
        Test loading with hard refresh threshold.

        Args:
            temp_cache_file: Temporary cache file path
        """
        # Create slightly expired cache file (90 minutes old)
        cache_data = {
            "timestamp": time.time() - 5400,  # 90 minutes ago
            "request_count": 10,
            "data": {"item": "value"},
        }
        with open(temp_cache_file, "w") as f:
            json.dump(cache_data, f)

        # Load cache with 1 hour TTL but 2 hour hard refresh
        result = load_json_cache(
            temp_cache_file,
            ttl_seconds=3600,  # 1 hour
            hard_refresh_seconds=7200,  # 2 hours
        )

        # Should return data but reset request_count
        assert "data" in result
        assert result["data"] == cache_data["data"]
        assert result["timestamp"] == cache_data["timestamp"]
        assert result["request_count"] == 0  # Reset to 0

    def test_load_nonexistent_file(self) -> None:
        """Test loading a non-existent cache file."""
        result = load_json_cache("/nonexistent/path/cache.json")
        assert result == {}

    def test_load_invalid_json(self, temp_cache_file: str) -> None:
        """
        Test loading an invalid JSON file.

        Args:
            temp_cache_file: Temporary cache file path
        """
        # Create invalid JSON file
        with open(temp_cache_file, "w") as f:
            f.write("this is not valid json")

        # Should return empty dict for invalid JSON
        result = load_json_cache(temp_cache_file)
        assert result == {}


class TestSaveJsonCache:
    """Tests for save_json_cache function."""

    def test_save_new_cache(self, temp_dir: str, sample_cache_data: tuple[str, Any]) -> None:
        """
        Test saving to a new cache file.

        Args:
            temp_dir: Temporary directory fixture
            sample_cache_data: Sample cache data
        """
        cache_path = os.path.join(temp_dir, "new_cache.json")

        # Save data to new cache file
        result = save_json_cache(cache_path, sample_cache_data)

        # Verify file was created and function returned True
        assert result is True
        assert os.path.exists(cache_path)

        # Verify contents match
        with open(cache_path, "r") as f:
            saved_data = json.load(f)
        assert saved_data == sample_cache_data

    def test_save_adds_timestamp(self, temp_dir: str) -> None:
        """
        Test that save adds timestamp if missing.

        Args:
            temp_dir: Temporary directory fixture
        """
        cache_path = os.path.join(temp_dir, "timestamped_cache.json")
        data_without_timestamp = {"data": "value"}

        # Save data without timestamp
        save_json_cache(cache_path, data_without_timestamp)

        # Read saved file
        with open(cache_path, "r") as f:
            saved_data = json.load(f)

        # Verify timestamp was added
        assert "timestamp" in saved_data
        assert isinstance(saved_data["timestamp"], (int, float))
        # The timestamp should be recent (within the last second)
        assert time.time() - saved_data["timestamp"] < 1

    def test_save_to_nonexistent_directory(
        self, temp_dir: str, sample_cache_data: tuple[str, Any]
    ) -> None:
        """
        Test saving to a file in a non-existent directory.

        Args:
            temp_dir: Temporary directory fixture
            sample_cache_data: Sample cache data
        """
        # Path with non-existent parent directories
        deep_path = os.path.join(temp_dir, "new", "deeper", "cache.json")

        # Ensure parent directory doesn't exist
        assert not os.path.exists(os.path.dirname(deep_path))

        # Save should create parent directories
        result = save_json_cache(deep_path, sample_cache_data)

        # Verify file was created
        assert result is True
        assert os.path.exists(deep_path)

    def test_save_updates_existing_file(self, temp_cache_file: str) -> None:
        """
        Test updating an existing cache file.

        Args:
            temp_cache_file: Temporary cache file path
        """
        # Create initial cache file
        initial_data = {"timestamp": time.time(), "value": "initial"}
        with open(temp_cache_file, "w") as f:
            json.dump(initial_data, f)

        # Update with new data
        new_data = {"value": "updated"}
        save_json_cache(temp_cache_file, new_data)

        # Read updated file
        with open(temp_cache_file, "r") as f:
            updated_data = json.load(f)

        # Verify contents were updated
        assert updated_data["value"] == "updated"
        assert "timestamp" in updated_data
