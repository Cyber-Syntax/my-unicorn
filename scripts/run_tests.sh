#!/bin/bash
# Quick test runner for GitHub Actions workflow tests
# Usage: ./run_tests.sh [python|bats|all]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${YELLOW}================================${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}================================${NC}"
    echo
}

run_python_tests() {
    print_header "Running Python Tests (pytest)"
    uv run pytest tests/.github/ -v --tb=short
}

run_bats_tests() {
    print_header "Running Bash Tests (bats)"
    bats tests/.github/test_extract_changelog.bats
}

run_all_tests() {
    run_python_tests
    echo
    run_bats_tests
    echo
    echo -e "${GREEN}✅ All tests passed!${NC}"
}

show_help() {
    cat <<EOF
GitHub Actions Test Runner

Usage: $0 [OPTION]

Options:
    python      Run Python tests only (pytest)
    bats        Run Bash tests only (bats)
    all         Run all tests (default)
    help        Show this help message

Examples:
    $0              # Run all tests
    $0 python       # Run only pytest tests
    $0 bats         # Run only bats tests

EOF
}

# Main logic
case "${1:-all}" in
    python)
        run_python_tests
        ;;
    bats)
        run_bats_tests
        ;;
    all)
        run_all_tests
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        echo -e "${RED}Error: Unknown option '$1'${NC}"
        echo
        show_help
        exit 1
        ;;
esac
