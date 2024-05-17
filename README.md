# <samp>Attention<samp>
- **Do not utilize without making a backup of the previous version.** This script is in its **beta phase**. Hence, you may experience some glitches.
- **This script works only on Linux for the moment. It may work on MacOS, however, I have not tested it.**
-  Make sure to **follow the instructions in the releases section** before updating the script, as I am adding new features and making changes to the script. Therefore, the instructions may be different from the previous version. However, I will try to keep the instructions as simple as possible.

## 🙏 If this script helped you;
- **Please consider giving stars ⭐, it will help me stay motivated to learn coding.**


## ‎ 🦄 <samp>About my-unicorn<samp>
-  Script that downloads AppImage from Github’s latest version through API. It also verifies the file using:
    - 🛠️ Tested;
        - [X] sha256
        - [X] sha512
- <samp>Which applications work with this script?<samp>
    - 🛠️ Tested;
        - [X] super-productivity
        - [X] siyuan-note
        - [X] Joplin

## ‎ <samp>Dependencies<samp>
- If you want, create virtual environment:
  1. Go to location where you cloned.
  2. Create virtual env
        - `python3 -m venv .venv`
  3. Activate virtual environment
        - `source .venv/bin/activate`
  4. Install dependencies for pip.
        - `pip install -r requirements.txt`
        - if that isn't work, install manually:
            - `pip3 install tqdm` 
            - Dependencies:
                - [requests](https://pypi.org/project/requests/)
                - [yaml](https://pypi.org/project/PyYAML/)
                - [tqdm](https://pypi.org/project/tqdm/)

## ‎ <samp> What you need to be aware of before utilizing<samp>
1. Github url (https://github.com/johannesjo/super-productivity)
2. If not work for your appimage:
    - Github sha name e.g - latest-linux.yml here - (https://github.com/johannesjo/super-productivity/releases)
3. Hash type (e.g - sha512 for super-productivity)

## ‎ <samp>How to use<samp>
- Example:
    1. Open terminal and clone this repo (make sure you have git installed)
        - `git clone https://github.com/Cyber-Syntax/my-unicorn.git`
    2. Go that location (You can use `pwd` command to see your location. `cd` for change directory)
        - Example: `cd ~/Downloads/Cyber-Syntax/my-unicorn`
    3. Activate virtual environment if you created:
        - `source .venv/bin/activate `
    4. Start script
        - `python3 main.py`
    5. Follow the instructions:
## ‎ <samp>How to install new appimage (This is need for json file create)<samp>
- **You can skip this step:**
    - if you have already installed the appimage with this script or if you created json file manually.

            ╰─❯ python3 main.py

            Welcome to the my-unicorn 🦄!
            Choose one of the following options:
            ====================================
            1. Update existing appimage
            2. Download new appimage
            3. Update json file
            4. Exit
            ====================================
            Enter your choice: 2
            Downloading new appimage
            Choose one of the following options:

            ====================================
            1. Backup old appimage and download new appimage
            2. Download new appimage and overwrite old appimage
            Enter your choice: 1
            =================================================
            Enter the app github url: https://github.com/laurent22/joplin
            Which directory to save appimage
            (Default: '~/Documents/appimages' if you leave it blank):
            Which directory to save old appimage
            (Default: '~/Documents/appimages/backup' if you leave it blank):
            Enter the hash type for your sha(sha256, sha512) file: sha512
            =================================================
            Parsing the owner and repo from the url...
            joplin downloading...Grab a cup of coffee :), it will take some time depending on your internet speed.
            Joplin-2.13.12.AppImage: 100%|██████████████████████████████████████████████████| 201M/201M [00:19<00:00, 11.0MiB/s]

## ‎ <samp>How to update appimage<samp>

    ╰─❯ python3 main.py

    Welcome to the my-unicorn 🦄!
    Choose one of the following options:
    ====================================
    1. Update existing appimage
    2. Download new appimage
    3. Update json file
    4. Exit
    ====================================
    Enter your choice: 1

    There are more than one .json file, please choose one of them:
    ================================================================
    1. siyuan.json
    2. super-productivity.json
    3. joplin.json
    ================================================================
    Enter your choice: 3

## ‎ <samp>LICENSE<samp>
- This script is licensed under the [GPL 3.0 License].
You can find a copy of the license in the [LICENSE](https://github.com/Cyber-Syntax/my-unicorn/blob/main/LICENSE) file or at [www.gnu.org](https://www.gnu.org/licenses/gpl-3.0.en.html)
