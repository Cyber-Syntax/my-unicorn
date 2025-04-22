import gettext
import os

from babel.support import Translations

from .global_config import GlobalConfigManager

# TODO: Need to setup for all of the prints with gettext


class LocaleManager:
    """Handles locale settings and translations."""

    def __init__(self, config: GlobalConfigManager):
        self.config = config
        self._ = gettext.gettext
        self.load_translations(self.config.locale)

    def get_locale_config(self):
        """Return the current locale."""
        return self.config.locale

    def save_locale_config(self, locale):
        """Save the selected locale to the config."""
        self.config.locale = locale
        self.config.save_config()

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
        except ValueError:
            print("Invalid input. Defaulting to English.")
            self.save_locale_config("en")
            self.load_translations("en")
        except KeyboardInterrupt:
            print("\nSelection interrupted. Defaulting to English.")
            self.save_locale_config("en")
            self.load_translations("en")
