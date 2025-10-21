#!/usr/bin/env bash
# Manual test script for my-unicorn
# REQUIRES: jq, python3
# USAGE: ./scripts/test.bash [--quick|--comprehensive|--help]
#
# This script provides a comprehensive CLI testing framework for my-unicorn,
# combining URL installs, catalog installs, updates, and all core functionality.
#
# Author: Cyber-Syntax
# License: Same as my-unicorn project

set -o errexit -o nounset -o pipefail

# ======== Configuration ========

# Get the absolute path to the application root
APP_ROOT="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")"
readonly APP_ROOT
readonly CONFIG_DIR="$HOME/.config/my-unicorn/apps/"
readonly BACKUP_DIR="$HOME/.config/my-unicorn/tmp/my_unicorn_test_backup"
readonly LOG_FILE="$HOME/.config/my-unicorn/logs/comprehensive_test.log"

# Test configuration
readonly TEST_VERSION="0.1.0"

# ======== Dependency Check ========

check_deps() {
    command -v jq >/dev/null || { echo "ERROR: jq not found. Install: sudo apt install jq"; exit 1; }
    command -v python3 >/dev/null || { echo "ERROR: python3 not found"; exit 1; }
}
check_deps

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

confirm() {
    local prompt="$1"
    local answer
    read -r -p "$prompt [Y/n]: " answer
    answer="${answer:-y}"
    [[ "${answer:0:1}" =~ [yY] ]]
}

# Initialize directories and logging
init_test_environment() {
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"

    # Clear previous log
    true >"$LOG_FILE"

    info "=== my-unicorn Comprehensive Testing Started ==="
    info "App Root: $APP_ROOT"
    info "Config Dir: $CONFIG_DIR"
    info "Backup Dir: $BACKUP_DIR"
    info "Log File: $LOG_FILE"
}

