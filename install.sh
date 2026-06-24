#!/usr/bin/env bash
#
# install.sh
# -----------------------------------------------------------------------------
# User-level installer for "my-unicorn"
#
# This installer is responsible for:
#   - Installing the CLI using `uv tool install`
#   - Supporting version-specific installs using Git tags (example: v2.3.0)
#   - Installing editable mode for local development contributors
#   - Setting up shell autocomplete for bash/zsh
#   - Copying the update helper script into ~/.local/bin
#   - Checking PATH configuration for proper CLI access
#
# Supported modes:
#
#   ./install.sh -i | --install [version]
#       Standard installation using uv tool install
#
#   ./install.sh -e | --editable
#       Editable install using local source code for development
#  
#   ./install.sh -u | --uninstall
#       Uninstall my-unicorn from user system
#
#   ./install.sh -h | --help
#       Show usage information
#
#
# Examples:
#
#   ./install.sh -i
#       Install latest version from GitHub
#
#   ./install.sh -i 2.3.0
#       Install tagged version v2.3.0
#
#   ./install.sh -i v2.3.0-alpha
#       Install tagged pre-release version directly
#
#   ./install.sh -e
#       Install editable mode for contributors
#
# Safety flags:
#
#   -e  Exit immediately if a command fails
#   -u  Exit if an unset variable is used
#   -o pipefail
#       Fail a pipeline if any command inside it fails
#

# NOTE:
# Using a single strict mode declaration to avoid redundancy.
set -Eeuo pipefail

# -----------------------------------------------------------------------------
# Global configuration
# -----------------------------------------------------------------------------


# Official GitHub repository used for installation
GITHUB_GIT_URL="git+https://github.com/Cyber-Syntax/my-unicorn"
readonly GITHUB_GIT_URL

# CLI executable name shown to users
CLI_NAME="my-unicorn"
readonly CLI_NAME

# Standard XDG user data location
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
readonly XDG_DATA_HOME

# Local install location for autocomplete assets and support files
INSTALL_DIR="$XDG_DATA_HOME/my-unicorn"
readonly INSTALL_DIR

# User-local executable directory
LOCAL_BIN_DIR="$HOME/.local/bin"
readonly LOCAL_BIN_DIR

# Update helper destination path
UPDATE_SCRIPT_PATH="$LOCAL_BIN_DIR/my-unicorn-update"
readonly UPDATE_SCRIPT_PATH

# -----------------------------------------------------------------------------
# Logging helpers
# -----------------------------------------------------------------------------

# Print normal informational messages to stdout
print_info() {
  local message
  message="$1"

  printf '%s\n' "$message"
}

# Print errors to stderr so failures are visible and script-safe
print_error() {
  local message
  message="$1"

  printf '× %s\n' "$message" >&2
}

# -----------------------------------------------------------------------------
# Utility helpers
# -----------------------------------------------------------------------------

# Return the absolute path of the current script directory.
#
# This helps us reliably locate project files such as:
#   scripts/autocomplete.bash
#   scripts/update.bash
#
# even when the installer is executed from another directory.
script_dir() {
  local src_dir

  if ! src_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; then
    print_error "Unable to determine script directory."
    return 1
  fi

  if [[ -z "${src_dir// /}" ]]; then
    print_error "Resolved script directory is empty."
    return 1
  fi

  printf '%s\n' "$src_dir"
}

# Ensure a required command exists before continuing.
#
# Example:
#   check_dependency uv
#
# This prevents confusing failures later in the install flow.
check_dependency() {
  local command_name
  command_name="$1"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    print_error "Required command not found: $command_name"
    return 1
  fi
}

