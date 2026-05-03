#!/usr/bin/env bash
#
# install.sh
# ------------------------------------------------
# User-level installer for "my-unicorn"
# - Copies project files into XDG user data directory
# - Creates/updates Python virtual environment
# - Installs wrapper script and ensures PATH configuration
# - Sets up shell autocomplete (bash/zsh/fish)
#
# Usage:
#   ./install.sh -i|--install   # Install or reinstall (includes autocomplete)
#   ./install.sh -e|--editable  # Install in editable mode (for development)
#   ./install.sh --autocomplete # Install shell completion only
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

# Check if UV is available and exit if not
check_uv_required() {
  if ! command -v uv >/dev/null 2>&1; then
    echo "❌ UV is not installed. Please install UV first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo " or you can use your package manager like 'brew install uv' or 'apt install uv'."
    exit 1
  fi
}

# Setup autocomplete from source directory
setup_autocomplete_from_src() {
  local src_dir="$1"
  local autocomplete_helper="$src_dir/scripts/autocomplete.bash"
  if [[ -x "$autocomplete_helper" ]]; then
    echo "🔁 Setting up autocomplete..."
    bash "$autocomplete_helper"
  else
    echo "⚠️  Warning: Autocomplete helper not found at $autocomplete_helper"
  fi
}

# Install using uv tool (recommended for production)
install_with_uv_tool() {
  echo "🚀 Installing my-unicorn using 'uv tool install'..."
  local src_dir
  src_dir="$(script_dir)"

  cd "$src_dir"
  uv tool install git+https://github.com/Cyber-Syntax/my-unicorn --force
  check_local_bin_in_path
  setup_autocomplete_from_src "$src_dir"
  setup_fish_completions
  copy_update_script

  echo "✅ Installation complete using uv tool."
  echo "Run 'my-unicorn --help' to get started."
}

# Install using uv tool in editable mode (for development)
install_with_uv_editable() {
  echo "🔧 Installing my-unicorn in editable mode using 'uv tool install --editable'..."
  local src_dir
  src_dir="$(script_dir)"

  cd "$src_dir"
  uv tool install --editable . --force
  check_local_bin_in_path
  setup_autocomplete_from_src "$src_dir"
  setup_fish_completions
  copy_update_script

  echo "✅ Editable installation complete using uv tool."
  echo "Changes to source code will be reflected immediately."
  echo "Run 'my-unicorn --help' to get started."
}

# Set up fish shell completions
setup_fish_completions() {
  local fish_dir="$HOME/.config/fish/completions"
  local fish_src="$INSTALL_DIR/completions/my-unicorn.fish"

  # Fallback to source directory if installed version not available
  if [[ ! -f "$fish_src" ]]; then
    fish_src="$(script_dir)/completions/my-unicorn.fish"
  fi

  if [[ -f "$fish_src" ]]; then
    if command -v fish &>/dev/null; then
      echo "Setting up fish completions..."
      mkdir -p "$fish_dir"
      cp "$fish_src" "$fish_dir/"
      echo "Fish completions installed to $fish_dir/my-unicorn.fish"
    fi
  fi
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
  # If helper is available in the source tree, attempt to install via uv to
  # populate the install directory (legacy non-uv installers removed).
  elif [[ -x "$(script_dir)/scripts/autocomplete.bash" ]]; then
    echo "🔁 Installing my-unicorn via 'uv' to get the new autocomplete folder..."
    install_with_uv_tool
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

# Standalone autocomplete installation
install_autocomplete() {
  echo "my-unicorn Autocomplete Installation"
  echo "========================================"
  # Always copy fresh autocomplete files from source. Legacy venv-based
  # installer was removed; ensure install dir exists and copy files from
  # this repository so autocomplete can be installed independently.
  echo "📁 Updating autocomplete files..."
  local src_dir
  src_dir="$(script_dir)"
  mkdir -p "$INSTALL_DIR"

  # Copy autocomplete folder, completions folder, and scripts
  for item in autocomplete completions scripts; do
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
    setup_fish_completions
    echo "Autocomplete installation complete!"
    echo ""
    echo "Please restart your shell or source your shell's rc file to enable autocompletion."
    echo "Test completion by typing: my-unicorn <TAB>"
  else
    echo "❌ Autocomplete setup failed"
    exit 1
  fi
}

# Usage function
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -i, --install       Install using 'uv tool install' (recommended for production)
  -e, --editable      Install using 'uv tool install --editable' (development)
  --autocomplete      Install shell completion only

Examples:
  $(basename "$0") -i              # Install as isolated tool (recommended)
  $(basename "$0") -e              # Install in editable mode (contributors)
  $(basename "$0") --autocomplete  # Install completion for current shell
EOF
  exit 1
}

# -- Entry point -------------------------------------------------------------
install=false
editable=false
autocomplete=false

while getopts "ie-:" opt; do
  case $opt in
    i) install=true ;;
    e) editable=true ;;
    -)
      case "${OPTARG}" in
        install) install=true ;;
        editable) editable=true ;;
        autocomplete) autocomplete=true ;;
        *) usage ;;
      esac ;;
    *) usage ;;
  esac
done

if $install; then
  check_uv_required
  install_with_uv_tool
elif $editable; then
  check_uv_required
  install_with_uv_editable
elif $autocomplete; then
  install_autocomplete
else
  usage
fi