#!/usr/bin/env bats
# Bats tests for scripts/extract_changelog.sh

setup() {
    # Create a temporary directory for test files
    TEST_TEMP_DIR="$(mktemp -d)"
    export GITHUB_OUTPUT="${TEST_TEMP_DIR}/github_output.txt"
    SCRIPT_PATH="${BATS_TEST_DIRNAME}/../../scripts/extract_changelog.sh"
}

teardown() {
    # Clean up temporary directory
    rm -rf "$TEST_TEMP_DIR"
}

@test "script exists and is executable" {
    [ -f "$SCRIPT_PATH" ]
    [ -x "$SCRIPT_PATH" ]
}

@test "extracts valid bracketed version" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

## [1.2.3] - 2024-01-15

### Added
- New feature A
- New feature B

### Fixed
- Bug fix C
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    [ -f "$GITHUB_OUTPUT" ]
    
    # Check output contains version
    grep -q "version=1.2.3" "$GITHUB_OUTPUT"
    grep -q "is_unreleased=false" "$GITHUB_OUTPUT"
    
    # Check output contains notes
    grep -q "### Added" "$GITHUB_OUTPUT"
    grep -q "New feature A" "$GITHUB_OUTPUT"
}

@test "extracts v-prefixed version" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

## v2.0.0

### Breaking Changes
- Major API refactor
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    grep -q "version=v2.0.0" "$GITHUB_OUTPUT"
    grep -q "is_unreleased=false" "$GITHUB_OUTPUT"
}

@test "handles Unreleased version" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

## [Unreleased]

### Added
- Work in progress
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    grep -q "version=Unreleased" "$GITHUB_OUTPUT"
    grep -q "is_unreleased=true" "$GITHUB_OUTPUT"
}

@test "handles unreleased (lowercase)" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

## [unreleased]

### Added
- Work in progress
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    grep -q "version=unreleased" "$GITHUB_OUTPUT"
    grep -q "is_unreleased=true" "$GITHUB_OUTPUT"
}

@test "extracts pre-release version" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

## [1.0.0-beta.1] - 2024-01-10

### Added
- Beta feature
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    grep -q "version=1.0.0-beta.1" "$GITHUB_OUTPUT"
    grep -q "is_unreleased=false" "$GITHUB_OUTPUT"
}

@test "fails when CHANGELOG.md is missing" {
    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/NONEXISTENT.md"
    
    [ "$status" -eq 1 ]
    [[ "$output" == *"::error::CHANGELOG.md not found"* ]]
}

@test "fails when no version header found" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

This is just some text without version headers.
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 1 ]
    [[ "$output" == *"::error::No version header found"* ]]
}

@test "extracts only first version from multiple versions" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

## [2.1.0] - 2024-02-01

### Added
- Latest feature

## [2.0.0] - 2024-01-15

### Added
- Previous feature
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    grep -q "version=2.1.0" "$GITHUB_OUTPUT"
    
    # Notes should include latest feature but not previous
    grep -q "Latest feature" "$GITHUB_OUTPUT"
    ! grep -q "Previous feature" "$GITHUB_OUTPUT"
}

@test "notes extraction stops at next version header" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

## [1.5.0] - 2024-01-20

### Added
- Feature for 1.5.0

## [1.4.0] - 2024-01-10

### Added
- Feature for 1.4.0
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    grep -q "Feature for 1.5.0" "$GITHUB_OUTPUT"
    ! grep -q "Feature for 1.4.0" "$GITHUB_OUTPUT"
}

@test "handles keepachangelog format with all sections" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

All notable changes to this project will be documented in this file.

## [1.3.0] - 2024-01-20

### Added
- New command-line option

### Changed
- Updated dependencies

### Deprecated
- Old API endpoint

### Removed
- Unused module

### Fixed
- Memory leak

### Security
- Patched CVE-2024-12345

## [1.2.0] - 2024-01-01

### Added
- Initial release
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    grep -q "version=1.3.0" "$GITHUB_OUTPUT"
    
    # Verify all sections are included
    grep -q "### Added" "$GITHUB_OUTPUT"
    grep -q "### Changed" "$GITHUB_OUTPUT"
    grep -q "### Deprecated" "$GITHUB_OUTPUT"
    grep -q "### Removed" "$GITHUB_OUTPUT"
    grep -q "### Fixed" "$GITHUB_OUTPUT"
    grep -q "### Security" "$GITHUB_OUTPUT"
    
    # Should not include 1.2.0 notes
    ! grep -q "Initial release" "$GITHUB_OUTPUT"
}

@test "outputs GitHub Actions annotations" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
## [1.0.0] - 2024-01-01

### Added
- Initial release
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    [[ "$output" == *"::notice::Detected version: 1.0.0"* ]]
}

@test "handles version with date suffix" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
# Changelog

## [1.2.3] - 2024-12-25

### Added
- Christmas feature
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    grep -q "version=1.2.3" "$GITHUB_OUTPUT"
    grep -q "Christmas feature" "$GITHUB_OUTPUT"
}

@test "uses multiline delimiter for notes output" {
    cat > "${TEST_TEMP_DIR}/CHANGELOG.md" <<'EOF'
## [1.0.0]

### Added
- Feature 1
- Feature 2
EOF

    run "$SCRIPT_PATH" "${TEST_TEMP_DIR}/CHANGELOG.md"
    
    [ "$status" -eq 0 ]
    
    # Check for multiline delimiter pattern
    grep -qP "notes<<[A-Za-z0-9+/=]+" "$GITHUB_OUTPUT"
}

@test "script follows strict error handling (set -euo pipefail)" {
    # Verify script has proper error handling
    grep -q "set -euo pipefail" "$SCRIPT_PATH"
}

@test "works with actual project CHANGELOG.md" {
    # Test with the real CHANGELOG.md from the project
    if [ -f "CHANGELOG.md" ]; then
        run "$SCRIPT_PATH" "CHANGELOG.md"
        
        # Should succeed or exit 0 for Unreleased
        [[ "$status" -eq 0 ]]
        
        # Should have version output
        grep -q "version=" "$GITHUB_OUTPUT"
    else
        skip "CHANGELOG.md not found in project root"
    fi
}
