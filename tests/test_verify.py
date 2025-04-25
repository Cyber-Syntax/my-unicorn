from unittest import mock
import pytest
from pathlib import Path
import builtins
import hashlib
import os
from src.verify import VerificationManager

# Assuming the VerificationManager class is defined in a module named verifier
# from verifier import VerificationManager

# Mock appimage and SHA content
APPIMAGE_CONTENT = b"dummy content for hashing"
SHA256_HASH = hashlib.sha256(APPIMAGE_CONTENT).hexdigest()
SHA_FILE_CONTENT = f"{SHA256_HASH}  appimage.AppImage\n"

@pytest.fixture
def mock_appimage(tmp_path):
    file_path = tmp_path / "appimage.AppImage"
    file_path.write_bytes(APPIMAGE_CONTENT)
    return str(file_path)

@pytest.fixture
def mock_sha_file(tmp_path):
    sha_path = tmp_path / "appimage.sha256"
    sha_path.write_text(SHA_FILE_CONTENT)
    return str(sha_path)

@pytest.fixture
def patch_requests_get():
    with mock.patch("requests.get") as mock_get:
        mock_response = mock.Mock()
        mock_response.text = SHA_FILE_CONTENT
        mock_response.raise_for_status = mock.Mock()
        mock_get.return_value = mock_response
        yield mock_get

def test_valid_sha256_verification(mock_appimage, tmp_path, patch_requests_get):
    sha_name = str(tmp_path / "appimage.sha256")
    vm = VerificationManager(
        sha_name=sha_name,
        sha_url="https://example.com/appimage.sha256",
        appimage_name=mock_appimage,
        hash_type="sha256"
    )

    assert vm.verify_appimage() is True

def test_invalid_hash_type():
    with pytest.raises(ValueError):
        VerificationManager(hash_type="md5")

def test_no_hash_mode_skips_verification(mock_appimage):
    vm = VerificationManager(
        sha_name=None,
        sha_url=None,
        appimage_name=mock_appimage,
        hash_type="no_hash"
    )

    assert vm.verify_appimage() is True

def test_missing_appimage_returns_false(tmp_path):
    vm = VerificationManager(
        sha_name="irrelevant",
        sha_url="https://example.com/sha256",
        appimage_name=str(tmp_path / "nonexistent.AppImage"),
        hash_type="sha256"
    )

    assert vm.verify_appimage() is False

def test_cleanup_on_failure(tmp_path):
    bad_appimage = tmp_path / "bad.AppImage"
    bad_appimage.write_text("corrupted content")

    sha_name = tmp_path / "bad.sha256"
    sha_name.write_text("bad_hash  bad.AppImage\n")

    vm = VerificationManager(
        sha_name=str(sha_name),
        sha_url="https://example.com/bad.sha256",
        appimage_name=str(bad_appimage),
        hash_type="sha256"
    )

    result = vm.verify_appimage(cleanup_on_failure=True)
    file_exists_after = os.path.exists(str(bad_appimage))

    assert result is False
    assert file_exists_after is False


import base64

# Extend the test suite with additional edge cases for YAML and .sha512 parsing,
# missing SHA fields, decoding errors, and fallback cases.

@pytest.fixture
def mock_yaml_sha_file(tmp_path):
    sha_path = tmp_path / "appimage.yml"
    hash_b64 = base64.b64encode(bytes.fromhex(SHA256_HASH)).decode("utf-8")
    sha_path.write_text(f"sha256: {hash_b64}")
    return str(sha_path)

def test_yaml_sha_verification(mock_appimage, mock_yaml_sha_file):
    vm = VerificationManager(
        sha_name=mock_yaml_sha_file,
        sha_url="",
        appimage_name=mock_appimage,
        hash_type="sha256"
    )
    assert vm.verify_appimage() is True

def test_yaml_sha_missing_field(tmp_path, mock_appimage):
    path = tmp_path / "bad.yml"
    path.write_text("sha512: invalid")
    vm = VerificationManager(
        sha_name=str(path),
        sha_url="",
        appimage_name=mock_appimage,
        hash_type="sha256"
    )
    assert vm.verify_appimage() is False

def test_yaml_sha_bad_base64(tmp_path, mock_appimage):
    path = tmp_path / "corrupt.yml"
    path.write_text("sha256: !!not_base64!!")
    vm = VerificationManager(
        sha_name=str(path),
        sha_url="",
        appimage_name=mock_appimage,
        hash_type="sha256"
    )
    assert vm.verify_appimage() is False

def test_sha512_file(mock_appimage, tmp_path):
    sha512 = hashlib.sha512(APPIMAGE_CONTENT).hexdigest()
    sha_path = tmp_path / "file.sha512"
    sha_path.write_text(f"{sha512}  appimage.AppImage\n")

    vm = VerificationManager(
        sha_name=str(sha_path),
        sha_url="",
        appimage_name=mock_appimage,
        hash_type="sha512"
    )

    assert vm.verify_appimage() is True

def test_text_sha_with_invalid_line(tmp_path, mock_appimage):
    sha_path = tmp_path / "mixed.txt"
    sha_path.write_text("invalid_line_without_hash\n")
    vm = VerificationManager(
        sha_name=str(sha_path),
        sha_url="",
        appimage_name=mock_appimage,
        hash_type="sha256"
    )

    assert vm.verify_appimage() is False

def test_verification_fallback_when_sha_matches_appimage(tmp_path):
    dummy_appimage = tmp_path / "App.AppImage"
    dummy_appimage.write_text("no real content")

    vm = VerificationManager(
        sha_name=str(dummy_appimage),
        sha_url="https://irrelevant.com",
        appimage_name=str(dummy_appimage),
        hash_type="sha256"
    )

    assert vm.verify_appimage() is True

def test_cleanup_verification_file(tmp_path):
    sha_path = tmp_path / "temp.sha256"
    sha_path.write_text("dummy")
    vm = VerificationManager(
        sha_name=str(sha_path),
        sha_url="",
        appimage_name="irrelevant",
        hash_type="no_hash"
    )
    vm._cleanup_verification_file()
    assert not os.path.exists(sha_path)

def test_log_comparison_output(capsys):
    vm = VerificationManager(
        sha_name="dummy",
        sha_url="dummy",
        appimage_name="test.AppImage",
        hash_type="sha256"
    )
    vm._log_comparison("abc123", "abc456")
    output = capsys.readouterr().out
    assert "VERIFICATION FAILED" in output
    assert "Expected" in output and "Actual" in output

