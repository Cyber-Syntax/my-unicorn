#!/usr/bin/env bash
#
# autocomplete.bash
# -----------------------------------------------------------------------------
# Shell completion installer for "my-unicorn"
#
# This script is responsible for:
#   - Installing bash completion files
#   - Installing zsh completion files
#   - Replacing completion files only when content actually changed
#   - Preserving shell rc files unless configuration is missing
#   - Supporting dry-run mode for safe preview
#   - Supporting force mode for manual overwrite
#
# Important behavior:
#
#   Completion files:
#       Replaced only when checksum/content changes
#
#   Shell rc files:
#       Never overwritten automatically
#       Users are only notified if required configuration is missing
#
# Supported options:
#
#   --force
#       Always replace completion files even if unchanged
#
#   --dry-run
#       Show what would happen without writing files
#
# Examples:
#
#   ./autocomplete.bash
#       Standard safe update
#
#   ./autocomplete.bash --force
#       Force overwrite all completion files
#
#   ./autocomplete.bash --dry-run
#       Preview changes only
#
# Safety flags:
#
#   -e  Exit immediately if a command fails
#   -u  Exit if an unset variable is used
#   -o pipefail
#       Fail a pipeline if any command inside it fails
#
set -Eeuo pipefail
set -o pipefail

# -----------------------------------------------------------------------------
# Global configuration
# -----------------------------------------------------------------------------

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
readonly XDG_DATA_HOME

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
readonly XDG_CONFIG_HOME

INSTALL_DIR="${INSTALL_DIR:-$XDG_DATA_HOME/my-unicorn}"
readonly INSTALL_DIR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

REPO_AUTOCOMPLETE="$(dirname "$SCRIPT_DIR")/autocomplete"
readonly REPO_AUTOCOMPLETE

LOG_DIR="$XDG_DATA_HOME/my-unicorn/logs"
readonly LOG_DIR

# Runtime flags
FORCE=false
DRY_RUN=false

# -----------------------------------------------------------------------------
# Source detection
# -----------------------------------------------------------------------------

# Determine where completion source files should be loaded from.
#
# Priority:
#
# 1. Repository source tree
#    Used when running directly from cloned repo
#
# 2. Installed location
#    Used after normal CLI installation
#
# This makes the script work both for developers and end users.
if [[ -d "$REPO_AUTOCOMPLETE" && -f "$REPO_AUTOCOMPLETE/bash_autocomplete" ]]; then
    SRC_DIR="$REPO_AUTOCOMPLETE"
elif [[ -d "$INSTALL_DIR/autocomplete" ]]; then
    SRC_DIR="$INSTALL_DIR/autocomplete"
else
    printf '❌ Error: Could not find autocomplete source files\n' >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# Help output
# -----------------------------------------------------------------------------

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --force      Always replace completion files
  --dry-run    Show actions without writing files
  -h, --help   Show this help

Examples:
  $(basename "$0")
  $(basename "$0") --force
  $(basename "$0") --dry-run
EOF
    exit 0
}

# -----------------------------------------------------------------------------
# Argument parsing
# -----------------------------------------------------------------------------

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force)
                FORCE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                printf '❌ Unknown argument: %s\n' "$1" >&2
                usage
                ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# Hash helper
# -----------------------------------------------------------------------------

# Return SHA256 checksum for a file.
#
# Supports:
#   sha256sum (Linux)
#
# Used to compare files safely before replacing them.
sha256() {
    local file
    file="$1"

    sha256sum "$file" | awk '{print $1}'

}

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

make_dirs() {
    mkdir -p "$LOG_DIR"
}

log() {
    local message
    message="$1"

    printf '%s %s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$message" >> "$LOG_DIR/completion-install.log"
}

# -----------------------------------------------------------------------------
# File replacement logic
# -----------------------------------------------------------------------------

