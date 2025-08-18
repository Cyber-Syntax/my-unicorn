"""Main CLI entry point for my-unicorn AppImage installer.

This module provides the minimal entry point for the command-line interface,
delegating all functionality to specialized command handlers and CLI components.
"""

import sys

import uvloop

from .cli import CLIRunner


async def async_main() -> None:
    """Async main function for CLI execution."""
    runner = CLIRunner()
    await runner.run()


def main() -> None:
    """Main entry point for the CLI application."""
    try:
        # Use uvloop for better async performance
        uvloop.install()
        uvloop.run(async_main())
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