# Normalize a version string into a Git tag.
#
# Examples:
#
#   2.3.0          -> v2.3.0
#   v2.3.0         -> v2.3.0
#   2.3.0-alpha    -> v2.3.0-alpha
#
# This matches the same logic used by the Python self-update module.
normalize_version_tag() {
  local version
  version="$1"

  if [[ -z "${version// /}" ]]; then
    print_error "Version value cannot be empty."
    return 1
  fi

  version="${version//[$'\r\n\t']/}"
  version="${version#"${version%%[![:space:]]*}"}"
  version="${version%"${version##*[![:space:]]}"}"

  if [[ -z "${version// /}" ]]; then
    print_error "Version value is invalid after sanitization."
    return 1
  fi

  if [[ "$version" =~ ^v ]]; then
    printf '%s\n' "$version"
    return
  fi

  printf 'v%s\n' "$version"
}

# -----------------------------------------------------------------------------
# PATH validation
# -----------------------------------------------------------------------------

# Check whether ~/.local/bin exists in PATH.
#
# uv installs CLI tools there for most user-level installs.
# If it is missing, users may install successfully but still be unable
# to run `my-unicorn`.
check_local_bin_in_path() {
  if [[ ":$PATH:" == *":$LOCAL_BIN_DIR:"* ]]; then
    print_info "✓ $LOCAL_BIN_DIR is already in your PATH"
    return 0
  fi

  cat <<EOF

! IMPORTANT: $LOCAL_BIN_DIR is not in your PATH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
To use '${CLI_NAME}' from anywhere, add this line to your shell config:

    export PATH="\$HOME/.local/bin:\$PATH"

Example shell configs:
    ~/.bashrc
    ~/.zshrc
    ~/.zshenv

Then restart your terminal or run:

    source ~/.bashrc
    source ~/.zshrc

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

  return 1
}

# -----------------------------------------------------------------------------
# Autocomplete setup
# -----------------------------------------------------------------------------

# Execute autocomplete installer from the source repository.
#
# This delegates the shell-specific logic to:
#   scripts/autocomplete.bash
setup_autocomplete_from_src() {
  local src_dir
  local autocomplete_helper

  src_dir="$1"
  autocomplete_helper="$src_dir/scripts/autocomplete.bash"

  if [[ -x "$autocomplete_helper" ]]; then
    print_info "🔁 Setting up autocomplete..."

    if ! bash "$autocomplete_helper"; then
      print_error "Autocomplete setup failed."
      return 1
    fi

    return 0
  fi

  print_info "! Warning: Autocomplete helper not found at $autocomplete_helper"
}

# -----------------------------------------------------------------------------
# Update helper installation
# -----------------------------------------------------------------------------

# Copy update helper script into ~/.local/bin so users can run:
#
#   my-unicorn-update
#
# This keeps updates easy and discoverable.
copy_update_script() {
  local src_dir
  local src_path

  if ! src_dir="$(script_dir)"; then
    return 1
  fi

  src_path="$src_dir/scripts/update.bash"

  if [[ ! -f "$src_path" ]]; then
    print_info "! Warning: Update script not found at $src_path, skipping copy."
    return 0
  fi

  mkdir -p "$LOCAL_BIN_DIR"

  if ! cp "$src_path" "$UPDATE_SCRIPT_PATH"; then
    print_error "Failed to copy update script."
    return 1
  fi

  if ! chmod +x "$UPDATE_SCRIPT_PATH"; then
    print_error "Failed to make update script executable."
    return 1
  fi

  print_info "✓ Update script copied to $UPDATE_SCRIPT_PATH"
}

# -----------------------------------------------------------------------------
# Installation methods
# -----------------------------------------------------------------------------

find_latest_prerelease_tag() {
  local latest_tag
  local repo_url
  local tag_list

  repo_url="https://github.com/Cyber-Syntax/my-unicorn.git"

  if ! check_dependency "git"; then
    return 1
  fi

  # Fetch remote tags without cloning the repository.
  # We sort using version-aware sorting and keep the newest tag.
  #
  # Examples expected:
  #   v2.5.2-alpha
  #   v2.5.2-beta
  #   v2.5.2
  #
  # This ensures:
  #
  #   ./install.sh -i
  #
  # installs the latest tagged release instead of the latest main branch commit.
  if ! tag_list="$(
    git ls-remote --tags --refs "$repo_url" 2>/dev/null |
      awk '{print $2}' |
      sed 's#refs/tags/##' |
      grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9]+)*$' |
      sort -V
  )"; then
    print_error "Failed to fetch remote tags from GitHub."
    return 1
  fi

  if [[ -z "${tag_list// /}" ]]; then
    print_error "No valid release tags were found."
    return 1
  fi

  if ! latest_tag="$(printf '%s\n' "$tag_list" | tail -n 1)"; then
    print_error "Failed to determine latest release tag."
    return 1
  fi

  if [[ -z "${latest_tag// /}" ]]; then
    print_error "Resolved latest tag is empty."
    return 1
  fi

  printf '%s\n' "$latest_tag"
}

