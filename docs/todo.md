# TODO List

- Use this for keeping simple todo stuff like;
    - Manual reviews, tests
    - Learn stuff
    - Simple bugfixes
    - Simple todo tasks like typos, restructure
    - Developer tasks like design pattern, api, architecture

- Use issues for big tasks like;
    - Adding new features
    - Refactoring big modules
    - Fixing big bugs which require big code changes

## testing

- [ ] Big reviews
    - [ ] Network retry logic
    - [ ] API rate limiting
    - [x] Logger rotation logic
    - [x] Logger rotation on virtual machine
    - [x] Logger rotation on production

- [x] add --force option to uv tool install on all of your project to prevent issue

## in-progress

- [ ] P1-Q1: Open Issues per big todo for all below, it is hard to follow big tasks, keep this todo.md only for simple stuff like learn this, review this, test this etc. use issues like directly implementing big stuff like improving tests, adding new feature etc.

- [ ] add remove --all command
- [ ] progress_service written optional but we must make it required. Only upgrade module not use it currently and not need to use it because upgrade module only use uv package manager to handle the installation and update process.
- [ ] make sure that user log console level is INFO and mandotory, like force user to use that on config, remove user configuration that option

- [ ] Need to check appimages installed or corrupted, same for others like .desktop, icon etc. which if we switch to new distro and move our configs, we can't be able to install all of our apps via my-unicorn cli configs because we save the configs to save names, reference, version etc. and than use that version to compare is there any new app etc. we can't even check if appimage exist or not we just check the .json file stay on the config location, we don't check any other .desktop exist or not... so we need to check appimages installed or not for better error handling and we need to find out what we can do about installing more than one file from scratch via app config or another installed database via .jsonl to handle that and another share... location to use active installed ones etc. etc. For example; we can use another jsonl database but that's also make things more complicated and probably non-sense which we already have .json files for that, we need another solution to handle fast installation for all installed apps, maybe we can add export command to export all the installed ones to a jsonl file and than we can use that file to install via my-unicorn easily to make easy installs for new distros or when we switch to new distro etc. but exporting names of the apps is realy enough for the catalog installed ones which we can just write the `install <app-name> <app_name2> ...` to install all of them ones more simply without botherin jsonl, and for the url we can export urls to another file because we can't install url via catalog install, so we can export another and than we can install via cli later via `install <url1> <url2> ...` so that would be more easy to handle and we don't bother with jsonl.




- [ ] supported catalog apps: muffon, simpmusic, spotube(test), pear-desktop
- [ ] Improve testing
    - [ ] Refactor folder e2e tmp files, move it to tmp/pytest-of-<user>-e2e/ for better structure
    - [ ] Make pytest log level DEBUG, better to setup env for that for easy pytest changes without bothering the settings.conf. In real world cli tools priority; env > config file
    - [x] P1-Q3: Never use the real user config logs, app location on pytest unittests which current is use them! #p1 #important #q3
    - [x] write ui integration test for progress bar
    - [x] Write e2e testing (Seems like scripts/test.py belongs to there and can be work with pytest)
    - [x] structure improve

