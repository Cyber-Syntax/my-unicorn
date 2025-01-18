class VerificationManager:
    """Handles verification of downloaded app image."""

    sha_name: str = None
    sha_url: str = None

    @staticmethod
    def sha_response_error(func):
        """Handle response errors"""

        def wrapper(self, response):
            if response.status_code == 200:
                self.download_sha(response=response)
                result = func(self, response)
            else:
                response.close()
                self.handle_connection_error()
                result = None
            return result

        return wrapper

    @handle_api_errors
    def get_sha(self):
        """Get the sha name and url"""
        print("************************************")
        print(_("Downloading {sha_name}...").format(sha_name=self.sha_name))
        response = requests.get(self.sha_url, timeout=10)
        return response

    def download_sha(self, response):
        """Install the sha file"""
        # Check if the sha file already exists
        if not os.path.exists(self.sha_name):
            with open(self.sha_name, "w", encoding="utf-8") as file:
                file.write(response.text)
            print(
                _("\033[42mDownloaded {sha_name}\033[0m").format(sha_name=self.sha_name)
            )
        else:
            # If the sha file already exists, check if it is the same as the downloaded one
            with open(self.sha_name, "r", encoding="utf-8") as file:
                if response.text == file.read():
                    print(_("{sha_name} already exists").format(sha_name=self.sha_name))
                else:
                    print(
                        _(
                            "{sha_name} already exists but it is different from the downloaded one"
                        ).format(sha_name=self.sha_name)
                    )
                    if input(_("Do you want to overwrite it? (y/n): ")).lower() == "y":
                        with open(self.sha_name, "w", encoding="utf-8") as file:
                            file.write(response.text)
                        print(
                            _("\033[42mDownloaded {sha_name}\033[0m").format(
                                sha_name=self.sha_name
                            )
                        )
                    else:
                        print(_("Exiting..."))
                        sys.exit()

    def handle_verification_error(self):
        """Handle verification errors"""
        print(
            _("\033[41;30mError verifying {appimage_name}\033[0m").format(
                appimage_name=self.appimage_name
            )
        )
        logging.error(f"Error verifying {self.appimage_name}")
        if (
            input(_("Do you want to delete the downloaded appimage? (y/n): ")).lower()
            == "y"
        ):
            os.remove(self.appimage_name)
            print(_("Deleted {appimage_name}").format(appimage_name=self.appimage_name))
            # Delete the downloaded sha file too
            if (
                input(
                    _("Do you want to delete the downloaded sha file? (y/n): ")
                ).lower()
                == "y"
            ):
                os.remove(self.sha_name)
                print(_("Deleted {sha_name}").format(sha_name=self.sha_name))
                sys.exit()
            else:
                if (
                    input(
                        _("Do you want to continue without verification? (y/n): ")
                    ).lower()
                    == "y"
                ):
                    self.make_executable()
                else:
                    print(_("Exiting..."))
                    sys.exit()

    def handle_connection_error(self):
        """Handle connection errors"""
        print(
            _("\033[41;30mError connecting to {sha_url}\033[0m").format(
                sha_url=self.sha_url
            )
        )
        logging.error(f"Error connecting to {self.sha_url}")
        sys.exit()

    @sha_response_error
    def verify_yml(self, response):
        """Verify yml/yaml sha files"""
        # parse the sha file
        with open(self.sha_name, "r", encoding="utf-8") as file:
            sha = yaml.safe_load(file)

        # get the sha from the sha file
        sha = sha[self.hash_type]
        decoded_hash = base64.b64decode(sha).hex()

        # find appimage sha
        with open(self.appimage_name, "rb") as file:
            appimage_sha = hashlib.new(self.hash_type, file.read()).hexdigest()

        # compare the two hashes
        if appimage_sha == decoded_hash:
            print(
                _("\033[42m{appimage_name} verified.\033[0m").format(
                    appimage_name=self.appimage_name
                )
            )
            print("************************************")
            print(_("--------------------- HASHES ----------------------"))
            print(_("AppImage Hash: {appimage_sha}").format(appimage_sha=appimage_sha))
            print(_("Parsed Hash: {decoded_hash}").format(decoded_hash=decoded_hash))
            print("----------------------------------------------------")
            return True
        else:
            self.handle_verification_error()
            return False

        # close response
        response.close()

    @sha_response_error
    def verify_other(self, response):
        """Verify other sha files"""
        # Parse the sha file
        with open(self.sha_name, "r", encoding="utf-8") as file:
            for line in file:
                if self.appimage_name in line:
                    decoded_hash = line.split()[0]
                    break

        # Find appimage sha
        with open(self.appimage_name, "rb") as file:
            appimage_hash = hashlib.new(self.hash_type, file.read()).hexdigest()

        # Compare the two hashes
        if appimage_hash == decoded_hash:
            print(
                _("\033[42m{appimage_name} verified.\033[0m").format(
                    appimage_name=self.appimage_name
                )
            )
            print("************************************")
            print(_("--------------------- HASHES ----------------------"))
            print(
                _("AppImage Hash: {appimage_hash}").format(appimage_hash=appimage_hash)
            )
            print(_("Parsed Hash: {decoded_hash}").format(decoded_hash=decoded_hash))
            print("----------------------------------------------------")
            return True
        else:
            self.handle_verification_error()
            return False

    def verify_sha(self):
        """Verify the downloaded appimage"""
        if self.sha_name.endswith(".yml") or self.sha_name.endswith(".yaml"):
            return self.verify_yml(response=self.get_sha())
        else:
            return self.verify_other(response=self.get_sha())
