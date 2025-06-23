#!/usr/bin/env bash
# Simple manual testing script for my-unicorn
# 
# QOwnNotes: Asset digest verification 
# Joplin: .yml sha512 verification
# Appflowy: no verification 
# Zettlr: sha256 verification with .txt file
# 

set -e # Exit on any error

# Configuration
APP_ROOT="$(dirname "$(dirname "$0")")"
CONFIG_DIR="$HOME/.config/myunicorn/apps"
BACKUP_DIR="/tmp/my_unicorn_test_backup"
LOG_FILE="$HOME/.local/state/my-unicorn/manual_test.log"

# Create necessary directories
mkdir -p "$CONFIG_DIR"
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Clear previous log and backup
>"$LOG_FILE"
rm -rf "$BACKUP_DIR"/*

# ======== Utility Functions ========

log() {
  local message="$1"
  local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
  echo -e "[$timestamp] $message" | tee -a "$LOG_FILE"
}

confirm() {
  local prompt="$1"
  read -p "$prompt [Y/n]: " answer
  answer=${answer:-y}
  [[ ${answer:0:1} =~ [yY] ]]
}

# ======== Backup and Restore ========

backup_app_configs() {
  log "Backing up QOwnNotes and Joplin configs"

  # Only backup QOwnNotes and Joplin
  if [ -f "$CONFIG_DIR/QOwnNotes.json" ]; then
    cp "$CONFIG_DIR/QOwnNotes.json" "$BACKUP_DIR/"
    log "Backed up QOwnNotes.json"
  fi

  if [ -f "$CONFIG_DIR/joplin.json" ]; then
    cp "$CONFIG_DIR/joplin.json" "$BACKUP_DIR/"
    log "Backed up joplin.json"
  fi
}

restore_app_configs() {
  log "Restoring QOwnNotes and Joplin configs"

  if [ -f "$BACKUP_DIR/QOwnNotes.json" ]; then
    cp "$BACKUP_DIR/QOwnNotes.json" "$CONFIG_DIR/"
    log "Restored QOwnNotes.json"
  fi

  if [ -f "$BACKUP_DIR/joplin.json" ]; then
    cp "$BACKUP_DIR/joplin.json" "$CONFIG_DIR/"
    log "Restored joplin.json"
  fi
}

# ======== Test Config Functions ========

setup_qownnotes_config() {
  local version="$1"
  log "Setting up QOwnNotes test config with version $version"

  cat >"$CONFIG_DIR/QOwnNotes.json" <<EOF
{
    "version": "$version",
    "appimage_name": "QOwnNotes-$version-x86_64.AppImage"
}
EOF
}

setup_zettlr_config() {
  local version="$1"
  log "Setting up Zettlr test config with version $version"

  cat >"$CONFIG_DIR/Zettlr.json" <<EOF
{
    "version": "$version",
    "appimage_name": "Zettlr-$version-x86_64.AppImage"
}
EOF
}

setup_appflowy_config() {
  local version="$1"
  log "Setting up AppFlowy test config with version $version"

  cat >"$CONFIG_DIR/AppFlowy.json" <<EOF
{
    "version": "$version",
    "appimage_name": "AppFlowy-$version-linux-x86_64.AppImage"
}
EOF
}

setup_joplin_config() {
  local version="$1"
  log "Setting up Joplin test config with version $version"

  cat >"$CONFIG_DIR/joplin.json" <<EOF
{
    "version": "$version",
    "appimage_name": "Joplin-$version.AppImage"
}
EOF
}

# ======== Test Functions ========

run_my_unicorn() {
  local choice="$1"
  local extra_input="$2"

  log "Running my-unicorn with option $choice and extra input $extra_input"
  cd "$APP_ROOT"

  if [ -z "$extra_input" ]; then
    # Simple choices without extra input
    cat >"/tmp/input.txt" <<EOF
$choice
0
EOF
  else
    # Choices with extra input
    cat >"/tmp/input.txt" <<EOF
$choice
$extra_input
y
0
EOF
  fi

  # Run command and handle errors
  python3 main.py <"/tmp/input.txt" || {
    local exit_code=$?
    if [ $exit_code -eq 1 ]; then
      log "Process completed with EOF (expected)"
    else
      log "ERROR: Command failed with exit code $exit_code"
    fi
  }

  # Cleanup
  rm -f "/tmp/input.txt"
  sleep 1 # Give time for file operations to complete
}

# ======== Test Scenarios ========

option3_joplin_qownnotes() {
  log "=== Testing Both QOwnNotes and Joplin Update Together ==="
  # set up outdated versions for both apps
  setup_qownnotes_config "0.1.0" # Old version for QOwnNotes
  setup_joplin_config "0.1.0"    # Old version for Joplin
  run_my_unicorn "3" "all"   # Update all
  log "Combined QOwnNotes and Joplin update test completed"
}

option3_four_apps() {
  log "=== Testing Both QOwnNotes and Joplin Update Together ==="
  # set up outdated versions for both apps
  setup_qownnotes_config "0.1.0" # Old version for QOwnNotes
  setup_joplin_config "0.1.0"    # Old version for Joplin
  setup_zettlr_config "0.1.0"    # Old version for Zettlr
  setup_appflowy_config "0.1.0"  # Old version for AppFlowy
  run_my_unicorn "3" "all"  # Update all
  log "Combined QOwnNotes and Joplin update test completed"
}

option3_qownnotes() {
  log "=== Testing QOwnNotes Update ==="
  setup_qownnotes_config "0.1.0" # Old version
  run_my_unicorn "3" "all"   # Update all
  log "QOwnNotes update test completed"
}

option3_joplin() {
  log "=== Testing Joplin Update ==="
  setup_joplin_config "0.1.0" # Old version
  run_my_unicorn "3" "all"     # Update all
  log "Joplin update test completed"
}

option4_qownnotes() {
  log "=== Testing Selective Update (QOwnNotes) ==="
  setup_qownnotes_config "0.1.0" # Old version

  #selecting option 4 and than qownnotes 3
  run_my_unicorn "4" "3"
  log "Selective update test completed"
}

option4_joplin() {
  log "=== Testing Selective Update (Joplin) ==="
  setup_joplin_config "0.1.0" # Old version

  #selecting option 4 and than joplin 6
  run_my_unicorn "4" "6"
  log "Selective update test completed"
}

option4_fourapp() {
    log "=== Testing Selective Update (Four Apps) ==="
    # Lower versions for all apps before selective update
    setup_appflowy_config "0.1.0"
    setup_qownnotes_config "0.1.0"
    setup_zettlr_config "0.1.0"
    setup_joplin_config "0.1.0"
    
    # handle the options
    run_my_unicorn "4" "1,2,3,4"

    log "Selective update test for four apps completed"
}

url_qownnotes() {
  log "=== Testing QOwnNotes Fresh Install ==="
  # Remove existing config if present
  rm -f "$CONFIG_DIR/QOwnNotes.json"

  # Create input file for download with GitHub URL
  cat >"/tmp/input.txt" <<EOF
1
https://github.com/pbek/QOwnNotes


0
EOF

  cd "$APP_ROOT"
  python3 main.py <"/tmp/input.txt" || true
  rm -f "/tmp/input.txt"

  log "QOwnNotes installation test completed"
}

url_joplin() {
  log "=== Testing Joplin Fresh Install ==="
  # Remove existing config if present
  rm -f "$CONFIG_DIR/joplin.json"

  # Create input file for download with GitHub URL
  cat >"/tmp/input.txt" <<EOF
1
https://github.com/laurent22/joplin


0
EOF

  cd "$APP_ROOT"
  python3 main.py <"/tmp/input.txt" || true
  rm -f "/tmp/input.txt"

  log "Joplin installation test completed"
}

# ======== Main Function ========

main() {
  echo "Simple Manual Testing Script for my-unicorn"
  echo "-------------------------------------------"
  echo "This script only backs up and tests QOwnNotes and Joplin"

  # Backup configs before testing
  backup_app_configs

  # Menu for test selection
  while true; do
    echo ""
    echo "Available tests:"
    echo "1) (Auto)Option 3 test with 4 apps"
    echo "2) (Selective)Option 4 test with 4 apps"
    echo "3) (Auto)Option 3 test QOwnNotes"
    echo "4) (Auto)Option 3 test Joplin"
    echo "5) (Selective)Option 4 test QOwnNotes"
    echo "6) (Selective)Option 4 test Joplin"
    
    echo "7) (URL)Option 1 test QOwnNotes"
    echo "8) (URL)Option 1 test Joplin"
    echo "9) (Auto)Option 3 test QOwnNotes and Joplin"
    echo "10) Exit and restore configs"
    echo ""

    read -p "Select a test (1-10): " choice

    case $choice in
    1) option3_fourapp ;;
    2) option4_fourapp ;;
    3) option3_qownnotes ;;
    4) option3_joplin ;;
    5) option4_qownnotes ;;
    6) option4_joplin ;;
    7) url_qownnotes ;;
    8) url_joplin ;;
    9) option3_joplin_qownnotes ;;
    10)
      log "Restoring original configurations"
      restore_app_configs
      log "Testing completed"
      exit 0
      ;;
    *)
      echo "Invalid selection. Please choose 1-10."
      ;;
    esac
  done
}

# Run the main function
main
