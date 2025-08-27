#!/usr/bin/env bash
# Simple manual testing script for my-unicorn
#
# qownnotes: Asset digest verification
# appflowy: no verification
# zettlr: sha256 verification with .txt file

set -e # Exit on any error

# Configuration
APP_ROOT="$(dirname "$(dirname "$0")")"
CONFIG_DIR="$HOME/.config/my-unicorn/apps/"
BACKUP_DIR="$HOME/.config/my-unicorn/tmp/my_unicorn_test_backup"
LOG_FILE="$HOME/.config/my-unicorn/logs/manual_test.log"

# Create necessary directories
# mkdir -p "$CONFIG_DIR"
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
  log "Backing up qownnotes"

  # Only backup qownnotes 
  if [ -f "$CONFIG_DIR/qownnotes.json" ]; then
    cp "$CONFIG_DIR/qownnotes.json" "$BACKUP_DIR/"
    log "Backed up qownnotes.json"
  fi
}

restore_app_configs() {
  log "Restoring qownnotes"

  if [ -f "$BACKUP_DIR/qownnotes.json" ]; then
    cp "$BACKUP_DIR/qownnotes.json" "$CONFIG_DIR/"
    log "Restored qownnotes.json"
  fi
}

# ======== Test Config Functions ========

setup_qownnotes_config() {
  local version="$1"
  log "Setting up qownnotes test config with version $version"

  cat >"$CONFIG_DIR/qownnotes.json" <<EOF
{
    "config_version": "1.0.0",
    "appimage": {
        "version": "$version",
        "name": "qownnotes-$version-x86_64.AppImage",
        "rename": "qownnotes",
        "name_template": "{repo}-{characteristic_suffix}.AppImage",
        "characteristic_suffix": [
            "x86_64.AppImage",
            "x86_64-Qt6.AppImage"
        ],
        "installed_date": "$(date --iso-8601=seconds)",
        "digest": ""
    },
    "owner": "pbek",
    "repo": "QOwnNotes",
    "github": {
        "repo": true,
        "prerelease": false
    },
    "verification": {
        "digest": true,
        "skip": false,
        "checksum_file": "",
        "checksum_hash_type": "sha256"
    },
    "icon": {
        "url": "https://raw.githubusercontent.com/pbek/QOwnNotes/develop/icons/icon.png",
        "name": "qownnotes.png",
        "installed": false
    }
}
EOF
}

setup_zettlr_config() {
  local version="$1"
  log "Setting up zettlr test config with version $version"

  cat >"$CONFIG_DIR/zettlr.json" <<EOF
{
    "config_version": "1.0.0",
    "appimage": {
        "version": "$version",
        "name": "zettlr-$version-x86_64.AppImage",
        "rename": "zettlr",
        "name_template": "{repo}-{characteristic_suffix}.AppImage",
        "characteristic_suffix": [
            "x86_64.AppImage"
        ],
        "installed_date": "$(date --iso-8601=seconds)",
        "digest": ""
    },
    "owner": "zettlr",
    "repo": "zettlr",
    "github": {
        "repo": true,
        "prerelease": false
    },
    "verification": {
        "digest": true,
        "skip": false,
        "checksum_file": "",
        "checksum_hash_type": "sha256"
    },
    "icon": {
        "url": "",
        "name": "zettlr.png",
        "installed": false
    }
}
EOF
}

setup_appflowy_config() {
  local version="$1"
  log "Setting up appflowy test config with version $version"

  cat >"$CONFIG_DIR/appflowy.json" <<EOF
{
    "config_version": "1.0.0",
    "appimage": {
        "version": "$version",
        "name": "appflowy-$version-linux-x86_64.AppImage",
        "rename": "appflowy",
        "name_template": "{repo}-{characteristic_suffix}.AppImage",
        "characteristic_suffix": [
            "linux-x86_64.AppImage"
        ],
        "installed_date": "$(date --iso-8601=seconds)",
        "digest": ""
    },
    "owner": "appflowy",
    "repo": "appflowy",
    "github": {
        "repo": true,
        "prerelease": false
    },
    "verification": {
        "digest": true,
        "skip": false,
        "checksum_file": "",
        "checksum_hash_type": "sha256"
    },
    "icon": {
        "url": "",
        "name": "appflowy.png",
        "installed": false
    }
}
EOF
}

