Turkish: [README.tr.md](README.tr.md)

> [!CAUTION]
>
> - This project is in a **alpha phase** due to limited testing at this time.
> - **Important:** Follow the instructions in the **Releases section** when updating the script.
> - **Supported OS:** Currently, only Linux is supported.

# **🦄 About my-unicorn**

> [!NOTE]
> My Unicorn is a command-line tool to manage AppImages on Linux. It allows users to install, update, and manage AppImages from GitHub repositories easily. It's designed to simplify the process of handling AppImages, making it more convenient for users to keep their applications up-to-date.
>
> - Detailed information: [wiki.md](docs/wiki.md)

- **Supported Applications:**
    - Super-Productivity, Siyuan, Joplin, Standard-notes, Logseq, QOwnNotes, Tagspaces, Zen-Browser, Zettlr, HeroicGamesLauncher, KDiskMark, AppFlowy, Obsidian
    - Applications without verification (developer doesn't provide hash):
        - WeekToDo
        - FreeTube
            - Related issue: <https://github.com/FreeTubeApp/FreeTube/issues/4720>)
    - More can be found in the [catalog](my_unicorn/catalog/) folder.
- **Supported hash types:**
    - sha256, sha512

# 💡 Installation

> [!TIP]
> Installer script uses venv to install the needed dependencies.

1. Open a terminal and clone this repo (make sure you have git installed):

    ```bash
    cd ~/Downloads &
    git clone https://github.com/Cyber-Syntax/my-unicorn.git
    ```

2. Build as a package:

    ```bash
    cd my-unicorn &
    sh setup.sh install
    ```

3. Add autocomplete (optional):

    ```bash
    # auto-detect your shell and install autocomplete
    sh setup.sh autocomplete

    # or manually add autocomplete for bash or zsh
    sh setup.sh autocomplete bash
    sh setup.sh autocomplete zsh
    ```

4. Start using my-unicorn:

    ```bash
    my-unicorn --help # to see the command options
    ```

## For using uncompatible apps (installing with URL)

> [!IMPORTANT]
> If you want to install an uncompatible app, you'll need to know some information about the application.

- **GitHub URL:** The repository URL of the app (e.g., `https://github.com/johannesjo/super-productivity`).
- Hash type and Hash file name are automatically detected. You need to provide below informations, if the app compatibility is not available or error occurs:
    - **Hash type:** Specify the hash type (e.g., sha512 for super-productivity).
    - **Hash verification issues:** If the hash verification fails, you can manually add the hash to the JSON file:
        - Look for the latest hash in the GitHub release page (e.g., [super-productivity releases](https://github.com/johannesjo/super-productivity/releases)).
        - Check the [catalog](my_unicorn/catalog/) folder for examples.

# **🙏 Support This Project**

- **Consider giving it a star ⭐** on GitHub to show your support and keep me motivated on my coding journey!
- **Testing:** It would be great if you could test the script and provide feedback on any issues you encounter.
- **💖 Sponsor me:** If you'd like to support my work and help me continue learning and building projects, consider sponsoring me:
    - [![Sponsor Me](https://img.shields.io/badge/Sponsor-💖-brightgreen)](https://github.com/sponsors/Cyber-Syntax)

## **🤝 Contributing**

- This project is primarily a learning resource for me, but I appreciate any feedback or suggestions! While I can't promise to incorporate all contributions or maintain active involvement, I’m open to improvements and ideas that align with the project’s goals.
- Anyway, please refer to the [CONTRIBUTING.md](.github/CONTRIBUTING.md) file for more detailed explanation.

# **📝 License**

This script is licensed under the [GPL 3.0 License]. You can find a copy of the license in the [LICENSE](https://github.com/Cyber-Syntax/my-unicorn/blob/main/LICENSE) file or at [www.gnu.org](https://www.gnu.org/licenses/gpl-3.0.en.html).