# Replace a file only when necessary.
#
# Rules:
#
# - If destination does not exist:
#     install it
#
# - If destination exists and checksum differs:
#     replace it
#
# - If destination exists and checksum matches:
#     do nothing
#
# --force overrides checksum behavior
# --dry-run performs no writes
#
# This avoids unnecessary overwrites and keeps updates predictable.
replace_file_if_changed() {
    local src
    local dst
    local rel
    local src_sum
    local dst_sum

    src="$1"
    dst="$2"
    rel="$3"

    if [[ ! -f "$src" ]]; then
        return 0
    fi

    if [[ -f "$dst" ]]; then
        if ! src_sum="$(sha256 "$src")"; then
            printf '❌ Failed to checksum source file: %s\n' "$src" >&2
            return 1
        fi

        if ! dst_sum="$(sha256 "$dst")"; then
            printf '❌ Failed to checksum destination file: %s\n' "$dst" >&2
            return 1
        fi

        if [[ "$src_sum" == "$dst_sum" && "$FORCE" == false ]]; then
            printf 'ℹ️  Unchanged: %s\n' "$rel"
            return 0
        fi

        if [[ "$DRY_RUN" == true ]]; then
            printf 'DRY RUN: would update %s\n' "$dst"
            return 0
        fi

        mkdir -p "$(dirname "$dst")"

        if ! cp -a "$src" "$dst"; then
            printf '❌ Failed to update: %s\n' "$dst" >&2
            return 1
        fi

        chmod 0644 "$dst" || true

        printf 'Updated: %s\n' "$rel"
        log "updated: $rel"
        return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
        printf 'DRY RUN: would install %s\n' "$dst"
        return 0
    fi

    mkdir -p "$(dirname "$dst")"

    if ! cp -a "$src" "$dst"; then
        printf '❌ Failed to install: %s\n' "$dst" >&2
        return 1
    fi

    chmod 0644 "$dst" || true

    printf 'Installed: %s\n' "$rel"
    log "installed: $rel"
}

# -----------------------------------------------------------------------------
# Bash completion setup
# -----------------------------------------------------------------------------

determine_bash_rc() {
    if [[ -f "$XDG_CONFIG_HOME/bash/.bashrc" ]]; then
        printf '%s\n' "$XDG_CONFIG_HOME/bash/.bashrc"
        return
    fi

    if [[ -f "$HOME/.bashrc" ]]; then
        printf '%s\n' "$HOME/.bashrc"
        return
    fi

    printf '%s\n' "$XDG_CONFIG_HOME/bash/.bashrc"
}

check_bash_rc_configured() {
    local rc_file
    rc_file="$1"

    [[ -f "$rc_file" ]] || return 1

    grep -q "for file in.*bash/completions.*; do" "$rc_file" 2>/dev/null && return 0
    grep -q "my-unicorn.*bash_autocomplete" "$rc_file" 2>/dev/null && return 0
    grep -q "source.*bash/completions/my-unicorn" "$rc_file" 2>/dev/null && return 0
    grep -q "\..*bash/completions/my-unicorn" "$rc_file" 2>/dev/null && return 0

    return 1
}

