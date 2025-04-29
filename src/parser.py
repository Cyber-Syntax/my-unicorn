from dataclasses import dataclass


@dataclass
class ParseURL:
    """Handles user inputs and repository information."""

    url: str = None
    _owner: str = None
    _repo: str = None

    def ask_url(self):
        """Ask user for input and update owner/repo."""
        self.url = input("Enter the GitHub URL: ").strip()
        if self.url:
            self._validate_url()
            self._parse_owner_repo()

    def _validate_url(self):
        """Validate the GitHub URL format."""
        if not self.url.startswith("https://github.com/"):
            raise ValueError("Invalid GitHub URL format. Must start with 'https://github.com/'.")

    def _parse_owner_repo(self):
        """Parse owner and repository from GitHub URL."""
        if not self.url:
            raise ValueError("URL is not set. Please provide a valid GitHub URL.")

        parts = self.url.split("/")
        if len(parts) >= 5:
            self._owner = parts[3]
            self._repo = parts[4]
            return self._owner, self._repo
        else:
            raise ValueError("Invalid GitHub URL. Unable to parse owner and repository.")

    @property
    def owner(self) -> str:
        """Return the owner from URL."""
        if not self._owner:
            raise ValueError("Owner not set. Please call 'ask_url()' first.")
        return self._owner

    @property
    def repo(self) -> str:
        """Return the repo from URL."""
        if not self._repo:
            raise ValueError("Repo not set. Please call 'ask_url()' first.")
        return self._repo