install_with_uv_tool() {
  local requested_version
  local version_tag
  local install_target
  local src_dir

  requested_version="${1:-}"

  if ! check_dependency "uv"; then
    return 1
  fi

  if ! src_dir="$(script_dir)"; then
    return 1
  fi

  # Behavior:
  #
  # ./install.sh -i
  #   -> installs latest prerelease/release tag from GitHub
  #
  # ./install.sh -i 2.5.2-alpha
  #   -> installs exact requested tag
  #
  # ./install.sh -i v2.5.2-alpha
  #   -> installs exact requested tag
  #
  # This prevents accidental installs from main branch HEAD.

  if [[ -n "${requested_version// /}" ]]; then
    if ! version_tag="$(normalize_version_tag "$requested_version")"; then
      return 1
    fi

    print_info "🔖 Requested version detected: ${version_tag}"
  else
    print_info "🔍 No version provided. Resolving latest prerelease tag..."

    if ! version_tag="$(find_latest_prerelease_tag)"; then
      print_error "Unable to determine latest prerelease tag."
      return 1
    fi

    print_info "🔖 Latest prerelease tag resolved: ${version_tag}"
  fi

  install_target="${GITHUB_GIT_URL}@${version_tag}"

  print_info "🚀 Installing ${CLI_NAME} version ${version_tag} using 'uv tool install'..."

  if ! cd "$src_dir"; then
    print_error "Failed to change directory to: $src_dir"
    return 1
  fi

  if ! uv tool install "$install_target" --force; then
    print_error "uv tool install failed for target: $install_target"
    return 1
  fi

  check_local_bin_in_path
  setup_autocomplete_from_src "$src_dir"
  setup_fish_completions
  copy_update_script

  print_info "✓ Installation complete using uv tool."
  print_info "Run '${CLI_NAME} --help' to get started."
}

# Editable installation for local development.
#
# This is intended for contributors working on the source code.
# Changes made locally are immediately reflected without reinstalling.
install_with_uv_editable() {
  local src_dir

  if ! check_dependency "uv"; then
    return 1
  fi

  if ! src_dir="$(script_dir)"; then
    return 1
  fi

  print_info "🔧 Installing ${CLI_NAME} in editable mode..."

  if ! cd "$src_dir"; then
    print_error "Failed to change directory to: $src_dir"
    return 1
  fi

  if ! uv tool install --editable . --force; then
    print_error "Editable installation failed."
    return 1
  fi

  check_local_bin_in_path
  setup_autocomplete_from_src "$src_dir"
  setup_fish_completions
  copy_update_script

  print_info "✓ Editable installation complete."
  print_info "Changes to source code will be reflected immediately."
}

    return 1
  fi

  print_info "🧹 Uninstalling ${CLI_NAME}..."

  printf "Are you sure you want to uninstall %s? (y/N): " "$CLI_NAME"
  read -r confirm

  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    print_info "❎ Uninstall cancelled."
    return 0
  fi
      fi
      print_info "🗑️  Removed uv tool installation"
    else
      print_info "uv tool installation not found"
    fi
  fi
  fi

  cat <<EOF

! MANUAL CLEANUP (OPTIONAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If you manually added completion config, remove from:

  ~/.bashrc
  ~/.zshrc

Directories (if still present):

  ~/.config/bash/completions/
  ~/.config/zsh/completions/

Then restart your shell.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

  print_info "✓ Uninstall complete."
}

# -----------------------------------------------------------------------------
# Usage
# -----------------------------------------------------------------------------

usage() {
  local exit_code
  # Default to exit code 0 for normal usage
  # If an error code is provided, use 1 to indicate failure
  exit_code="${1:-0}"
  cat <<EOF
Usage: ./install.sh [OPTIONS]

Options:
  -i, --install [version]   Install using uv tool (default: latest prerelease tag)
  -e, --editable            Install in editable mode (development)
  -u, --uninstall           Remove my-unicorn from user system
  -h, --help                Show this help message

Examples:
  ./install.sh -i
  ./install.sh -i 2.5.2-alpha
  ./install.sh -e
  ./install.sh -u
EOF
  exit "$exit_code"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
  local mode
  local version
  local arg_count

  mode="${1:-}"
  version="${2:-}"
  arg_count="$#"

  # Strict argument validation
  #
  # Allowed patterns:
  #   install:     ./install.sh -i [version]
  #   editable:    ./install.sh -e
  #   uninstall:   ./install.sh -u
  #   help:        ./install.sh -h
  #
  # Reject any malformed invocation such as:
  #   ./install.sh -e extra
  #   ./install.sh -u something wrong
  #   ./install.sh -i v1 v2 v3
  #
  if [[ "$arg_count" -gt 2 ]]; then
    print_error "Too many arguments provided."
    usage 1
  fi

  case "$mode" in
  -i | --install)
    install_with_uv_tool "$version"
    ;;
  -e | --editable)
    if [[ "$arg_count" -gt 1 ]]; then
      print_error "Editable mode does not accept additional arguments."
      usage 1
    fi
    install_with_uv_editable
    ;;
  -u | --uninstall)
    if [[ "$arg_count" -gt 1 ]]; then
      print_error "Uninstall mode does not accept additional arguments."
      usage 1
    fi
    uninstall_my_unicorn
    ;;
  -h | --help | "")
    if [[ "$arg_count" -gt 1 ]]; then
      print_error "Help does not accept additional arguments."
      usage 1
    fi
    usage 0
    ;;
  *)
    print_error "Unknown option: $mode"
    usage 1
    ;;
  esac
}

main "$@"
