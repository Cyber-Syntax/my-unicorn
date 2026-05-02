#!/usr/bin/env bash

set -euo pipefail
set -o pipefail

APPIMAGE_PATH="${HOME}/Downloads"
CHECKSUM_FILE_NAME="latest-linux.yml"

cleanup() { :; }

handle_signal() {
  printf '[ERROR] Signal received: %s\n' "${1:-UNKNOWN}" >&2
  exit 1
}

trap 'handle_signal INT' INT
trap 'handle_signal TERM' TERM

log_info() { printf '[INFO] %s\n' "$1" >&2; }
log_error() { printf '[ERROR] %s\n' "$1" >&2; }
log_data() { printf '[DATA] %-24s : %s\n' "$1" "$2" >&2; }

validate_dependencies() {
  for cmd in find sed base64 xxd sha512sum awk; do
    command -v "$cmd" >/dev/null 2>&1 || {
      log_error "Missing dependency: $cmd"
      return 1
    }
  done
  log_info "Dependencies OK"
}

validate_directory() {
  [[ -d "${APPIMAGE_PATH}" ]] || {
    log_error "Missing directory: ${APPIMAGE_PATH}"
    return 1
  }
  log_data "Download dir" "${APPIMAGE_PATH}"
}

find_yaml_file() {
  local file

  log_info "Searching YAML file"

  file=$(find "${APPIMAGE_PATH}" -maxdepth 1 -type f -name "${CHECKSUM_FILE_NAME}" 2>/dev/null | head -n 1)

  [[ -n "${file// /}" ]] || {
    log_error "YAML not found"
    return 1
  }

  log_data "YAML file" "${file}"
  printf '%s\n' "${file}"
}

extract_appimage() {
  local yaml="$1"
  local value

  value=$(sed -n 's/^path:[[:space:]]*\(.*\.AppImage\)$/\1/p' "$yaml" | head -n 1)

  [[ -n "${value// /}" ]] || {
    log_error "Failed to parse AppImage"
    return 1
  }

  log_data "AppImage" "${value}"
  printf '%s\n' "${value}"
}

extract_sha512_base64() {
  local yaml="$1"
  local value

  value=$(awk '/^path:.*AppImage$/ {getline; if ($1=="sha512:") print $2}' "$yaml")

  [[ -n "${value// /}" ]] || {
    log_error "Failed to extract base64 sha512"
    return 1
  }

  log_data "Base64 SHA512" "${value}"
  printf '%s\n' "${value}"
}

base64_to_hex() {
  local b64="$1"
  local hex

  hex=$(printf '%s' "$b64" | base64 -d 2>/dev/null | xxd -p -c 256)

  [[ -n "${hex// /}" ]] || {
    log_error "Base64 decode failed"
    return 1
  }

  log_data "Expected HEX" "${hex}"
  printf '%s\n' "${hex}"
}

sha512_file() {
  local file="$1"
  local hash

  hash=$(sha512sum "$file" | awk '{print $1}')

  [[ -n "${hash// /}" ]] || {
    log_error "sha512 failed"
    return 1
  }

  log_data "Actual HEX" "${hash}"
  printf '%s\n' "${hash}"
}

verify() {
  local file="$1"
  local expected="$2"
  local actual

  actual=$(sha512_file "$file")

  printf '\n[COMPARE]\n' >&2
  log_data "Expected" "$expected"
  log_data "Actual" "$actual"

  [[ "$expected" == "$actual" ]] && {
    printf '[SUCCESS] Match\n'
    return 0
  }

  log_error "Mismatch"
  return 1
}

main() {
  local yaml appimage b64 expected file

  validate_dependencies || return 1
  validate_directory || return 1

  yaml=$(find_yaml_file) || return 1
  appimage=$(extract_appimage "$yaml") || return 1

  file="${APPIMAGE_PATH}/${appimage}"

  [[ -f "$file" ]] || {
    log_error "Missing AppImage: $file"
    return 1
  }

  b64=$(extract_sha512_base64 "$yaml") || return 1
  expected=$(base64_to_hex "$b64") || return 1

  verify "$file" "$expected"
}

main "$@"
