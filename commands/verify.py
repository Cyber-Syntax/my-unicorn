from commands.base import Command
from src.verify import VerificationManager, HashManager, SHAFileManager


class VerifyCommand(Command):
    """Command to verify the integrity of the downloaded AppImage."""

    def __init__(self, appimage_path, sha_name, sha_url, hash_type="sha256"):
        self.appimage_path = appimage_path
        self.sha_name = sha_name
        self.sha_url = sha_url
        self.hash_type = hash_type

    def execute(self):

        # Initialize the hash manager and SHA file manager
        hash_manager = HashManager(hash_type=self.hash_type)
        sha_manager = SHAFileManager(sha_name=self.sha_name, sha_url=self.sha_url)

        # Initialize the verification manager
        verification_manager = VerificationManager(
            hash_manager=hash_manager, sha_manager=sha_manager
        )
        verification_manager.appimage_path = self.appimage_path

        # Perform verification
        verification_manager.verify_appimage()
