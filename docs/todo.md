# TODO List

## testing

- [~] #BUG: Rotation error on logs...
    - not keep the old ones in .1, .2, .3, instead it is also clear those too.
    - This happened when I try to update with the update.bash and cancelled the update.
- [~] appimage build take times
    - [x] install/update show installation error reasons(show appimage build takes times)
    - [ ] take care the edge cases, maybe app not have appimage at all?
- [~] Remove overengineering
    - [ ] dataclasses
    - [ ] strategy
          " If you only have a couple of algorithms and they rarely change, there’s no real reason to overcomplicate the program with new classes and interfaces
          that come along with the pattern." by <https://refactoring.guru/design-patterns/strategy>
    - [x] template
          "Template methods tend to be harder to maintain the more steps they have.
          You might violate the Liskov Substitution Principle by suppressing a default step implementation via a subclass.
          " by <https://refactoring.guru/design-patterns/template-method>

## in-progress

- [ ] update.bash check network connection
- [ ] png need priority one because kde not show .svg on its bar when pinned
- [ ] update docs with mermaid, use copilot to create them it seems copilot handles mermaid pretty well
- [ ] #BUG: is backup folder not created after new feature? test qownnotes when there is update available
- [~] refactor
  <https://refactoring.guru/refactoring/smells>
    - [x] general
    - [x] logger
    - [x] scripts
    - [ ] config
    - [ ] handle FIXME, TODO for duplicate functions
    - [x] service.progress already active
    - [ ] services
    - [ ] utils.py seperated folders
    - [ ] strategies
    - [ ] reading code from top to bottom
    - [ ] functions instead of comments
    - [ ] contexts
    - [ ] remove license, contribution from readme.md because there is already markdown files for them

## todo

- [ ] API rate limiting
- [ ] #BUG: Cycle detected in import chain for cache.py
- [ ] dev(improve): rename list.py to catalog.py and all it's commands list to catalog
- [ ] TEST: test probably use AppImageKit, better to make sure it is only used for though.
- [ ] #TEST: test.bash need another command --use-cache, --no-cache which remove and not remove
- [ ] is it better to use functional programming?
- [ ] dev: lets load global config on the app starts because we need to access those
- [ ] dev: build with uv
- [ ] dev(docs): libsecret also our prerequested dependency,
- [ ] dev(improve): our logger use singleton
- [ ] dev(test): manual test script need network exception error handling
- [ ] python security practices
- [ ] good to use aiodns with aiohttp
- [ ] might be better to use loguru
- [ ] mv neovim to usr bin to use appimage neovim
      mv /tmp/nvim.appimage /usr/local/bin/nvim
- [ ] make sure tha decrease files on template and move them to one file to read more easy and make it function base utilities for it
- [ ] make sure skip not skip verification if there is verification option
    - tested obsidian and it seems work but we need to make sure about it.
- [ ] upgrade need auto easy update and notify like appimages
- [ ] config structure refactor
- [ ] log rotation fix
- [ ] things tested and need updates
    - [ ] general test
    - [ ] fish terminal, kitty terminal not good with rich library but alacrity good(artifacts on bars)
    - [x] auth log info, validation
    - [ ] add my unicorn export path to fish shells
    - [ ] kde wallet support via dbus-python, test in the shared folder 3. kdewallet isn't show any token saved which seems like we don't support ito. written script to keyring-my-unicorn folder, check that out.
          dbus-python used on kdewallet saves, so we can add that to auth later as a support.

- [ ] #BUG: digest not became true on catalog installs if its use checksum_file with digest verify both
- [ ] add verification passed or not to verification section on app-specific config
- [ ] #BUG: upgrade command get stable cache 1.2.3 version for my-unicorn repo
- [ ] #TEST: bdd style tests
- [ ] #TEST: make sure standard-notes naming work as expected with new features like cache
- [ ] read all the test from stratch with your examples to make sure they work as expected like examples not good current
- [ ] circular import problem

## backlog

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

- [ ] typer, click libraries

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
