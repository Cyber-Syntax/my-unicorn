## 🙏 If this script helped you;
- **Please consider giving stars ⭐, it will help me stay motivated for learn to code.** 
- 🤯 **It is it difficult for me to stay motivated while writing scripts and learning coding**

# <samp>Attention<samp>
- **Do not use without taking old version backup.** This script is in alpha version. Therefore, you may encounter some errors.


## ‎ 🦄 <samp>About my-unicorn<samp>
- Script that downloads appimage github latest version via api. It also validates the file with:
    - 🛠️ Tested; 
        - [X] sha256
        - [X] sha512
        - [ ] md5 
        - [ ] sha1
- <samp>Which apps work with this script?<samp>
    - 🛠️ Tested; 
        - [X] super-productivity
        - [X] siyuan-note
        - [X] Joplin        

## ‎ <samp>How to use<samp>
- Example:
    - `python3 main.py`
    - Do you want to download new appimage? (y/n): y
    - Enter your choice: 1
    - Enter the app github url: https://github.com/siyuan-note/siyuan
    - Enter the sha name: SHA256SUMS.txt
    - Which directory(e.g /Documents/appimages)to save appimage: /Documents/appimages
    - Enter the hash type for your sha (e.g md5, sha256, sha1) file: sha256
    - Do you want to backup siyuan.AppImage to /home/developer/Documents/appimages/backup/ (y/n): y

- Detailed:
    - You can use it by choosing what to do from the list.
    - First you need to know the "github url" of the application you want to download.
    - After knowing this, if you want to make sure that the downloaded file is not changed while it is being downloaded for security purposes, you should also know the full name of the file that is commonly used for linux, such as sha512, sha1...
    - Also, do not forget to write hash type and appimage directory.
