# Common used basic functions to insert without classes

    def list_json_files(self):
        """List the json files in the current directory, if json file exists."""
        try:
            json_files = [
                file
                for file in os.listdir(self.config_folder_path)
                if file.endswith(".json")
            ]
        except FileNotFoundError as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(_("\033[41;30mError: {error}. Exiting...\033[0m").format(error=error))
            self.ask_inputs()

        if len(json_files) > 1:
            print(_("Available json files:"))
            print("================================================================")
            for index, file in enumerate(json_files):
                print(f"{index + 1}. {file}")
            try:
                print(
                    "================================================================"
                )
                choice = int(input(_("Enter your choice: ")))
            except ValueError as error2:
                logging.error(f"Error: {error2}", exc_info=True)
                print(_("Invalid choice. Please write a number."))
                self.list_json_files()
            else:
                self.repo = json_files[choice - 1].replace(".json", "")
                self.load_credentials()
        elif len(json_files) == 1:
            self.repo = json_files[0].replace(".json", "")
            self.load_credentials()
        else:
            print(_("There is no .json file in the current directory"))
            self.ask_inputs()

