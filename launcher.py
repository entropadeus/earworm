#!/usr/bin/env python3
"""
Launcher script for Earworm.
This allows PyInstaller to properly handle the package imports.
"""

import sys
import os

# Ensure src directory is in path for imports
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    base_path = sys._MEIPASS
else:
    # Running as script
    base_path = os.path.dirname(os.path.abspath(__file__))

src_path = os.path.join(base_path, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Now import and run using absolute imports
from app import main

if __name__ == "__main__":
    main()
