from dataclasses import dataclass


@dataclass
class ParseURL:
    """Handles user inputs and repository information."""

    url: str
    owner: str
    repo: str

    def ask_url(self):
        """Ask user for input and update owner/repo."""
        self.url = input("Enter the GitHub URL: ").strip()
        if self.url:
            self.validate_url()
            self.parse_owner_repo()

    def validate_url(self):
        """Validate the GitHub URL format."""
        if not self.url.startswith("https://github.com/"):
            raise ValueError("Invalid GitHub URL format. Must start with 'https://github.com/'.")

    def parse_owner_repo(self):
        """Parse owner and repository from GitHub URL."""
        if not self.url:
            raise ValueError("URL is not set. Please provide a valid GitHub URL.")

        parts = self.url.split("/")
        if len(parts) >= 5:
            self.owner = parts[3]
            self.repo = parts[4]
            return self.owner, self.repo
        else:
            raise ValueError("Invalid GitHub URL. Unable to parse owner and repository.")

    @property
    def get_owner(self) -> str:
        """Return the owner from URL."""
        if not self.owner:
            raise ValueError("Owner not set. Please call 'ask_url()' first.")
        return self.owner

    @property
    def get_repo(self) -> str:
        """Return the repo from URL."""
        if not self.repo:
            raise ValueError("Repo not set. Please call 'ask_url()' first.")
        return self.repo
