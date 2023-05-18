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
    1. Open terminal and install all files 
        - `git clone https://github.com/Cyber-Syntax/my-unicorn.git`
    2. Go that location 
        - Example: `cd ~/Downloads/`
    3. Start script   
        - `python3 main.py`
    4. Follow the instructions:
        - Example for new appimage download. (This is need for json file create):
            Welcome to the my-unicorn 🦄!
            Choose one of the following options:
            1. Update appimage from json file
            2. Download new appimage
            3. Exit
            Enter your choice:2
            
            Choose one of the following options:
            1. Download new appimage, save old appimage
            2. Download new appimage, don't save old appimage
            Enter your choice:2

            Enter the app github url:https://github.com/laurent22/joplin
            Enter the sha name:latest-linux.yml
            Which directory(e.g /Documents/appimages)to save appimage:/Documents/appimages
            Enter the hash type for your sha (e.g md5, sha256, sha1) file:sha512
            Downloading started...      
        - Example for update appimage via json file:
            Enter your choice:1
            There are more than one .json file, please choose one of them:
            1. joplin.json
            2. siyuan.json
            3. super-productivity.json
            Enter your choice:1
            Do you want to change some credentials? (y/n):y
            Do you want to change the appimage folder? (y/n):y
            Enter new appimage folder:/Documents/appimages/anotherFolder
            Do you want to change the choice? (y/n): y
            Enter new choice: 3
            Do you want to change the sha name? (y/n):y
            Enter new sha name:latest-linux.yml
            Do you want to change the hash type? (y/n):y
            Enter new hash type:sha512
            Downloading started...


- Detailed:
    - You can use it by choosing what to do from the list.
    - First you need to know the "github url" of the application you want to download.
    - After knowing this, if you want to make sure that the downloaded file is not changed while it is being downloaded for security purposes, you should also know the full name of the file that is commonly used for linux, such as sha512, sha1...
    - Also, do not forget to write hash type and appimage directory.
