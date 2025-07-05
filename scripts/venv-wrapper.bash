#!/usr/bin/env bash
# Wrapper script around my-unicorn using the python virtual environment

set -eu

# bailout function
err_exit() {
  echo "$(basename $0): ${1:-wrong invocation. try --help for help.}" 1>&2
  exit 1
}

# Use XDG_DATA_HOME or fallback to ~/.local/share
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
install_dir="$XDG_DATA_HOME/my-unicorn"
venv_bin_dir="$install_dir/venv/bin"

# Check if installation exists
if [[ ! -d "$install_dir" ]]; then
  err_exit "my-unicorn not found at $install_dir. Run setup.sh first."
fi

if [[ ! -d "$venv_bin_dir" ]]; then
  err_exit "Virtual environment not found at $venv_bin_dir. Run setup.sh first."
fi

# Load python virtual environment
source "$venv_bin_dir/activate"

# Execute my-unicorn with all passed arguments
# Since it's installed as a console script, we can call it directly
exec "$venv_bin_dir/my-unicorn" "$@"
