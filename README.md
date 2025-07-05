[![en](https://img.shields.io/badge/lang-en-green.svg)](https://github.com/Cyber-Syntax/my-unicorn/blob/main/README.md)
[![tr](https://img.shields.io/badge/lang-tr-blue.svg)](https://github.com/Cyber-Syntax/my-unicorn/blob/main/README.tr.md)

> [!WARNING]
> **This project is in a beta phase** due to limited testing at this time.. Although primarily developed for learning purposes, it effectively addresses my specific needs.
> **Important:** Follow the instructions in the **Releases section** when updating the script. Updates may include new features or changes that could require different steps. I’ll strive to keep the instructions as simple as possible.
> **Currently supported:** Linux only.

## **🦄 About my-unicorn**

> [!NOTE]
> I created this project to solve my problem. This script installs an AppImage from the GitHub API, saves it to a user-selected directory, creates a config file (JSON) to save information about the AppImage and automate the update process. Also, this script is able to verify whether the AppImage has been installed correctly from GitHub by checking the SHA256 or SHA512 hash of the verification file from the GitHub repository against the actual AppImage.

- **Applications tested with this script:**
    - 🛠️ **Tested:**
        - [x] super-productivity
        - [x] siyuan-note
        - [x] Joplin
        - [x] FreeTube (Without verification because developer doesn't provide hash. Related issue: https://github.com/FreeTubeApp/FreeTube/issues/4720)
        - [x] Standard-notes
        - [x] AppFlowy (Without verification because developer doesn't provide hash.)
        - More can be found in the [apps/](apps/) folder.

- 🛠️ **Tested:**
    - [x] sha256
    - [x] sha512
    - Without verification (e.g., FreeTube, AppFlowy)

## **💡 Installation **

1. Open a terminal and clone this repo (make sure you have git installed):

    ```bash
    cd ~/Downloads &
    git clone https://github.com/Cyber-Syntax/my-unicorn.git
    ```

2. Navigate to the project directory:

    ```bash
    cd ~/Downloads/Cyber-Syntax/my-unicorn
    ```

## ** Building the script as a package **

1. Export the `PATH` variable on your .bashrc or .zshrc file:

    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    ```

2. Build the project:

    ```bash
    cd ~/Downloads/Cyber-Syntax/my-unicorn
    pip install -e .
    ```

## ** How to use the script **

### Using as a package:

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

### For using uncompatible apps(Choice 1, installing with URL):

1. Using the app to create one for you, but you'll need to know some information about the application:
    - **GitHub URL:** The repository URL of the app (e.g., `https://github.com/johannesjo/super-productivity`).
2. Hash type and Hash file name are automatically detected. You need to provide below informations, if the app compatibility is not available or error occurs:
    - **Hash type:** Specify the hash type (e.g., sha512 for super-productivity).
    - **Hash verification issues:** If the hash verification fails, you can manually add the hash to the JSON file:
        - Look for the latest hash in the GitHub release page (e.g., [super-productivity releases](https://github.com/johannesjo/super-productivity/releases)).
        - Check the `apps/` folder for examples.

## ** Using without building as a package **

1. After cloning the repository, navigate to the project directory:

    ```bash
    cd my-unicorn/src
    ```

2. **Optional: Create a virtual environment (Recommended)**

> [!IMPORTANT]
> This would increase performance.

- Install `uv` and `pip` if you haven't already(Example for fedora-based systems):

    ```bash
    sudo dnf python3-pip uv
    ```

- Create a virtual environment:
- `uv venv`
- Activate the virtual environment:
    - `source .venv/bin/activate`
- Install dependencies using `pip`:
    - `uv pip install -r requirements.txt`

3. Activate the virtual environment (if applicable):

    ```bash
    source .venv/bin/activate
    ```

4. Start the script:

    ```bash
     uv run main.py
    ```

## **🙏 Support This Project**

- **Consider giving it a star ⭐** on GitHub to show your support and keep me motivated on my coding journey!
- **💖 Sponsor me:** If you'd like to support my work and help me continue learning and building projects, consider sponsoring me:
    - [![Sponsor Me](https://img.shields.io/badge/Sponsor-💖-brightgreen)](https://github.com/sponsors/Cyber-Syntax)

### **🤝 Contributing**

- This project is primarily a learning resource for me, but I appreciate any feedback or suggestions! While I can't promise to incorporate all contributions or maintain active involvement, I’m open to improvements and ideas that align with the project’s goals.
- Anyway, please refer to the [CONTRIBUTING.md](.github/CONTRIBUTING.md) file for more detailed explanation.

## **📝 License**

This script is licensed under the [GPL 3.0 License]. You can find a copy of the license in the [LICENSE](https://github.com/Cyber-Syntax/my-unicorn/blob/main/LICENSE) file or at [www.gnu.org](https://www.gnu.org/licenses/gpl-3.0.en.html).
