import os
import sys
import logging
import requests
from tqdm import tqdm
from .api import GitHubAPI


class DownloadManager:
    """Manages the downloading of the app image."""

    def __init__(self, api: GitHubAPI):
        self.api = api
        self.appimage_name = None

    # TODO: we need a logic to check is .json file exists or
    # not for the appimage and even are the values are not empty -e.g owner, repo -

    def is_app_exist(self):
        """Check if the AppImage already exists in the current directory."""
        if not self.api.appimage_name:
            print("AppImage name is not set.")
            return False

        if os.path.exists(self.api.appimage_name):
            print(f"{self.api.appimage_name} already exists in the current directory")
            return True
        return False

    def download(self):
        """Download the appimage from the github api."""
        if self.is_app_exist():
            # If the file exists, do not proceed with the download
            return

        print(
            f"{self.api.appimage_name} downloading... Grab a cup of coffee :), it will take some time depending on your internet speed."
        )

        try:
            response = requests.get(self.api.appimage_url, stream=True, timeout=10)
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching data from GitHub API: {e}")
            return None

        total_size_in_bytes = int(response.headers.get("content-length", 0))

        if response.status_code == 200:
            with open(f"{self.api.appimage_name}", "wb") as file, tqdm(
                desc=self.api.appimage_name,
                total=total_size_in_bytes,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
                miniters=1,
            ) as progress_bar:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
                    file.flush()  # Force write to disk
                    progress_bar.update(len(chunk))
        else:
            print(f"Error downloading {self.api.appimage_name}")
            logging.error(f"Error downloading {self.api.appimage_url}")
            sys.exit()

        if response is not None:
            response.close()
            print(f"Download completed! {self.api.appimage_name} installed.")
        else:
            print(f"Error downloading {self.api.appimage_name}")
