#!/usr/bin/env bash
# This script is used to automatically update the appimages.
# This would be update only that if you have their configs
# in the ~/.config/my-unicorn/apps directory.
# You need to install the apps first to use this script.
#
# Make sure you enabled batch mode if you want to run this
# script in an automated fashion (e.g. via cron or a window
# manager autostart). Batch mode already defaults to true
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

# my-unicorn new version check command
check_upgrade() {
  if ! output="$("$UNICORN" upgrade --check-only --refresh-cache 2>&1)"; then
    echo "Error: Failed to check for updates. Possible network issue."
    echo "$output"
    return 1
  fi
  echo "$output"
}

# Notify user about CLI upgrade using machine-friendly output so power
# users / WMs can handle notifications their own way.
notify_cli_upgrade() {
  local title="$1"
  local body="$2"

  # Print a machine-friendly notification line so power-users and
  # window managers can consume it (for example via a log-watcher or
  # a startup hook). Keep a simple format that is easy to grep.
  printf 'MY-UNICORN-NOTIFY: %s\n%s\n' "$title" "$body"

  # Also try to trigger a Qtile widget refresh if present. This is
  # left as-is for users using Qtile who want an immediate widget update.
  if command -v qtile >/dev/null 2>&1; then
    qtile cmd-obj -o widget my-unicorn -f force_update >/dev/null 2>&1 || true
  fi
}

# Show CLI upgrade status to user and send notification if an upgrade exists
show_cli_upgrade() {
  local output
  if ! output=$(check_upgrade); then
    echo "⚠️ Could not check CLI upgrade information."
    return 1
  fi

  # Detect common 'no update' responses (allow spaces or hyphens):
  # examples: "no new version", "up to date", "up-to-date", "already at version"
  if echo "$output" | grep -qiE 'no (new|updates?|upgrade)|up[ -]?to[ -]?date|already( at| )?version|nothing to (do|update)|no updates found|no update available'; then
    echo "CLI up-to-date"
    return 0
  fi

  # Try to extract a semantic version from the output (best-effort)
  local new_version
  new_version=$(echo "$output" | grep -Eo '([0-9]+\.){1,3}[0-9]+' | head -n1 || true)

  echo "⬆️ CLI update available"
  if [ -n "$new_version" ]; then
    echo "New version: $new_version"
    notify_cli_upgrade "my-unicorn CLI update available" "New version: $new_version"
  else
    # Fallback to printing entire output and notify with full text
    echo "$output"
    notify_cli_upgrade "my-unicorn CLI update available" "$output"
  fi
}

# Perform CLI upgrade (run the CLI's upgrade command). This may prompt
# interactively depending on the user's my-unicorn settings; callers that
# want fully automated behavior should ensure batch mode is enabled in
# ~/.config/my-unicorn/settings.conf or provide appropriate CLI flags.
upgrade_cli() {
  echo "Upgrading my-unicorn CLI..."
  if ! "$UNICORN" upgrade; then
    echo "Error: CLI upgrade failed. Check logs or run '$UNICORN upgrade' manually."
    return 1
  fi

  echo "✓ CLI upgraded successfully"
  notify_cli_upgrade "my-unicorn CLI upgraded" "Upgrade completed"
}

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
    echo "Up-to-date"
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
  done <<<"$output"

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
  readarray -t outdated_apps <<<"$outdated_output"

  # Remove empty elements
  local filtered_apps=()
  for app in "${outdated_apps[@]}"; do
    if [[ -n "$app" ]]; then
      filtered_apps+=("$app")
    fi
  done
  outdated_apps=("${filtered_apps[@]}")

  if [ ${#outdated_apps[@]} -eq 0 ]; then
    echo "✓ All apps are up-to-date"
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

  echo "✓ All outdated apps updated successfully"
}

# help for CLI
help() {
  echo "Usage: $0 [OPTION] [APP_NAMES...]"
  echo ""
  echo "Options:"
  echo "  --check           Display status of updates (default)"
  echo "  --update-all      Update all of your downloaded AppImages (concurrent)"
  echo "  --update-outdated Update only outdated AppImages (concurrent)"
  echo "  --check-cli       Check for my-unicorn CLI updates"
  echo "  --upgrade-cli     Run the my-unicorn CLI upgrade command (may be interactive)"
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
--check-cli)
  show_cli_upgrade
  ;;
--update-all)
  update_all
  ;;
--update-outdated)
  update_outdated
  ;;
--upgrade-cli)
  upgrade_cli
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
