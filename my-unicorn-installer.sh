#!/usr/bin/env bash
#
# my-unicorn-installer.sh
# User‑level installer & updater for "my-unicorn"
# Handles venv creation, wrapper install, and shell rc setup
# ------------------------------------------------
set -euo pipefail

# -- Configuration --
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$XDG_DATA_HOME/my-unicorn"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$VENV_DIR/bin"
WRAPPER_SRC="$INSTALL_DIR/scripts/venv-wrapper.bash"
WRAPPER_DST="$HOME/.local/bin/my-unicorn"

EXPORT_LINE='export PATH="$HOME/.local/bin:$PATH"'

# -- Helpers --

script_dir() {
  # Resolve path to the currently running script
  local src="${BASH_SOURCE[0]}"
  while [ -h "$src" ]; do
    src="$(readlink "$src")"
  done
  dirname "$src"
}

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
  [[ ! -f "$rc" ]] && touch "$rc"
  echo "$rc"
}

ensure_path_in_rc() {
  local rc_file="$1"
  if ! grep -Fxq "$EXPORT_LINE" "$rc_file"; then
    printf "\n# Added by my-unicorn installer\n%s\n" "$EXPORT_LINE" >> "$rc_file"
    echo "✅ Added '$HOME/.local/bin' to PATH in $rc_file"
  else
    echo "ℹ️ PATH already configured in $rc_file"
  fi
}

copy_source_to_install_dir() {
  echo "📁 Copying source files to $INSTALL_DIR..."
  local src_dir
  src_dir="$(script_dir)"
  mkdir -p "$INSTALL_DIR"

  # List of directories/files to copy
  for item in my_unicorn scripts pyproject.toml "$(basename "$0")"; do
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

setup_venv() {
  echo "🐍 Creating/updating virtual environment in $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
  source "$BIN_DIR/activate"
  python3 -m pip install --upgrade pip wheel
  echo "📦 Installing my-unicorn (editable) into venv..."
  python3 -m pip install -e "$INSTALL_DIR"
}

install_wrapper() {
  echo "🔧 Installing wrapper to $WRAPPER_DST..."
  mkdir -p "$(dirname "$WRAPPER_DST")"
  cp "$WRAPPER_SRC" "$WRAPPER_DST"
  chmod +x "$WRAPPER_DST"
}

install_my_unicorn() {
  echo "=== Installing my‑unicorn ==="
  copy_source_to_install_dir
  setup_venv
  install_wrapper

  local rc
  rc="$(detect_rc_file)"
  ensure_path_in_rc "$rc"

  echo "✅ Installation complete."
  echo "Restart your shell or run 'source $rc' to apply PATH."
  echo "Run 'my-unicorn --help' to get started."
}

update_my_unicorn() {
  echo "=== Updating my‑unicorn ==="
  setup_venv
  echo "✅ Update complete."
}

# -- Entry point --
case "${1-}" in
  install|"") install_my_unicorn ;;
  update) update_my_unicorn ;;
  *)
    cat <<EOF
Usage: $(basename "$0") [install|update]

  install   Copy source, setup venv, install wrapper, configure PATH
  update    Copy source again, rebuild venv, reinstall wrapper
EOF
    exit 1
    ;;
esac

