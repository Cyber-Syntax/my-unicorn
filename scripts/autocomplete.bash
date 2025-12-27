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

MARKER_START="# >>> my-unicorn completion start >>>"
MARKER_END="# <<< my-unicorn completion end <<<"

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

extract_existing_marker_block() {
  local file
  file="$1"
  awk -v start="$MARKER_START" -v end="$MARKER_END" '
    BEGIN{inblock=0}
    $0 ~ start {inblock=1; next}
    $0 ~ end {inblock=0; next}
    inblock {print}
  ' "$file" 2>/dev/null
}

ensure_marker_block_in_file() {
  local file block_content tmp existing_block expected_block
  file="$1"
  block_content="$2"
  tmp=$(mktemp)
  touch "$file"

  # Extract existing marker block content (without markers)
  existing_block=$(extract_existing_marker_block "$file")
  
  # Extract expected block content (without markers) by removing first and last lines
  expected_block=$(printf '%s\n' "$block_content" | sed '1d;$d')

  # Check if the existing block matches what we want to insert
  if [[ "$existing_block" == "$expected_block" ]] && [[ "$FORCE" == false ]]; then
    echo "ℹ️  Autocomplete already configured in: $file"
    rm -f "$tmp"
    return 0
  fi

  # Filter out any existing marker block (start..end) and write the rest to tmp.
  # We avoid passing block_content into awk via -v because it may contain
  # backslashes or escape sequences that trigger awk warnings. Instead write
  # the block to the temp file later using printf which preserves it verbatim.
  awk -v start="$MARKER_START" -v end="$MARKER_END" '
    BEGIN{inblock=0}
    $0 ~ start {inblock=1; next}
    $0 ~ end {inblock=0; next}
    !inblock {print}
  ' "$file" > "$tmp"

  # Append the block content literally.
  printf '%s\n' "$block_content" >> "$tmp"

  if [[ "$DRY_RUN" == true ]]; then
    echo "DRY RUN: would write marker block to $file"
    rm -f "$tmp"
    return 0
  fi

  cp "$tmp" "$file"
  rm -f "$tmp"
  echo "Updated rc file: $file (marker block replaced/inserted)"
  log "rc updated: $file"
}

update_bash_completion() {
  local src dst_dir dst rel block
  src="$SRC_DIR/bash_autocomplete"
  dst_dir="$XDG_DATA_HOME/my-unicorn/autocomplete"
  dst="$dst_dir/bash_autocomplete"
  rel="autocomplete/bash_autocomplete"

  replace_file_if_changed "$src" "$dst" "$rel"

  # Create block with proper newlines
  block="$MARKER_START
MY_UNICORN_COMPLETION_DIR=\"$dst_dir\"
if [ -f \"\$MY_UNICORN_COMPLETION_DIR/bash_autocomplete\" ]; then
  source \"\$MY_UNICORN_COMPLETION_DIR/bash_autocomplete\"
fi
$MARKER_END"

  ensure_marker_block_in_file "$HOME/.bashrc" "$block"
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

check_fpath_exists() {
  local rc_file dst_dir
  rc_file="$1"
  dst_dir="$2"
  
  # Check if fpath already contains our completions directory
  # Look for patterns like: fpath=(..."/path/to/completions"...) or fpath=(/path/to/completions ...)
  grep -q "fpath=.*[\"'(]${dst_dir//\//\\/}[\"')]" "$rc_file" 2>/dev/null ||
  grep -q "fpath=.*(${dst_dir//\//\\/}[[:space:]]" "$rc_file" 2>/dev/null
}

clean_broken_markers() {
  local rc_file tmp
  rc_file="$1"
  tmp=$(mktemp)
  
  # Remove any orphaned markers and incomplete blocks
  awk -v start="$MARKER_START" -v end="$MARKER_END" '
    BEGIN{inblock=0; skip_next_end=0}
    $0 ~ start {
      if(inblock) {
        # Already in block, this is a duplicate start marker
        next
      }
      inblock=1
      print
      next
    }
    $0 ~ end {
      if(!inblock) {
        # End marker without start, skip it
        next
      }
      inblock=0
      print
      next
    }
    {print}
  ' "$rc_file" > "$tmp"
  
  if [[ "$DRY_RUN" == false ]]; then
    cp "$tmp" "$rc_file"
  fi
  rm -f "$tmp"
}

update_zsh_completion() {
  local src dst_dir dst rel rc_file tmp fpath_line
  src="$SRC_DIR/zsh_autocomplete"
  dst_dir="${XDG_CONFIG_HOME:-$HOME/.config}/zsh/completions"
  dst="$dst_dir/_my-unicorn"
  rel="zsh/_my-unicorn"

  mkdir -p "$dst_dir"
  replace_file_if_changed "$src" "$dst" "$rel"

  rc_file=$(determine_zsh_rc)
  mkdir -p "$(dirname "$rc_file")"
  touch "$rc_file"

  # Clean up any broken markers first
  clean_broken_markers "$rc_file"

  # Check if fpath already contains our completions directory
  if check_fpath_exists "$rc_file" "$dst_dir"; then
    echo "ℹ️  fpath already contains $dst_dir in $rc_file"
    log "fpath exists: $dst_dir in $rc_file"
    return 0
  fi

  fpath_line="fpath=($dst_dir \$fpath)"

  # Check if there's already a compinit line
  if grep -q "compinit" "$rc_file" 2>/dev/null; then
    # Check if our fpath line already exists before compinit
    if grep -B5 "compinit" "$rc_file" | grep -q "fpath=.*${dst_dir//\//\\/}"; then
      echo "ℹ️  fpath already configured before compinit in $rc_file"
      return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
      echo "DRY RUN: would insert fpath before compinit in $rc_file"
      return 0
    fi

    tmp=$(mktemp)
    
    # Insert fpath line before the first compinit occurrence
    awk -v fpath_line="$fpath_line" '
      BEGIN{inserted=0}
      /compinit/ && !inserted {
        print fpath_line
        inserted=1
      }
      {print}
    ' "$rc_file" > "$tmp"
    
    cp "$tmp" "$rc_file"
    echo "Inserted fpath before compinit in $rc_file"
    log "fpath inserted before compinit: $rc_file"
    rm -f "$tmp"
  else
    # No compinit found, add both fpath and compinit using marker block
    if [[ "$DRY_RUN" == true ]]; then
      echo "DRY RUN: would add fpath and compinit block to $rc_file"
      return 0
    fi

    block="$MARKER_START
$fpath_line
autoload -Uz compinit && compinit >/dev/null 2>&1
$MARKER_END"

    ensure_marker_block_in_file "$rc_file" "$block"
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
