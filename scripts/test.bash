#!/usr/bin/env bash
# Comprehensive Manual Testing Script for my-unicorn
#
# This script provides a comprehensive CLI testing framework for my-unicorn,
# combining URL installs, catalog installs, updates, and all core functionality.
#
# Author: my-unicorn development team
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
    read -p "$prompt [Y/n]: " answer
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

# ======== Backup and Restore Functions ========

backup_app_configs() {
    info "Backing up existing app configurations"

    local apps=("qownnotes" "nuclear" "keepassxc" "appflowy" "legcord" "joplin" "zettlr")

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

# ======== App Configuration Setup Functions ========

setup_qownnotes_config() {
    local version="${1:-$TEST_VERSION}"
    info "Setting up qownnotes test config with version $version"

    cat >"$CONFIG_DIR/qownnotes.json" <<EOF
{
    "config_version": "1.0.0",
    "source": "catalog",
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
        "extraction": true,
        "url": "https://raw.githubusercontent.com/pbek/QOwnNotes/develop/icons/icon.png",
        "name": "qownnotes.png",
        "source": "extraction",
        "installed": false
    }
}
EOF
}

setup_nuclear_config() {
    local version="${1:-$TEST_VERSION}"
    info "Setting up nuclear test config with version $version"

    cat >"$CONFIG_DIR/nuclear.json" <<EOF
{
    "config_version": "1.0.0",
    "source": "url",
    "appimage": {
        "version": "$version",
        "name": "nuclear-$version.AppImage",
        "rename": "nuclear",
        "name_template": "",
        "characteristic_suffix": [],
        "installed_date": "$(date --iso-8601=seconds)",
        "digest": ""
    },
    "owner": "nukeop",
    "repo": "nuclear",
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
        "extraction": true,
        "url": "",
        "name": "nuclear.png",
        "source": "extraction",
        "installed": false
    }
}
EOF
}

setup_keepassxc_config() {
    local version="${1:-$TEST_VERSION}"
    info "Setting up keepassxc test config with version $version"

    cat >"$CONFIG_DIR/keepassxc.json" <<EOF
{
    "config_version": "1.0.0",
    "source": "url",
    "appimage": {
        "version": "$version",
        "name": "keepassxc-$version-x86_64.AppImage",
        "rename": "keepassxc",
        "name_template": "",
        "characteristic_suffix": [],
        "installed_date": "$(date --iso-8601=seconds)",
        "digest": ""
    },
    "owner": "keepassxreboot",
    "repo": "keepassxc",
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
        "extraction": true,
        "url": "",
        "name": "keepassxc.png",
        "source": "extraction",
        "installed": false
    }
}
EOF
}

setup_appflowy_config() {
    local version="${1:-$TEST_VERSION}"
    info "Setting up appflowy test config with version $version"

    cat >"$CONFIG_DIR/appflowy.json" <<EOF
{
    "config_version": "1.0.0",
    "source": "catalog",
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
    "owner": "appflowy-io",
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
        "extraction": true,
        "url": "",
        "name": "appflowy.png",
        "source": "extraction",
        "installed": false
    }
}
EOF
}

setup_legcord_config() {
    local version="${1:-$TEST_VERSION}"
    info "Setting up legcord test config with version $version"

    cat >"$CONFIG_DIR/legcord.json" <<EOF
{
    "config_version": "1.0.0",
    "source": "catalog",
    "appimage": {
        "version": "$version",
        "name": "legcord-$version.AppImage",
        "rename": "legcord",
        "name_template": "{repo}-{characteristic_suffix}.AppImage",
        "characteristic_suffix": [
            ".AppImage"
        ],
        "installed_date": "$(date --iso-8601=seconds)",
        "digest": ""
    },
    "owner": "legcord",
    "repo": "legcord",
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
        "extraction": true,
        "url": "",
        "name": "legcord.png",
        "source": "extraction",
        "installed": false
    }
}
EOF
}

setup_joplin_config() {
    local version="${1:-$TEST_VERSION}"
    info "Setting up joplin test config with version $version"

    cat >"$CONFIG_DIR/joplin.json" <<EOF
{
    "config_version": "1.0.0",
    "source": "catalog",
    "appimage": {
        "version": "$version",
        "name": "joplin-$version.AppImage",
        "rename": "joplin",
        "name_template": "{repo}-{characteristic_suffix}.AppImage",
        "characteristic_suffix": [
            ".AppImage"
        ],
        "installed_date": "$(date --iso-8601=seconds)",
        "digest": ""
    },
    "owner": "laurent22",
    "repo": "joplin",
    "github": {
        "repo": true,
        "prerelease": false
    },
    "verification": {
        "digest": true,
        "skip": false,
        "checksum_file": "latest-linux.yml",
        "checksum_hash_type": "sha256"
    },
    "icon": {
        "extraction": true,
        "url": "",
        "name": "joplin.png",
        "source": "extraction",
        "installed": false
    }
}
EOF
}

