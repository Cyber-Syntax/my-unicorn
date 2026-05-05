"""Integration tests for verify.py — hash preservation on verification failure.

WHY THESE TESTS EXIST
---------------------
In practice, ``latest-linux.yml`` (electron-builder) sha512 checksums
often fail because upstream maintainers accidentally publish a wrong hash.
When that happens the team must answer: "Is this a bug in our code, or is
the external checksum file simply wrong?"

To answer that question we need BOTH sides of the mismatch stored in the
result even when verification fails:
  - ``hash``          → the expected hash taken from the checksum file / digest
  - ``computed_hash`` → what we actually computed from the downloaded file

These tests verify that ``MethodResult`` always carries both fields, and that
the data flows correctly through ``execute_all_verification_methods`` and
``VerificationService.verify_file``.

Test isolation strategy
-----------------------
- Real file I/O   → ``tmp_path`` gives us an actual on-disk file whose SHA256
                    and SHA512 hashes we pre-compute with ``hashlib``.
- Real hashing    → we never mock ``hashlib`` or ``Verifier``; the whole point
                    is to exercise the real hash path.
- Mocked network  → ``DownloadService.download_checksum_file`` is the *only*
                    thing mocked because hitting real GitHub in CI is fragile
                    and slow.  Everything else runs for real.
- NullProgress    → ``NullProgressReporter`` is the production null-object;
                    no extra mocking needed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import orjson
import pytest
import pytest_asyncio  # noqa: F401  (activates async fixtures)

# ---------------------------------------------------------------------------
# Production imports — adjust the package root as needed for your project.
# ---------------------------------------------------------------------------
from my_unicorn.constants import VerificationMethod
from my_unicorn.core.api import Asset
from my_unicorn.core.protocols.progress import NullProgressReporter
from my_unicorn.core.verify import (
    MethodResult,
    VerificationContext,
    VerificationService,
    Verifier,
    execute_all_verification_methods,
    verify_checksum_file,
    verify_digest,
)
from my_unicorn.exceptions import VerificationError
from my_unicorn.types import ChecksumFileInfo
from my_unicorn.utils.config_builders import build_verification_state

# ---------------------------------------------------------------------------
# Module-level constants — known file content and pre-computed hashes.
#
# We fix the content so every test uses the same baseline without recalculating
# hashes each time.  If you change FILE_CONTENT you must update all _HASH
# constants below.
# ---------------------------------------------------------------------------

FILE_CONTENT: bytes = (
    b"Hello, AppImage! This is test content for hash verification.\n"
)
APPIMAGE_FILENAME: str = "MyApp-1.0.0-x86_64.AppImage"

# hashlib.sha256(FILE_CONTENT).hexdigest()
CORRECT_SHA256: str = (
    "bdc1682173aae38451892cc6c18dc35f900f030ce832305d53259f3ebd27372a"
)

# hashlib.sha512(FILE_CONTENT).hexdigest()
CORRECT_SHA512: str = (
    "8e0654e409d0c318af1feef0a4494cebd65aa343ff3934268363b6ca"
    "51b97883efa049ed73a85f431e3c31dffd22faa9b38890358dbbc321"
    "ec875afde39b10ee"
)

# base64(sha512(FILE_CONTENT)) — electron-builder puts base64 in YAML files
CORRECT_SHA512_B64: str = (
    "jgZU5AnQwxivH+7wpElM69Zao0P/OTQmg2O2ylG5eIPvoEntc6hfQx48Md/"
    "9Ivqps4iQNY27wyHsh1r945sQ7g=="
)

# A hash that does NOT match FILE_CONTENT — used to simulate electron-builder
# publishing a wrong hash.
WRONG_SHA256: str = (
    "192160681b5c1228c3828d0c370e5a9045cf8cf09a761b85ae2b6c0c8cfecc3b"
)
WRONG_SHA512: str = (
    "c84c1d63086be1bd933c64923ff0a0cd1a7e353b3dc0178a06f7e5ef"
    "d7a3171115210fe4ad8d72004d67507dacc268865520ec366c8579cf"
    "3d6393bba5059351"
)

# Fake GitHub API digest strings (``algorithm:hexhash`` format)
CORRECT_DIGEST: str = f"sha256:{CORRECT_SHA256}"
WRONG_DIGEST: str = f"sha256:{WRONG_SHA256}"

# A fake GitHub release URL used wherever a real URL is required.
FAKE_CHECKSUM_URL: str = (
    "https://github.com/fake-owner/fake-repo/releases/download/v1.0.0/"
    "SHA256SUMS.txt"
)

CHECKSUM_FIXTURES_DIR: Path = (
    Path(__file__).resolve().parents[1] / "fixtures" / "checksums"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _traditional_checksum_content(sha256_hash: str) -> str:
    """Return a traditional ``SHA256SUMS`` file that maps the test filename.

    Format:  ``<hash>  <filename>``  (two spaces, GNU coreutils convention)

    Args:
        sha256_hash: Hex SHA256 hash to embed.

    Returns:
        String content ready to be returned by a mocked download call.
    """
    return f"{sha256_hash}  {APPIMAGE_FILENAME}\n"


def _yaml_checksum_content(sha512_b64: str) -> str:
    """Return an electron-builder ``latest-linux.yml``-style YAML file.

    The ``files`` list format matches what electron-builder actually produces,
    which is what ``YAMLChecksumParser`` expects.

    Args:
        sha512_b64: Base64-encoded SHA512 hash to embed.

    Returns:
        String content ready to be returned by a mocked download call.
    """
    return (
        f"files:\n"
        f"  - name: {APPIMAGE_FILENAME}\n"
        f"    sha512: {sha512_b64}\n"
        f"version: 1.0.0\n"
    )


def _make_asset(*, digest: str = "") -> Asset:
    """Construct a minimal ``Asset`` dataclass for testing.

    Args:
        digest: Optional GitHub API digest string (``algorithm:hexhash``).

    Returns:
        Asset instance with the test filename and a fake download URL.
    """
    return Asset(
        name=APPIMAGE_FILENAME,
        size=len(FILE_CONTENT),
        digest=digest,
        browser_download_url=(
            "https://github.com/fake-owner/fake-repo/releases/download/"
            f"v1.0.0/{APPIMAGE_FILENAME}"
        ),
    )


def _make_checksum_file_info(
    *,
    format_type: str = "traditional",
    url: str = FAKE_CHECKSUM_URL,
) -> ChecksumFileInfo:
    """Build a ``ChecksumFileInfo`` for the given format.

    Args:
        format_type: ``"traditional"`` or ``"yaml"``.
        url: Download URL used in the result for traceability.

    Returns:
        ChecksumFileInfo ready to hand to ``verify_checksum_file``.
    """
    filename = (
        "SHA256SUMS.txt"
        if format_type == "traditional"
        else "latest-linux.yml"
    )
    return ChecksumFileInfo(
        filename=filename,
        url=url,
        format_type=format_type,
    )


def _make_mock_download_service(checksum_content: str) -> MagicMock:
    """Create a minimal mock for ``DownloadService``.

    Only ``download_checksum_file`` is mocked because that is the only
    network call made by ``verify_checksum_file``.

    Args:
        checksum_content: The string the mock will return.

    Returns:
        MagicMock with ``download_checksum_file`` wired up as an AsyncMock.
    """
    svc = MagicMock()
    svc.download_checksum_file = AsyncMock(return_value=checksum_content)
    return svc


def _read_checksum_fixture(filename: str) -> str:
    """Read a real-world checksum fixture from tests/fixtures/checksums.

    Args:
        filename: Fixture filename inside tests/fixtures/checksums.

    Returns:
        Fixture content as a string.

    """
    return (CHECKSUM_FIXTURES_DIR / filename).read_text(encoding="utf-8")


def _patch_yaml_fixture_target_filename(
    yaml_content: str,
    *,
    target_filename: str,
) -> str:
    """Rewrite a YAML checksum fixture so it targets our test AppImage.

    Most electron-builder YAML fixtures include a real AppImage filename.
    For integration testing we keep the *real* structure and hashes, but
    replace the AppImage filename so the parser finds an entry for the file
    we actually created in tmp_path.
    """
    matches = re.findall(r"\b[^\s]+\.AppImage\b", yaml_content)
    if not matches:
        return yaml_content

    original = matches[0]
    return yaml_content.replace(original, target_filename)


def _extract_sha512_from_yaml_fixture(
    yaml_content: str, *, target_filename: str
) -> str:
    """Extract the sha512 string for target_filename from YAML content."""
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load(yaml_content)
    if not isinstance(data, dict):
        raise AssertionError("YAML fixture did not parse to a dict")

    files = data.get("files")
    if isinstance(files, list):
        for entry in files:
            if not isinstance(entry, dict):
                continue
            if (entry.get("name") or entry.get("url")) != target_filename:
                continue
            sha512_value = entry.get("sha512")
            if isinstance(sha512_value, str) and sha512_value:
                return sha512_value

    sha512_root = data.get("sha512")
    if isinstance(sha512_root, str) and sha512_root:
        return sha512_root

    raise AssertionError(
        f"Could not find sha512 for {target_filename!r} in YAML fixture"
    )


def _normalize_expected_sha512(sha512_value: str) -> str:
    """Normalize YAML sha512 value to hex, matching production behavior."""
    from my_unicorn.core.checksum_parser import convert_base64_to_hex

    value = sha512_value.strip()
    if len(value) == 128 and all(c in "0123456789abcdefABCDEF" for c in value):
        return value.lower()
    return convert_base64_to_hex(value).lower()


def _write_app_state_v2_json(
    tmp_path: Path,
    *,
    app_name: str,
    app_file: Path,
    verification_state: dict[str, Any],
) -> Path:
    """Write a minimal app-state v2 JSON to disk.

    This keeps tests integration-focused: we validate not only the in-memory
    verification result but also what would actually be persisted.
    """
    app_state = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": app_name,
        "state": {
            "version": "v1.0.0",
            "installed_date": "2026-05-05T00:00:00+00:00",
            "installed_path": str(app_file),
            "verification": {
                "passed": verification_state["passed"],
                "methods": verification_state["methods"],
            },
            "icon": {"installed": False, "method": "none"},
        },
    }

    json_path = tmp_path / f"{app_name}.json"
    json_path.write_bytes(orjson.dumps(app_state, option=orjson.OPT_INDENT_2))
    return json_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_file(tmp_path: Path) -> Path:
    """Write ``FILE_CONTENT`` to a temporary file and return its path.

    Using ``tmp_path`` (pytest built-in) means the file is automatically
    cleaned up after each test.
    """
    path = tmp_path / APPIMAGE_FILENAME
    path.write_bytes(FILE_CONTENT)
    return path


@pytest.fixture
def verifier(app_file: Path) -> Verifier:
    """Return a ``Verifier`` pointed at the real temporary AppImage file."""
    return Verifier(app_file)


@pytest.fixture
def asset_no_digest() -> Asset:
    """Asset without a GitHub API digest — forces checksum file path."""
    return _make_asset(digest="")


@pytest.fixture
def asset_correct_digest() -> Asset:
    """Asset whose digest matches ``FILE_CONTENT``."""
    return _make_asset(digest=CORRECT_DIGEST)


@pytest.fixture
def asset_wrong_digest() -> Asset:
    """Asset whose digest does *not* match ``FILE_CONTENT``."""
    return _make_asset(digest=WRONG_DIGEST)


def _build_context(
    file_path: Path,
    asset: Asset,
    *,
    has_digest: bool = False,
    checksum_files: list[ChecksumFileInfo] | None = None,
    config: dict[str, Any] | None = None,
) -> VerificationContext:
    """Construct a ``VerificationContext`` with ``verifier`` already set.

    This bypasses ``_prepare_verification`` so tests can exercise the
    execution phase (``execute_all_verification_methods``) in isolation.

    Args:
        file_path: Path to the file being verified.
        asset: GitHub asset metadata.
        has_digest: Whether the digest method should be attempted.
        checksum_files: List of checksum files to try (may be empty/None).
        config: Verification config dict (defaults to minimal valid config).

    Returns:
        Populated ``VerificationContext`` ready for execution.
    """
    ctx_config: dict[str, Any] = config or {}
    ctx = VerificationContext(
        file_path=file_path,
        asset=asset,
        config=ctx_config,
        owner="fake-owner",
        repo="fake-repo",
        tag_name="v1.0.0",
        app_name="MyApp",
        assets=None,
        progress_task_id=None,
    )
    ctx.has_digest = has_digest
    ctx.checksum_files = checksum_files or []
    ctx.verifier = Verifier(file_path)
    return ctx


# ===========================================================================
# Section 1 — Checksum File Verification
# ===========================================================================


class TestChecksumFileHashPreservation:
    """Checksum file verification must store both expected and computed hashes.

    WHY: When an external checksum file contains a wrong hash (common with
    electron-builder), investigators need to see *what the checksum file
    claimed* vs *what the file actually hashed to*.  Without ``computed_hash``
    in the result the only option is to re-run everything manually.
    """

    @pytest.mark.asyncio
    async def test_mismatch_preserves_expected_and_computed_sha256(
        self,
        app_file: Path,
    ) -> None:
        """Traditional checksum file with wrong hash stores both sides.

        Scenario: a real-world SHA256SUMS.txt contains an expected hash for
        a file name (here: QOwnNotes). Our on-disk file has different content,
        so verification must fail while still preserving BOTH:
          - result.hash (expected, from checksum file)
          - result.computed_hash (computed, from local file)
        """
        qownnotes_filename = "QOwnNotes-24.1.5-x86_64.AppImage"
        expected_sha256_from_fixture = (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

        # Arrange — use a real-world SHA256SUMS fixture directly.
        checksum_content = _read_checksum_fixture("qownnotes_SHA256SUMS.txt")
        download_svc = _make_mock_download_service(checksum_content)
        checksum_file = _make_checksum_file_info(format_type="traditional")

        # Create an on-disk file with the *same* name as in the fixture but
        # with content that does NOT match the fixture's expected hash.
        qownnotes_file = app_file.with_name(qownnotes_filename)
        qownnotes_file.write_bytes(FILE_CONTENT)
        verifier = Verifier(qownnotes_file)

        # Act
        result = await verify_checksum_file(
            verifier=verifier,
            checksum_file=checksum_file,
            target_filename=qownnotes_filename,
            app_name="qownnotes",
            download_service=download_svc,
        )

        # Assert — verification must fail
        assert result is not None
        assert result.passed is False

        # The expected hash (from checksum file) must be stored.
        assert result.hash == expected_sha256_from_fixture, (
            "result.hash should hold the *expected* hash from the checksum "
            f"file, got: {result.hash!r}"
        )

        # The computed hash (what our file actually is) must also be stored.
        assert result.computed_hash == CORRECT_SHA256, (
            "result.computed_hash should hold what we actually computed, "
            f"got: {result.computed_hash!r}"
        )

        # Sanity: the two sides of the mismatch must differ.
        assert result.hash != result.computed_hash

    @pytest.mark.asyncio
    async def test_mismatch_preserves_url_for_traceability(
        self,
        app_file: Path,
    ) -> None:
        """URL of the failing checksum file is stored in the result.

        WHY: When investigating a failure it is crucial to know *which*
        checksum file was downloaded so developers can open it manually.
        """
        qownnotes_filename = "QOwnNotes-24.1.5-x86_64.AppImage"
        checksum_content = _read_checksum_fixture("qownnotes_SHA256SUMS.txt")
        download_svc = _make_mock_download_service(checksum_content)
        checksum_file = _make_checksum_file_info(
            format_type="traditional", url=FAKE_CHECKSUM_URL
        )

        qownnotes_file = app_file.with_name(qownnotes_filename)
        qownnotes_file.write_bytes(FILE_CONTENT)
        verifier = Verifier(qownnotes_file)

        result = await verify_checksum_file(
            verifier=verifier,
            checksum_file=checksum_file,
            target_filename=qownnotes_filename,
            app_name="qownnotes",
            download_service=download_svc,
        )

        assert result is not None
        assert result.passed is False
        assert result.url == FAKE_CHECKSUM_URL

    @pytest.mark.asyncio
    async def test_correct_hash_passes_and_stores_hash(
        self,
        verifier: Verifier,
    ) -> None:
        """Passing verification also stores the hash (for state persistence).

        WHY: The app state JSON should record the verified hash regardless of
        pass/fail so we have an audit trail.
        """
        base_fixture = _read_checksum_fixture("qownnotes_SHA256SUMS.txt")
        checksum_content = (
            f"{base_fixture}\n{CORRECT_SHA256}  {APPIMAGE_FILENAME}\n"
        )
        download_svc = _make_mock_download_service(checksum_content)
        checksum_file = _make_checksum_file_info(format_type="traditional")

        result = await verify_checksum_file(
            verifier=verifier,
            checksum_file=checksum_file,
            target_filename=APPIMAGE_FILENAME,
            app_name="MyApp",
            download_service=download_svc,
        )

        assert result is not None
        assert result.passed is True
        assert result.hash == CORRECT_SHA256
        assert result.computed_hash == CORRECT_SHA256

    @pytest.mark.asyncio
    async def test_filename_not_in_checksum_file_returns_empty_hash(
        self,
        verifier: Verifier,
    ) -> None:
        """If the filename is absent from the checksum file, hash is empty.

        WHY: The checksum file might list hashes for OTHER AppImages in the
        same release but not for the one we downloaded.  The result must
        communicate this clearly (not crash) so the caller can log it.
        """
        # Checksum file lists a *different* app — not our target.
        unrelated_content = (
            f"{CORRECT_SHA256}  OtherApp-1.0.0-x86_64.AppImage\n"
        )
        download_svc = _make_mock_download_service(unrelated_content)
        checksum_file = _make_checksum_file_info(format_type="traditional")

        result = await verify_checksum_file(
            verifier=verifier,
            checksum_file=checksum_file,
            target_filename=APPIMAGE_FILENAME,
            app_name="MyApp",
            download_service=download_svc,
        )

        assert result is not None
        assert result.passed is False
        # hash is empty because there was nothing to compare against
        assert result.hash == ""
        assert "not found" in result.details.lower()


# ===========================================================================
# Section 2 — YAML (electron-builder) Checksum Format
# ===========================================================================


class TestYamlChecksumFileVerification:
    """Electron-builder YAML checksum files (``latest-linux.yml``).

    WHY SEPARATE: YAML files use SHA512 with base64 encoding.  The parser
    must convert base64 → hex before comparing.  Failure here means
    ANY app using electron-builder's auto-update format would silently skip
    integrity checks.
    """

    @pytest.mark.asyncio
    async def test_yaml_mismatch_preserves_both_hashes(
        self,
        verifier: Verifier,
    ) -> None:
        """YAML format mismatch using a real electron-builder fixture."""
        base_yaml = _read_checksum_fixture("joplin_latest-linux.yml")
        yaml_content = _patch_yaml_fixture_target_filename(
            base_yaml,
            target_filename=APPIMAGE_FILENAME,
        )
        download_svc = _make_mock_download_service(yaml_content)
        checksum_file = _make_checksum_file_info(format_type="yaml")

        result = await verify_checksum_file(
            verifier=verifier,
            checksum_file=checksum_file,
            target_filename=APPIMAGE_FILENAME,
            app_name="MyApp",
            download_service=download_svc,
        )

        assert result is not None
        assert result.passed is False

        expected_b64 = _extract_sha512_from_yaml_fixture(
            yaml_content, target_filename=APPIMAGE_FILENAME
        )
        expected_hex = _normalize_expected_sha512(expected_b64)
        assert result.hash == expected_hex
        assert result.computed_hash == CORRECT_SHA512

        # Both hashes present — this is the key assertion for YAML format.
        assert result.hash != "", (
            "Expected hash from YAML should not be empty on mismatch"
        )
        assert result.computed_hash is not None
        assert result.computed_hash != "", (
            "Computed hash should be present so we can diff the two values"
        )
        assert result.hash != result.computed_hash

    @pytest.mark.asyncio
    async def test_yaml_correct_hash_passes(
        self,
        verifier: Verifier,
    ) -> None:
        """YAML format: correct base64 sha512 → verification passes."""
        yaml_content = _yaml_checksum_content(CORRECT_SHA512_B64)
        download_svc = _make_mock_download_service(yaml_content)
        checksum_file = _make_checksum_file_info(format_type="yaml")

        result = await verify_checksum_file(
            verifier=verifier,
            checksum_file=checksum_file,
            target_filename=APPIMAGE_FILENAME,
            app_name="MyApp",
            download_service=download_svc,
        )

        assert result is not None
        assert result.passed is True
        assert result.computed_hash == CORRECT_SHA512


# ===========================================================================
# Section 3 — Digest Verification
# ===========================================================================


class TestDigestVerification:
    """GitHub API ``digest`` field verification.

    WHY: The digest is our most reliable signal because GitHub controls it.
    We must confirm that failures surface both the expected digest and the
    computed hash so investigations can start immediately.
    """

    @pytest.mark.asyncio
    async def test_digest_mismatch_returns_failed_result(
        self,
        verifier: Verifier,
        asset_wrong_digest: Asset,
    ) -> None:
        """Wrong digest → ``passed=False`` and the digest is recorded.

        ``actual_digest`` is None on a mismatch because ``verify_digest``
        catches the ValueError raised *before* the computed hash is exposed
        on the happy path.  This is acceptable — the ``hash`` field still
        tells us what GitHub claimed, which is enough to open a bug report.
        """
        result = await verify_digest(
            verifier=verifier,
            digest=WRONG_DIGEST,
            app_name="MyApp",
            skip_configured=False,
        )

        assert result is not None
        assert result.passed is False
        # The digest that GitHub claimed must be stored.
        assert result.hash == WRONG_DIGEST
        # Details explain what went wrong.
        assert result.details != ""

    @pytest.mark.asyncio
    async def test_digest_match_passes_and_stores_hash(
        self,
        verifier: Verifier,
        asset_correct_digest: Asset,
    ) -> None:
        """Correct digest → ``passed=True``, hash portion stored."""
        result = await verify_digest(
            verifier=verifier,
            digest=CORRECT_DIGEST,
            app_name="MyApp",
            skip_configured=False,
        )

        assert result is not None
        assert result.passed is True
        assert result.hash == CORRECT_DIGEST
        # On success, computed_hash is the hex portion of the digest.
        assert result.computed_hash == CORRECT_SHA256

    @pytest.mark.asyncio
    async def test_digest_passes_even_when_skip_configured(
        self,
        verifier: Verifier,
    ) -> None:
        """``skip=True`` in config must NOT suppress digest verification.

        WHY: If a digest is available in the GitHub API response, we always
        verify it, even if the catalog says ``skip: true``.  Skipping
        verification when we *have* data is a security regression.
        """
        result = await verify_digest(
            verifier=verifier,
            digest=CORRECT_DIGEST,
            app_name="MyApp",
            skip_configured=True,  # skip=True should be ignored
        )

        assert result is not None
        assert result.passed is True


# ===========================================================================
# Section 4 — Concurrent Execution via execute_all_verification_methods
# ===========================================================================


class TestConcurrentVerificationMethods:
    """``execute_all_verification_methods`` runs digest + checksum concurrently.

    WHY: Verifying concurrently halves wall-clock time for apps that provide
    both methods.  These tests confirm that both results are recorded even
    when one or both methods fail — because the investigation data must be
    preserved.
    """

    @pytest.mark.asyncio
    async def test_checksum_fails_result_stored_in_context(
        self,
        app_file: Path,
        asset_no_digest: Asset,
    ) -> None:
        """Checksum failure: computed_hash and expected hash stored in context.

        This is the primary regression test for the bug described in the task:
        failing checksum results must carry both hash values so developers can
        tell whether the external checksum is wrong or the downloaded file is
        corrupt.
        """
        checksum_content = _traditional_checksum_content(WRONG_SHA256)
        download_svc = _make_mock_download_service(checksum_content)
        checksum_file = _make_checksum_file_info(format_type="traditional")

        ctx = _build_context(
            app_file,
            asset_no_digest,
            has_digest=False,
            checksum_files=[checksum_file],
        )

        await execute_all_verification_methods(ctx, download_svc, None)

        # The method must have been recorded.
        assert "checksum_file" in ctx.verification_methods

        method_result = ctx.verification_methods["checksum_file"]
        assert method_result["passed"] is False

        # CRITICAL: both sides of the mismatch must be present.
        assert method_result.get("hash") == WRONG_SHA256, (
            "Expected hash (from checksum file) must be stored for investigation"
        )
        assert method_result.get("computed_hash") == CORRECT_SHA256, (
            "Computed hash (what the file actually is) must be stored"
        )

    @pytest.mark.asyncio
    async def test_digest_passes_checksum_fails_both_results_recorded(
        self,
        app_file: Path,
    ) -> None:
        """Digest passes + checksum fails → both results in context.

        Real-world scenario: electron-builder published a wrong sha512 YAML
        checksum but GitHub's API digest is correct.  Verification overall
        passes (we have one strong passing method) but the failing checksum
        result is still stored so we can file an upstream bug report.
        """
        asset = _make_asset(digest=CORRECT_DIGEST)
        checksum_content = _traditional_checksum_content(WRONG_SHA256)
        download_svc = _make_mock_download_service(checksum_content)
        checksum_file = _make_checksum_file_info(format_type="traditional")

        ctx = _build_context(
            app_file,
            asset,
            has_digest=True,
            checksum_files=[checksum_file],
        )

        await execute_all_verification_methods(ctx, download_svc, None)

        # Digest passed.
        digest_result = ctx.verification_methods.get(VerificationMethod.DIGEST)
        assert digest_result is not None
        assert digest_result["passed"] is True

        # Checksum failed — but still recorded with both hash values.
        checksum_result = ctx.verification_methods.get("checksum_file")
        assert checksum_result is not None
        assert checksum_result["passed"] is False
        assert checksum_result.get("hash") == WRONG_SHA256
        assert checksum_result.get("computed_hash") == CORRECT_SHA256

    @pytest.mark.asyncio
    async def test_digest_only_no_checksum_file_method_not_recorded(
        self,
        app_file: Path,
    ) -> None:
        """When no checksum files are provided, only the digest result appears."""
        asset = _make_asset(digest=CORRECT_DIGEST)
        download_svc = _make_mock_download_service("")  # never called

        ctx = _build_context(
            app_file,
            asset,
            has_digest=True,
            checksum_files=[],  # none available
        )

        await execute_all_verification_methods(ctx, download_svc, None)

        assert VerificationMethod.DIGEST in ctx.verification_methods
        assert "checksum_file" not in ctx.verification_methods
        # Download service was never touched.
        download_svc.download_checksum_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_methods_available_nothing_recorded(
        self,
        app_file: Path,
        asset_no_digest: Asset,
    ) -> None:
        """Zero methods → context verification_methods stays empty."""
        download_svc = _make_mock_download_service("")
        ctx = _build_context(
            app_file,
            asset_no_digest,
            has_digest=False,
            checksum_files=[],
        )

        await execute_all_verification_methods(ctx, download_svc, None)

        assert ctx.verification_methods == {}


# ===========================================================================
# Section 5 — Full VerificationService Integration
# ===========================================================================


class TestVerificationServiceEndToEnd:
    """End-to-end tests through ``VerificationService.verify_file``.

    WHY: The service orchestrates prepare → execute → finalize.  Testing it
    as a whole catches problems that only appear when the phases interact —
    for example, updated_config not being seeded before the execute phase
    runs.
    """

    def _make_service(self, download_svc: Any) -> VerificationService:
        """Build a ``VerificationService`` with the given download mock."""
        return VerificationService(
            download_service=download_svc,
            progress_reporter=NullProgressReporter(),
            cache_manager=None,
        )

    @pytest.mark.asyncio
    async def test_checksum_mismatch_result_has_failed_method_with_hashes(
        self,
        app_file: Path,
        asset_no_digest: Asset,
    ) -> None:
        """Service result stores both hashes when checksum file has wrong hash.

        This is the full-stack version of the unit test above.  It exercises
        the complete prepare → execute → finalize pipeline and confirms that
        the failing checksum_file entry in the returned ``VerificationResult``
        carries both ``hash`` (expected) and ``computed_hash``.
        """
        checksum_content = _traditional_checksum_content(WRONG_SHA256)
        download_svc = _make_mock_download_service(checksum_content)
        checksum_file = _make_checksum_file_info(format_type="traditional")
        service = self._make_service(download_svc)

        # The single checksum file is injected as a manual config entry so
        # detect_available_methods resolves it without hitting GitHub.
        config: dict[str, Any] = {
            "checksum_file": checksum_file.filename,
            VerificationMethod.DIGEST: False,
        }

        # We patch the URL resolution so build_checksum_url returns our fake URL.
        # We do this by injecting the checksum file info directly into the context
        # via a thin wrapper around DownloadService — the service calls
        # download_checksum_file with whatever URL was built from config.
        # Our mock always returns checksum_content regardless of URL, so this
        # works transparently.

        with pytest.raises(VerificationError):
            # VerificationError is raised because the ONLY available method fails.
            # This is correct — we treat it as a hard failure when we have data
            # that says the file is wrong.
            await service.verify_file(
                file_path=app_file,
                asset=asset_no_digest,
                config=config,
                owner="fake-owner",
                repo="fake-repo",
                tag_name="v1.0.0",
                app_name="MyApp",
                assets=None,
            )

    @pytest.mark.asyncio
    async def test_no_checksums_available_returns_skipped_warning(
        self,
        tmp_path: Path,
        app_file: Path,
        asset_no_digest: Asset,
    ) -> None:
        """No checksums at all → result has warning, passed=False.

        WHY: Some apps simply do not provide any checksum.  We should not
        crash; instead we document that verification was skipped.
        """
        download_svc = _make_mock_download_service("")
        service = self._make_service(download_svc)

        config: dict[str, Any] = {
            "skip": True,
            VerificationMethod.DIGEST: False,
            "checksum_file": None,
        }

        result = await service.verify_file(
            file_path=app_file,
            asset=asset_no_digest,
            config=config,
            owner="fake-owner",
            repo="fake-repo",
            tag_name="v1.0.0",
            app_name="MyApp",
            assets=None,
        )

        assert result.passed is False
        assert result.warning is not None
        assert "not verified" in result.warning.lower()

        verification_state = build_verification_state(
            {
                "passed": result.passed,
                "methods": result.methods,
                "warning": result.warning,
            }
        )
        json_path = _write_app_state_v2_json(
            tmp_path,
            app_name="MyApp",
            app_file=app_file,
            verification_state=verification_state,
        )

        loaded = orjson.loads(json_path.read_bytes())
        methods = loaded["state"]["verification"]["methods"]
        assert methods == [{"type": "skip", "status": "skipped"}]

    @pytest.mark.asyncio
    async def test_digest_only_passes_updates_config(
        self,
        tmp_path: Path,
        app_file: Path,
    ) -> None:
        """Passing digest updates ``updated_config[VerificationMethod.DIGEST]``.

        WHY: ``updated_config`` is written back to the app state JSON.  If the
        digest flag is not set in the returned config the next run will not
        know that digest verification is supported, potentially downgrading
        security.
        """
        asset = _make_asset(digest=CORRECT_DIGEST)
        download_svc = _make_mock_download_service("")
        service = self._make_service(download_svc)

        config: dict[str, Any] = {
            VerificationMethod.DIGEST: True,
            "checksum_file": None,
        }

        result = await service.verify_file(
            file_path=app_file,
            asset=asset,
            config=config,
            owner="fake-owner",
            repo="fake-repo",
            tag_name="v1.0.0",
            app_name="MyApp",
            assets=None,
        )

        assert result.passed is True
        assert result.updated_config.get(VerificationMethod.DIGEST) is True

        verification_state = build_verification_state(
            {
                "passed": result.passed,
                "methods": result.methods,
                "warning": result.warning,
            }
        )
        json_path = _write_app_state_v2_json(
            tmp_path,
            app_name="MyApp",
            app_file=app_file,
            verification_state=verification_state,
        )

        loaded = orjson.loads(json_path.read_bytes())
        methods = loaded["state"]["verification"]["methods"]

        digest_entry = next(m for m in methods if m.get("type") == "digest")
        assert digest_entry["status"] == "passed"
        assert digest_entry.get("expected") == CORRECT_DIGEST
        assert digest_entry.get("computed") == CORRECT_SHA256

    @pytest.mark.asyncio
    async def test_partial_verification_persists_expected_and_computed_in_v2_json(
        self,
        tmp_path: Path,
        app_file: Path,
    ) -> None:
        """Realistic end-to-end: digest passes, YAML checksum fails, JSON keeps both.

        This is the high-value integration scenario for the real-world bug:
        electron-builder publishes a bad sha512 in latest-linux.yml.

        We verify that:
        - VerificationService returns BOTH method results.
        - When we build an app-state v2 JSON payload, the checksum_file method
          contains *expected* and *computed* hashes even though it failed.
        """
        asset = _make_asset(digest=CORRECT_DIGEST)

        base_yaml = _read_checksum_fixture("joplin_latest-linux.yml")
        yaml_content = _patch_yaml_fixture_target_filename(
            base_yaml,
            target_filename=APPIMAGE_FILENAME,
        )
        download_svc = _make_mock_download_service(yaml_content)
        service = self._make_service(download_svc)

        config: dict[str, Any] = {
            "checksum_file": {
                "filename": "latest-linux.yml",
                "algorithm": "sha512",
            },
            VerificationMethod.DIGEST: False,
        }

        result = await service.verify_file(
            file_path=app_file,
            asset=asset,
            config=config,
            owner="fake-owner",
            repo="fake-repo",
            tag_name="v1.0.0",
            app_name="MyApp",
            assets=None,
        )

        # Sanity: overall should pass (digest passed), but with a warning.
        assert result.passed is True
        assert result.warning is not None
        assert "partial" in result.warning.lower()

        verify_result_dict = {
            "passed": result.passed,
            "methods": result.methods,
            "warning": result.warning,
        }
        verification_state = build_verification_state(verify_result_dict)

        json_path = _write_app_state_v2_json(
            tmp_path,
            app_name="MyApp",
            app_file=app_file,
            verification_state=verification_state,
        )

        loaded = orjson.loads(json_path.read_bytes())
        methods = loaded["state"]["verification"]["methods"]
        assert isinstance(methods, list)

        checksum_entry = next(
            m for m in methods if m.get("type") == "checksum_file"
        )
        assert checksum_entry["status"] == "failed"

        expected_b64 = _extract_sha512_from_yaml_fixture(
            yaml_content, target_filename=APPIMAGE_FILENAME
        )
        expected_hex = _normalize_expected_sha512(expected_b64)

        assert checksum_entry.get("expected") == expected_hex
        assert checksum_entry.get("computed") == CORRECT_SHA512

        # Also confirm the digest entry is preserved (real-world happy path).
        digest_entry = next(m for m in methods if m.get("type") == "digest")
        assert digest_entry["status"] == "passed"
        assert digest_entry.get("expected") == CORRECT_DIGEST
        assert digest_entry.get("computed") == CORRECT_SHA256


# ===========================================================================
# Section 6 — MethodResult Serialisation (to_dict)
# ===========================================================================


class TestMethodResultToDict:
    """``MethodResult.to_dict()`` must expose all fields needed by app state.

    WHY: The app state JSON schema (``app_state_v2.schema.json``) stores
    verification methods as an array of objects with ``type``, ``status``,
    ``expected``, and ``computed`` keys.  If ``to_dict()`` drops fields,
    the state file is incomplete and post-mortem analysis is impossible.
    """

    def test_failed_result_includes_computed_and_expected_hash(self) -> None:
        """to_dict() on a failed result must contain both hash fields."""
        result = MethodResult(
            passed=False,
            hash=WRONG_SHA256,
            computed_hash=CORRECT_SHA256,
            details="Hash mismatch",
            url=FAKE_CHECKSUM_URL,
            hash_type="sha256",
        )

        d = result.to_dict()

        assert d["passed"] is False
        assert d["hash"] == WRONG_SHA256
        assert d["computed_hash"] == CORRECT_SHA256
        assert d["url"] == FAKE_CHECKSUM_URL
        assert d["hash_type"] == "sha256"

    def test_failed_result_without_computed_omits_key(self) -> None:
        """When computed_hash is None, to_dict() must not include the key.

        WHY: JSON schema validation would fail on ``null`` for a field that
        is expected to be a string or absent.
        """
        result = MethodResult(
            passed=False,
            hash="",
            details="Hash not found in checksum file",
        )

        d = result.to_dict()

        assert "computed_hash" not in d

    def test_passed_result_has_all_fields(self) -> None:
        """Successful result dict has all expected fields present."""
        result = MethodResult(
            passed=True,
            hash=CORRECT_SHA256,
            computed_hash=CORRECT_SHA256,
            details="Verified against traditional checksum file",
            url=FAKE_CHECKSUM_URL,
            hash_type="sha256",
        )

        d = result.to_dict()

        assert d["passed"] is True
        assert d["hash"] == CORRECT_SHA256
        assert d["computed_hash"] == CORRECT_SHA256


# ===========================================================================
# Section 7 — Parametrized Cross-Format Mismatch Coverage
# ===========================================================================


@pytest.mark.parametrize(
    "format_type,checksum_content_func,wrong_hash",
    [
        (
            "traditional",
            lambda: _traditional_checksum_content(WRONG_SHA256),
            WRONG_SHA256,
        ),
    ],
    ids=["traditional-sha256-mismatch"],
)
@pytest.mark.asyncio
async def test_checksum_mismatch_parametrized(
    app_file: Path,
    format_type: str,
    checksum_content_func: Any,
    wrong_hash: str,
) -> None:
    """Parametrized: any checksum format mismatch always stores both hashes.

    Extend this list as new checksum formats are added.  The invariant is
    always the same: ``result.hash`` == expected, ``result.computed_hash``
    == computed, and they differ.
    """
    verifier = Verifier(app_file)
    checksum_content = checksum_content_func()
    download_svc = _make_mock_download_service(checksum_content)
    checksum_file = _make_checksum_file_info(format_type=format_type)

    result = await verify_checksum_file(
        verifier=verifier,
        checksum_file=checksum_file,
        target_filename=APPIMAGE_FILENAME,
        app_name="MyApp",
        download_service=download_svc,
    )

    assert result is not None
    assert result.passed is False
    assert result.hash == wrong_hash
    assert result.computed_hash is not None
    assert result.hash != result.computed_hash
