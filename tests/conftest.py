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
