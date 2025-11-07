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

# The line to add to shell rc files to ensure ~/.local/bin is in PATH
EXPORT_LINE="export PATH=\"\$HOME/.local/bin:\$PATH\""

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

# Detect which shell rc file to update for PATH (bash or zsh)
detect_rc_file() {
  local rc user_shell
  user_shell="$(basename "${SHELL:-}")"
  case "$user_shell" in
  zsh)
    rc="$HOME/.zshrc"
    [[ -f "$HOME/.config/zsh/.zshrc" ]] && rc="$HOME/.config/zsh/.zshrc"
    ;;
  bash)
    rc="$HOME/.bashrc"
    ;;
  *)
    rc="$HOME/.bashrc"
    ;;
  esac
  # Create the file if it doesn't exist
  [[ ! -f "$rc" ]] && touch "$rc"
  echo "$rc"
}

# Ensure PATH line is present in a given file
# $1 = rc file path
# $2 = position (optional: prepend|append, default append)
ensure_path_in_file() {
  local rc_file="$1"
  local position="${2:-append}"

  [[ ! -f "$rc_file" ]] && touch "$rc_file"

  if ! grep -Fxq "$EXPORT_LINE" "$rc_file"; then
    if [[ "$position" == "prepend" ]]; then
      # Put PATH export at the very top
      {
        echo "# Added by my-unicorn installer"
        echo "$EXPORT_LINE"
        echo
        cat "$rc_file"
      } >"$rc_file.tmp" && mv "$rc_file.tmp" "$rc_file"
      echo "Added PATH to top of $rc_file"
    else
      # Add PATH export at the bottom
      printf '\n# Added by my-unicorn installer\n%s\n' "$EXPORT_LINE" >>"$rc_file"
      echo "Added PATH to bottom of $rc_file"
    fi
  else
    echo "ℹ️ PATH already configured in $rc_file"
  fi
}

# Ensure PATH is set for both bash and zsh shells
# - Prepend for bashrc so it’s loaded before anything else
# - Append for zshrc so it runs after bashrc in login shell chains
ensure_path_for_shells() {
  local bashrc="$HOME/.bashrc"
  local zshrc="$HOME/.zshrc"

  [[ -f "$HOME/.config/zsh/.zshrc" ]] && zshrc="$HOME/.config/zsh/.zshrc"

  ensure_path_in_file "$bashrc" prepend
  ensure_path_in_file "$zshrc" append
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

# Create or update virtual environment and install package in editable mode
setup_venv() {
  if has_uv; then
    echo "🐍 Creating/updating virtual environment with UV in $VENV_DIR..."
    cd "$INSTALL_DIR"
    uv venv "$VENV_DIR" --clear
    # shellcheck source=/dev/null
    source "$BIN_DIR/activate"
    echo "📦 Installing my-unicorn with UV (editable mode)..."
    uv pip install -e "$INSTALL_DIR"
    cd - >/dev/null
  else
    echo "🐍 Creating/updating virtual environment with pip in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    # shellcheck source=/dev/null
    source "$BIN_DIR/activate"
    python3 -m pip install --upgrade pip wheel
    echo "📦 Installing my-unicorn (editable) into venv..."
    python3 -m pip install -e "$INSTALL_DIR"
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

# Full installation process
install_my_unicorn() {
  echo "=== Installing my-unicorn ==="
  copy_source_to_install_dir
  setup_venv
  install_wrapper
  ensure_path_for_shells
  setup_autocomplete

  local rc
  rc=$(detect_rc_file)

  echo "✅ Installation complete."
  echo "Restart your shell or run 'source $rc' to apply PATH."
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
*)
  cat <<EOF
Usage: $(basename "$0") [install|update|autocomplete]

  install       Full installation with autocomplete
  update        Update venv and autocomplete
  autocomplete  Install shell completion only

Examples:
  $(basename "$0") install            # Full installation (default)
  $(basename "$0") update             # Update virtual environment and autocomplete
  $(basename "$0") autocomplete       # Install completion for current shell
EOF
  exit 1
  ;;
esac
