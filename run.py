#!/usr/bin/env python3
"""Entry point script for my-unicorn development."""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the main function
from my_unicorn.main import main

if __name__ == "__main__":
    main()