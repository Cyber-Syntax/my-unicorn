"""Constants for the API module."""

from typing import Final

DEFAULT_TIMEOUT: Final[int] = 30
DEFAULT_PER_PAGE: Final[int] = 100
APPIMAGE_EXTENSION: Final[str] = ".appimage"
SHA_TYPE_OPTIONS: Final[list[str]] = ["sha256", "sha512"]

# HTTP Status Codes
HTTP_OK = 200
HTTP_NOT_FOUND = 404
HTTP_FORBIDDEN = 403
HTTP_RATE_LIMIT: Final[int] = 429

# Request parameters
MAX_RETRIES: Final[int] = 3
RETRY_DELAY: Final[int] = 2

### SHA asset constants
SHA_EXTENSIONS: Final[tuple[str, str]] = (".sha256", ".sha512")
PLATFORM_INDICATORS = ["mac", "windows", "win"]
PYTEST_ENV_VAR = "PYTEST_CURRENT_TEST"
