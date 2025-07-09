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

# No longer needed: run_my_unicorn replaced by direct CLI calls

# ======== Test Scenarios ========

option3_joplin_qownnotes() {
  log "=== Testing Both QOwnNotes and Joplin Update Together ==="
  setup_qownnotes_config "0.1.0"
  setup_joplin_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update --select qownnotes,joplin || log "ERROR: update --select qownnotes,joplin failed"
  log "Combined QOwnNotes and Joplin update test completed"
}

option3_fourapp() {
  log "=== Testing Update All (Four Apps) ==="
  setup_qownnotes_config "0.1.0"
  setup_joplin_config "0.1.0"
  setup_zettlr_config "0.1.0"
  setup_appflowy_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update --all || log "ERROR: update --all failed"
  log "Update all (four apps) test completed"
}

option3_qownnotes() {
  log "=== Testing QOwnNotes Update ==="
  setup_qownnotes_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update --select qownnotes || log "ERROR: update --select qownnotes failed"
  log "QOwnNotes update test completed"
}

option3_joplin() {
  log "=== Testing Joplin Update ==="
  setup_joplin_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update --select joplin || log "ERROR: update --select joplin failed"
  log "Joplin update test completed"
}

option4_qownnotes() {
  log "=== Testing Selective Update (QOwnNotes) ==="
  setup_qownnotes_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update --select qownnotes || log "ERROR: update --select qownnotes failed"
  log "Selective update test completed"
}

option4_joplin() {
  log "=== Testing Selective Update (Joplin) ==="
  setup_joplin_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update --select joplin || log "ERROR: update --select joplin failed"
  log "Selective update test completed"
}

option4_fourapp() {
  log "=== Testing Selective Update (Four Apps) ==="
  setup_appflowy_config "0.1.0"
  setup_qownnotes_config "0.1.0"
  setup_zettlr_config "0.1.0"
  setup_joplin_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update --select appflowy,qownnotes,zettlr,joplin || log "ERROR: update --select appflowy,qownnotes,zettlr,joplin failed"
  log "Selective update test for four apps completed"
}

url_qownnotes() {
  log "=== Testing QOwnNotes Fresh Install ==="
  rm -f "$CONFIG_DIR/QOwnNotes.json"
  cd "$APP_ROOT"
  python3 run.py download https://github.com/pbek/QOwnNotes || log "ERROR: download QOwnNotes failed"
  log "QOwnNotes installation test completed"
}

url_joplin() {
  log "=== Testing Joplin Fresh Install ==="
  rm -f "$CONFIG_DIR/joplin.json"
  cd "$APP_ROOT"
  python3 run.py download https://github.com/laurent22/joplin || log "ERROR: download joplin failed"
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