- [ ] P1-Q1: improve e2e tests #p1 #q1 #important #testing
    - [ ] add backup test to --quick flag on test.py
    - [ ] add --refresh-cache flag to --quick and --all flags to make sure cache also work after test passed without refresh cache flag.
    - [ ] Update container to test with this manual test script, so we don't need to test in our local machine.
        - [ ] add env variable support for github token to use on container tests.
        - [ ] add flag to close progress bar on cli for better support on ci tests.
    - [ ] make sure the api fetch install works (we do that by remove and install on manual test script but seems like remove didn't removed the cache and I couldn't able to detect the api bug correctly, so we need to make manual test to make sure remove did it's job correctly etc.)
    - [ ] add backup tests to make sure backup command also work as expected on tests etc.
    - [ ] add new command to manual test script like `--slow` for big apps like joplin.
    - [ ] add new command to test remove, upgrade, migrate commands.

add a diagnose test after the test done to make sure everything is fine after all tests
we can do a something like return a report at the end of the tests with diagnose output etc.
current test summary couldn't detect the failed passed correctly but we can make
comprehensive report by checking the appimage config, backup metedata, check appimage location, desktop entry etc. all of the things to make sure everything is fine after the tests.
we probably need to define one correct example or we can just use the json scheme

- [ ] Not write computed when failed

```json
{
  "catalog_ref": "super-productivity",
  "config_version": "2.0.0",
  "source": "catalog",
  "state": {
    "icon": {
      "installed": true,
      "method": "extraction",
      "path": "/home/gamer/Applications/icons/super-productivity.png"
    },
    "installed_date": "2026-02-18T20:51:49.297441+03:00",
    "installed_path": "/home/gamer/Applications/super-productivity.AppImage",
    "verification": {
      "methods": [
        {
          "algorithm": "SHA256",
          "computed": "17949b253c93d004849b5bb04c0647cf4cf95d7f89ec66e59cd2b9bd08866b82",
          "expected": "sha256:17949b253c93d004849b5bb04c0647cf4cf95d7f89ec66e59cd2b9bd08866b82",
          "source": "github_api",
          "status": "passed",
          "type": "digest"
        },
        {
          "algorithm": "SHA256",
          "computed": "",
          "expected": "sha512:8ca635e2956ef992780c9c45a1e10eedf5139cca6d0bff94699751f1590bbd9b58453e17ccb8e7d8d9dfe4ad086c26c4a593152eff60b25fd975a3ee03547c37",
          "source": "",
          "status": "failed",
          "type": "checksum_file"
        }
      ],
      "passed": true
    },
    "version": "17.1.8"
  }
}
```

- [ ] LEARN: Learn more about testing;
    - [ ] Learn Schemathesis
    - [ ] Learn <https://hypothesis.readthedocs.io/en/latest/stateful.html>
    - [ ] Learn <https://realpython.com/python-cli-testing/#lo-fi-debugging-with-print>
    - [x] Learn and add integration tests after workflows refactor.

- [ ] Refactor: Cleaning up dead codes;
    - [ ] remove unused from types.py
    - [ ] P1: Remove desktop_entry.py and other similar modules that only export things for backward compatbility.
    - [ ] P1-Q2: deprecate my-unicorn package and repo directories (migrated to uv) #q2 #important #refactor
    - [ ] P9: remove unused `"method": "extraction",` from icon app state which we only use extraction type now.

- [ ] P1: refactor core/update/update.py to better architecture for update all command and update with appimage names.
    - [ ] Example; `my-unicorn update` would update all apps, `my-unicorn update appflowy qownnotes` would update only qownnotes and appflowy.
- [ ] remove interactive argument on the AsciiProgressBackend when you understand what it's do which we don't use any kind of interactive mode on our progress bar, so we can remove that and just use the output.isatty() to detect the interactive mode if needed.

- [ ] LEARN: Improve code quality with better practices:
    - [ ] <https://github.com/carlosperate/awesome-pyproject?tab=readme-ov-file#testing>
    - [ ] learn dependency injection better which seems like protocol used for that to make better decoupling.
    - [ ] <https://github.com/ArjanCodes/betterpython/blob/main/1%20-%20coupling%20and%20cohesion/coupling-cohesion-after.py>
    - [ ] <https://docs.python-guide.org/writing/style/>
    - [ ] learn Makefile
    - [ ] learn testing trophy philosophy

- [ ] Improve agents.md
    - [x] <https://github.com/langchain-ai/langchain/blob/master/AGENTS.md>
    - [ ] <https://alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/>

- [ ] use functools.cache for reading json files, caches for performance?

- [ ] P4-Q7: backup create command feature -> will make a backup directly from the command line `my-unicorn backup create appflowy` or `my-unicorn backup create --all` for all apps.
- [ ] p1-q1: load app config one time instead of loading on every function call like remove, backup, update... etc.

- [ ] P1-Q2 decrease all the modules lines to less than 500 lines for better structure and maintainability.
    - [ ] workflows/update.py
    - [ ] workflows/install.py

- [ ] P2-Q4: fix all mypy issues #p2 #important #q4
- [ ] P3-Q6: Correct comman design pattern with receiver and invoker, commands need to be thin and execute receivers only, learn from examples/patterns/Command/ folder

## todo

- [ ] Refresh cache flag is update the caches by request api again but github releases section seems not update it. It might be related with the our class get it from cache even we use api because of the way we implemented the cache, so we need to check that and make sure it is working as expected. Below is the log for that, we can see that github releases section is not updated but api section is updated.

```bash
uv run my-unicorn update --refresh-cache
Fetching from API:
GitHub Releases      1/1 Retrieved from cache
```

- [ ] P2: redundant remove prints:

```
2026-01-28 13:22:47 - my_unicorn.core.remove - DEBUG - _remove_appimage_files:276 - Removed AppImage: /home/developer/Applications/neovim.AppImage
2026-01-28 13:22:47 - my_unicorn.core.cache - DEBUG - clear_cache:222 - Cleared cache for neovim/neovim
2026-01-28 13:22:47 - my_unicorn.core.remove - DEBUG - _clear_cache:300 - Removed cache for neovim/neovim
2026-01-28 13:22:47 - my_unicorn.core.desktop_entry - DEBUG - remove_desktop_file:431 - Removed desktop file: /home/developer/.local/share/applications/neovim.desktop
2026-01-28 13:22:47 - my_unicorn.core.remove - DEBUG - _remove_desktop_entry:354 - Removed desktop entry for neovim
2026-01-28 13:22:47 - my_unicorn.core.remove - DEBUG - _remove_icon:379 - Removed icon: /home/developer/Applications/icons/neovim.png
2026-01-28 13:22:47 - my_unicorn.core.remove - DEBUG - _remove_config:399 - Removed config for neovim
2026-01-28 13:22:47 - my_unicorn.core.remove - INFO - _log_removal_results:200 - ✅ Removed AppImage(s): /home/developer/Applications/neovim.AppImage
2026-01-28 13:22:47 - my_unicorn.core.remove - INFO - _log_removal_results:203 - ✅ Removed cache for neovim/neovim
2026-01-28 13:22:47 - my_unicorn.core.remove - INFO - _log_removal_results:216 - ⚠️  No backups found at: /home/developer/Applications/backups/neovim
2026-01-28 13:22:47 - my_unicorn.core.remove - INFO - _log_removal_results:219 - ✅ Removed desktop entry for neovim
2026-01-28 13:22:47 - my_unicorn.core.remove - INFO - _log_removal_results:223 - ✅ Removed icon: /home/developer/Applications/icons/neovim.png
2026-01-28 13:22:47 - my_unicorn.core.remove - INFO - _log_removal_results:230 - ✅ Removed config for neovim
```

- [ ] P4: cli upgrade command need notification for itself, maybe update command would invoke upgrade command or check my-unicorn as repo?
- [ ] P4: Remove code smells: <https://refactoring.guru/refactoring/smells>
    - [ ] contexts
    - [ ] config
    - [x] handle FIXME, TODO for duplicate functions
- [ ] config --show is showing global config, better to name it --show-global-config for more clarity
- [ ] performance improvements on api : <https://github.com/xbeat/Machine-Learning/blob/main/9%20Strategies%20to%20Boost%20API%20Performance.md>
    - [ ] APIGateway would be useful when we impemented gitlab support
    - [ ] GraphQL-like query system for REST APIs
- [ ] Add command to migrate from URL installs to Catalog installs
      Example; `my-unicorn migrate --app appflowy` or `my-unicorn migrate --all`
      but we use migrate command to migrate old config to new config structure
      so we need to use flags like `--from-url-to-catalog` or something like that.

- [ ] Add option in global config for [auth]
- [ ] What about threading usage on logging? Example: <https://github.com/Roulbac/uv-func/blob/main/src/uv_func/logging.py>

- [ ] Script Tasks;
    - [ ] P2: update.bash check network connection
    - [ ] add fish autocomplete support

- [ ] add autocompletion for the catalog apps to autocomplete app names (e.g: `super<tab>-productivity`)

- [ ] mv neovim to usr bin to use appimage neovim
      mv /tmp/nvim.appimage /usr/local/bin/nvim

## backlog

- [ ] Add kde wallet support via dbus-python.(check plans/keyring-for-my-unicorn folder )
      dbus-python used on kdewallet saves, so we can add that to auth later as a support.

```python
# Example kdewallet usage via keyring library
import keyring
import dbus
from keyring.backends.kwallet import DBusKeyring  # explicit KWallet backend

def store_password(service: str, username: str, password: str):
    keyring.set_keyring(DBusKeyring())
    keyring.set_password(service, username, password)
    print(f"Stored password for {username}@{service} using KWallet.")

def retrieve_password(service: str, username: str):
    keyring.set_keyring(DBusKeyring())
    pwd = keyring.get_password(service, username)
    if pwd:
        print(f"Retrieved password: {pwd!r}")
    else:
        print("No password found in KWallet.")

if __name__ == "__main__":
    svc = "myservice"
    user = "demo"
    pwd = "s3cr3t"

    store_password(svc, user, pwd)
    retrieve_password(svc, user)

```

- [ ] P4: Add progress bar for checksum file installations?
- [ ] python security practices
- [ ] might be better to use loguru
- [ ] add my unicorn export path to fish shells
- [ ] #TEST: bdd style tests
- [ ] Simple video about cli tool workflow
- [ ] good to use aiodns with aiohttp
- [ ] add env variable support for github token to use on container tests.
- [ ] good cli design princibles (WIP, LEARN MORE)
      <https://clig.dev/>
      <https://www.amazon.com/UNIX-Programming-Addison-Wesley-Professional-Computng/dp/0131429019>
      - [ ] Write man pages
      - [ ] Add env to disable emojis or directly remove emojis?
      - [ ] Implement did you mean? for typos and dangerous commands
      - [ ] Use subcommands for better structure (Go/Docker/AWS style) rather than a flat assortment of flags
      - [ ] If you are displaying tabular data, present an ncurses interface
      - [ ] Don't use escape codes in your output. Use the library that is designed for this purpose: terminfo??

- [ ] Allow users to specify target architecture (ARM, x86_64, etc.)
- [ ] Switch to stable releases only when we publish stable versions (currently using prereleases in upgrade module)

## done

- [x] workflows and workflows/services folder structure refactor for better structure.
      Currently install.py, update.py, appimage_setup.py(install and update use this, so I didn't move that to util folder which we might be make a new module to handle it there in class etc.) is work together.
- [x] #BUG: upgrade command get stable cache 1.2.3 version for my-unicorn repo
- [ ] #TEST: test.bash need another command --use-cache, --no-cache which remove and not remove
- [x] P1: BUG: missing computed hashes on verified app when used checksum_file (example tagspace) this happens on update command, install command show the hashes computed etc.

```json
      "methods": [
        {
          "algorithm": "sha256",
          "filename": "SHA256SUMS.txt",
          "status": "passed",
          "type": "checksum_file"
        }
      ],

            "methods": [
        {
          "algorithm": "SHA256",
          "source": "github_api",
          "status": "passed",
          "type": "digest"
        },
        {
          "algorithm": "SHA256",
          "source": "https://github.com/tagspaces/tagspaces/releases/download/v6.8.2/SHA256SUMS.txt",
          "status": "passed",
          "type": "checksum_file"
        }
      ],
```

- [x] P1:BUG: cache also won't save the checksum_file if digest exist?

```json
{
  "cached_at": "2026-02-04T15:04:13.654171+03:00",
  "ttl_hours": 24,
  "release_data": {
    "owner": "tagspaces",
    "repo": "tagspaces",
    "version": "6.8.2",
    "prerelease": false,
    "assets": [
      {
        "name": "tagspaces-linux-x86_64-6.8.2.AppImage",
        "size": 159537674,
        "digest": "sha256:3c8ca310ab79d09202b55c2a832d5d09c7caf81c5db2270821dc05e90172e2df",
        "browser_download_url": "https://github.com/tagspaces/tagspaces/releases/download/v6.8.2/tagspaces-linux-x86_64-6.8.2.AppImage"
      }
    ],
    "original_tag_name": "v6.8.2"
  }
}
```

- [x] Remove legacy cli tool install from install.sh
- [x] Create architecture-blueprint file
- [x] try git worktree, is it really can be good?
- [x] P3-Q5: move workflow folder modules to utils folder for better structure
- [x] catalog_adapter.py is probably unnecessary because it just delegate the config manager...
- [x] Test new features
    - [x] github action for releases
    - [x] `my-unicorn upgrade` command now use uv package manager.
    - [x] Test `migrate` command
    - [x] Test `migrate` command on virtual machine.
- [x] use orjson for the migrate modules for better performance
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
- [x] read all the test from stratch with your examples to make sure they work as expected like examples not good current
- [x] update docs with mermaid, use copilot to create them it seems copilot handles mermaid pretty well
- [x] is it better to use functional programming?
- [x] TEST: test probably use AppImageKit, better to make sure it is only used for though.
- [x] P3: #BUG: when there is one fail(keepassxc fails on checksum because external
      issue by devs) on verification but our ui not show when
      there is one verification success, so it might be better to show the failed and success.
      Also need to fix ui progress bar created two time because of this issue.

- [x] P4: remove legacy upgrade command
- [x] P1: png need priority one because kde not show .svg on its bar when pinned
- [x] add token command and use it as token storage etc. keep auth command for authentication only.
- [x] writing every test from scratch for better understanding of tests and make sure they work as expected
    - [x] cli tests
    - [x] commands tests
    - [x] integration tests
    - [x] migration tests
    - [x] services tests
    - [x] schemas tests
- [x] P1-Q8: add lock for one instance only to prevent multiple instance run at the same time via fcntl.flock and make sure it would work for asyncio
    - [x] 16G error log, because of 2 instance running at the same time.(This solved by logger rotation fix but still better to add lock to prevent multiple instance run at the same time)
