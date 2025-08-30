#!/usr/bin/env bash
# This script is used to automatically update the appimages.
# This would be update only that if you have their configs
# in the ~/.config/my-unicorn/apps directory.
# You need to install the apps first to use this script.

# Make sure you set to update without any user interaction.
# in the ~/.config/my-unicorn/settings.conf file.
#
#   "batch_mode": true,
#

set -euo pipefail

UNICORN=~/.local/bin/my-unicorn

# Ensure binary exists
if [ ! -x "$UNICORN" ]; then
  echo "Error: my-unicorn binary not found at $UNICORN"
  exit 127
fi

# Function to determine update need apps and print them
# basic notification function that show how many apps need update
check_updates() {
  if ! output=$("$UNICORN" update --check-only 2>&1); then
    echo "Error: Failed to check updates. Possible network issue."
    echo "$output"
    return 1
  fi
  echo "$output"
}

# Function to update all apps
update() {
  if ! "$UNICORN" update; then
    echo "Error: Update failed. Check your network connection or logs."
    return 1
  fi

  if command -v qtile >/dev/null 2>&1; then
    if ! qtile cmd-obj -o widget my-unicorn -f force_update; then
      echo "Warning: Qtile widget update failed"
    fi
  fi
}

# Function to determine update need apps and print them
show_updates() {
  local output
  if ! output=$(check_updates); then
    echo "⚠️ Could not fetch update information."
    return 1
  fi

  local count
  count=$(echo "$output" | grep -c '📦 Update available' || true)

  if [ "$count" -eq 0 ]; then
    echo "✅ Up-to-date"
  else
    echo "AppImage Updates: $count"
  fi
}

# help for CLI
help() {
  echo "Usage: $0 {update|check|help}"
  echo "--update   Update all of your downloaded AppImages"
  echo "--check    Display status of updates"
  echo "--help     Display this help message"
}

# Parse command line options
case "${1:-}" in
  --check | "")
    show_updates
    ;;
  --update)
    update
    ;;
  --help | -h)
    help
    ;;
  *)
    echo "Invalid option: $1"
    echo ""
    help
    exit 1
    ;;
esac

exit 0
