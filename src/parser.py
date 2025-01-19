from dataclasses import dataclass
from src.decorators import handle_common_errors


@dataclass
class ParseURL:
    """Handles user inputs and repository information."""

    # TODO: setting up property for the owner and repo ?
    # or just use parent child inheritance and after that just use configManager to load for other classes.
    # need to decrease rely on the different classes or decide to use inharitance or property etc.
    url: str = None
    owner: str = None
    repo: str = None

    def ask_url(self):
        """Ask user for input and update owner/repo."""
        self.url = input("Enter github url: ")

    def __post_init__(self):
        """Initialize owner and repo after URL is set."""
        if self.url:
            self.parse_owner_repo()

    @handle_common_errors
    def parse_owner_repo(self):
        """Parse owner repo from github url"""
        while True:
            print(_("Parsing the owner and repo from the url..."))
            self.owner = self.url.split("/")[3]
            self.repo = self.url.split("/")[4]
            self.url = f"https://github.com/{self.owner}/{self.repo}"
            break
