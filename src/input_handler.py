class InputHandler:
    """Handles user inputs for different configurations."""

    @staticmethod
    def handle_global_config_setup():
        """Prompt user for global configuration setup."""
        # from global_config_setup import GlobalConfigSetup

        return GlobalConfigSetup.create_global_config()

    @staticmethod
    def handle_app_config_setup():
        """Prompt user for app-specific configuration setup."""
        return AppConfigSetup.create_app_config()

    @staticmethod
    def handle_all():
        """Guide user through all required setups."""
        print("Starting configuration setup...")
        global_config = InputHandler.handle_global_config_setup()
        app_config = InputHandler.handle_app_config_setup()
        return global_config, app_config
