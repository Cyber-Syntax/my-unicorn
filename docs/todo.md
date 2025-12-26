# TODO List

## review

- Network retry logic
- Logger rotation logic
- API rate limiting
- Build with uv

## in-progress

- [ ] What about threading usage on logging? Example: <https://github.com/Roulbac/uv-func/blob/main/src/uv_func/logging.py>
- [ ] P1: deprecate my-unicorn package and repo directories after migration to uv package manager:
    repo = /home/developer/.local/share/my-unicorn-repo
    package = /home/developer/.local/share/my-unicorn

- [ ] P1: remove icon download logic because we extract icon from appimage now.
- [ ] P1: Clear all the examples, plan...
- [ ] P1: add INFO level logs for verification instead of DEBUG
- [ ] P2: add lock for one instance only to prevent multiple instance run at the same time
    - [ ] 16G error log, because of 2 instance running at the same time.

- [ ] P2: #BUG: Cycle, circular import detected in import chain for cache.py
- [ ] P3: Never use the real user config logs, app location on pytest unittests which current is use them!

- [ ] P4: Remove code smells: <https://refactoring.guru/refactoring/smells>
    - [ ] contexts
    - [ ] config
    - [x] handle FIXME, TODO for duplicate functions

- [ ] just simply use github release sections, not bother to write fetching from api

```bash
my-unicorn install super-productivity
Fetching from API: # this line is not needed at all.
GitHub Releases      0/1 Fetching... # add here to fetchin from api basically.
#it isn't long  text
Fetching from API:
GitHub Releases      1/1 Retrieved
```

- [ ] Improve our branch structure for this project. Currently, we use the main branch as stable as possible, but maybe it would be better to reserve main for development and
create a separate stable branch or utilize tags to install stable branches. This is because we update our scripts so frequently, which often results in changes that break
things, necessitating hotfixes. Let's explore ways to manage branches and tags more effectively.

Some sources define 'Rawhide' as equivalent to either 'development' or 'main' (as it serves as the main branch in package git repositories).

Others suggest that 'main branches should be development', proposing a stable branch for users to install the stable release instead.

Alternatively, another perspective states that 'origin/master' is considered the main branch where the source code of HEAD always reflects a production-ready state.

## todo

- [ ] sphinx for docs?
- [ ] Make a better todo.md structure with priorities, labels etc.
- [ ] clean this todo list, make priority to BUGS first.
- [ ] P1: png need priority one because kde not show .svg on its bar when pinned
- [ ] P3: config structure refactor
    - [ ] Add option in config for [auth]
    - [ ] Move owner, repo to github section
- [ ] P4: remove legacy upgrade command
- [ ] P3: #BUG: when there is one fail(keepassxc fails on checksum because external
      issue by devs) on verification but our ui not show when
      there is one verification success, so it might be better to show the failed and success.
      Also need to fix ui progress bar created two time because of this issue.

- [ ] P2: update.bash check network connection
- [ ] add autocompletion for the catalog apps to autocomplete app names (e.g: `super<tab>-productivity`)
- [ ] #BUG: `/tmp/.mount_appflobIOEjI/AppFlowy: error while loading shared libraries: libkeybinder-3.0.so.0: cannot open shared object file: No such file or directory`
    - This is dependency issue, installing `keybinder3` solve the issue. I don't think I can do anything from my side, maybe document it on the docs.

- [ ] dev(improve): rename list.py to catalog.py and all it's commands list to catalog
- [ ] TEST: test probably use AppImageKit, better to make sure it is only used for though.
- [ ] #TEST: test.bash need another command --use-cache, --no-cache which remove and not remove
- [ ] is it better to use functional programming?
- [ ] dev(test): manual test script need network exception error handling
- [ ] mv neovim to usr bin to use appimage neovim
    mv /tmp/nvim.appimage /usr/local/bin/nvim

- [ ] Add kde wallet support via dbus-python.
      dbus-python used on kdewallet saves, so we can add that to auth later as a support.
- [ ] add verification passed or not to verification section on app-specific config

## backlog

- [ ] dev(docs): libsecret also our prerequested dependency,
- [ ] P4: upgrade need auto easy update and notify like appimages
- [ ] P4: Add progress bar for checksum file installations?
- [ ] update docs with mermaid, use copilot to create them it seems copilot handles mermaid pretty well
- [ ] python security practices
- [ ] might be better to use loguru
- [ ] add my unicorn export path to fish shells
- [ ] #BUG: upgrade command get stable cache 1.2.3 version for my-unicorn repo
- [ ] #TEST: bdd style tests
- [ ] read all the test from stratch with your examples to make sure they work as expected like examples not good current
- [ ] Simple video about cli tool workflow
- [ ] good to use aiodns with aiohttp
- [ ] Environment variable support

