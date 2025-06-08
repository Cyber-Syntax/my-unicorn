#!/usr/bin/env bash
# Simple manual testing script for my-unicorn
# Focused only on testing QOwnNotes and Joplin

set -e # Exit on any error

# Configuration
APP_ROOT="$(dirname "$(dirname "$0")")"
CONFIG_DIR="$HOME/.config/myunicorn/apps"
BACKUP_DIR="/tmp/my_unicorn_test_backup"
LOG_FILE="$APP_ROOT/logs/manual_test.log"

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
    "owner": "pbek",
    "repo": "QOwnNotes",
    "version": "$version",
    "checksum_file_name": "QOwnNotes-x86_64.AppImage.sha256",
    "checksum_hash_type": "sha256",
    "appimage_name": "QOwnNotes-$version-x86_64.AppImage",
    "arch_keyword": "x86_64"
}
EOF
}

setup_joplin_config() {
    local version="$1"
    log "Setting up Joplin test config with version $version"

    cat >"$CONFIG_DIR/joplin.json" <<EOF
{
    "owner": "laurent22",
    "repo": "joplin",
    "version": "$version",
    "checksum_file_name": "latest-linux.yml",
    "checksum_hash_type": "sha512",
    "appimage_name": "Joplin-$version.AppImage",
    "arch_keyword": ".appimage"
}
EOF
}

# ======== Test Functions ========

run_my_unicorn() {
    local choice="$1"
    local extra_input="$2"

    log "Running my-unicorn with option $choice"
    cd "$APP_ROOT"

    if [ -z "$extra_input" ]; then
        # Simple choices without extra input
        cat >"/tmp/input.txt" <<EOF
$choice
10
EOF
    else
        # Choices with extra input
        cat >"/tmp/input.txt" <<EOF
$choice
$extra_input
10
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

test_update_both_apps() {
    log "=== Testing Both QOwnNotes and Joplin Update Together ==="
    # set up outdated versions for both apps
    setup_qownnotes_config "21.8.0" # Old version for QOwnNotes
    setup_joplin_config "2.9.17"    # Old version for Joplin
    run_my_unicorn "3" "all"        # Update all
    log "Combined QOwnNotes and Joplin update test completed"
}

test_update_qownnotes() {
    log "=== Testing QOwnNotes Update ==="
    setup_qownnotes_config "21.8.0" # Old version
    run_my_unicorn "3" "all"        # Update all
    log "QOwnNotes update test completed"
}

test_update_joplin() {
    log "=== Testing Joplin Update ==="
    setup_joplin_config "2.9.17" # Old version
    run_my_unicorn "3" "all"     # Update all
    log "Joplin update test completed"
}

test_selective_update() {
    log "=== Testing Selective Update (QOwnNotes) ==="
    setup_qownnotes_config "21.8.0" # Old version

    # Find QOwnNotes position in the app list (usually 3)
    # Add "y" to confirm the update after selecting the app
    run_my_unicorn "4" "4\ny" # Selective update, select QOwnNotes and confirm with "y"
    log "Selective update test completed"
}

test_install_qownnotes() {
    log "=== Testing QOwnNotes Fresh Install ==="
    # Remove existing config if present
    rm -f "$CONFIG_DIR/QOwnNotes.json"

    # Create input file for download with GitHub URL
    cat >"/tmp/input.txt" <<EOF
1
https://github.com/pbek/QOwnNotes


10
EOF

    cd "$APP_ROOT"
    python3 main.py <"/tmp/input.txt" || true
    rm -f "/tmp/input.txt"

    log "QOwnNotes installation test completed"
}

test_install_joplin() {
    log "=== Testing Joplin Fresh Install ==="
    # Remove existing config if present
    rm -f "$CONFIG_DIR/joplin.json"

    # Create input file for download with GitHub URL
    cat >"/tmp/input.txt" <<EOF
1
https://github.com/laurent22/joplin


10
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
        echo "1) Update QOwnNotes"
        echo "2) Update Joplin"
        echo "3) Selectively update QOwnNotes"
        echo "4) Fresh install QOwnNotes"
        echo "5) Fresh install Joplin"
        echo "6) Update Both QOwnNotes and Joplin"
        echo "7) Exit and restore configs"
        echo ""

        read -p "Select a test (1-7): " choice

        case $choice in
            1) test_update_qownnotes ;;
            2) test_update_joplin ;;
            3) test_selective_update ;;
            4) test_install_qownnotes ;;
            5) test_install_joplin ;;
            6) test_update_both_apps ;;
            7)
                log "Restoring original configurations"
                restore_app_configs
                log "Testing completed"
                exit 0
                ;;
            *)
                echo "Invalid selection. Please choose 1-7."
                ;;
        esac
    done
}

# Run the main function
main
