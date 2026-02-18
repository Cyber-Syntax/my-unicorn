"""Desktop entry file validation utilities."""

from pathlib import Path

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def should_update_desktop_file(
    existing_content: str, new_content: str
) -> bool:
    """Check if desktop file should be updated by comparing key fields.

    Args:
        existing_content: Current desktop file content
        new_content: New desktop file content that would be written

    Returns:
        True if desktop file should be updated

    """

    def parse_desktop_fields(content: str) -> dict[str, str]:
        """Parse key fields from desktop file content."""
        fields = {}
        for line in content.split("\n"):
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                fields[key.strip()] = value.strip()
        return fields

    existing_fields = parse_desktop_fields(existing_content)
    new_fields = parse_desktop_fields(new_content)

    # Key fields that should trigger an update if changed
    important_fields = [
        "Exec",  # AppImage path or parameters
        "Icon",  # Icon path
        "Name",  # Display name
        "Comment",  # Description
        "Categories",  # Application categories
        "MimeType",  # MIME type associations
        "Keywords",  # Search keywords
    ]

    for field in important_fields:
        if existing_fields.get(field) != new_fields.get(field):
            logger.debug("Desktop file field changed: %s", field)
            logger.debug("  Old: %s", existing_fields.get(field))
            logger.debug("  New: %s", new_fields.get(field))
            return True

    return False


def validate_desktop_file(desktop_file: Path) -> list[str]:
    """Validate desktop file format and content.

    Args:
        desktop_file: Path to desktop file to validate

    Returns:
        List of validation errors (empty if valid)

    """
    errors = []

    if not desktop_file.exists():
        errors.append("Desktop file does not exist")
        return errors

    try:
        with desktop_file.open(encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")

        # Check for required header
        if not lines or lines[0] != "[Desktop Entry]":
            errors.append("Missing or invalid [Desktop Entry] header")

        # Check for required fields
        required_fields = ["Name", "Exec", "Type"]
        found_fields = set()

        for line in lines:
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                found_fields.add(key)

        for field in required_fields:
            if field not in found_fields:
                errors.append(f"Missing required field: {field}")

        # Check if AppImage file exists
        for line in lines:
            if line.startswith("Exec="):
                exec_path = line.split("=", 1)[1].strip()
                if not Path(exec_path).exists():
                    errors.append(f"AppImage file does not exist: {exec_path}")

    except OSError as e:
        errors.append(f"Failed to read desktop file: {e}")

    return errors
