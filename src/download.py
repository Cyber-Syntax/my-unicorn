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

    def download(self):
        """Download the appimage from the github api."""
        if os.path.exists(self.api.appimage_name) or os.path.exists(
            self.api.appimage_name + ".AppImage"
        ):
            print(f"{self.api.appimage_name} already exists in the current directory")
            return

        print(
            f"{self.api.appimage_name} downloading... Grab a cup of coffee :), it will take some time depending on your internet speed."
        )

        response = requests.get(self.api.appimage_url, timeout=10, stream=True)
        total_size_in_bytes = int(response.headers.get("content-length", 0))

        if response.status_code == 200:
            with open(f"{self.api.appimage_name}", "wb") as file, tqdm(
                desc=self.api.appimage_name,
                total=total_size_in_bytes,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as progress_bar:
                for data in response.iter_content(chunk_size=8192):
                    size = file.write(data)
                    progress_bar.update(size)
        else:
            print(f"Error downloading {self.api.appimage_name}")
            logging.error(f"Error downloading {self.api.appimage_url}")
            sys.exit()

        if response is not None:
            response.close()
            print(f"Download completed! {self.api.appimage_name} installed.")
        else:
            print(f"Error downloading {self.api.appimage_name}")
