from commands.base import Command


class SelectConfigurationFilesCommand(Command):
    """Command to select AppImage configuration files."""

    def __init__(self, app_config):
        self.app_config = app_config

    def execute(self):
        json_files = self.app_config.list_json_files()
        if not json_files:
            print("No configuration files found. Please create one first.")
            return None

        if self.global_config.batch_mode:
            print("Batch mode: Selecting all available configuration files")
            return json_files

        print("Available configuration files:")
        for idx, json_file in enumerate(json_files, start=1):
            print(f"{idx}. {json_file}")

        user_input = input(
            "Enter the numbers of the configuration files you want to update (comma-separated): "
        ).strip()

        try:
            selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]
            if any(idx < 0 or idx >= len(json_files) for idx in selected_indices):
                raise ValueError("Invalid selection.")
            return [json_files[idx] for idx in selected_indices]
        except (ValueError, IndexError):
            print("Invalid selection. Please enter valid numbers.")
            return None
