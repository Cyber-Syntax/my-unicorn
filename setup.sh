#!/usr/bin/env bash
#
# setup.sh
# ------------------------------------------------
# User-level installer & updater for "my-unicorn"
# - Copies project files into XDG user data directory
# - Creates/updates Python virtual environment
# - Installs wrapper script and ensures PATH configuration
# - Sets up shell autocomplete (bash/zsh)
#
# Usage:
#   ./setup.sh install   # Install or reinstall (includes autocomplete)
#   ./setup.sh update    # Update venv and autocomplete
#
# Exit immediately if:
# - a command exits with a non-zero status (`-e`)
# - an unset variable is used (`-u`)
# - a pipeline fails anywhere (`-o pipefail`)
set -euo pipefail

# -- Configuration -----------------------------------------------------------

# Where user-specific data should be stored
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"

# Final install location of our project
INSTALL_DIR="$XDG_DATA_HOME/my-unicorn"

# Virtual environment directory inside install dir
VENV_DIR="$INSTALL_DIR/venv"

# Virtual environment bin folder (where python/pip are located)
BIN_DIR="$VENV_DIR/bin"

# Source of our wrapper script (inside repo)
WRAPPER_SRC="$INSTALL_DIR/scripts/venv-wrapper.bash"

# Destination of wrapper script in user's PATH
WRAPPER_DST="$HOME/.local/bin/my-unicorn"

# -- Helper functions --------------------------------------------------------

# Log messages to stderr
log() {
  printf '%s\n' "$*" >&2
}

# Get absolute directory path of currently running script (resolves symlinks)
script_dir() {
  local src="${BASH_SOURCE[0]}"
  while [ -h "$src" ]; do
    src="$(readlink "$src")"
  done
  dirname "$src"
}

