# TODO List

## review

- [ ] Big reviews
    - [ ] Network retry logic
    - [x] Logger rotation logic
    - [ ] Logger rotation on production
    - [ ] Logger rotation on virtual machine
    - [ ] API rate limiting

- [ ] Test new features
    - [ ] github action for releases
    - [ ] `my-unicorn upgrade` command now use uv package manager.
    - [x] Test `migrate` command
    - [x] Test `migrate` command on virtual machine.

## in-progress

- [ ] Improve manual test script
    - [ ] make sure the api fetch install works (we do that by remove and install on manual test script but seems like remove didn't removed the cache and I couldn't able to detect the api bug correctly, so we need to make manual test to make sure remove did it's job correctly etc.)
    - [ ] add backup tests to make sure backup command also work as expected on tests etc.
    - [ ] add new command to manual test script like `--slow` for big apps like joplin.
    - [ ] add new command to test remove, upgrade, migrate commands.

- [ ] writing every test from scratch for better understanding of tests and make sure they work as expected
    - [ ] cli tests
    - [ ] commands tests
    - [ ] integration tests
    - [ ] migration tests
    - [ ] services tests
    - [ ] schemas tests
    - [ ] maybe TDT style tests later if possible

- [ ] config --show is showing global config, better to name it --show-global-config for more clarity
- [ ] move workflow folder modules to utils folder for better structure
- [ ] Correct comman design pattern with receiver and invoker, commands need to be thin and execute receivers only, learn from examples/patterns/Command/ folder

- [ ] Make a better todo.md structure with priorities, labels etc.
    - [ ] clean this todo list, make priority to BUGS first.
    - [ ] handle todos, in-progress better which we conflict all of them, keep in-progress to what you working on etc.
    - [ ] move big tasks to issues if you need
    - [ ] get some issues to here with their #code like this
    - [ ] make a template for yourself to keep same template all of your other projects

- [ ] P1: deprecate my-unicorn package and repo directories (migrated to uv)
    - [ ] Move venv-wrapper.bash to archive to your lin-utils repo
    - [ ] Remove legacy cli tool install from setup.sh

- [ ] use space-separated to follow KISS principle?

```bash
  # Install from catalog (comma-separated or space-separated)
  my-unicorn install appflowy,joplin,obsidian
  my-unicorn install appflowy joplin obsidian
```

- [ ] P1: add INFO level logs for verification instead of DEBUG
- [ ] add remove --all command
- [ ] P2: add lock for one instance only to prevent multiple instance run at the same time
    - [ ] 16G error log, because of 2 instance running at the same time.

- [ ] P3: Never use the real user config logs, app location on pytest unittests which current is use them!

- [ ] P4: Remove code smells: <https://refactoring.guru/refactoring/smells>
    - [ ] contexts
    - [ ] config
    - [x] handle FIXME, TODO for duplicate functions

## todo

- [ ] add token command and use it as token storage etc. keep auth command for authentication only.
- [ ] performance improvements on api : <https://github.com/xbeat/Machine-Learning/blob/main/9%20Strategies%20to%20Boost%20API%20Performance.md>
    - [ ] APIGateway would be useful when we impemented gitlab support
    - [ ] GraphQL-like query system for REST APIs
- [ ] Add command to migrate from URL installs to Catalog installs
Example; `my-unicorn migrate --app appflowy` or `my-unicorn migrate --all`
but we use migrate command to migrate old config to new config structure
so we need to use flags like `--from-url-to-catalog` or something like that.

- [ ] Add option in global config for [auth]
- [ ] What about threading usage on logging? Example: <https://github.com/Roulbac/uv-func/blob/main/src/uv_func/logging.py>

- [ ] make wiki page
- [ ] sphinx for docs?
- [ ] P1: png need priority one because kde not show .svg on its bar when pinned
- [ ] P4: remove legacy upgrade command
- [ ] P3: #BUG: when there is one fail(keepassxc fails on checksum because external
      issue by devs) on verification but our ui not show when
      there is one verification success, so it might be better to show the failed and success.
      Also need to fix ui progress bar created two time because of this issue.

- [ ] P2: update.bash check network connection
- [ ] add autocompletion for the catalog apps to autocomplete app names (e.g: `super<tab>-productivity`)
- [ ] #BUG: `/tmp/.mount_appflobIOEjI/AppFlowy: error while loading shared libraries: libkeybinder-3.0.so.0: cannot open shared object file: No such file or directory`
    - This is dependency issue, installing `keybinder3` solve the issue. I don't think I can do anything from my side, maybe document it on the docs.

- [ ] TEST: test probably use AppImageKit, better to make sure it is only used for though.
- [ ] #TEST: test.bash need another command --use-cache, --no-cache which remove and not remove
- [ ] is it better to use functional programming?
- [ ] dev(test): manual test script need network exception error handling
- [ ] mv neovim to usr bin to use appimage neovim
      mv /tmp/nvim.appimage /usr/local/bin/nvim

## backlog

- [ ] Add kde wallet support via dbus-python.
      dbus-python used on kdewallet saves, so we can add that to auth later as a support.
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

- [ ] Allow users to specify target architecture (ARM, x86_64, etc.)
- [ ] Switch to stable releases only when we publish stable versions (currently using prereleases in upgrade module)

## done

- [x] fix: remove service can't remove caches!
- [x] unused comma seperate function on commands/base.py
- [x] P2: #BUG: Cycle, circular import detected in import chain for cache.py
- [x] we use logger.info so much, maybe we can disable logger.info on progress.py but keep logger info default on other modules for better user experience?
    - [x] progress.py logger.info disable by default
    - [x] other modules keep logger.info default
- [x] Cleanup unused code lines
    - [x] update.py unused progress task id lines
    - [x] install.py and update.py module lines so much, better to move some of the functions to utils module. For example, creating_desktop_entry, parse_github_url etc.
- [x] fix: integration test couldn't skipeable test
    - [x] integration logger test is slow because of logger rotation, need to fix that
- [x] cleanup folder structure for better structure
    - [x] move asset and release.py from domain to correct folder
- [x] token save, remove not work on zsh completion?
- [x] remove unused autocomplete flags from auth for save remove token and backup --migrate flag
- [x] P1: remove icon download logic because we extract icon from appimage now.
- [x] beekeper-studio.png is wrong, extract manually and find the correct icon
- [x] P3: Catalog and app state config structure refactor
    - [x] Move owner, repo to github section
    - [x] Better structure
    - [x] Migration logic automatically on old config detected(decided to make a seperate command)
        - [x] Make a new plan for more simple migration logic
        - [x] via script?
        - [x] via code on startup? Current one `class AppConfigV2(TypedDict):` used like this. Seems like violate DRY prenciple.
    - [x] Update docs
    - [x] add description to catalogs
    - [x] show description on list --available command
- [x] add verification passed or not to verification section on app-specific config
- [x] dev(improve): rename list.py to catalog.py and all it's commands list to catalog
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
