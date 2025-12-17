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
    - Super-Productivity, Siyuan, Joplin, Standard-notes, Logseq, QOwnNotes, Tagspaces, Zen-Browser, Zettlr, HeroicGamesLauncher, KDiskMark, AppFlowy, Obsidian, FreeTube
    - Applications without verification (developer doesn't provide hash):
        - WeekToDo
    - More can be found in the [catalog](src/my_unicorn/catalog) folder.
- **Supported hash types:**
    - sha256, sha512

# 💡 Installation

## Option 1: Install using uv (Recommended)

> [!TIP]
> This is the recommended method for production use. It installs my-unicorn as an isolated CLI tool.

### Prerequisites

Install `uv` if you haven't already:

```bash
# Fedora
sudo dnf install uv

# Arch Linux
sudo pacman -S uv

# Universal installer (Linux, macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Production Install

**Method 1: Using setup.sh (easiest)**

```bash
cd ~/Downloads
git clone https://github.com/Cyber-Syntax/my-unicorn.git
cd my-unicorn
./setup.sh uv-install
```

**Method 2: Direct uv command**

```bash
cd ~/Downloads
git clone https://github.com/Cyber-Syntax/my-unicorn.git
cd my-unicorn
uv tool install .
```

### Updating

**Using setup.sh:**

```bash
cd ~/Downloads/my-unicorn
./setup.sh uv-update
```

**Direct uv command:**

```bash
cd ~/Downloads/my-unicorn
git pull
uv tool install . --reinstall
```

### Development Install (for contributors)

**Using setup.sh:**

```bash
cd ~/Downloads/my-unicorn
./setup.sh uv-editable
```

**Direct uv command:**

```bash
cd ~/Downloads/my-unicorn
uv tool install --editable .
```

Changes to the source code will be reflected immediately without reinstalling.

## Option 2: Traditional Installation (Legacy)

> [!TIP]
> Installer script uses venv to install the needed dependencies.

1. Open a terminal and clone this repo (make sure you have git installed):

    ```bash
    cd ~/Downloads &
    git clone https://github.com/Cyber-Syntax/my-unicorn.git
    ```

2. Install `uv` (RECOMMENDED):

    > `uv` would be used to install the dependencies to venv, it is more efficient than pip.

    ```bash
    # fedora
    sudo dnf install uv
    # arch
    sudo pacman -S uv
    # or `uv` astral official standalone installer
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

3. Build as a package:

    ```bash
    # Go to the project directory
    cd my-unicorn &
    # Run installer (automatically uses UV if available)
    ./setup.sh install
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
        - Check the [catalog](src/my_unicorn/catalog) folder for examples.

# **🙏 Support This Project**

- **Consider giving it a star ⭐** on GitHub to show your support and keep me motivated on my coding journey!
- **Testing:** It would be great if you could test the script and provide feedback on any issues you encounter.
- **💖 Sponsor me:** If you'd like to support my work and help me continue learning and building projects, consider sponsoring me:
    - [![Sponsor Me](https://img.shields.io/badge/Sponsor-💖-brightgreen)](https://github.com/sponsors/Cyber-Syntax)