# ======== Version Manipulation Functions ========

set_app_version() {
    local app_name="$1"
    local version="$2"

    if [[ ! -f "$CONFIG_DIR/$app_name.json" ]]; then
        error "Configuration file for $app_name does not exist"
        return 1
    fi

    # Use python to update JSON (more reliable than sed for JSON)
    python3 -c "
import json
import sys

try:
    with open('$CONFIG_DIR/$app_name.json', 'r') as f:
        config = json.load(f)
    
    config['appimage']['version'] = '$version'
    
    with open('$CONFIG_DIR/$app_name.json', 'w') as f:
        json.dump(config, f, indent=4)
    
    print('Successfully updated $app_name version to $version')
except Exception as e:
    print(f'Error updating $app_name version: {e}', file=sys.stderr)
    sys.exit(1)
"
}

set_multiple_app_versions() {
    local version="$1"
    shift
    local apps=("$@")

    info "Setting version $version for apps: ${apps[*]}"

    for app in "${apps[@]}"; do
        set_app_version "$app" "$version"
    done
}

# ======== qownnotes Specific Tests ========

test_qownnotes_install_url() {
    info "=== Testing qownnotes URL Install ==="

    # Remove existing config to ensure clean installation
    cd "$APP_ROOT"
    if python3 run.py remove qownnotes; then
        info "Cleanup (qownnotes): SUCCESS"
    else
        warn "Cleanup (qownnotes): FAILED or app not installed"
    fi

    rm -f "$CONFIG_DIR/qownnotes.json"
    cd "$APP_ROOT"

    if python3 run.py install https://github.com/pbek/QOwnNotes; then
        info "qownnotes URL install: SUCCESS"
    else
        error "qownnotes URL install: FAILED"
    fi
}

test_qownnotes_install_catalog() {
    info "=== Testing qownnotes Catalog Install ==="

    # Remove existing config to ensure clean installation
    cd "$APP_ROOT"
    if python3 run.py remove qownnotes; then
        info "Cleanup (qownnotes): SUCCESS"
    else
        warn "Cleanup (qownnotes): FAILED or app not installed"
    fi

    rm -f "$CONFIG_DIR/qownnotes.json"
    cd "$APP_ROOT"

    if python3 run.py install qownnotes; then
        info "qownnotes catalog install: SUCCESS"
    else
        error "qownnotes catalog install: FAILED"
    fi
}

test_qownnotes_update() {
    info "=== Testing qownnotes Update ==="
    setup_qownnotes_config "$TEST_VERSION"
    cd "$APP_ROOT"

    if python3 run.py update qownnotes; then
        info "qownnotes update: SUCCESS"
    else
        error "qownnotes update: FAILED"
    fi
}

test_qownnotes_list() {
    info "=== Testing qownnotes List ==="
    cd "$APP_ROOT"

    if python3 run.py list; then
        info "qownnotes list: SUCCESS"
    else
        error "qownnotes list: FAILED"
    fi
}

test_qownnotes_remove() {
    info "=== Testing qownnotes Remove ==="
    cd "$APP_ROOT"

    if python3 run.py remove qownnotes; then
        info "qownnotes remove: SUCCESS"
    else
        error "qownnotes remove: FAILED"
    fi
}

test_qownnotes_backup() {
    info "=== Testing qownnotes Backup ==="
    setup_qownnotes_config "1.0.0"
    cd "$APP_ROOT"

    if python3 run.py backup qownnotes; then
        info "qownnotes backup: SUCCESS"
    else
        error "qownnotes backup: FAILED"
    fi
}

# ======== URL Tests ========

test_nuclear_url() {
    info "=== Testing nuclear URL Install ==="

    # Step 1: Remove existing app to ensure clean installation
    cd "$APP_ROOT"
    if python3 run.py remove nuclear; then
        info "Cleanup (nuclear): SUCCESS"
    else
        warn "Cleanup (nuclear): FAILED or app not installed"
    fi

    # Also clean config file manually to be sure
    rm -f "$CONFIG_DIR/nuclear.json"

    # Step 2: Test URL installation
    cd "$APP_ROOT"
    if python3 run.py install https://github.com/nukeop/nuclear; then
        info "nuclear URL install: SUCCESS"
    else
        error "nuclear URL install: FAILED"
    fi
}

