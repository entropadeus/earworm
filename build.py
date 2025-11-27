#!/usr/bin/env python3
"""
Build script for creating the Earworm executable.
"""

import subprocess
import sys
import os
from pathlib import Path


def find_faster_whisper_data():
    """Find faster-whisper package location for bundling."""
    try:
        import faster_whisper
        return Path(faster_whisper.__file__).parent
    except ImportError:
        return None


def build():
    """Build the executable using PyInstaller."""
    project_dir = Path(__file__).parent
    main_script = project_dir / "launcher.py"

    # Base PyInstaller command
    icon_path = project_dir / "assets" / "earhole.ico"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "Earworm",
        "--onefile",  # Single executable
        "--windowed",  # No console window for release
        "--add-data", f"{project_dir / 'src'};src",
    ]

    # Add icon if it exists
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    # Add faster-whisper data if found
    fw_path = find_faster_whisper_data()
    if fw_path:
        cmd.extend(["--collect-all", "faster_whisper"])
        cmd.extend(["--collect-all", "ctranslate2"])

    # Collect all submodules for problematic packages
    cmd.extend(["--collect-all", "tkinter"])
    cmd.extend(["--collect-all", "PIL"])
    cmd.extend(["--collect-all", "pynput"])

    # Hidden imports that PyInstaller might miss
    hidden_imports = [
        # pynput platform-specific
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        # Audio
        "sounddevice",
        "wave",
        # Data/ML
        "numpy",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageTk",
        # Tkinter and submodules
        "tkinter",
        "tkinter.ttk",
        "tkinter.font",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "_tkinter",
        # Standard library that might be missed
        "queue",
        "tempfile",
        "json",
        "pathlib",
        "typing",
        "re",
        "dataclasses",
        "enum",
        "abc",
        "math",
        "threading",
        "time",
        "os",
    ]

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # The main script
    cmd.append(str(main_script))

    print("Building Earworm executable...")
    print(f"Command: {' '.join(cmd)}")

    # Run PyInstaller
    result = subprocess.run(cmd, cwd=project_dir)

    if result.returncode == 0:
        print("\nBuild successful!")
        print(f"Executable: {project_dir / 'dist' / 'Earworm.exe'}")
    else:
        print("\nBuild failed!")
        sys.exit(1)


if __name__ == "__main__":
    build()
