#!/usr/bin/env bash
#
# my-unicorn-installer.sh
# User‑level installer & updater for "my-unicorn"
# ------------------------------------------------
set -euo pipefail

#–– Configuration ––
# Where to clone / install your repo/data
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$XDG_DATA_HOME/my-unicorn"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$VENV_DIR/bin"
SCRIPT_NAME="my-unicorn"
MY_UNICORN_FILE="$HOME/.local/bin/my-unicorn"

# Path‐export line to add to shell rc
EXPORT_LINE='export PATH="$HOME/.local/bin:$PATH"'

#–– Helpers ––

# Determine which shell rc file to use (zsh or bash), return path or empty
detect_rc_file() {
  local rc user_shell
  user_shell="$(basename "${SHELL:-}")"

  case "$user_shell" in
    zsh)
      rc="${HOME}/.zshrc"
      [[ -f "${HOME}/.config/zsh/.zshrc" ]] && rc="${HOME}/.config/zsh/.zshrc"
      ;;
    bash)
      rc="${HOME}/.bashrc"
      ;;
    *)
      rc="${HOME}/.bashrc"
      ;;
  esac

  [[ ! -f "$rc" ]] && touch "$rc"
  echo "$rc"
}


# Ensure EXPORT_LINE is present in rc_file exactly once
ensure_path_in_rc() {
  local rc_file="$1"
  if ! grep -Fxq "$EXPORT_LINE" "$rc_file"; then
    printf "\n# Added by my‑unicorn installer\n%s\n" "$EXPORT_LINE" >>"$rc_file"
    echo "✅ Added $BIN_DIR to PATH in $rc_file"
  else
    echo "ℹ️  PATH already configured in $rc_file"
  fi
}

#–– Core operations ––

install_my_unicorn() {
  local rc
  rc="$(detect_rc_file)"
  echo "Using shell rc: $rc"

  # 1) Clone or pull repo
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "🔄 Repository exists; pulling latest changes..."
    git -C "$INSTALL_DIR" pull --ff-only
  else
    echo "📥 Cloning repository into $INSTALL_DIR..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone https://github.com/Cyber-Syntax/my-unicorn.git "$INSTALL_DIR"
  fi

  # 2) Create or update virtualenv
  echo "🐍 Setting up virtual environment in $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip wheel

  # 3) Install project in editable mode
  echo "📦 Installing my-unicorn (editable)..."
  pip install -e "$INSTALL_DIR"

  # this is necessary since we need this script before we can run my-unicorn itself
  cp scripts/venv-wrapper.bash "$MY_UNICORN_FILE"
  chmod a+x "$MY_UNICORN_FILE"

  # 4) Verify installation
  if [[ -f "$BIN_DIR/my-unicorn" ]]; then
    echo "✅ my-unicorn script created successfully"
  else
    echo "❌ Error: my-unicorn script not found in $BIN_DIR"
    exit 1
  fi

  # 5) Ensure CLI is on PATH
  echo "🔧 Ensuring $EXPORT_LINE is in your PATH..."
  ensure_path_in_rc "$rc"

  echo "✅ Installation complete!"
  echo "Please restart your shell or run 'source $rc' to activate."
  echo "Then you can run: my-unicorn --help"
}

update_my_unicorn() {
  echo "🔄 Running update..."
  # Re‑use install path logic (pull + reinstall)
  install_my_unicorn
  echo "✅ Update complete!"
}

#–– Entry point ––
if [[ "${1-}" == "update" ]]; then
  update_my_unicorn
  exit 0
elif [[ "${1-}" == "install" || -z "${1-}" ]]; then
  # default to install if no arg
  install_my_unicorn
  exit 0
else
  cat <<EOF
Usage: $(basename "$0") [install|update]

  install   Bootstrap my-unicorn (clone, venv, install, set PATH)
  update    Pull latest and reinstall

EOF
  exit 1
fi
