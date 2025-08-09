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

# Function to check updates
check_updates() {
  ~/.local/bin/my-unicorn update --check-only
}

# Function to update all apps
update() {
  ~/.local/bin/my-unicorn update
  
  # Update qtile widget after update if Qtile is installed
  if command -v qtile >/dev/null 2>&1; then
    qtile cmd-obj -o widget my-unicorn -f force_update || true
  fi
}

# Function to determine update need apps and print them
# basic notification function that show how many apps need update
show_updates() {
  local count=$(check_updates | grep -c '📦 Update available')

  if [ "$count" = "0" ]; then
    echo "✅ Up-to-date"
  else
    echo "AppImage Updates: $count"
  fi
}

# help for CLI
help() {
  echo "Usage: $0 {update|check|notify|help}"
  echo "--update   Update all of your downloaded AppImages"
  echo "--check    Display status of updates"
  echo "--help     Display this help message"
}

# Parse command line options
case "$1" in
--check | "")
  # Default action if no arguments provided
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
