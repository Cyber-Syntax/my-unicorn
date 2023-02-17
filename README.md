# If this script helped you;
- **Please consider giving stars, it will help me stay motivated and learn to code. I find it difficult to stay motivated while learning and writing such scripts.**

# About my-unicorn
Script that downloads appimage github latest version via api. It also validates the file with:
- Tested; 
    - [X] sha256
    - [X] sha512
    - [ ] md5 
    - [ ] sha1

# Usage
- Example:
    - 1.Download the new latest AppImage, save old AppImage
    - Enter your choice: 1
    - Enter the app github url: https://github.com/siyuan-note/siyuan
    - Enter the sha name: SHA256SUMS.txt
    - Which directory(e.g /Documents/appimages)to save appimage: /Documents/appimages
    - Enter the hash type for your sha (e.g md5, sha256, sha1) file: sha256
    - Do you want to backup siyuan.AppImage to /home/developer/Documents/appimages/backup/ (y/n): y    

- Detailed:
    - You can use it by choosing what to do from the list.
    - First you need to know the github url of the application you want to download.
    - After knowing this, if you want to make sure that the downloaded file is not changed while it is being downloaded for security purposes, you should also know the full name of the file that is commonly used for linux, such as sha512, sha1...
    - Also, do not forget to write hash type and appimage directory.