test_keepassxc_url() {
    info "=== Testing keepassxc URL Install ==="

    # Step 1: Remove existing app to ensure clean installation
    cd "$APP_ROOT"
    if python3 run.py remove keepassxc; then
        info "Cleanup (keepassxc): SUCCESS"
    else
        warn "Cleanup (keepassxc): FAILED or app not installed"
    fi

    # Also clean config file manually to be sure
    rm -f "$CONFIG_DIR/keepassxc.json"

    # Step 2: Test URL installation
    cd "$APP_ROOT"
    if python3 run.py install https://github.com/keepassxreboot/keepassxc; then
        info "keepassxc URL install: SUCCESS"
    else
        error "keepassxc URL install: FAILED"
    fi
}

test_all_urls() {
    info "=== Testing All URL Installs (Concurrent) ==="

    # Step 1: Remove any existing configs to ensure clean installation
    info "Step 1/2: Removing existing configs for clean URL install test"
    cd "$APP_ROOT"
    if python3 run.py remove nuclear keepassxc; then
        info "Cleanup (nuclear + keepassxc): SUCCESS"
    else
        warn "Cleanup (nuclear + keepassxc): FAILED or apps not installed"
    fi

    # Also clean config files manually to be sure
    rm -f "$CONFIG_DIR/nuclear.json"
    rm -f "$CONFIG_DIR/keepassxc.json"

    # Step 2: Install both URLs concurrently using Python script's built-in concurrency
    info "Step 2/2: Testing concurrent URL installs (nuclear + keepassxc)"
    cd "$APP_ROOT"
    if python3 run.py install https://github.com/nukeop/nuclear https://github.com/keepassxreboot/keepassxc; then
        info "Concurrent URL installs (nuclear + keepassxc): SUCCESS"
    else
        error "Concurrent URL installs (nuclear + keepassxc): FAILED"
    fi
}

# ======== Catalog Tests ========

test_single_catalog_install() {
    info "=== Testing Single Catalog Install ==="

    # Step 1: Remove existing app to ensure clean installation
    info "Step 1/2: Removing existing appflowy for clean install test"
    cd "$APP_ROOT"
    if python3 run.py remove appflowy; then
        info "Cleanup (appflowy): SUCCESS"
    else
        warn "Cleanup (appflowy): FAILED or app not installed"
    fi

    # Also clean config file manually to be sure
    rm -f "$CONFIG_DIR/appflowy.json"

    # Step 2: Test single catalog installation
    info "Step 2/2: Testing single catalog install (appflowy)"
    cd "$APP_ROOT"
    if python3 run.py install appflowy; then
        info "Single catalog install: SUCCESS"
    else
        error "Single catalog install: FAILED"
    fi
}

test_multiple_catalog_install() {
    info "=== Testing Multiple Catalog Install ==="
    local apps=("appflowy" "legcord" "joplin")

    # Step 1: Remove existing apps and configs to ensure clean installation
    info "Step 1/2: Removing existing apps for clean catalog install test"
    cd "$APP_ROOT"
    if python3 run.py remove "${apps[@]}"; then
        info "Cleanup (${apps[*]}): SUCCESS"
    else
        warn "Cleanup (${apps[*]}): FAILED or apps not installed"
    fi

    # Also clean config files manually to be sure
    for app in "${apps[@]}"; do
        rm -f "$CONFIG_DIR/$app.json"
    done

    # Step 2: Install multiple apps from catalog
    info "Step 2/2: Testing multiple catalog install (${apps[*]})"
    cd "$APP_ROOT"
    if python3 run.py install "${apps[@]}"; then
        info "Multiple catalog install: SUCCESS"
    else
        error "Multiple catalog install: FAILED"
    fi
}

