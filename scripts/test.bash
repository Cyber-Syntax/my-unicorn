#!/usr/bin/env bash
# Manual test script for my-unicorn
# REQUIRES: jq, python3
# USAGE: ./scripts/test.bash [--quick|--all|--help]
#
# This script provides a comprehensive CLI testing framework for my-unicorn,
# combining URL installs, catalog installs, updates, and all core functionality.
#
# Auto-detects container vs normal machine:
#  - In container: uses installed 'my-unicorn' command
#  - On normal machine: uses 'python3 run.py' for development
#
# # Update specific apps to test update functionality
# appflowy: Catalog + digest
# qownnotes: Catalog + digest
# legcord: Catalog + checksum_file via latest-linux.yml
# keepassxc: URL + checksum_file via x.AppImage.DIGEST
# freetube: Catalog/URL + always beta app + digest test. 
# tagspaces: Catalog + Digest and checksum_file via SHA256SUMS.txt
# logseq: Catalog + checksum_file via SHA256SUMS.txt
# standard-notes: Catalog + checksum_file via SHA256SUMS.txt 
#                + special naming logic  which repo name is desktop
#
# Author: Cyber-Syntax
# License: Same as my-unicorn project

set -o errexit -o nounset -o pipefail

# ======== Configuration ========

# Get the absolute path to the application root
APP_ROOT="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")"
readonly APP_ROOT
readonly CONFIG_DIR="$HOME/.config/my-unicorn/apps/"
readonly LOG_FILE="$HOME/.config/my-unicorn/logs/comprehensive_test.log"

# Test configuration
readonly TEST_VERSION="0.1.0"

# Optional: set DEBUG=true in env for more logs
DEBUG="${DEBUG:-false}"

# ======== Dependency Check ========

check_deps() {
  command -v jq >/dev/null || {
    echo "ERROR: jq not found. Install: sudo apt install jq"
    exit 1
  }
  command -v python3 >/dev/null || {
    echo "ERROR: python3 not found"
    exit 1
  }
}
check_deps

# ======== Environment Detection ========

is_container() {
  # Common container detection heuristics
  if [[ -f "/.dockerenv" ]] || [[ -f "/run/.containerenv" ]]; then
    return 0
  fi
  if [[ -r /proc/1/cgroup ]]; then
    if grep -qaE 'docker|lxc|containerd|kubepods|podman' /proc/1/cgroup 2>/dev/null; then
      return 0
    fi
  fi
  # Check if it is qemu virtual machine
  if [[ -x /usr/bin/systemd-detect-virt ]] && [[ -x /usr/bin/lscpu ]]; then
    virt=$(/usr/bin/systemd-detect-virt 2>/dev/null)
    if [[ "$virt" == "qemu" || "$virt" == "kvm" ]]; then
      if /usr/bin/lscpu | grep -q 'Hypervisor'; then
        return 0
      fi
    fi
  fi
  return 1
}

# run_cli: prefer installed CLI inside container, otherwise run repo script
run_cli() {
  local args=("$@")
  export CI=true
  if is_container; then
    if command -v my-unicorn >/dev/null 2>&1; then
      my-unicorn "${args[@]}"
      return $?
    fi
    # fallback to repository script if installed binary not present
    python3 "$APP_ROOT/run.py" "${args[@]}"
    return $?
  else
    python3 "$APP_ROOT/run.py" "${args[@]}"
    return $?
  fi
}

# ======== Utility Functions ========

log() {
  local message="$1"
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  echo -e "[$timestamp] $message" | tee -a "$LOG_FILE"
}

debug() {
  local message="$1"
  if [[ "${DEBUG:-false}" == "true" ]]; then
    log "DEBUG: $message"
  fi
}

info() {
  local message="$1"
  log "INFO: $message"
}

warn() {
  local message="$1"
  log "WARN: $message"
}

error() {
  local message="$1"
  log "ERROR: $message" >&2
}

# Initialize directories and logging
init_test_environment() {
  mkdir -p "$(dirname "$LOG_FILE")"

  # Clear previous log
  true >"$LOG_FILE"

  info "=== my-unicorn Comprehensive Testing Started ==="
  info "App Root: $APP_ROOT"
  info "Config Dir: $CONFIG_DIR"
  info "Log File: $LOG_FILE"

  if is_container; then
    info "Detected environment: container"
  else
    info "Detected environment: normal machine"
  fi
}

# ======== Version Manipulation ========

set_version() {
  local app="$1" version="$2"
  local config_file="$CONFIG_DIR/${app}.json"

  if [[ ! -f "$config_file" ]]; then
    warn "Config not found: $config_file; skipping version set"
    return 1
  fi

  info "Setting $app version to $version (for update test)"
  jq --arg v "$version" '.appimage.version = $v' "$config_file" >"$config_file.tmp" &&
    mv "$config_file.tmp" "$config_file"
}

