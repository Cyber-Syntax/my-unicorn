"""GitHub release description checksum parsing strategies.

This module provides functionality to extract SHA256 checksums from GitHub release descriptions 
using various parsing strategies. Each strategy handles different common formats found in release
descriptions.
"""

import logging
import re

logger = logging.getLogger(__name__)


def parse_checksums_from_description(description: str) -> list[str]:
    """Extract SHA256 checksum lines from the release description.

    Args:
        description: Release description text

    Returns:
        list of lines containing SHA256 checksums in "hash filename" format

    """
    checksums = []

    # Strategy 1: Look in <details> sections with checksums/SHA keywords
    checksums_section = re.search(
        r"<details>.*?<summary>.*?(checksum|sha|hash).*?</summary>(.*?)</details>",
        description,
        re.IGNORECASE | re.DOTALL,
    )

    if checksums_section:
        logger.debug("Found checksums in <details> section")
        section_content = checksums_section.group(2)

        # Look for code blocks within the section
        code_blocks = re.findall(r"```[^\n]*\n(.*?)```", section_content, re.DOTALL)

        # Process each code block
        for block in code_blocks:
            lines = block.strip().split("\n")
            for line in lines:
                line = line.strip()
                # Match SHA256 hash pattern (64 hex chars) followed by filename
                if re.match(r"^[0-9a-f]{64}\s+\S+", line, re.IGNORECASE):
                    checksums.append(line)

    # Strategy 2: Check code blocks directly if nothing found in details
    if not checksums:
        logger.debug("Looking for checksums in code blocks")
        code_blocks = re.findall(r"```[^\n]*\n(.*?)```", description, re.DOTALL)

        for block in code_blocks:
            lines = block.strip().split("\n")
            for line in lines:
                line = line.strip()
                if re.match(r"^[0-9a-f]{64}\s+\S+", line, re.IGNORECASE):
                    checksums.append(line)

    # Strategy 3: Last resort - scan the entire description line by line
    if not checksums:
        logger.debug("Scanning entire description for checksums")
        lines = description.split("\n")
        for line in lines:
            line = line.strip()
            if re.match(r"^[0-9a-f]{64}\s+\S+", line, re.IGNORECASE):
                checksums.append(line)

    logger.debug(f"Found {len(checksums)} SHA256 checksum entries")
    return checksums
