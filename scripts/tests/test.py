#!/usr/bin/env python3
"""Manual test script for my-unicorn.

This script provides comprehensive CLI testing for my-unicorn,
combining URL installs, catalog installs, updates, and all core functionality.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import argparse
import logging
import sys
from pathlib import Path

from cli_runner import (
    APP_ROOT,
    MY_UNICORN_PROD_VERSION,
    MY_UNICORN_VERSION,
    set_test_mode,
)
from log import setup_logging
from runner import TestRunner

logger = logging.getLogger("my-unicorn-test")

# Configuration constants
CONFIG_DIR = Path.home() / ".config" / "my-unicorn"
APPS_DIR = CONFIG_DIR / "apps"
LOG_DIR = CONFIG_DIR / "logs"
BENCHMARK_DIR = LOG_DIR / "benchmarks"
LOG_FILE = LOG_DIR / "comprehensive_test.log"
DIAGNOSTICS_LOG = LOG_DIR / "test_diagnostics.log"


def init_test_environment(mode: str) -> None:
    """Initialize test environment and logging.

    Args:
        mode: Test mode ("production" or "development")
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 80)
    logger.info("my-unicorn Comprehensive Testing")
    logger.info("=" * 80)
    logger.info("App Root:      %s", APP_ROOT)
    logger.info("Config Dir:    %s", CONFIG_DIR)
    logger.info("Apps Dir:      %s", APPS_DIR)
    logger.info("Log File:      %s", LOG_FILE)
    logger.info("Benchmark Dir: %s", BENCHMARK_DIR)
    logger.info("Test Mode:     %s", mode)
    logger.info("Version:       %s", MY_UNICORN_VERSION)
    logger.info("Version (production): %s", MY_UNICORN_PROD_VERSION)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Comprehensive Manual Testing Script for my-unicorn",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
test modes:
  --quick            Run quick tests (qownnotes only)
  --all              Run all comprehensive tests
  --slow             Run slow tests (large apps like Joplin)
  --test-backup      Test backup functionality
  --test-remove      Test remove with verification
  --test-migrate     Test migration functionality

options:
  --production       Use production my-unicorn (installed command)
  --dev              Use development my-unicorn (uv run my-unicorn)
  --benchmark        Enable benchmarking and save results
  --debug            Enable debug logging

examples:
  # Run quick tests (5 steps: update → catalog install → URL install)
  %(prog)s --quick --dev

  # Run all comprehensive tests (URL installs, catalog installs, updates)
  %(prog)s --all --production --benchmark

  # Test backup functionality
  %(prog)s --test-backup --dev

  # Run slow tests with large apps
  %(prog)s --slow --production --benchmark
        """,
    )

    # Test modes
    parser.add_argument(
        "--quick",
        action="store_true",
        help=(
            "Run quick tests "
            "(qownnotes: update → catalog install → URL install)"
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all comprehensive tests",
    )
    parser.add_argument(
        "--slow",
        action="store_true",
        help="Run slow tests with large apps",
    )
    parser.add_argument(
        "--test-backup",
        action="store_true",
        help="Test backup functionality",
    )
    parser.add_argument(
        "--test-remove",
        action="store_true",
        help="Test remove with verification",
    )
    parser.add_argument(
        "--test-migrate",
        action="store_true",
        help="Test migration functionality",
    )
    parser.add_argument(
        "--test-upgrade",
        action="store_true",
        help="Test upgrade functionality",
    )

    # Options
    parser.add_argument(
        "--production",
        action="store_true",
        help="Use production my-unicorn (installed command)",
    )
    parser.add_argument(
        "--report-format",
        choices=["console", "json", "markdown"],
        default="console",
        help="Output format for test reports (default: console)",
    )
    parser.add_argument(
        "--output",
        help="Output file for reports (JSON or Markdown format)",
    )
    parser.add_argument(
        "--status",
        nargs="?",
        const="latest",
        help="Show report status for specific version or latest",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use development my-unicorn (uv run my-unicorn)",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Enable benchmarking and save results",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Validate mode flags
    if args.production and args.dev:
        parser.error("Cannot use both --production and --dev flags")

    # Determine test mode (default to development)
    if args.production:
        mode = "production"
    elif args.dev:
        mode = "development"
    else:
        mode = "development"  # Default to development mode

    # Set up logging
    setup_logging(debug=args.debug)

    # Set CLI runner mode
    set_test_mode(mode)

    # Initialize environment
    init_test_environment(mode)

    # Create test runner with optional benchmarking
    runner = TestRunner(enable_benchmark=args.benchmark)

    # Run tests based on arguments
    try:
        # Check for status retrieval first
        if args.status:
            version = args.status if args.status != "latest" else None
            report_status = runner.get_report_status(version)
            if report_status:
                version_str = report_status["version"]
                logger.info("Report Status for version %s:", version_str)
                logger.info("  Total Tests: %s", report_status["total"])
                logger.info("  Passed: %s", report_status["passed"])
                logger.info("  Failed: %s", report_status["failed"])
                logger.info("  Warnings: %s", report_status["warnings"])
                logger.info("  Timestamp: %s", report_status["timestamp"])
            else:
                logger.error("No report found for version: %s", args.status)
            return 0

        if args.quick:
            runner.run_quick()
        elif args.all:
            runner.run_all()
        elif args.slow:
            runner.run_slow()
        elif args.test_backup:
            runner.run_backup_mode()
        elif args.test_remove:
            runner.run_remove_mode()
        elif args.test_migrate:
            runner.run_migrate_mode()
        elif args.test_upgrade:
            runner.run_upgrade_mode()
        else:
            parser.print_help()
            return 0

        # Print summary
        runner.print_summary()

        # Export report if requested
        if args.output and args.report_format in ("json", "markdown"):
            output_path = Path(args.output)
            if args.report_format == "json":
                runner.generate_json_report(output_path)
                logger.info("JSON report saved to: %s", output_path)
            elif args.report_format == "markdown":
                runner.generate_markdown_report(output_path)
                logger.info("Markdown report saved to: %s", output_path)

    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("Tests interrupted by user")
        return 130
    except Exception:
        logger.exception("Unexpected error")
        return 1
    else:
        return 0 if runner.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