# Check if $HOME/.local/bin is in PATH and inform user if not
check_local_bin_in_path() {
  # Check if ~/.local/bin is already in PATH
  if [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
    echo "✅ $HOME/.local/bin is already in your PATH"
    return 0
  fi
  
  # Not in current PATH - inform the user
  cat <<EOF

⚠️  IMPORTANT: ~/.local/bin is not in your PATH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
To use 'my-unicorn' from anywhere, please add the following line to
your shell configuration file (~/.bashrc, ~/.zshrc, ~/.zshenv, etc.):

    export PATH="\$HOME/.local/bin:\$PATH"

Then restart your shell or run:
    source ~/.bashrc  (for bash)
    source ~/.zshrc   (for zsh)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
  return 1
}

# Copy source files to install directory
copy_source_to_install_dir() {
  echo "📁 Copying source files to $INSTALL_DIR..."
  local src_dir
  src_dir="$(script_dir)"
  mkdir -p "$INSTALL_DIR"

  # Source files to copy
  for item in my_unicorn scripts pyproject.toml autocomplete "$(basename "$0")"; do
    local src_path="$src_dir/$item"
    local dst_path="$INSTALL_DIR/$item"
    if [ -e "$src_path" ]; then
      if [ -d "$src_path" ]; then
        rm -rf "$dst_path"
        cp -r "$src_path" "$dst_path"
      else
        cp "$src_path" "$dst_path"
      fi
    else
      echo "⚠️  Warning: $item not found in $src_dir"
    fi
  done
}

# Check if UV is available
has_uv() {
  command -v uv >/dev/null 2>&1
}

# Install using uv tool (recommended for production)
install_with_uv_tool() {
  echo "🚀 Installing my-unicorn using 'uv tool install'..."
  local src_dir
  src_dir="$(script_dir)"

  if ! has_uv; then
    echo "❌ UV is not installed. Please install UV first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi

  cd "$src_dir"
  uv tool install git+https://github.com/Cyber-Syntax/my-unicorn
  check_local_bin_in_path
  
  # For uv tool installs, run autocomplete setup from source directory
  local autocomplete_helper="$src_dir/scripts/autocomplete.bash"
  if [[ -x "$autocomplete_helper" ]]; then
    echo "🔁 Setting up autocomplete..."
    bash "$autocomplete_helper"
  else
    echo "⚠️  Warning: Autocomplete helper not found at $autocomplete_helper"
  fi

  copy_update_script

  echo "✅ Installation complete using uv tool."
  echo "Run 'my-unicorn --help' to get started."
}

# Update using uv tool (for production installations)
update_with_uv_tool() {
  echo "🔄 Updating my-unicorn using 'uv tool install --reinstall'..."
  local src_dir
  src_dir="$(script_dir)"

  if ! has_uv; then
    echo "❌ UV is not installed. Please install UV first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi

  cd "$src_dir"
  git pull || echo "⚠️  Warning: Could not update git repository"
  uv tool upgrade my-unicorn || uv tool install --force .
  
  # For uv tool installs, run autocomplete setup from source directory
  local autocomplete_helper="$src_dir/scripts/autocomplete.bash"
  if [[ -x "$autocomplete_helper" ]]; then
    echo "🔁 Setting up autocomplete..."
    bash "$autocomplete_helper"
  else
    echo "⚠️  Warning: Autocomplete helper not found at $autocomplete_helper"
  fi

  copy_update_script

  echo "✅ Update complete using uv tool."
}

# Install using uv tool in editable mode (for development)
install_with_uv_editable() {
  echo "🔧 Installing my-unicorn in editable mode using 'uv tool install --editable'..."
  local src_dir
  src_dir="$(script_dir)"

  if ! has_uv; then
    echo "❌ UV is not installed. Please install UV first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi

  cd "$src_dir"
  uv tool install --editable .
  check_local_bin_in_path
  
  # For uv tool installs, run autocomplete setup from source directory
  local autocomplete_helper="$src_dir/scripts/autocomplete.bash"
  if [[ -x "$autocomplete_helper" ]]; then
    echo "🔁 Setting up autocomplete..."
    bash "$autocomplete_helper"
  else
    echo "⚠️  Warning: Autocomplete helper not found at $autocomplete_helper"
  fi

  copy_update_script

  echo "✅ Editable installation complete using uv tool."
  echo "Changes to source code will be reflected immediately."
  echo "Run 'my-unicorn --help' to get started."
}

# Create or update virtual environment and install packages
setup_venv() {
  if has_uv; then
    echo "🐍 Creating/updating virtual environment with UV in $VENV_DIR..."
    cd "$INSTALL_DIR"
    uv venv "$VENV_DIR" --clear
    # shellcheck source=/dev/null
    source "$BIN_DIR/activate"
    echo "📦 Installing my-unicorn with UV..."
    uv pip install "$INSTALL_DIR"
    cd - >/dev/null
  else
    echo "🐍 Creating/updating virtual environment with pip in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    # shellcheck source=/dev/null
    source "$BIN_DIR/activate"
    python3 -m pip install --upgrade pip wheel
    echo "📦 Installing my-unicorn into venv..."
    python3 -m pip install "$INSTALL_DIR"
  fi
}

# Install wrapper script into ~/.local/bin so `my-unicorn` works globally
install_wrapper() {
  echo "🔧 Installing wrapper to $WRAPPER_DST..."
  mkdir -p "$(dirname "$WRAPPER_DST")"
  cp "$WRAPPER_SRC" "$WRAPPER_DST"
  chmod +x "$WRAPPER_DST"
}

# Set up shell autocomplete by delegating to autocomplete.bash
setup_autocomplete() {
  local helper="$INSTALL_DIR/scripts/autocomplete.bash"

  # Fallback to source directory if installed version not available
  if [[ ! -x "$helper" ]]; then
    local src_helper
    src_helper="$(script_dir)/scripts/autocomplete.bash"
    [[ -x "$src_helper" ]] && helper="$src_helper"
  fi

  if [[ -x "$helper" ]]; then
    echo "🔁 Setting up autocomplete..."
    bash "$helper"
  # call install_myunicorn to get the new autocomplete folder, else fail
  elif [[ -x "$(script_dir)/scripts/autocomplete.bash" ]]; then
    echo "🔁 Installing my-unicorn to get the new autocomplete folder..."
    install_my_unicorn
  else
    echo "❌ Autocomplete helper script not found or not executable"
    return 1
  fi
}

# Copy update script to shared location for UV installs
copy_update_script() {
  local src_dir
  src_dir="$(script_dir)"
  local src_path="$src_dir/scripts/update.bash"
  local dst_path="$HOME/.local/bin/my-unicorn-update"
  if [ -f "$src_path" ]; then
    mkdir -p "$HOME/.local/bin"
    cp "$src_path" "$dst_path"
    chmod +x "$dst_path"
    echo "✅ Update script copied to $dst_path"
  else
    echo "⚠️  Warning: Update script not found at $src_path, skipping copy."
  fi
}

# Full installation process
install_my_unicorn() {
  echo "=== Installing my-unicorn ==="
  copy_source_to_install_dir
  setup_venv
  install_wrapper
  check_local_bin_in_path
  setup_autocomplete

  echo "✅ Installation complete."
  echo "Run 'my-unicorn --help' to get started."
}

# Update virtual environment and source files to get new features
update_my_unicorn() {
  echo "=== Updating my-unicorn ==="
  copy_source_to_install_dir
  setup_venv
  install_wrapper
  setup_autocomplete
  echo "✅ Update complete."
}

# Standalone autocomplete installation
install_autocomplete() {
  echo "my-unicorn Autocomplete Installation"
  echo "========================================"

  # Check if my-unicorn is installed
  if [[ ! -d "$INSTALL_DIR" ]]; then
    echo "❌ my-unicorn is not installed. Please run './setup.sh install' first."
    exit 1
  fi

  # Always copy fresh autocomplete files from source
  echo "📁 Updating autocomplete files..."
  local src_dir
  src_dir="$(script_dir)"
  mkdir -p "$INSTALL_DIR"

  # Copy autocomplete folder and scripts
  for item in autocomplete scripts; do
    local src_path="$src_dir/$item"
    local dst_path="$INSTALL_DIR/$item"
    if [ -e "$src_path" ]; then
      if [ -d "$src_path" ]; then
        rm -rf "$dst_path"
        cp -r "$src_path" "$dst_path"
      else
        cp "$src_path" "$dst_path"
      fi
    fi
  done

  if setup_autocomplete; then
    echo "✅ Autocomplete installation complete!"
    echo ""
    echo "Please restart your shell or source your shell's rc file to enable autocompletion."
    echo "Test completion by typing: my-unicorn <TAB>"
  else
    echo "❌ Autocomplete setup failed"
    exit 1
  fi
}

# -- Entry point -------------------------------------------------------------
case "${1-}" in
install | "") install_my_unicorn ;;
update) update_my_unicorn ;;
autocomplete) install_autocomplete ;;
uv-install) install_with_uv_tool ;;
uv-update) update_with_uv_tool ;;
uv-editable) install_with_uv_editable ;;
*)
  cat <<EOF
Usage: $(basename "$0") [install|update|autocomplete|uv-install|uv-update|uv-editable]

  install       Full installation with venv and autocomplete (default)
  update        Update venv and autocomplete
  autocomplete  Install shell completion only
  uv-install    Install using 'uv tool install' (recommended for production)
  uv-update     Update using 'uv tool install --reinstall' (production)
  uv-editable   Install using 'uv tool install --editable' (development)

Examples:
  $(basename "$0") install            # Full venv-based installation (legacy)
  $(basename "$0") update             # Update venv installation
  $(basename "$0") autocomplete       # Install completion for current shell
  $(basename "$0") uv-install         # Install as isolated tool (recommended)
  $(basename "$0") uv-update          # Update isolated tool installation
  $(basename "$0") uv-editable        # Install in editable mode (contributors)
EOF
  exit 1
  ;;
esac
