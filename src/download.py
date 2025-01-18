import os
import json
import sys
import logging
import requests
from tqdm import tqdm
from dataclasses import dataclass, field
from src.decorators import handle_api_errors


@dataclass
class DownloadManager(ParseURL):
    """Manages the downloading of the app image."""

    api_url: str = None
    version: str = None
    sha_url: str = None
    appimage_name: str = None

    @handle_api_errors
    def get_response(self):
        """get the api response from the github api"""
        self.api_url = (
            f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        )

        response = requests.get(self.api_url, timeout=10)

        if response is None:
            print("-------------------------------------------------")
            print(
                _("Failed to get response from API: {api_url}").format(
                    api_url=self.api_url
                )
            )
            print("-------------------------------------------------")
            return

        if response.status_code == 200:
            data = json.loads(response.text)
            self.version = data["tag_name"].replace("v", "")

            if self.choice in [3, 4]:
                if self.version == self.appimages["version"]:
                    print(_("{repo}.AppImage is up to date").format(repo=self.repo))
                    print(_("Version: {version}").format(version=self.version))
                    print(_("Exiting..."))
                    sys.exit()
                else:
                    print("-------------------------------------------------")
                    print(
                        _("Current version: {version}").format(
                            version=self.appimages["version"]
                        )
                    )
                    print(
                        _("\033[42mLatest version: {version}\033[0m").format(
                            version=self.version
                        )
                    )
                    print("-------------------------------------------------")

            keywords = {
                "linux",
                "sum",
                "sha",
                "SHA",
                "SHA256",
                "SHA512",
                "SHA-256",
                "SHA-512",
                "checksum",
                "checksums",
                "CHECKSUM",
                "CHECKSUMS",
            }
            valid_extensions = {
                ".sha256",
                ".sha512",
                ".yml",
                ".yaml",
                ".txt",
                ".sum",
                ".sha",
            }

            for asset in data["assets"]:
                if asset["name"].endswith(".AppImage"):
                    self.appimage_name = asset["name"]
                    self.url = asset["browser_download_url"]
                elif any(keyword in asset["name"] for keyword in keywords) and asset[
                    "name"
                ].endswith(tuple(valid_extensions)):
                    self.sha_name = asset["name"]
                    self.sha_url = asset["browser_download_url"]
                    if self.sha_name is None:
                        print(_("Couldn't find the sha file"))
                        logging.error(_("Couldn't find the sha file"))
                        self.sha_name = input(_("Enter the exact sha name: "))
                        self.sha_url = asset["browser_download_url"]

    @handle_api_errors
    def download(self):
        """Download the appimage from the github api"""
        if os.path.exists(self.appimage_name) or os.path.exists(
            self.repo + ".AppImage"
        ):
            print(
                _("{appimage_name} already exists in the current directory").format(
                    appimage_name=self.appimage_name
                )
            )
            return

        print(
            _(
                "{repo} downloading... Grab a cup of coffee :), it will take some time depending on your internet speed."
            ).format(repo=self.repo)
        )
        response = requests.get(self.url, timeout=10, stream=True)

        total_size_in_bytes = int(response.headers.get("content-length", 0))

        if response.status_code == 200:
            with open(f"{self.appimage_name}", "wb") as file, tqdm(
                desc=self.appimage_name,
                total=total_size_in_bytes,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as progress_bar:
                for data in response.iter_content(chunk_size=8192):
                    size = file.write(data)
                    progress_bar.update(size)
        else:
            print(
                _("\033[41;30mError downloading {appimage_name}\033[0m").format(
                    appimage_name=self.appimage_name
                )
            )
            logging.error(f"Error downloading {self.appimage_name}")
            sys.exit()

        with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)

        if response is not None:
            response.close()
            print("-------------------------------------------------")
            print(
                _(
                    "\033[42mDownload completed! {appimage_name} installed.\033[0m"
                ).format(appimage_name=self.appimage_name)
            )
            print("-------------------------------------------------")
        else:
            print("-------------------------------------------------")
            print(
                _("\033[41;30mError downloading {appimage_name}\033[0m").format(
                    appimage_name=self.appimage_name
                )
            )
            print("-------------------------------------------------")
