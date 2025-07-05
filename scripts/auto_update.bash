#!/usr/bin/env bash
# This script is used to automatically update the appimages.
# This would be update only that if you have their configs
# in the ~/.config/myunicorn/apps directory.
# You need to install the apps first to use this script.

# Make sure you set to update without any user interaction.
# in the ~/.config/myunicorn/settings.json file.
#
#   "batch_mode": true,
#

set -e # Exit on any error

python3 main.py update --all