update_bash_completion() {
    local src
    local dst_dir
    local dst
    local rel
    local rc_file
    local display_dir

    src="$SRC_DIR/bash_autocomplete"
    dst_dir="$XDG_CONFIG_HOME/bash/completions"
    dst="$dst_dir/my-unicorn"
    rel="bash/completions/my-unicorn"

    if [[ "$DRY_RUN" != true ]]; then
        mkdir -p "$dst_dir"
    fi

    if ! replace_file_if_changed "$src" "$dst" "$rel"; then
        return 1
    fi

    if ! rc_file="$(determine_bash_rc)"; then
        return 1
    fi

    # Important:
    #
    # "Installed: bash/completions/my-unicorn"
    # means the actual completion file was copied to:
    #
    #   ~/.config/bash/completions/my-unicorn
    #
    # "Bash completion loader already configured"
    # means ~/.bashrc already contains the required logic
    # to automatically source files from:
    #
    #   ~/.config/bash/completions/
    #
    # These are separate checks, so both messages can appear together.

    if check_bash_rc_configured "$rc_file"; then
        printf '✅ Bash completion loader already configured in %s for %s\n' "$rc_file" "$dst_dir"
        log "bash completion loader already configured in $rc_file for $dst_dir"
        return 0
    fi

    display_dir="${dst_dir/#$HOME/\$HOME}"

    cat <<EOF

⚠️  BASH COMPLETION SETUP REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
To enable bash completion for my-unicorn, add this to:

$rc_file

    for file in $display_dir/*; do
        [ -f "\$file" ] && source "\$file"
    done

Then restart your shell or run:

    source $rc_file

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

    log "bash completion user notification displayed for $rc_file"
}

# -----------------------------------------------------------------------------
# Zsh completion setup
# -----------------------------------------------------------------------------

determine_zsh_rc() {
    if [[ -f "$XDG_CONFIG_HOME/zsh/.zshrc" ]]; then
        printf '%s\n' "$XDG_CONFIG_HOME/zsh/.zshrc"
        return
    fi

    if [[ -f "$HOME/.zshrc" ]]; then
        printf '%s\n' "$HOME/.zshrc"
        return
    fi

    printf '%s\n' "$XDG_CONFIG_HOME/zsh/.zshrc"
}

check_zsh_fpath_configured() {
    local rc_file
    local dst_dir
    local expanded_dir

    rc_file="$1"
    dst_dir="$2"

    [[ -f "$rc_file" ]] || return 1

    expanded_dir="${dst_dir/#$HOME/\$HOME}"

    grep -q "fpath=.*[\"'(]${dst_dir//\//\\/}[\"')]" "$rc_file" 2>/dev/null && return 0
    grep -q "fpath=.*(${dst_dir//\//\\/}[[:space:]]" "$rc_file" 2>/dev/null && return 0
    grep -q "fpath=.*[\"'(]${expanded_dir//\//\\/}[\"')]" "$rc_file" 2>/dev/null && return 0

    return 1
}

update_zsh_completion() {
    local src
    local dst_dir
    local dst
    local rel
    local rc_file
    local display_dir

    src="$SRC_DIR/zsh_autocomplete"
    dst_dir="$XDG_CONFIG_HOME/zsh/completions"
    dst="$dst_dir/_my-unicorn"
    rel="zsh/_my-unicorn"

    if [[ "$DRY_RUN" != true ]]; then
        mkdir -p "$dst_dir"
    fi

    if ! replace_file_if_changed "$src" "$dst" "$rel"; then
        return 1
    fi

    if ! rc_file="$(determine_zsh_rc)"; then
        return 1
    fi

    # Important:
    #
    # "Installed: zsh/_my-unicorn"
    # means the actual completion file was copied to:
    #
    #   ~/.config/zsh/completions/_my-unicorn
    #
    # "Zsh fpath already configured"
    # means ~/.zshrc already contains the required:
    #
    #   fpath=(~/.config/zsh/completions $fpath)
    #
    # These are separate checks, so both messages can appear together.

    if check_zsh_fpath_configured "$rc_file" "$dst_dir"; then
        printf '✅ Zsh fpath already configured in %s for %s\n' "$rc_file" "$dst_dir"
        log "zsh fpath already configured in $rc_file for $dst_dir"
        return 0
    fi

    display_dir="${dst_dir/#$HOME/\$HOME}"

    cat <<EOF

⚠️  ZSH COMPLETION SETUP REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Add this BEFORE any 'compinit' call inside:

$rc_file

    fpath=($display_dir \$fpath)

If compinit does not exist yet, also add:

    autoload -Uz compinit && compinit

Then restart your shell or run:

    source $rc_file

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

    log "zsh completion user notification displayed for $rc_file"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
    parse_args "$@"
    make_dirs

    if [[ ! -d "$SRC_DIR" ]]; then
        printf 'No autocomplete source directory found at %s\n' "$SRC_DIR" >&2
        return 0
    fi

    if ! update_bash_completion; then
        return 1
    fi

    if ! update_zsh_completion; then
        return 1
    fi

    printf '✅ Autocomplete update finished.\n'
}

main "$@"
