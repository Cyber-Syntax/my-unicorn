from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.verify import VerificationConfig, Verifier


@pytest.fixture
def patch_logger():
    """Patch get_logger to avoid real logging output."""
    with patch("my_unicorn.verify.get_logger") as mock_logger:
        yield mock_logger


def test_verify_digest_success(tmp_path: Path, patch_logger):
    """Test Verifier.verify_digest succeeds with correct digest."""
    file = tmp_path / "file.bin"
    data = b"abc123"
    file.write_bytes(data)
    verifier = Verifier(file)
    algo = "sha256"
    import hashlib

    expected_hash = hashlib.sha256(data).hexdigest()
    digest = f"{algo}:{expected_hash}"
    verifier.verify_digest(digest)  # Should not raise


def test_verify_digest_invalid_format(tmp_path: Path, patch_logger):
    """Test Verifier.verify_digest raises on invalid digest format."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    with pytest.raises(ValueError):
        verifier.verify_digest("sha256")  # Missing hash


def test_verify_digest_wrong_hash(tmp_path: Path, patch_logger):
    """Test Verifier.verify_digest raises on hash mismatch."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    digest = "sha256:deadbeef"
    with pytest.raises(ValueError):
        verifier.verify_digest(digest)


def test_verify_digest_unsupported_algo(tmp_path: Path, patch_logger):
    """Test Verifier.verify_digest raises on unsupported algorithm."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    digest = "sha999:abcd"
    with pytest.raises(ValueError):
        verifier.verify_digest(digest)


def test_verify_hash_success(tmp_path: Path, patch_logger):
    """Test Verifier.verify_hash succeeds with correct hash."""
    file = tmp_path / "file.bin"
    data = b"xyz"
    file.write_bytes(data)
    verifier = Verifier(file)
    import hashlib

    expected_hash = hashlib.sha1(data).hexdigest()
    verifier.verify_hash(expected_hash, "sha1")  # Should not raise


def test_verify_hash_mismatch(tmp_path: Path, patch_logger):
    """Test Verifier.verify_hash raises on hash mismatch."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"xyz")
    verifier = Verifier(file)
    with pytest.raises(ValueError):
        verifier.verify_hash("deadbeef", "sha1")


def test_compute_hash_all_types(tmp_path: Path, patch_logger):
    """Test Verifier.compute_hash for all supported types."""
    file = tmp_path / "file.bin"
    data = b"test"
    file.write_bytes(data)
    verifier = Verifier(file)
    import hashlib

    assert verifier.compute_hash("sha1") == hashlib.sha1(data).hexdigest()
    assert verifier.compute_hash("sha256") == hashlib.sha256(data).hexdigest()
    assert verifier.compute_hash("sha512") == hashlib.sha512(data).hexdigest()
    assert verifier.compute_hash("md5") == hashlib.md5(data).hexdigest()


def test_compute_hash_unsupported(tmp_path: Path, patch_logger):
    """Test Verifier.compute_hash raises on unsupported type."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)
    with pytest.raises(ValueError):
        verifier.compute_hash("sha999")


def test_compute_hash_file_not_found(tmp_path: Path, patch_logger):
    """Test Verifier.compute_hash raises if file missing."""
    file = tmp_path / "nofile.bin"
    verifier = Verifier(file)
    with pytest.raises(FileNotFoundError):
        verifier.compute_hash("sha256")


@pytest.mark.asyncio
async def test_verify_from_checksum_file_success(tmp_path: Path, patch_logger):
    """Test Verifier.verify_from_checksum_file finds hash and verifies."""
    file = tmp_path / "file.bin"
    data = b"abc"
    file.write_bytes(data)
    verifier = Verifier(file)
    checksum_content = f"{verifier.compute_hash('sha256')} {file.name}\n"
    mock_download_service = MagicMock()
    mock_download_service.download_checksum_file = AsyncMock(return_value=checksum_content)
    await verifier.verify_from_checksum_file(
        checksum_url="http://example.com/checksum.txt",
        hash_type="sha256",
        download_service=mock_download_service,
        filename=file.name,
    )


@pytest.mark.asyncio
async def test_verify_from_checksum_file_not_found(tmp_path: Path, patch_logger):
    """Test Verifier.verify_from_checksum_file raises if hash not found."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    checksum_content = "deadbeef otherfile.bin\n"
    mock_download_service = MagicMock()
    mock_download_service.download_checksum_file = AsyncMock(return_value=checksum_content)
    with pytest.raises(ValueError):
        await verifier.verify_from_checksum_file(
            checksum_url="http://example.com/checksum.txt",
            hash_type="sha256",
            download_service=mock_download_service,
            filename=file.name,
        )


def test_parse_checksum_file_sha256(tmp_path: Path, patch_logger):
    """Test _parse_checksum_file parses SHA256SUMS format."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    hashval = verifier.compute_hash("sha256")
    content = f"{hashval} {file.name}\n"
    result = verifier._parse_checksum_file(content, file.name, "sha256")
    assert result == hashval


def test_parse_checksum_file_generic(tmp_path: Path, patch_logger):
    """Test _parse_checksum_file parses generic format."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    hashval = "deadbeef"
    content = f"{hashval} {file.name}\n"
    result = verifier._parse_checksum_file(content, file.name, "sha256")
    assert result == hashval


def test_get_file_size(tmp_path: Path, patch_logger):
    """Test Verifier.get_file_size returns correct size."""
    file = tmp_path / "file.bin"
    data = b"abcde"
    file.write_bytes(data)
    verifier = Verifier(file)
    assert verifier.get_file_size() == len(data)


def test_get_file_size_not_found(tmp_path: Path, patch_logger):
    """Test Verifier.get_file_size raises if file missing."""
    file = tmp_path / "nofile.bin"
    verifier = Verifier(file)
    with pytest.raises(FileNotFoundError):
        verifier.get_file_size()


def test_verify_size_success(tmp_path: Path, patch_logger):
    """Test Verifier.verify_size passes if size matches."""
    file = tmp_path / "file.bin"
    data = b"abc"
    file.write_bytes(data)
    verifier = Verifier(file)
    verifier.verify_size(len(data))  # Should not raise


def test_verify_size_mismatch(tmp_path: Path, patch_logger):
    """Test Verifier.verify_size raises if size mismatches."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    with pytest.raises(ValueError):
        verifier.verify_size(10)


def test_verification_config_init_and_from_dict():
    """Test VerificationConfig construction and from_dict."""
    config = VerificationConfig(
        digest=True,
        skip=False,
        checksum_file="foo.txt",
        checksum_hash_type="sha256",
        verify_size=True,
    )
    assert config.digest is True
    assert config.skip is False
    assert config.checksum_file == "foo.txt"
    assert config.checksum_hash_type == "sha256"
    assert config.verify_size is True

    data = {
        "digest": False,
        "skip": True,
        "checksum_file": "bar.txt",
        "checksum_hash_type": "md5",
        "verify_size": False,
    }
    config2 = VerificationConfig.from_dict(data)
    assert config2.digest is False
    assert config2.skip is True
    assert config2.checksum_file == "bar.txt"
    assert config2.checksum_hash_type == "md5"
    assert config2.verify_size is False
