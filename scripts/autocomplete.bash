#!/usr/bin/env bash
set -euo pipefail

# autocomplete.bash
# Installs/updates shell completion files from the package install dir.
# Default behavior: replace files only when their checksum changes.(Only autocomplete files,
# not rc files)
# Rc files are updated only if necessary line is missing or changed.
# Supports: --force (always replace) and --dry-run (no writes).

XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
INSTALL_DIR="${INSTALL_DIR:-$XDG_DATA_HOME/my-unicorn}"

# Detect source directory: prefer repository location if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_AUTOCOMPLETE="$(dirname "$SCRIPT_DIR")/autocomplete"

if [[ -d "$REPO_AUTOCOMPLETE" && -f "$REPO_AUTOCOMPLETE/bash_autocomplete" ]]; then
  # Running from repository
  SRC_DIR="$REPO_AUTOCOMPLETE"
elif [[ -d "$INSTALL_DIR/autocomplete" ]]; then
  # Running from installed location
  SRC_DIR="$INSTALL_DIR/autocomplete"
else
  echo "Error: Could not find autocomplete source files"
  exit 1
fi

LOG_DIR="$XDG_DATA_HOME/my-unicorn/logs"

# Defaults
FORCE=false
DRY_RUN=false

usage() {
  cat <<EOF
usage: $(basename "$0") [--force] [--dry-run] [--help]

Default: replace files only when content changed.
Options:
  --force    Always replace files
  --dry-run  Show actions but don't write files
  -h, --help Show this help
EOF
  exit 1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --force) FORCE=true; shift ;;
      --dry-run) DRY_RUN=true; shift ;;
      -h|--help) usage ;;
      *) echo "Unknown arg: $1"; usage ;;
    esac
  done
}

sha256() {
  local file
  file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  else
    shasum -a 256 "$file" | awk '{print $1}'
  fi
}

make_dirs() {
  mkdir -p "$LOG_DIR"
}

log() {
  local msg
  msg="$1"
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$msg" >> "$LOG_DIR/completion-install.log"
}

replace_file_if_changed() {
  local src dst rel ssum dstsum
  src="$1"
  dst="$2"
  rel="$3"

  if [[ ! -f "$src" ]]; then
    return 0
  fi

  mkdir -p "$(dirname "$dst")"

  if [[ -f "$dst" ]]; then
    ssum=$(sha256 "$src")
    dstsum=$(sha256 "$dst")

    if [[ "$ssum" == "$dstsum" ]] && [[ "$FORCE" == false ]]; then
      echo "ℹ️  Unchanged: $rel"
      return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
      echo "DRY RUN: would replace $dst"
      return 0
    fi

    cp -a "$src" "$dst"
    chmod 0644 "$dst" || true
    echo "Updated: $rel"
    log "updated: $rel"
  else
    if [[ "$DRY_RUN" == true ]]; then
      echo "DRY RUN: would install $dst"
      return 0
    fi
    cp -a "$src" "$dst"
    chmod 0644 "$dst" || true
    echo "Installed: $rel"
    log "installed: $rel"
  fi
}

