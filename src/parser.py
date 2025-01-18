from dataclasses import dataclass
from src.decorators import handle_common_errors


@dataclass
class InputHandler:
    """Handles user inputs and repository information."""

    url: str = None
    owner: str = None
    repo: str = None

    def ask_url(self):
        """Ask user for input and update owner/repo."""
        self.url = input("Enter github url: ")

    @handle_common_errors
    def parse_owner_repo(self):
        """Parse owner repo from github url"""
        while True:
            print(_("Parsing the owner and repo from the url..."))
            self.owner = self.url.split("/")[3]
            self.repo = self.url.split("/")[4]
            self.url = f"https://github.com/{self.owner}/{self.repo}"
            break
