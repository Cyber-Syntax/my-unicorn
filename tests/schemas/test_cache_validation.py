"""Tests for cache release entry validation."""

import pytest

from my_unicorn.config.schemas import SchemaValidationError, validate_cache_release


@pytest.fixture
def valid_cache_entry():
    """Return valid cache entry fixture."""
    return {
        "cached_at": "2025-12-27T13:45:07.291225+00:00",
        "ttl_hours": 24,
        "release_data": {
            "owner": "obsidianmd",
            "repo": "obsidian-releases",
            "version": "1.10.6",
            "prerelease": False,
            "assets": [
                {
                    "name": "Obsidian-1.10.6.AppImage",
                    "size": 125170595,
                    "digest": (
                        "sha256:162d753076d0610e4dccfdccf391c13a"
                        "f5fcb557ba7574b77f0e90ac3c522b1c"
                    ),
                    "browser_download_url": (
                        "https://github.com/obsidianmd/obsidian-releases/"
                        "releases/download/v1.10.6/Obsidian-1.10.6.AppImage"
                    ),
                }
            ],
            "original_tag_name": "v1.10.6",
        },
    }


def test_valid_cache_entry(valid_cache_entry):
    """Test validation passes for valid cache entry."""
    validate_cache_release(valid_cache_entry, "obsidianmd_obsidian-releases")


def test_missing_required_field(valid_cache_entry):
    """Test validation fails for missing required fields."""
    del valid_cache_entry["cached_at"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_cache_release(valid_cache_entry)
    assert "cached_at" in str(exc_info.value).lower()


def test_invalid_timestamp_format(valid_cache_entry):
    """Test validation fails for invalid timestamp format."""
    valid_cache_entry["cached_at"] = "2025-12-27 13:45:07"  # Missing timezone
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_cache_release(valid_cache_entry)
    assert "cached_at" in str(exc_info.value).lower()


def test_invalid_ttl_too_low(valid_cache_entry):
    """Test validation fails for TTL below minimum."""
    valid_cache_entry["ttl_hours"] = 0
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_cache_release(valid_cache_entry)
    assert "ttl_hours" in str(exc_info.value).lower()


def test_invalid_ttl_too_high(valid_cache_entry):
    """Test validation fails for TTL above maximum."""
    valid_cache_entry["ttl_hours"] = 200
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_cache_release(valid_cache_entry)
    assert "ttl_hours" in str(exc_info.value).lower()


def test_empty_assets_array(valid_cache_entry):
    """Test validation passes for empty assets array."""
    valid_cache_entry["release_data"]["assets"] = []
    # Should pass - empty assets is valid (no compatible AppImages)
    validate_cache_release(valid_cache_entry)


def test_invalid_digest_format(valid_cache_entry):
    """Test validation fails for invalid digest format."""
    valid_cache_entry["release_data"]["assets"][0]["digest"] = (
        "invalid_digest"  # Missing algorithm:hash format
    )
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_cache_release(valid_cache_entry)
    assert "digest" in str(exc_info.value).lower()


def test_null_digest_allowed(valid_cache_entry):
    """Test validation passes when digest is null."""
    valid_cache_entry["release_data"]["assets"][0]["digest"] = None
    validate_cache_release(valid_cache_entry)


def test_sha512_digest_format(valid_cache_entry):
    """Test validation passes for SHA512 digest."""
    # SHA512 requires 128 hex chars
    valid_cache_entry["release_data"]["assets"][0]["digest"] = (
        "sha512:" + "a" * 128
    )
    validate_cache_release(valid_cache_entry)


def test_multiple_assets(valid_cache_entry):
    """Test validation passes for multiple assets."""
    valid_cache_entry["release_data"]["assets"].append(
        {
            "name": "Obsidian-1.10.6-arm64.AppImage",
            "size": 120000000,
            "digest": (
                "sha256:abcdef1234567890abcdef1234567890"
                "abcdef1234567890abcdef1234567890"
            ),
            "browser_download_url": (
                "https://github.com/obsidianmd/obsidian-releases/"
                "releases/download/v1.10.6/Obsidian-1.10.6-arm64.AppImage"
            ),
        }
    )
    validate_cache_release(valid_cache_entry)


def test_cache_name_in_error_message(valid_cache_entry):
    """Test cache name appears in error message."""
    del valid_cache_entry["cached_at"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_cache_release(valid_cache_entry, "test_cache")
    assert "test_cache" in str(exc_info.value)


def test_prerelease_true(valid_cache_entry):
    """Test validation passes for prerelease=true."""
    valid_cache_entry["release_data"]["prerelease"] = True
    validate_cache_release(valid_cache_entry)


def test_lowercase_appimage_extension(valid_cache_entry):
    """Test validation passes for lowercase .appimage extension."""
    valid_cache_entry["release_data"]["assets"][0]["name"] = (
        "Obsidian-1.10.6.appimage"
    )
    validate_cache_release(valid_cache_entry)


def test_missing_asset_required_field(valid_cache_entry):
    """Test validation fails for missing asset required field."""
    del valid_cache_entry["release_data"]["assets"][0]["size"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_cache_release(valid_cache_entry)
    assert "size" in str(exc_info.value).lower()


def test_invalid_url_format(valid_cache_entry):
    """Test validation fails for non-GitHub URL."""
    valid_cache_entry["release_data"]["assets"][0]["browser_download_url"] = (
        "https://example.com/file.AppImage"
    )
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_cache_release(valid_cache_entry)
    assert "browser_download_url" in str(exc_info.value).lower()
