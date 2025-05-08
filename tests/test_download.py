import os
import stat
from types import SimpleNamespace

import pytest
import requests

from src.download import DownloadManager


@pytest.fixture
def github_api():
    """Minimal stub for GitHubAPI with controlled URL and name."""
    return SimpleNamespace(
        appimage_url="https://example.com/fake.AppImage", appimage_name="fake.AppImage"
    )


@pytest.fixture
def mock_global_config(monkeypatch):
    """Create a mock GlobalConfigManager that uses the 'downloads' directory."""

    class MockGlobalConfig:
        @property
        def expanded_app_download_path(self):
            return "downloads"

    # Mock the GlobalConfigManager class and its expanded_app_download_path property
    monkeypatch.setattr(DownloadManager, "_global_config", MockGlobalConfig())
    return MockGlobalConfig()


@pytest.fixture(autouse=True)
def isolate_download_dir(tmp_path, monkeypatch):
    """Change CWD to a tmp_path so that 'downloads/' is created in an isolated temp directory."""
    downloads_dir = tmp_path / "downloads"

    # Create the downloads directory
    downloads_dir.mkdir(exist_ok=True)

    # Change to the temp directory for the duration of the test
    monkeypatch.chdir(tmp_path)

    yield

    # Explicit cleanup after test completes or fails
    if downloads_dir.exists():
        # Remove all files in the downloads directory
        for file_path in downloads_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()


@pytest.fixture
def fake_head_response():
    """A fake Response for requests.head with a content-length header."""

    class Resp:
        headers = {"content-length": "4096"}

        def raise_for_status(self):
            pass

    return Resp()


@pytest.fixture
def fake_get_response():
    """A fake Response for requests.get() with .iter_content()."""

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            # yield four 1 KiB chunks
            for _ in range(4):
                yield b"x" * 1024

    return Resp()


def test_successful_download(
    monkeypatch, github_api, fake_head_response, fake_get_response, mock_global_config
):
    # Arrange: stub HTTP methods
    monkeypatch.setattr(requests, "head", lambda *args, **kw: fake_head_response)
    monkeypatch.setattr(requests, "get", lambda *args, **kw: fake_get_response)

    # Create downloads directory for test
    os.makedirs("downloads", exist_ok=True)

    # Act
    dm = DownloadManager(github_api, app_index=1, total_apps=1)
    dm.download()

    # Assert: file exists in downloads/ with correct size and is executable
    path = os.path.join("downloads", github_api.appimage_name)
    assert os.path.isfile(path)
    assert os.stat(path).st_size == 4096
    # executable bit set
    mode = os.stat(path).st_mode
    assert bool(mode & stat.S_IXUSR)


def test_missing_url_or_name_raises(github_api, monkeypatch):
    # No URL
    bad = SimpleNamespace(appimage_url="", appimage_name="n")
    dm = DownloadManager(bad)
    with pytest.raises(ValueError):
        dm.download()
    # No name
    bad2 = SimpleNamespace(appimage_url="u", appimage_name=None)
    dm2 = DownloadManager(bad2)
    with pytest.raises(ValueError):
        dm2.download()


def test_head_network_error(monkeypatch, github_api, fake_get_response):
    # Simulate head() raising a RequestException
    def bad_head(*args, **kw):
        raise requests.exceptions.RequestException("fail head")

    monkeypatch.setattr(requests, "head", bad_head)
    dm = DownloadManager(github_api)
    with pytest.raises(RuntimeError) as exc:
        dm.download()
    assert "Network error" in str(exc.value)


def test_get_network_error(monkeypatch, github_api, fake_head_response):
    # head succeeds
    monkeypatch.setattr(requests, "head", lambda *a, **k: fake_head_response)

    # get() raises
    def bad_get(*args, **kw):
        raise requests.exceptions.RequestException("fail get")

    monkeypatch.setattr(requests, "get", bad_get)

    dm = DownloadManager(github_api)
    with pytest.raises(RuntimeError) as exc:
        dm.download()
    assert "Network error" in str(exc.value)


def test_progress_cleanup(
    monkeypatch, github_api, fake_head_response, fake_get_response, mock_global_config
):
    # Spy on progress to ensure remove_task is called
    calls = {}

    class FakeProgress:
        def __init__(self):
            pass

        def start(self):
            pass

        def add_task(self, desc, total, prefix, **kw):
            calls["added"] = True
            return 42

        def update(self, *a, **k):
            calls.setdefault("updates", 0)
            calls["updates"] += 1

        def remove_task(self, task_id):
            calls["removed"] = task_id

        def stop(self):
            pass

    monkeypatch.setattr(
        DownloadManager, "get_or_create_progress", classmethod(lambda cls: FakeProgress())
    )
    monkeypatch.setattr(requests, "head", lambda *a, **k: fake_head_response)
    monkeypatch.setattr(requests, "get", lambda *a, **k: fake_get_response)

    # Create downloads directory for test
    os.makedirs("downloads", exist_ok=True)

    dm = DownloadManager(github_api)
    dm.download()

    assert calls.get("added") is True
    assert calls.get("updates", 0) >= 1
    assert calls.get("removed") == 42
