# Helper Scripts

Helper scripts for managing the my-unicorn project.

- Updater: `scripts/update.bash` is automate the my-unicorn cli usage with one command. It can be used in window manager widgets, cron jobs, or manually.
- Installer: `./setup.sh` (top-level) installs the project into your XDG data dir, creates a virtualenv, installs a small wrapper executable, and sets up shell completion.
- Wrapper: `scripts/venv-wrapper.bash` provides helper functions when sourced; the installer will copy a wrapper executable to `~/.local/bin/my-unicorn` for everyday use.
- Autocomplete: `scripts/autocomplete.bash` provides shell completion snippets.
- Tests: `scripts/test.bash` runs the manual (real installation) test suite.

See also: `docs/wiki.md` for full documentation.
