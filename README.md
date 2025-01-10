[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Cyber-Syntax/my-unicorn/blob/main/README.md)
[![tr](https://img.shields.io/badge/lang-tr-red.svg)](https://github.com/Cyber-Syntax/my-unicorn/blob/main/README.tr.md)

---

# **⚠️ Attention**

- **This project is in a permanent beta phase** due to limited testing. Although primarily developed for learning purposes, it effectively addresses my specific needs.
- **Important:** Follow the instructions in the **Releases section** when updating the script. Updates may include new features or changes that could require different steps. I’ll strive to keep the instructions as simple as possible.
- **Currently supported:** Linux only. While it might work on macOS, it has not been tested yet.

---

## **🙏 Support This Project**

If this script has been helpful:

- **Consider giving it a star ⭐** on GitHub to show your support and keep me motivated on my coding journey!
- **💖 Support This Project:** If you'd like to support my work and help me continue learning and building projects, consider sponsoring me:
  - [![Sponsor Me](https://img.shields.io/badge/Sponsor-💖-brightgreen)](https://github.com/sponsors/Cyber-Syntax)

### **🤝 Contributing**

- This project is primarily a learning resource for me, but I appreciate any feedback or suggestions! While I can't promise to incorporate all contributions or maintain active involvement, I’m open to improvements and ideas that align with the project’s goals.
- Anyway, please refer to the [CONTRIBUTING.md](.github/CONTRIBUTING.md) file for more detailed explanation.

---

## **🦄 About my-unicorn**

- A script that downloads the latest AppImage from GitHub via API. It also verifies the file using:

  - 🛠️ **Tested:**
    - [x] sha256
    - [x] sha512

- **Applications tested with this script:**
  - 🛠️ **Tested:**
    - [x] super-productivity
    - [x] siyuan-note
    - [x] Joplin

---

## **🛠️ Dependencies**

- [requests](https://pypi.org/project/requests/)
- [yaml](https://pypi.org/project/PyYAML/)
- [tqdm](https://pypi.org/project/tqdm/)

### Optional: Create a virtual environment

1. Navigate to the directory where you cloned the repository.
2. Create a virtual environment:
   - `python3 -m venv .venv`
3. Activate the virtual environment:
   - `source .venv/bin/activate`
4. Install dependencies using `pip`:
   - `pip install -r requirements.txt`
   - If this doesn’t work, install manually:
     - `pip3 install tqdm`

---

## **⚠️ What You Need to Know Before Using**

1. **GitHub URL:** The repository URL of the app (e.g., `https://github.com/johannesjo/super-productivity`).
2. **Hash type:** Specify the hash type (e.g., sha512 for super-productivity).
3. **Hash verification issues:** If the hash verification fails, you can manually add the hash to the JSON file:
   - Look for the latest hash in the GitHub release page (e.g., [super-productivity releases](https://github.com/johannesjo/super-productivity/releases)).
   - Check the `json_files` folder for examples. All JSON files should work as expected.

---

## **💡 How to Use**

### Example steps:

1. Open a terminal and clone this repo (make sure you have git installed):

   ```bash
   git clone https://github.com/Cyber-Syntax/my-unicorn.git
   ```

2. Navigate to the project directory:

   ```bash
   cd ~/Downloads/Cyber-Syntax/my-unicorn
   ```

3. Activate the virtual environment (if applicable):

   ```bash
   source .venv/bin/activate
   ```

4. Start the script:

   ```bash
   python3 main.py
   ```

5. Follow the on-screen instructions.

---

## **📥 How to Install a New AppImage (Create Config File)**

You can skip this step if you have already installed the AppImage with this script or if you manually created the config file (e.g., `siyuan.json`).

```bash
╰─❯ python3 main.py
Welcome to my-unicorn 🦄!
Choose one of the following options:
===================================
1. Update existing AppImage
2. Download new AppImage
3. Update json file
4. Exit
===================================
Enter your choice: 2
Downloading new AppImage
Choose one of the following options:
===================================
1. Backup old AppImage and download new AppImage
2. Download new AppImage and overwrite old AppImage
Enter your choice: 1
===================================
Enter the app GitHub URL: https://github.com/laurent22/joplin
Which directory to save the AppImage (Default: '~/Documents/appimages'):
Which directory to save the old AppImage (Default: '~/Documents/appimages/backup'):
Enter the hash type for your sha (sha256, sha512): sha512
===================================
Parsing the owner and repo from the URL...
Joplin downloading... Grab a cup of coffee :) This may take a while depending on your internet speed.
Joplin-2.13.12.AppImage: 100%|██████████████████████████████████████████████████| 201M/201M [00:19<00:00, 11.0MiB/s]
```

---

## **🔄 How to Update AppImage**

```bash
╰─❯ python3 main.py

Welcome to my-unicorn 🦄!
Choose one of the following options:
====================================
1. Update existing AppImage
2. Download new AppImage
3. Update json file
4. Exit
====================================
Enter your choice: 1

There are more than one .json file, please choose one of them:
============================================================
1. siyuan.json
2. super-productivity.json
3. joplin.json
============================================================
Enter your choice: 3
```

---

## **📝 License**

This script is licensed under the [GPL 3.0 License]. You can find a copy of the license in the [LICENSE](https://github.com/Cyber-Syntax/my-unicorn/blob/main/LICENSE) file or at [www.gnu.org](https://www.gnu.org/licenses/gpl-3.0.en.html).

---
