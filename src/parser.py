from dataclasses import dataclass


@dataclass
class ParseURL:
    """Handles user inputs and repository information."""

    url: str = None
    _owner: str = None
    _repo: str = None

    def ask_url(self):
        """Ask user for input and update owner/repo."""
        self.url = input("Enter github url: ")
        self._validate_url()
        self._parse_owner_repo()

    def _validate_url(self):
        """Validate the GitHub URL format."""
        if not self.url.startswith("https://github.com/"):
            raise ValueError("Invalid GitHub URL format.")

    def _parse_owner_repo(self):
        """Parse owner repo from github url"""
        if self.url:
            self._owner = self.url.split("/")[3]
            self._repo = self.url.split("/")[4]

    @property
    def owner(self):
        """Return the owner from URL."""
        return self._owner

    @property
    def repo(self):
        """Return the repo from URL."""
        return self._repo
