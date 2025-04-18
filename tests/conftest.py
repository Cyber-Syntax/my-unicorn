import pytest
import requests_mock
from httmock import HTTMock, all_requests


@pytest.fixture
def mock_requests_get():
    with requests_mock.Mocker() as m:
        yield m


@pytest.fixture
def httmock():
    @all_requests
    def response_content(url, request):
        return {"status_code": 200, "content": "mocked response"}

    with HTTMock(response_content):
        yield


# New fixtures for secure token and auth tests
@pytest.fixture
def mock_keyring_config():
    """Return a configuration for basic keyring testing."""
    return {
        "keyring_module_installed": True,
        "any_keyring_available": True,
        "gnome_keyring_available": True,
        "kde_wallet_available": False,
        "crypto_available": True,
    }


@pytest.fixture
def token_metadata():
    """Return sample token metadata for testing."""
    from datetime import datetime, timedelta

    now = datetime.now()
    return {
        "created_at": now.timestamp(),
        "expires_at": (now + timedelta(days=30)).timestamp(),
        "last_used_at": now.timestamp(),
        "storage_method": "Encrypted file",
        "storage_location": "keyring",
        "storage_status": "active",
    }


@pytest.fixture
def github_rate_limit_response():
    """Return a sample GitHub API rate limit response."""
    import time

    reset_time = int(time.time()) + 3600  # 1 hour from now

    return {
        "resources": {
            "core": {"limit": 5000, "remaining": 4990, "reset": reset_time, "used": 10},
            "search": {"limit": 30, "remaining": 28, "reset": reset_time, "used": 2},
            "graphql": {"limit": 5000, "remaining": 4999, "reset": reset_time, "used": 1},
        },
        "rate": {"limit": 5000, "remaining": 4990, "reset": reset_time, "used": 10},
    }
