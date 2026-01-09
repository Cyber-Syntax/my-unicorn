#!/usr/bin/env bash
# Extract version and release notes from CHANGELOG.md for GitHub Actions
# Outputs to GitHub Actions environment using GITHUB_OUTPUT
# Follows keepachangelog format

set -euo pipefail

# Constants
readonly CHANGELOG_FILE="${1:-CHANGELOG.md}"
readonly GITHUB_OUTPUT="${GITHUB_OUTPUT:-/dev/stdout}"

# Main extraction function
main() {
    local first_header version notes eof

    # Validate CHANGELOG file exists
    if [[ ! -f "$CHANGELOG_FILE" ]]; then
        echo "::error::CHANGELOG.md not found at $CHANGELOG_FILE"
        exit 1
    fi

    # Extract the first version header from CHANGELOG.md
    # Supports both formats: ## [version] and ## vX.Y.Z
    first_header=$(grep -m 1 '^## \[' "$CHANGELOG_FILE" || grep -m 1 '^## v' "$CHANGELOG_FILE" || true)

    if [[ -z "$first_header" ]]; then
        echo "::error::No version header found in CHANGELOG.md"
        echo "::error::Expected format: '## [X.Y.Z]' or '## vX.Y.Z'"
        exit 1
    fi

    # Extract version from header
    if [[ "$first_header" =~ ^\#\#\ \[([0-9]+\.[0-9]+\.[0-9]+[^]]*)\] ]]; then
        # Format: ## [version]
        version="${BASH_REMATCH[1]}"
    elif [[ "$first_header" =~ ^\#\#\ (v[0-9]+\.[0-9]+\.[0-9]+.*) ]]; then
        # Format: ## vX.Y.Z
        version="${BASH_REMATCH[1]}"
    elif [[ "$first_header" =~ ^\#\#\ \[([Uu]nreleased)\] ]]; then
        # Format: ## [Unreleased]
        version="${BASH_REMATCH[1]}"
    else
        echo "::error::Invalid version format in: $first_header"
        echo "::error::Expected: '## [X.Y.Z]' or '## vX.Y.Z'"
        exit 1
    fi

    echo "version=$version" >> "$GITHUB_OUTPUT"
    echo "::notice::Detected version: $version"

    # Check if version is "Unreleased"
    if [[ "$version" =~ ^[Uu]nreleased$ ]]; then
        echo "is_unreleased=true" >> "$GITHUB_OUTPUT"
        echo "::notice::Version is Unreleased, skipping release creation"
        exit 0
    fi

    echo "is_unreleased=false" >> "$GITHUB_OUTPUT"

    # Extract notes for this version (everything between this version header and the next ## header)
    notes=$(awk -v ver="$version" '
        BEGIN { found=0; capture=0; notes=""; }
        /^## \[/ {
            if (!found && index($0, ver) > 0) {
                found=1;
                capture=1;
                next;
            } else if (capture==1) {
                capture=0;
            }
        }
        /^## v/ {
            if (!found && index($0, ver) > 0) {
                found=1;
                capture=1;
                next;
            } else if (capture==1) {
                capture=0;
            }
        }
        capture==1 { notes = notes $0 "\n"; }
        END { print notes; }
    ' "$CHANGELOG_FILE")

    # Save notes to output with correct GitHub multiline syntax
    eof=$(dd if=/dev/urandom bs=15 count=1 status=none | base64)
    {
        echo "notes<<$eof"
        echo "$notes"
        echo "$eof"
    } >> "$GITHUB_OUTPUT"

    # For debugging
    echo "Release notes excerpt:"
    echo "$notes" | head -10
}

main "$@"