cleanup_test_environment() {
    info "Cleaning up test environment"
    if [[ -n "${BACKUP_DIR:?}" && -d "$BACKUP_DIR" ]]; then
        rm -rf "${BACKUP_DIR:?}"/*
    fi
}

# ======== Version Manipulation ========

set_version() {
    local app="$1" version="$2"
    local config_file="$CONFIG_DIR/${app}.json"
    
    [[ -f "$config_file" ]] || { error "Config not found: $config_file"; return 1; }
    
    info "Setting $app version to $version (for update test)"
    jq --arg v "$version" '.appimage.version = $v' "$config_file" > "$config_file.tmp" \
        && mv "$config_file.tmp" "$config_file"
}

# ======== Backup and Restore Functions ========

backup_app_configs() {
    info "Backing up existing app configurations"

    local apps=("keepassxc" "legcord" "zettlr")

    for app in "${apps[@]}"; do
        if [[ -f "$CONFIG_DIR/$app.json" ]]; then
            cp "$CONFIG_DIR/$app.json" "$BACKUP_DIR/"
            info "Backed up $app.json"
        fi
    done
}

restore_app_configs() {
    info "Restoring original app configurations"

    for backup_file in "$BACKUP_DIR"/*.json; do
        if [[ -f "$backup_file" ]]; then
            local filename
            filename="$(basename "$backup_file")"
            cp "$backup_file" "$CONFIG_DIR/"
            info "Restored $filename"
        fi
    done
}

# ======== qownnotes Specific Tests ========

test_qownnotes_install_url() {
    info "Testing qownnotes URL install"
    python3 run.py remove qownnotes 2>/dev/null || true
    python3 run.py install https://github.com/pbek/QOwnNotes
}

test_qownnotes_install_catalog() {
    info "Testing qownnotes catalog install"
    python3 run.py remove qownnotes 2>/dev/null || true
    python3 run.py install qownnotes
}

test_qownnotes_update() {
    info "Testing qownnotes update"
    set_version "qownnotes" "$TEST_VERSION"
    cd "$APP_ROOT"
    python3 run.py update qownnotes
}

test_qownnotes_list() {
    info "Testing qownnotes list"
    cd "$APP_ROOT"
    python3 run.py list
}

test_qownnotes_backup() {
    info "Testing qownnotes backup"
    set_version "qownnotes" "1.0.0"
    cd "$APP_ROOT"
    python3 run.py backup qownnotes
}

# ======== URL Tests ========

test_nuclear_url() {
    info "Testing nuclear URL install"
    python3 run.py remove nuclear 2>/dev/null || true
    python3 run.py install https://github.com/nukeop/nuclear
}

test_keepassxc_url() {
    info "Testing keepassxc URL install"
    python3 run.py remove keepassxc 2>/dev/null || true
    python3 run.py install https://github.com/keepassxreboot/keepassxc
}

test_all_urls() {
    info "Testing all URL installs (concurrent)"
    info "Step 1/2: Removing existing configs for clean URL install test"
    python3 run.py remove nuclear keepassxc 2>/dev/null || true

    info "Step 2/2: Testing concurrent URL installs (nuclear + keepassxc)"
    python3 run.py install https://github.com/nukeop/nuclear https://github.com/keepassxreboot/keepassxc
}

# ======== Catalog Tests ========

test_single_catalog_install() {
    info "Testing single catalog install"
    info "Step 1/2: Removing existing appflowy for clean install test"
    python3 run.py remove appflowy 2>/dev/null || true

    info "Step 2/2: Testing single catalog install (appflowy)"
    python3 run.py install appflowy
}

test_multiple_catalog_install() {
    info "Testing multiple catalog install"
    local apps=("appflowy" "legcord" "joplin")

    info "Step 1/2: Removing existing apps for clean catalog install test"
    python3 run.py remove "${apps[@]}" 2>/dev/null || true

    info "Step 2/2: Testing multiple catalog install (${apps[*]})"
    cd "$APP_ROOT"
    python3 run.py install "${apps[@]}"
}

# ======== Update Tests ========
# Update specific apps to test update functionality
# appflowy: Catalog + digest
# legcord: Catalog + checksum_file via latest-linux.yml
# keepassxc: URL + checksum_file via x.AppImage.DIGEST
# tagspaces: Catalog + Digest and checksum_file via SHA256SUMS.txt
test_updates() {
    info "=== Testing Updates ==="
    local apps=("appflowy" "legcord" "tagspaces" "keepassxc")

    # Step 1: Set up configs with old versions and test updates
    info "Step 1/3: Setting up old versions and testing updates"
    for app in "${apps[@]}"; do
        set_version "$app" "$TEST_VERSION"
    done

    cd "$APP_ROOT"
    python3 run.py update "${apps[@]}"

}

# `update` command is different than above because it updates all apps instead of specific ones
test_updates_all() {
    info "=== Testing Updates All ==="
    local apps=("appflowy" "legcord" "tagspaces")

    # Step 1: Set up configs with old versions and test updates all
    info "Step 1/3: Setting up old versions and testing updates all"
    for app in "${apps[@]}"; do
        set_version "$app" "$TEST_VERSION"
    done

    cd "$APP_ROOT"
    python3 run.py update

}

# ======== Comprehensive Tests ========

test_all_qownnotes() {
    info "=== Running All qownnotes Tests ==="

    # Step 1: Test update functionality (requires existing installation)
    info "Step 1/5: Setting up and testing qownnotes update"
    set_version "qownnotes" "$TEST_VERSION"
    test_qownnotes_update

    # Step 3: Test catalog installation (fresh install with full config/icon/desktop creation)
    info "Step 2/5: Testing qownnotes catalog installation (fresh install)"
    test_qownnotes_install_catalog

    # Step 4: Test list functionality (verify installation)
    info "Step 3/5: Testing qownnotes list"
    test_qownnotes_list

    # Step 5: Test backup functionality
    info "Step 4/5: Testing qownnotes backup"
    test_qownnotes_backup

    # Step 7: Test URL installation (fresh install via URL)
    info "Step 5/5: Testing qownnotes URL installation"
    test_qownnotes_install_url
}

test_quick() {
    info "=== Running Quick Comprehensive Tests ==="

    # Step 1: Update qownnotes + appflowy (set old versions first)
    info "Step 3/3: Testing update for qownnotes + appflowy"
    set_version "qownnotes" "$TEST_VERSION"
    set_version "appflowy" "$TEST_VERSION"
    cd "$APP_ROOT"
    python3 run.py update qownnotes appflowy

    # Step 2: remove the apps and their config, icons etc.
    info "Removing qownnotes + appflowy before re-install"
    python3 run.py remove qownnotes appflowy keepassxc 2>/dev/null || true

    # Step 3: Install qownnotes + appflowy from catalog
    info "Step 2/3: Installing qownnotes + appflowy from catalog"
    cd "$APP_ROOT"
    python3 run.py install qownnotes appflowy

    # Step 4: Install keepassxc via URL
    info "Step 1/3: Installing keepassxc via URL"
    python3 run.py remove keepassxc 2>/dev/null || true
    python3 run.py install https://github.com/keepassxreboot/keepassxc

    info "Quick comprehensive tests completed successfully!"
}

test_comprehensive() {
    info "=== Running Comprehensive Tests ==="

    # Test all qownnotes functionality (includes update→remove→install pattern)
    test_all_qownnotes

    # Test URL installs (includes cleanup and fresh installs)
    test_all_urls

    # Test catalog functionality (includes cleanup and fresh installs)
    test_multiple_catalog_install

    # Test updates (includes update→remove→reinstall pattern)
    test_updates

    info "=== All comprehensive tests completed ==="
}

# ======== Help Function ========

show_help() {
    cat <<EOF
Comprehensive Manual Testing Script for my-unicorn

USAGE:
    $0 [COMMAND]

COMMANDS:
    qownnotes Tests:
        --qown-install-url      Install qownnotes via URL
        --qown-install-catalog  Install qownnotes from catalog
        --qown-update          Update qownnotes (sets up old version first)
        --qown-list            List installed apps (after installing qownnotes)
        --qown-remove          Remove qownnotes
        --qown-backup          Test backup functionality with qownnotes
        --qown-all             Run all qownnotes tests

    URL Tests:
        --url-nuclear          Install nuclear via URL
        --url-keepassxc        Install keepassxc via URL
        --url-all              Run all URL tests (keepassxc + nuclear)
    Update Tests:
        --update               Test updates for multiple apps (appflowy + legcord + joplin)
        --update-all           Test updates for all apps

    Catalog Tests:
        --catalog-single       Install single app from catalog (appflowy)
        --catalog-multiple     Install multiple apps from catalog

    Comprehensive Tests:
        --quick               Run quick tests (url + catalog + update)
        --comprehensive       Run all comprehensive tests
        --all                 Alias for --comprehensive

    Utilities:
        --cleanup             Clean up test environment
        --backup-configs      Backup current app configurations
        --restore-configs     Restore app configurations from backup
        --help               Show this help message

EXAMPLES:
    $0 --qown-all                    # Test all qownnotes functionality
    $0 --catalog-multiple            # Test multiple catalog installs
    $0 --comprehensive               # Run all tests
    $0 --quick                       # Quick smoke test

NOTES:
    - Tests will backup existing configurations automatically
    - Logs are written to: $LOG_FILE
    - Set DEBUG=true environment variable for detailed logging
    - Tests run from: $APP_ROOT

EOF
}

# ======== Argument Parsing ========

parse_arguments() {
    if [[ $# -eq 0 ]]; then
        show_help
        exit 0
    fi

    case "$1" in
        --qown-install-url)
            test_qownnotes_install_url
            ;;
        --qown-install-catalog)
            test_qownnotes_install_catalog
            ;;
        --qown-update)
            test_qownnotes_update
            ;;
        --qown-list)
            test_qownnotes_list
            ;;
        --qown-backup)
            test_qownnotes_backup
            ;;
        --qown-all)
            test_all_qownnotes
            ;;
        --url-nuclear)
            test_nuclear_url
            ;;
        --url-keepassxc)
            test_keepassxc_url
            ;;
        --url-all)
            test_all_urls
            ;;
        --catalog-single)
            test_single_catalog_install
            ;;
        --catalog-multiple)
            test_multiple_catalog_install
            ;;
        --update)
            test_updates
            ;;
        --update-all)
            test_updates_all
            ;;
        --quick)
            test_quick
            ;;
        --comprehensive | --all)
            # Run updates first so install tests can use the global removal helper safely
            if ! test_updates; then
                warn "test_updates failed; continuing with comprehensive tests"
            fi
            test_comprehensive
            ;;
        --cleanup)
            cleanup_test_environment
            ;;
        --backup-configs)
            backup_app_configs
            ;;
        --restore-configs)
            restore_app_configs
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

    # # Backup existing configs
    # backup_app_configs

    # # Set up cleanup trap
    # trap 'restore_app_configs; cleanup_test_environment' EXIT

    # Parse and execute command
    parse_arguments "$@"

    info "=== Test completed successfully ==="
}

# Execute main function with all arguments
main "$@"
