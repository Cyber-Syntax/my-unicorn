#!/bin/bash
# This script is used to test the basic functionality of the application.

function test_qownnotes {
    python3 run.py remove qownnotes &&
      python3 run.py install qownnotes
}

function test_more_apps {
    python3 run.py remove appflowy legcord joplin qownnotes &&
      python3 run.py install appflowy legcord joplin qownnotes
}

# bash cli to make it easy to test the application

# help cli
function help {
    echo "Usage: $0 [command]"
    echo "Commands:"
    echo "--qown"
    echo "--more"
    echo "--help"
}

# parse command line arguments
function parse_args {
    case "$1" in
        --qown)
            test_qownnotes
            ;;
        --more)
            test_more_apps
            ;;
        --help)
            help
            ;;
        *)
            echo "Invalid command: $1"
            help
            ;;
    esac
}

# parse command line arguments
parse_args "$@"