determine_bash_rc() {
  if [[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/bash/.bashrc" ]]; then
    echo "${XDG_CONFIG_HOME:-$HOME/.config}/bash/.bashrc"
  elif [[ -f "$HOME/.bashrc" ]]; then
    echo "$HOME/.bashrc"
  else
    echo "${XDG_CONFIG_HOME:-$HOME/.config}/bash/.bashrc"
  fi
}

check_bash_rc_configured() {
  local rc_file="$1"
  
  # Check if rc file exists
  if [[ ! -f "$rc_file" ]]; then
    return 1
  fi
  
  # Look for loop sourcing completions directory (new method)
  grep -q "for file in.*bash/completions.*; do" "$rc_file" 2>/dev/null && return 0
  
  # Look for direct source statement or completion files (legacy)
  grep -q "my-unicorn.*bash_autocomplete" "$rc_file" 2>/dev/null && return 0
  grep -q "source.*bash/completions/my-unicorn" "$rc_file" 2>/dev/null && return 0
  grep -q "\..*bash/completions/my-unicorn" "$rc_file" 2>/dev/null && return 0
  
  return 1
}

update_bash_completion() {
  local src dst_dir dst rel rc_file
  src="$SRC_DIR/bash_autocomplete"
  dst_dir="${XDG_CONFIG_HOME:-$HOME/.config}/bash/completions"
  dst="$dst_dir/my-unicorn"
  rel="bash/completions/my-unicorn"

  mkdir -p "$dst_dir"
  replace_file_if_changed "$src" "$dst" "$rel"

  rc_file=$(determine_bash_rc)
  
  # Check if completion already configured
  if check_bash_rc_configured "$rc_file"; then
    echo "✅ Bash completion already configured in $rc_file"
    log "bash completion: already configured in $rc_file"
  else
    # Provide user-friendly path with $HOME
    local display_dir="${dst_dir/#$HOME/\$HOME}"
    
    cat <<EOF

⚠️  BASH COMPLETION SETUP REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
To enable bash completion for my-unicorn, add the following to your
$rc_file file:

    # Add custom completions directory
    for file in $display_dir/*; do
        [ -f "\$file" ] && source "\$file"
    done

Then restart your shell or run:
    source $rc_file
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
    log "bash completion: user notification displayed for $rc_file"
  fi
}

determine_zsh_rc() {
  if [[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/.zshrc" ]]; then
    echo "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/.zshrc"
  elif [[ -f "$HOME/.zshrc" ]]; then
    echo "$HOME/.zshrc"
  else
    echo "${XDG_CONFIG_HOME:-$HOME/.config}/zsh/.zshrc"
  fi
}

check_zsh_fpath_configured() {
  local rc_file="$1"
  local dst_dir="$2"
  
  # Check if rc file exists
  if [[ ! -f "$rc_file" ]]; then
    return 1
  fi
  
  # Check for various fpath patterns that include our directory
  # Handles both literal paths and $HOME expansion
  local expanded_dir="${dst_dir/#$HOME/\$HOME}"
  grep -q "fpath=.*[\"'(]${dst_dir//\//\\/}[\"')]" "$rc_file" 2>/dev/null && return 0
  grep -q "fpath=.*(${dst_dir//\//\\/}[[:space:]]" "$rc_file" 2>/dev/null && return 0
  grep -q "fpath=.*[\"'(]${expanded_dir//\//\\/}[\"')]" "$rc_file" 2>/dev/null && return 0
  
  return 1
}

update_zsh_completion() {
  local src dst_dir dst rel rc_file
  src="$SRC_DIR/zsh_autocomplete"
  dst_dir="${XDG_CONFIG_HOME:-$HOME/.config}/zsh/completions"
  dst="$dst_dir/_my-unicorn"
  rel="zsh/_my-unicorn"

  mkdir -p "$dst_dir"
  replace_file_if_changed "$src" "$dst" "$rel"

  rc_file=$(determine_zsh_rc)
  
  # Check if fpath already configured
  if check_zsh_fpath_configured "$rc_file" "$dst_dir"; then
    echo "✅ Zsh completion already configured in $rc_file"
    log "zsh completion: already configured in $rc_file"
  else
    # Provide user-friendly path with $HOME
    local display_dir="${dst_dir/#$HOME/\$HOME}"
    
    cat <<EOF

⚠️  ZSH COMPLETION SETUP REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
To enable zsh completion for my-unicorn, add the following to your
$rc_file file BEFORE any 'compinit' call:

    # my-unicorn completion
    fpath=($display_dir \$fpath)

If you don't have a 'compinit' call yet, also add:

    autoload -Uz compinit && compinit

Then restart your shell or run:
    source $rc_file
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
    log "zsh completion: user notification displayed for $rc_file"
  fi
}

main() {
  parse_args "$@"
  make_dirs

  if [[ ! -d "$SRC_DIR" ]]; then
    echo "No autocomplete source directory found at $SRC_DIR. Nothing to do." >&2
    exit 0
  fi

  update_bash_completion
  update_zsh_completion

  echo "Autocomplete update finished."
}

main "$@"
