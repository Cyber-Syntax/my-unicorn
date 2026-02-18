"""Main CLI entry point for my-unicorn AppImage installer.

This module provides the minimal entry point for the command-line
interface, delegating all functionality to specialized command
handlers and CLI components.
"""

import sys

import uvloop

from my_unicorn.cli import CLIRunner
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


async def async_main() -> None:
    """Run the CLI asynchronously.

    Initialize the CLI runner and execute the main command loop
    asynchronously.
    """
    logger.info("CLI started")
    runner = CLIRunner()
    try:
        await runner.run()
        logger.debug("CLI completed successfully")
    except Exception:
        logger.exception("CLI encountered an error")
        raise


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
        logger.info("CLI cancelled by user")
        sys.exit(1)
    except Exception:
        logger.exception("❌ Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    main()