test_catalog_updates() {
    info "=== Testing Catalog Updates ==="
    local apps=("appflowy" "legcord" "joplin")

    # Step 1: Set up configs with old versions and test updates
    info "Step 1/3: Setting up old versions and testing catalog updates"
    for app in "${apps[@]}"; do
        case "$app" in
            "appflowy") setup_appflowy_config "$TEST_VERSION" ;;
            "legcord") setup_legcord_config "$TEST_VERSION" ;;
            "joplin") setup_joplin_config "$TEST_VERSION" ;;
        esac
    done

    cd "$APP_ROOT"
    if python3 run.py update "${apps[@]}"; then
        info "Catalog updates: SUCCESS"
    else
        error "Catalog updates: FAILED"
        return 1
    fi

    # Step 2: Remove apps to test cleanup
    info "Step 2/3: Testing removal after updates"
    if python3 run.py remove "${apps[@]}"; then
        info "Post-update removal (${apps[*]}): SUCCESS"
    else
        warn "Post-update removal (${apps[*]}): FAILED"
    fi

    # Step 3: Reinstall to verify clean state
    info "Step 3/3: Reinstalling apps to verify clean state"
    if python3 run.py install "${apps[@]}"; then
        info "Post-removal reinstall: SUCCESS"
    else
        error "Post-removal reinstall: FAILED"
    fi
}

# ======== Comprehensive Tests ========

test_all_qownnotes() {
    info "=== Running All qownnotes Tests ==="

    # Step 1: Test update functionality (requires existing installation)
    info "Step 1/7: Setting up and testing qownnotes update"
    setup_qownnotes_config "$TEST_VERSION"
    test_qownnotes_update

    # Step 2: Test remove functionality (cleans everything for fresh install test)
    info "Step 2/7: Testing qownnotes removal (cleanup for fresh install test)"
    test_qownnotes_remove

    # Step 3: Test catalog installation (fresh install with full config/icon/desktop creation)
    info "Step 3/7: Testing qownnotes catalog installation (fresh install)"
    test_qownnotes_install_catalog

    # Step 4: Test list functionality (verify installation)
    info "Step 4/7: Testing qownnotes list"
    test_qownnotes_list

    # Step 5: Test backup functionality
    info "Step 5/7: Testing qownnotes backup"
    test_qownnotes_backup

    # Step 6: Remove again to prepare for URL install test
    info "Step 6/7: Removing qownnotes for URL install test"
    test_qownnotes_remove

    # Step 7: Test URL installation (fresh install via URL)
    info "Step 7/7: Testing qownnotes URL installation"
    test_qownnotes_install_url
}

test_quick() {
    info "=== Running Quick Comprehensive Tests ==="

    # Step 1: Update qownnotes + appflowy (set old versions first)
    info "Step 3/3: Testing update for qownnotes + appflowy"
    set_app_version "qownnotes" "$TEST_VERSION"
    set_app_version "appflowy" "$TEST_VERSION"
    cd "$APP_ROOT"
    if python3 run.py update qownnotes appflowy; then
        info "Update (qownnotes + appflowy): SUCCESS"
    else
        error "Update (qownnotes + appflowy): FAILED"
    fi

    # Step 2: remove the apps and their config, icons etc.
    info "Removing qownnotes + appflowy before re-install"
    if python3 run.py remove qownnotes appflowy keepassxc; then
        info "Remove (qownnotes + appflowy + keepassxc): SUCCESS"
    else
        warn "Remove (qownnotes + appflowy + keepassxc): FAILED or apps not installed"
    fi

    # Step 3: Install qownnotes + appflowy from catalog
    info "Step 2/3: Installing qownnotes + appflowy from catalog"
    cd "$APP_ROOT"
    if python3 run.py install qownnotes appflowy; then
        info "Catalog install (qownnotes + appflowy): SUCCESS"
    else
        error "Catalog install (qownnotes + appflowy): FAILED"
    fi

    # Step 4: Install keepassxc via URL
    info "Step 1/3: Installing keepassxc via URL"
    rm -f "$CONFIG_DIR/keepassxc.json"
    cd "$APP_ROOT"
    if python3 run.py install https://github.com/keepassxreboot/keepassxc; then
        info "keepassxc URL install: SUCCESS"
    else
        error "keepassxc URL install: FAILED"
    fi

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

    # Test catalog updates (includes update→remove→reinstall pattern)
    test_catalog_updates

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

    Catalog Tests:
        --catalog-single       Install single app from catalog (appflowy)
        --catalog-multiple     Install multiple apps from catalog
        --catalog-update       Test updating multiple catalog apps

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
        --qown-remove)
            test_qownnotes_remove
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
        --catalog-update)
            test_catalog_updates
            ;;
        --quick)
            test_quick
            ;;
        --comprehensive | --all)
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

    # Backup existing configs
    backup_app_configs

    # Set up cleanup trap
    trap 'restore_app_configs; cleanup_test_environment' EXIT

    # Parse and execute command
    parse_arguments "$@"

    info "=== Test completed successfully ==="
}

# Execute main function with all arguments
main "$@"