# ======== Test Scenarios ========

## Option 1 : URL Installs
option1_qownnotes() {
  log "=== Testing qownnotes Fresh Install ==="
  rm -f "$CONFIG_DIR/qownnotes.json"
  cd "$APP_ROOT"
  python3 run.py install https://github.com/pbek/qownnotes || log "ERROR: download qownnotes failed"
  log "qownnotes installation test completed"
}

## Option 2: Catalog Installs
option2_qownnotes() {
  log "=== Testing qownnotes Catalog Install ==="
  cd "$APP_ROOT"
  python3 run.py install qownnotes || log "ERROR: install qownnotes failed"
  log "qownnotes catalog install test completed"
}

## Option 3: Auto Update Installations
option3_zettlr_qownnotes() {
  log "=== Testing Both qownnotes and zettlr Update Together ==="
  setup_qownnotes_config "0.1.0"
  setup_zettlr_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update --select qownnotes,zettlr || log "ERROR: update --select qownnotes,zettlr failed"
  log "Combined qownnotes and zettlr update test completed"
}

option3_threeapp() {
  log "=== Testing Update All (Three Apps) ==="
  setup_qownnotes_config "0.1.0"
  setup_zettlr_config "0.1.0"
  setup_appflowy_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update || log "ERROR: update failed"
  log "Update all (three apps) test completed"
}

option3_qownnotes() {
  log "=== Testing qownnotes Update ==="
  setup_qownnotes_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update qownnotes || log "ERROR: update qownnotes failed"
  log "qownnotes update test completed"
}

option3_zettlr() {
  log "=== Testing zettlr Update ==="
  setup_zettlr_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update zettlr || log "ERROR: update zettlr failed"
  log "zettlr update test completed"
}

## Option 4: Selective Update Installations
option4_qownnotes() {
  log "=== Testing Selective Update (qownnotes) ==="
  setup_qownnotes_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update qownnotes || log "ERROR: update qownnotes failed"
  log "Selective update test completed"
}

option4_zettlr() {
  log "=== Testing Selective Update (zettlr) ==="
  setup_zettlr_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update zettlr || log "ERROR: update zettlr failed"
  log "Selective update test completed"
}

option4_threeapp() {
  log "=== Testing Selective Update (Three Apps) ==="
  setup_appflowy_config "0.1.0"
  setup_qownnotes_config "0.1.0"
  setup_zettlr_config "0.1.0"
  cd "$APP_ROOT"
  python3 run.py update appflowy,qownnotes,zettlr || log "ERROR: update appflowy,qownnotes,zettlr failed"
  log "Selective update test for three apps completed"
}

# ======== Main Function ========

main() {
  echo "Simple Manual Testing Script for my-unicorn"
  echo "-------------------------------------------"
  echo "This script only backs up and tests qownnotes and zettlr"

  # Backup configs before testing
  backup_app_configs

  # Menu for test selection
  while true; do
    echo ""
    echo "Available tests:"
    echo "1) (URL)Option 1 test qownnotes"
    echo "2) (URL)Option 1 test zettlr"
    echo "3) (Catalog)Option 2 test qownnotes"
    echo "4) (Catalog)Option 2 test zettlr"
    echo "5) (Auto)Option 3 test with 3 apps"
    echo "6) (Auto)Option 3 test qownnotes and zettlr"
    echo "7) (Auto)Option 3 test qownnotes"
    echo "8) (Auto)Option 3 test zettlr"
    echo "9) (Selective)Option 4 test with 3 apps"
    echo "10) (Selective)Option 4 test qownnotes"
    echo "11) (Selective)Option 4 test zettlr"
    echo "0) Exit and restore configs"
    echo ""

    read -p "Select a test (1-10): " choice

    case $choice in
    1) option1_qownnotes ;;
    2) option1_zettlr ;;
    3) option2_qownnotes ;;
    4) option2_zettlr ;;
    5) option3_threeapp ;;
    6) option3_zettlr_qownnotes ;;
    7) option3_qownnotes ;;
    8) option3_zettlr ;;
    9) option4_threeapp ;;
    10) option4_qownnotes ;;
    11) option4_zettlr ;;
    0)
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