# ======== Remove Apps Function ========

remove_apps() {
  local apps=("$@")
  info "Removing apps: ${apps[*]}"
  run_cli remove "${apps[@]}" 2>/dev/null || true
}

# ======== Test Functions ========

test_url_install() {
  local app="$1"
  local url="$2"
  info "Testing $app URL install"
  run_cli install "$url"
}

test_catalog_install() {
  local apps=("$@")
  info "Testing catalog install: ${apps[*]}"
  run_cli install "${apps[@]}"
}

test_update() {
  local apps=("$@")
  info "Testing update for: ${apps[*]}"

  # Set old versions for update test
  for app in "${apps[@]}"; do
    set_version "$app" "$TEST_VERSION" || true
  done

  run_cli update "${apps[@]}"
}

# ======== Comprehensive Test Suites ========

test_quick() {
  info "=== Running Quick Tests (appflowy) ==="

  # Step 1: Remove appflowy for clean state
  info "Step 1/5: Removing appflowy for clean URL install test"
  remove_apps appflowy

  # Step 2: Test URL install
  info "Step 2/5: Testing appflowy URL install"
  run_cli install https://github.com/AppFlowy-IO/AppFlowy

  # Step 3: Remove appflowy for clean catalog test
  info "Step 3/5: Removing appflowy for clean catalog install test"
  remove_apps appflowy

  # Step 4: Test catalog install (keep installed for update test)
  info "Step 4/5: Testing appflowy catalog install"
  test_catalog_install appflowy

  # Step 5: Test update (appflowy is already installed from catalog)
  info "Step 5/5: Testing appflowy update"
  test_update appflowy

  info "=== Quick tests completed successfully ==="
}

test_all() {
  info "=== Running All Comprehensive Tests ==="

  # Test multiple URL installs: nuclear + keepassxc
  info "--- Testing URL installs (nuclear + keepassxc) ---"

  info "Step 1/2: Removing apps for clean URL install test"
  remove_apps nuclear keepassxc

  info "Step 2/2: Testing concurrent URL installs"
  run_cli install https://github.com/nukeop/nuclear https://github.com/keepassxreboot/keepassxc

  # Test multiple catalog installs
  info "--- Testing catalog installs (legcord + tagspaces + (already installed appflowy)) ---"

  info "Step 1/2: Removing apps for clean catalog install test"
  remove_apps legcord tagspaces

  info "Step 2/2: Testing multiple catalog install"
  test_catalog_install legcord tagspaces appflowy standard-notes

  # Test updates for multiple apps
  info "--- Testing updates for multiple apps ---"
  test_update legcord tagspaces keepassxc appflowy standard-notes

  info "=== All comprehensive tests completed ==="
}

# ======== Help Function ========

show_help() {
  cat <<EOF
Comprehensive Manual Testing Script for my-unicorn

USAGE:
    $0 [COMMAND]

COMMANDS:
    --quick               Run quick tests (appflowy: URL -> catalog -> update)
    --all                 Run all comprehensive tests (appflowy + URLs + catalog + updates)
    --help                Show this help message

TEST FLOW:
    Quick Test:
        1. Remove appflowy
        2. Install appflowy via URL
        3. Remove appflowy
        4. Install appflowy from catalog
        5. Update appflowy

    All Tests:
        1. appflowy: remove -> URL install -> remove -> catalog install -> update
        2. URL installs: remove (nuclear, keepassxc) -> concurrent URL install
        3. Catalog installs: remove (legcord, tagspaces) -> catalog install
        4. Updates: test updates for legcord, tagspaces, keepassxc

EXAMPLES:
    $0 --quick                       # Run quick tests (appflowy only)
    $0 --all                         # Run all comprehensive tests

NOTES:
    - Auto-detects container vs normal machine
    - In containers: uses 'my-unicorn' command if available
    - On normal machines: uses 'python3 run.py' for development
    - Logs are written to: $LOG_FILE
    - Set DEBUG=true environment variable for detailed logging
    - Tests run from: $APP_ROOT
    - Remove is called before each install test to ensure clean state
    - Apps are kept after catalog install to test update functionality

EOF
}

# ======== Argument Parsing ========

parse_arguments() {
  if [[ $# -eq 0 ]]; then
    show_help
    exit 0
  fi

  case "$1" in
  --quick)
    test_quick
    ;;
  --all)
    test_all
    ;;
  --help)
    show_help
    ;;
  *)
    error "Unknown command: $1"
    echo
    show_help
    exit 1
    ;;
  esac
}

# ======== Main Function ========

main() {
  # Initialize test environment
  init_test_environment

  # Parse and execute command
  parse_arguments "$@"

  info "=== Test completed successfully ==="
}

# Execute main function with all arguments
main "$@"