```bash
# log
2025-10-31 12:04:00 - my_unicorn.backup - WARNING - warning:306 - Invalid version format detected, using lexicographic sorting
2025-10-31 12:04:00 - my_unicorn.auth - ERROR - error:321 - Failed to retrieve GitHub token from keyring: Environment variable DBUS_SESSION_BUS_ADDRESS is unse

# try to test it in container, and I confirm it is dbus issue
github_pat_aXCvasdfbcasdfXZCXVA^Cdg1231asdfascvasd123 # example github pat, not real
[devuser@arch-dev my-unicorn]$ my-unicorn auth --save-token
Enter your GitHub token (input hidden):
Confirm your GitHub token:
15:37:15 - my_unicorn.auth - ERROR - Failed to save GitHub token to keyring: Environment variable DBUS_SESSION_BUS_ADDRESS is unset
15:37:15 - my_unicorn.cli.runner - ERROR - Unexpected error: Environment variable DBUS_SESSION_BUS_ADDRESS is unset
❌ Unexpected error: Environment variable DBUS_SESSION_BUS_ADDRESS is unset
```

- [ ] good cli design princibles
      <https://clig.dev/>
      <https://www.amazon.com/UNIX-Programming-Addison-Wesley-Professional-Computng/dp/0131429019>

  My advice as a user of CLI:

    - no emojis please, ever
    Many people are more visually oriented, and are greatly aided by images and color.
    A standard `NO_EMOJIS` environment variable could perhaps be used to help both camps, just like `NO_COLOR` is available today.
    - if you want to make it look nice, use ANSI escape codes for color rather than emojis.
    even then, don't use color alone to convey meaning because it will most likely get destroyed by whatever you're piping it to.
    - No, please don't use escape codes in your output. Use the library that is designed for this purpose: terminfo.
    - please take the time to write detailed man pages, not just a "--help" screen
    - implement "did you mean?" for typos (git style) and potentially dangerous commands
    - separate the interface into a tree of subcommands (Go/Docker/AWS style) rather than a flat assortment of flags
    - if you are displaying tabular data, present an ncurses interface
    - (extremely important) shell completion for bash and zsh

## done

- [x] fix the autocomplete zshrc local bin exporting
- [ ] janitor code cleanup in progress:
    - [x] progress.py
- [x] remove writing commits to release desc
    - [x] removed commits
    - [x] make it work with keepachangelog template which that template not use v0.1.0 `v` prefix on its heading
        so our github action bash script need to add itself when creating tags because conventional tags need v in front of them.
- [x] #BUG: Rotation error on logs... - Currently, implemented to custom rotation logic more simple and efficient
      and also increased 1MB log to 10MB to increase the log size. Manual and pytest
      succesfully passed.
    - [x] Fixed rotation error on logs
- [ ] appimage build take times
    - [x] install/update show installation error reasons(show appimage build takes times)
- [ ] #TEST: version command logic is deprecated, so testing to use **version** library
- [ ] network retry etc.
    - [x] Attempt is work as expected, when network connection come back, it starts the download again.
- [ ] #BUG: progress bar ui artifact fix
    - [x] Switch the text based progress bar to a more efficient one
    - [x] After implementation text based, some other tests hangs, diagnose that and fix.
    - [x] duplicate on ui progress bar not happens on alacritty and kitty but happens on the zed editor. Test the commited on other terminals and than test the current code changes on again in virt-manager
    - [x] test on different terminals
    - [x] update pytest to test the new progress bar implementation
    - [x] Clean complexity and publish
- [ ] dev(improve): our logger use singleton
- [ ] #BUG: is backup folder not created after new feature? test qownnotes when there is update available
- [x] move the src/ layout for better packaging and installation
- [x] #BUG: digest not became true on catalog installs if its use checksum_file with digest verify both
- [x] make sure skip not skip verification if there is verification option
    - [x] freetube test verify digest even it is skip: true on the catalog,
        and I still keep it skip purposely
    - [x] obsidian test
- [x] Clean up code
    - [x] general
    - [x] logger
    - [x] scripts
    - [x] service.progress already active
    - [x] services
    - [x] utils.py seperated folders
    - [x] reading code from top to bottom
    - [x] functions instead of comments
    - [x] remove license, contribution from readme.md because there is already markdown files for them
- [x] Remove overengineering
    - [x] template
- [x] clean unused code
    - [x] locale, batch_mode on configs
- [x] auth log info, validation
- [x] #BUG: Token need to be optional (container error, it might be related to dbus issue which container based not use secretservice dbus?)
    - [x] when there is correctly setup gnome-keyring, it works.
- [x] Start source code readonly on container
- [x] test.bash -> update test not available because we remove before catalog install or url install
      so we need a better logic to handle this case
- [x] BUG: two time installed print on new version

## Future Enhancements (Good-to-have)

### Asset detection, filtering, and prioritization

1. **Configurable Architecture Support**

   - Allow users to specify target architecture (ARM, x86_64, etc.)
   - Useful for edge cases like Raspberry Pi users

2. **Smart Checksum Prioritization**

   - Prefer SHA512 > SHA256 > MD5 when multiple checksums available
   - Documented in filtering methods

3. **Cache Statistics Enhancement**

   - Add metrics for filtered vs. total assets
   - Show cache size savings in stats output

4. **Pattern Configuration**
   - Move platform patterns to configuration file
   - Allow advanced users to customize filtering rules

## Future Improvements

- [ ] Switch to stable releases only when we publish stable versions (currently using prereleases in upgrade module)
