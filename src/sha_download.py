import os
import requests


class SHAFileManager:
    """Handles downloading and managing the SHA file."""

    def __init__(self, sha_url: str, sha_name: str):
        self.sha_url = sha_url
        self.sha_name = sha_name

    def download_sha(self):
        """Download the SHA file from the given URL."""
        response = requests.get(self.sha_url, timeout=10)
        if response.status_code == 200:
            self.save_sha(response)
        else:
            print(f"Error: Unable to download SHA file from {self.sha_url}")
            response.close()
            return None
        return response

    def save_sha(self, response):
        """Save the SHA file to disk."""
        if not os.path.exists(self.sha_name):
            with open(self.sha_name, "w", encoding="utf-8") as file:
                file.write(response.text)
            print(f"Downloaded {self.sha_name}")
        else:
            print(f"{self.sha_name} already exists.")
            with open(self.sha_name, "r", encoding="utf-8") as file:
                if response.text != file.read():
                    self.handle_sha_mismatch(response)
                else:
                    print(f"{self.sha_name} is up to date.")

    def handle_sha_mismatch(self, response):
        """Handle SHA mismatch if the file already exists."""
        print(f"{self.sha_name} exists but is different from the downloaded one.")
        if input("Overwrite SHA file? (y/n): ").lower() == "y":
            with open(self.sha_name, "w", encoding="utf-8") as file:
                file.write(response.text)
            print(f"SHA file {self.sha_name} overwritten.")
        else:
            print("SHA file not overwritten.")
