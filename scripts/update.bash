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
# Author: Cyber-Syntax
# License: same as my-unicorn project

set -euo pipefail

UNICORN=~/.local/bin/my-unicorn

# Ensure binary exists
if [ ! -x "$UNICORN" ]; then
  echo "Error: my-unicorn binary not found at $UNICORN"
  exit 127
fi

# Function to determine update need apps and print them
check_updates() {
  if ! output=$("$UNICORN" update --check-only --refresh-cache 2>&1); then
    echo "Error: Failed to check updates. Possible network issue."
    echo "$output"
    return 1
  fi
  echo "$output"
}

update_all() {
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

determine_outdated_apps() {
  local output
  if ! output=$(check_updates); then
    echo "Error: Failed to check updates"
    return 1
  fi
  
  local outdated_apps=()
  while IFS= read -r line; do
    if [[ $line == *"📦 Update available"* ]]; then
      # Extract the app name from the line (first field)
      local app_name
      app_name=$(echo "$line" | awk '{print $1}')
      outdated_apps+=("$app_name")
    fi
  done <<< "$output"
  
  # Return the array of outdated apps
  printf '%s\n' "${outdated_apps[@]}"
}

# Updates only outdated apps via update specific command (concurrent)
update_outdated() {
  local outdated_apps=()
  local outdated_output
  
  if ! outdated_output=$(determine_outdated_apps); then
    echo "Error: Failed to determine outdated apps"
    return 1
  fi
  
  # Use readarray to populate the array safely
  readarray -t outdated_apps <<< "$outdated_output"
  
  # Remove empty elements
  local filtered_apps=()
  for app in "${outdated_apps[@]}"; do
    if [[ -n "$app" ]]; then
      filtered_apps+=("$app")
    fi
  done
  outdated_apps=("${filtered_apps[@]}")
  
  if [ ${#outdated_apps[@]} -eq 0 ]; then
    echo "✅ All apps are up-to-date"
    return 0
  fi
  
  echo "Updating ${#outdated_apps[@]} outdated app(s): ${outdated_apps[*]}"
  
  # Update all outdated apps concurrently in a single command
  if ! "$UNICORN" update "${outdated_apps[@]}"; then
    echo "Error: Update failed for some apps. Check your network connection or logs."
    return 1
  fi

  if command -v qtile >/dev/null 2>&1; then
    if ! qtile cmd-obj -o widget my-unicorn -f force_update; then
      echo "Warning: Qtile widget update failed"
    fi
  fi
  
  echo "✅ All outdated apps updated successfully"
}

# help for CLI
help() {
  echo "Usage: $0 [OPTION] [APP_NAMES...]"
  echo ""
  echo "Options:"
  echo "  --check           Display status of updates (default)"
  echo "  --update-all      Update all of your downloaded AppImages"
  echo "  --update-outdated Update only outdated AppImages (concurrent)"
  echo "  --help, -h        Display this help message"
  echo ""
  echo "Examples:"
  echo "  $0                           # Check for updates"
  echo "  $0 --update-all              # Update all apps"
  echo "  $0 --update-outdated         # Update only outdated apps concurrently"
}

# Parse command line options
case "${1:-}" in
  --check | "")
    show_updates
    ;;
  --update-all)
    update_all
    ;;
  --update-outdated)
    update_outdated
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
