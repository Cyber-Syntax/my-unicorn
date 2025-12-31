#!/usr/bin/env python3
"""Test script for logger rotation functionality.

This script tests the my-unicorn logger rotation by:
1. Writing approximately 10MB of log data to my-unicorn.log
2. Running 'my-unicorn install qownnotes' to trigger rotation
3. Verifying rotation happened correctly

Usage:
    uv run python scripts/test_log_rotation.py
"""

import subprocess
import sys
from pathlib import Path


def write_large_log_file(log_path: Path, target_size_mb: int = 10) -> None:
    """Write large amount of data to log file to test rotation.

    Args:
        log_path: Path to the log file
        target_size_mb: Target size in megabytes (default: 10)
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create/open log file in append mode
    target_bytes = target_size_mb * 1024 * 1024
    log_line = "2025-12-30 12:00:00,000 - INFO - my_unicorn.test - Test log entry for rotation testing\n"
    line_bytes = len(log_line.encode("utf-8"))

    print(f"Writing ~{target_size_mb}MB to {log_path}")
    print(f"Each log line is {line_bytes} bytes")

    lines_needed = target_bytes // line_bytes
    print(f"Writing {lines_needed:,} lines...")

    with log_path.open("a", encoding="utf-8") as f:
        for i in range(lines_needed):
            f.write(log_line)
            if (i + 1) % 10000 == 0:
                sys.stdout.write(
                    f"\rProgress: {(i + 1):,}/{lines_needed:,} lines"
                )
                sys.stdout.flush()

    print(f"\nFile size: {log_path.stat().st_size / 1024 / 1024:.2f} MB")


def run_install_command() -> int:
    """Run my-unicorn install qownnotes to trigger log rotation.

    Returns:
        Return code from subprocess
    """
    print("\nRunning: my-unicorn install qownnotes")
    print("This should trigger log rotation if file >= 10MB\n")

    result = subprocess.run(
        ["my-unicorn", "install", "qownnotes"],
        check=False,
    )

    return result.returncode


def check_rotation_results(log_dir: Path) -> None:
    """Check if rotation created backup files.

    Args:
        log_dir: Directory containing log files
    """
    print("\n" + "=" * 60)
    print("Checking rotation results...")
    print("=" * 60)

    # List all log files
    log_files = sorted(log_dir.glob("my-unicorn*.log*"))

    if not log_files:
        print("❌ No log files found!")
        return

    print(f"\nFound {len(log_files)} log file(s):\n")
    for log_file in log_files:
        size_mb = log_file.stat().st_size / 1024 / 1024
        print(f"  {log_file.name:40s} - {size_mb:8.2f} MB")

    # Check for rotation
    rotated_files = [f for f in log_files if f.name != "my-unicorn.log"]

    if rotated_files:
        print(
            f"\n✅ Rotation successful! Found {len(rotated_files)} backup file(s)"
        )
    else:
        print("\n⚠️  No backup files found - rotation may not have occurred")


def main() -> None:
    """Main test function."""
    log_dir = Path.home() / ".config" / "my-unicorn" / "logs"
    log_file = log_dir / "my-unicorn.log"

    print("=" * 60)
    print("My-Unicorn Logger Rotation Test")
    print("=" * 60)
    print(f"\nLog directory: {log_dir}")
    print(f"Log file: {log_file}\n")

    # Step 1: Write large log file
    write_large_log_file(log_file, target_size_mb=10)

    # Step 2: Run install command
    return_code = run_install_command()

    if return_code != 0:
        print(f"\n⚠️  Command exited with code {return_code}")
        print("This might be expected if qownnotes isn't available")

    # Step 3: Check results
    check_rotation_results(log_dir)

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
