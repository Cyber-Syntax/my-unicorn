import os
import json
from babel.support import Translations
import gettext
from dataclasses import dataclass
from src.config import ConfigurationManager


@dataclass
class LocaleManager:
    config: ConfigurationManager

    def __post_init__(self, config_path):
        self.config_path = config_path
        self._ = gettext.gettext

    def get_locale_config(self):
        """Load locale configuration from the config file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as file:
                config = json.load(file)
                return config.get("locale")
        return None

    def save_locale_config(self, locale):
        """Save the selected locale to the config file."""
        os.makedirs(
            os.path.dirname(self.app_image_downloader.config_path), exist_ok=True
        )
        with open(self.app_image_downloader.config_path, "w", encoding="utf-8") as file:
            json.dump({"locale": locale}, file, indent=4)

    def load_translations(self, locale):
        """Load translations for the specified locale."""
        locales_dir = os.path.join(os.path.dirname(__file__), "locales")
        translations = Translations.load(locales_dir, [locale])
        translations.install()
        self._ = translations.gettext

    def select_language(self):
        """Prompt the user to select a language."""
        languages = {1: "en", 2: "tr"}
        current_locale = self.get_locale_config()
        if current_locale:
            self.load_translations(current_locale)
            return

        print("Choose your language / Dilinizi seçin:")
        print("1. English")
        print("2. Türkçe")
        try:
            choice = int(input("Enter your choice: "))
            language = languages.get(choice, "en")
            self.save_locale_config(language)
            self.load_translations(language)
        except (ValueError, KeyboardInterrupt):
            print("Invalid input. Defaulting to English.")
