"""Tests for the Verifier integration points and helpers."""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.domain.verification import VerificationConfig, Verifier


def test_verify_digest_success(tmp_path: Path) -> None:
    """Digest verification succeeds when hashes match."""
    file = tmp_path / "file.bin"
    data = b"abc123"
    file.write_bytes(data)
    verifier = Verifier(file)

    expected_hash = hashlib.sha256(data).hexdigest()
    digest = f"sha256:{expected_hash}"
    verifier.verify_digest(digest)


def test_verify_digest_invalid_format(tmp_path: Path) -> None:
    """Digest verification fails on invalid format."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    with pytest.raises(ValueError, match="Invalid digest format"):
        verifier.verify_digest("sha256")


def test_verify_digest_wrong_hash(tmp_path: Path) -> None:
    """Digest verification fails on mismatch."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    digest = "sha256:deadbeef"
    with pytest.raises(ValueError, match="Digest mismatch"):
        verifier.verify_digest(digest)


def test_verify_digest_unsupported_algo(tmp_path: Path) -> None:
    """Digest verification fails on unsupported algorithms."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    with pytest.raises(ValueError, match="Unsupported digest algorithm"):
        verifier.verify_digest("sha999:abcd")


def test_verify_hash_success(tmp_path: Path) -> None:
    """Hash verification succeeds for matching hashes."""
    file = tmp_path / "file.bin"
    data = b"xyz"
    file.write_bytes(data)
    verifier = Verifier(file)

    expected_hash = hashlib.sha1(data).hexdigest()  # noqa: S324
    verifier.verify_hash(expected_hash, "sha1")


def test_verify_hash_mismatch(tmp_path: Path) -> None:
    """Hash verification fails on mismatch."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"xyz")
    verifier = Verifier(file)
    with pytest.raises(ValueError, match="SHA1 mismatch"):
        verifier.verify_hash("deadbeef", "sha1")


def test_compute_hash_all_types(tmp_path: Path) -> None:
    """Compute hashes across supported algorithms."""
    file = tmp_path / "file.bin"
    data = b"test"
    file.write_bytes(data)
    verifier = Verifier(file)

    assert verifier.compute_hash("sha1") == hashlib.sha1(data).hexdigest()  # noqa: S324
    assert verifier.compute_hash("sha256") == hashlib.sha256(data).hexdigest()
    assert verifier.compute_hash("sha512") == hashlib.sha512(data).hexdigest()
    assert verifier.compute_hash("md5") == hashlib.md5(data).hexdigest()  # noqa: S324


def test_compute_hash_unsupported(tmp_path: Path) -> None:
    """Unsupported hash types raise errors."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)
    with pytest.raises(ValueError, match="Unsupported hash type"):
        verifier.compute_hash("sha999")


def test_compute_hash_file_not_found(tmp_path: Path) -> None:
    """Missing file raises FileNotFoundError."""
    file = tmp_path / "nofile.bin"
    verifier = Verifier(file)
    with pytest.raises(FileNotFoundError, match="File not found"):
        verifier.compute_hash("sha256")


@pytest.mark.asyncio
async def test_verify_from_checksum_file_success(tmp_path: Path) -> None:
    """Checksum file verification succeeds when hash found."""
    file = tmp_path / "file.bin"
    data = b"abc"
    file.write_bytes(data)
    verifier = Verifier(file)
    checksum_content = f"{verifier.compute_hash('sha256')} {file.name}\n"
    mock_download_service = MagicMock()
    mock_download_service.download_checksum_file = AsyncMock(
        return_value=checksum_content
    )

    await verifier.verify_from_checksum_file(
        checksum_url="http://example.com/checksum.txt",
        hash_type="sha256",
        download_service=mock_download_service,
        filename=file.name,
    )


@pytest.mark.asyncio
async def test_verify_from_checksum_file_not_found(tmp_path: Path) -> None:
    """Checksum verification fails when target hash missing."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    checksum_content = "deadbeef otherfile.bin\n"
    mock_download_service = MagicMock()
    mock_download_service.download_checksum_file = AsyncMock(
        return_value=checksum_content
    )

    with pytest.raises(ValueError, match="not found in checksum file"):
        await verifier.verify_from_checksum_file(
            checksum_url="http://example.com/checksum.txt",
            hash_type="sha256",
            download_service=mock_download_service,
            filename=file.name,
        )


def test_verification_config_init_and_from_dict() -> None:
    """Configuration model stores provided fields."""
    config = VerificationConfig(
        digest_enabled=True,
        skip=False,
        checksum_file="foo.txt",
        checksum_hash_type="sha256",
    )
    assert config.digest_enabled is True
    assert config.skip is False
    assert config.checksum_file == "foo.txt"
    assert config.checksum_hash_type == "sha256"

    config2 = VerificationConfig(
        digest_enabled=False,
        skip=True,
        checksum_file="bar.txt",
        checksum_hash_type="sha512",
    )
    assert config2.digest_enabled is False
    assert config2.skip is True
    assert config2.checksum_file == "bar.txt"
    assert config2.checksum_hash_type == "sha512"
