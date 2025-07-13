Türkçe Açıklama: [README.tr.md](README.tr.md)

> [!CAUTION]
> This project is in a **alpha phase** due to limited testing at this time.
>
> **Important:** Follow the instructions in the **Releases section** when updating the script.
>
> **Supported OS:** Currently, only Linux is supported.

# **🦄 About my-unicorn**

> [!NOTE]
> I always frustrated with the manual AppImage update process and I created this project to automate the process.
>
> Detailed information: [wiki.md](docs/wiki.md)

- **Supported Applications:**
    - Super-Productivity, Siyuan, Joplin, Standard-notes, Logseq, QOwnNotes, Tagspaces, Zen-Browser, weektodo, Zettlr
    - Applications without verification (developer doesn't provide hash):
        - FreeTube
            - Related issue: https://github.com/FreeTubeApp/FreeTube/issues/4720)
        - AppFlowy
        - Obsidian
    - More can be found in the [apps](my_unicorn/apps/) folder.
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
    sh my-unicorn-installer.sh install
    ```

## Remove the package:

> [!TIP]
> This would remove the package if you installed globally.

    ```bash
    pip uninstall my-unicorn
    ```

# How to use the script?

## Using as a package:

```bash
my-unicorn --help # to see the command options
```

```bash
usage: my-unicorn [-h] {download,install,update,token,migrate} ...

my-unicorn: AppImage management tool

positional arguments:
  {download,install,update,token,migrate}
                        Available commands
    download            Download AppImage from URL
    install             Install app from catalog
    update              Update AppImages
    token               GitHub token management
    migrate             Migrate configuration files

options:
  -h, --help            show this help message and exit

Examples:
my-unicorn # Interactive mode (default)
my-unicorn download https://github.com/johannesjo/super-productivity # Download AppImage from URL
my-unicorn install joplin # Install AppImage from catalog
my-unicorn update --all # Update all AppImages
my-unicorn update --select joplin,super-productivity # Select AppImages to update
my-unicorn token --save # Save GitHub token to keyring
my-unicorn token --remove # Remove GitHub token
my-unicorn token --check # Check GitHub API rate limits
my-unicorn migrate --clean # Migrate configuration files
my-unicorn migrate --force # Migrate configuration without confirmation
```

## For using uncompatible apps (installing with URL):

> [!IMPORTANT]
> If you want to install an uncompatible app, you'll need to know some information about the application.

- **GitHub URL:** The repository URL of the app (e.g., `https://github.com/johannesjo/super-productivity`).
- Hash type and Hash file name are automatically detected. You need to provide below informations, if the app compatibility is not available or error occurs:
    - **Hash type:** Specify the hash type (e.g., sha512 for super-productivity).
    - **Hash verification issues:** If the hash verification fails, you can manually add the hash to the JSON file:
        - Look for the latest hash in the GitHub release page (e.g., [super-productivity releases](https://github.com/johannesjo/super-productivity/releases)).
        - Check the [apps](my_unicorn/apps/) folder for examples.

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
