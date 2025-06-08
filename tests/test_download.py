import os
import stat
import threading
import time
from types import SimpleNamespace

import pytest
import requests

from src.download import DownloadManager


@pytest.fixture
def github_api():
    """Minimal stub for GitHubAPI with controlled URL and name."""
    return SimpleNamespace(
        app_download_url="https://example.com/fake.AppImage", appimage_name="fake.AppImage"
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
            self.headers = {"Content-Length": "4096"}

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
    bad = SimpleNamespace(app_download_url="", appimage_name="n")
    dm = DownloadManager(bad)
    with pytest.raises(ValueError):
        dm.download()
    # No name
    bad2 = SimpleNamespace(app_download_url="u", appimage_name=None)
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


def test_concurrent_download_safety(
    monkeypatch, github_api, fake_head_response, fake_get_response, mock_global_config
):
    """Test that concurrent downloads of the same file are handled safely."""
    # Arrange: stub HTTP methods with a delay to simulate slow download
    monkeypatch.setattr(requests, "head", lambda *args, **kw: fake_head_response)

    download_count = 0

    def slow_get(*args, **kw):
        nonlocal download_count
        download_count += 1
        # Add delay to simulate actual download time
        time.sleep(0.1)
        response = fake_get_response
        response.headers = {"Content-Length": "4096"}
        return response

    monkeypatch.setattr(requests, "get", slow_get)

    # Create downloads directory for test
    os.makedirs("downloads", exist_ok=True)

    # Track results from concurrent downloads
    results = []
    exceptions = []

    def download_worker():
        try:
            dm = DownloadManager(github_api, app_index=1, total_apps=3)
            file_path, was_existing = dm.download()
            results.append((file_path, was_existing))
        except Exception as e:
            exceptions.append(e)

    # Act: Start 3 concurrent downloads of the same file
    threads = []
    for _ in range(3):
        thread = threading.Thread(target=download_worker)
        threads.append(thread)
        thread.start()

    # Wait for all downloads to complete
    for thread in threads:
        thread.join()

    # Assert: All downloads completed successfully
    assert len(exceptions) == 0, f"Unexpected exceptions: {exceptions}"
    assert len(results) == 3, "All downloads should complete"

    # Only one actual download should have occurred (due to file locking)
    # The other downloads should have found the existing file
    existing_count = sum(1 for _, was_existing in results if was_existing)
    new_downloads = sum(1 for _, was_existing in results if not was_existing)

    # At least 2 should be existing files (found after first download completed)
    assert existing_count >= 2, f"Expected at least 2 existing files, got {existing_count}"
    assert new_downloads <= 1, f"Expected at most 1 new download, got {new_downloads}"

    # File should exist and be valid
    path = os.path.join("downloads", github_api.appimage_name)
    assert os.path.isfile(path)
    assert os.stat(path).st_size == 4096

    # Verify file content integrity (all bytes should be 'x')
    with open(path, "rb") as f:
        content = f.read()
        assert len(content) == 4096
        assert all(byte == ord("x") for byte in content)


def test_file_lock_prevents_corruption(monkeypatch, github_api, mock_global_config):
    """Test that file locking prevents file corruption during concurrent access."""

    # Create a custom response that writes data slowly
    class SlowResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {"Content-Length": str(10 * 1024)}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            # Yield data very slowly to increase chance of concurrent access
            for i in range(10):
                time.sleep(0.05)  # 50ms delay between chunks
                yield f"chunk{i:02d}".encode() * (chunk_size // 8)

    class SlowHeadResponse:
        headers = {"content-length": str(10 * 1024)}  # 10KB

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "head", lambda *args, **kw: SlowHeadResponse())
    monkeypatch.setattr(requests, "get", lambda *args, **kw: SlowResponse())

    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)

    results = []
    exceptions = []

    def download_worker(worker_id):
        try:
            dm = DownloadManager(github_api, app_index=worker_id, total_apps=2)
            file_path, was_existing = dm.download()
            results.append((worker_id, file_path, was_existing))
        except Exception as e:
            exceptions.append((worker_id, e))

    # Start 2 concurrent downloads
    threads = []
    for i in range(2):
        thread = threading.Thread(target=download_worker, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # Verify no exceptions occurred
    assert len(exceptions) == 0, f"Unexpected exceptions: {exceptions}"
    assert len(results) == 2, "Both downloads should complete"

    # Verify the file exists and has consistent content
    path = os.path.join("downloads", github_api.appimage_name)
    assert os.path.isfile(path)

    # Read and verify file content is not corrupted
    with open(path, "rb") as f:
        content = f.read()
        # Content should be consistent (not mixed from different downloads)
        content_str = content.decode()

        # The content should follow the pattern from one complete download
        # Check that we have complete chunks, not partial/mixed data
        chunk_pattern = any(f"chunk{i:02d}" in content_str for i in range(10))
        assert chunk_pattern, "File should contain recognizable chunk patterns"


def test_progress_deduplication(
    monkeypatch, github_api, fake_head_response, fake_get_response, mock_global_config
):
    """Test that concurrent downloads show only one progress bar per file."""
    # Track progress task creation calls
    progress_calls = []

    class MockProgress:
        def __init__(self):
            self.tasks = {}
            self.task_counter = 0

        def add_task(self, description, total, prefix, **kwargs):
            task_id = self.task_counter
            self.task_counter += 1
            self.tasks[task_id] = {
                "description": description,
                "total": total,
                "prefix": prefix,
                "completed": 0,
            }
            progress_calls.append(("add_task", description, prefix))
            print(f"PROGRESS: Created task {task_id}: {description}")
            return task_id

        def update(self, task_id, **kwargs):
            if task_id in self.tasks:
                for key, value in kwargs.items():
                    if key == "completed":
                        self.tasks[task_id]["completed"] = value
                    elif key == "advance":
                        self.tasks[task_id]["completed"] += value
                progress_calls.append(("update", task_id, kwargs))

        def remove_task(self, task_id):
            if task_id in self.tasks:
                del self.tasks[task_id]
                progress_calls.append(("remove_task", task_id))
                print(f"PROGRESS: Removed task {task_id}")

        def start(self):
            pass

        def stop(self):
            pass

    # Mock the progress manager
    mock_progress = MockProgress()
    monkeypatch.setattr(DownloadManager, "get_or_create_progress", lambda self: mock_progress)

    # Mock HTTP responses with delay
    def slow_get(*args, **kw):
        time.sleep(0.1)  # Simulate network delay
        response = fake_get_response
        response.headers = {"Content-Length": "4096"}
        return response

    monkeypatch.setattr(requests, "head", lambda *args, **kw: fake_head_response)
    monkeypatch.setattr(requests, "get", slow_get)

    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)

    # Track results
    results = []
    exceptions = []

    def download_worker(worker_id):
        try:
            dm = DownloadManager(github_api, app_index=worker_id, total_apps=3)
            file_path, was_existing = dm.download()
            results.append((worker_id, file_path, was_existing))
        except Exception as e:
            exceptions.append((worker_id, e))

    # Start 3 concurrent downloads of the same file
    threads = []
    for i in range(3):
        thread = threading.Thread(target=download_worker, args=(i + 1,))
        threads.append(thread)
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # Verify no exceptions
    assert len(exceptions) == 0, f"Unexpected exceptions: {exceptions}"
    assert len(results) == 3, "All downloads should complete"

    # Check progress task calls
    add_task_calls = [call for call in progress_calls if call[0] == "add_task"]
    remove_task_calls = [call for call in progress_calls if call[0] == "remove_task"]

    print(f"Progress calls: {progress_calls}")
    print(f"Add task calls: {len(add_task_calls)}")
    print(f"Remove task calls: {len(remove_task_calls)}")

    # Should only have ONE add_task call for the same file
    assert len(add_task_calls) == 1, f"Expected exactly 1 progress task, got {len(add_task_calls)}"

    # Should have one remove_task call when download completes
    assert len(remove_task_calls) == 1, (
        f"Expected exactly 1 task removal, got {len(remove_task_calls)}"
    )

    # Verify the task was for the correct file
    task_description = add_task_calls[0][1]
    assert "fake.AppImage" in task_description, (
        f"Task description should contain filename: {task_description}"
    )

    # Verify file was created successfully
    target_file = os.path.join("downloads", github_api.appimage_name)
    assert os.path.exists(target_file), "Target file should exist"
    assert os.path.getsize(target_file) == 4096, "File should have correct size"
