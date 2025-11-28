"""Main CLI entry point for my-unicorn AppImage installer.

This module provides the minimal entry point for the command-line
interface, delegating all functionality to specialized command
handlers and CLI components.
"""

import sys

import uvloop

from .cli import CLIRunner


async def async_main() -> None:
    """Run the CLI asynchronously.

    Initialize the CLI runner and execute the main command loop
    asynchronously.
    """
    runner = CLIRunner()
    await runner.run()


def main() -> None:
    """Run the CLI application.

    Install uvloop for improved async performance and run the CLI
    asynchronously.

    Raises:
        KeyboardInterrupt: If the user cancels the operation.
        Exception: For any unexpected errors during execution.

    """
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
