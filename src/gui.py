"""
Earhole - GUI window for STT status display.
Shows recording status and provides visual feedback.
"""

import tkinter as tk
from tkinter import ttk
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw, ImageTk


def create_ear_icon(size: int = 32, color: str = "#4CAF50") -> Image.Image:
    """Create an ear-shaped icon programmatically."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Scale factor
    s = size / 64

    # Background circle
    margin = int(2 * s)
    draw.ellipse([margin, margin, size - margin, size - margin],
                 fill="#1e1e1e", outline=color, width=max(1, int(2 * s)))

    # Simplified ear shape (outer curve)
    ear_points = [
        (40 * s, 12 * s),
        (50 * s, 20 * s),
        (52 * s, 32 * s),
        (48 * s, 44 * s),
        (40 * s, 50 * s),
        (32 * s, 50 * s),
        (28 * s, 46 * s),
        (30 * s, 40 * s),
        (34 * s, 44 * s),
        (40 * s, 40 * s),
        (44 * s, 32 * s),
        (42 * s, 22 * s),
        (34 * s, 16 * s),
        (26 * s, 20 * s),
        (22 * s, 30 * s),
        (24 * s, 42 * s),
    ]

    # Draw ear outline
    for i in range(len(ear_points) - 1):
        draw.line([ear_points[i], ear_points[i + 1]], fill=color, width=max(2, int(3 * s)))

    # Sound waves on left
    wave_color = color
    # Wave 1
    draw.arc([int(8 * s), int(24 * s), int(18 * s), int(40 * s)],
             start=60, end=300, fill=wave_color, width=max(1, int(2 * s)))
    # Wave 2
    draw.arc([int(2 * s), int(20 * s), int(14 * s), int(44 * s)],
             start=60, end=300, fill=wave_color, width=max(1, int(2 * s)))

    return img


class StatusWindow:
    """A small always-on-top window showing Earhole status."""

    STATE_IDLE = "idle"
    STATE_RECORDING = "recording"
    STATE_PROCESSING = "processing"

    def __init__(self):
        self._root: Optional[tk.Tk] = None
        self._label: Optional[tk.Label] = None
        self._state = self.STATE_IDLE
        self._callbacks = {}
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._icon_photo = None  # Keep reference to prevent garbage collection

    def _create_window(self) -> None:
        """Create the tkinter window."""
        self._root = tk.Tk()
        self._root.title("Earhole")
        self._root.attributes('-topmost', True)  # Always on top
        self._root.resizable(False, False)

        # Set window icon
        try:
            icon = create_ear_icon(32, "#4CAF50")
            self._icon_photo = ImageTk.PhotoImage(icon)
            self._root.iconphoto(True, self._icon_photo)
        except (tk.TclError, OSError) as e:
            print(f"Could not set icon: {e}")

        # Position in bottom-right corner
        self._root.geometry("180x70+{}+{}".format(
            self._root.winfo_screenwidth() - 200,
            self._root.winfo_screenheight() - 130
        ))

        # Main frame
        frame = ttk.Frame(self._root, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)

        # Status label
        self._label = tk.Label(
            frame,
            text="Ready\n(Hold F9)",
            font=("Segoe UI", 10, "bold"),
            fg="#4CAF50",
            bg="#1e1e1e",
            width=16,
            height=2
        )
        self._label.pack(fill=tk.BOTH, expand=True)

        # Dark theme
        self._root.configure(bg="#1e1e1e")
        frame.configure(style="Dark.TFrame")

        style = ttk.Style()
        style.configure("Dark.TFrame", background="#1e1e1e")

        # Handle window close
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._ready.set()

    def _on_close(self) -> None:
        """Handle window close button."""
        if "exit" in self._callbacks:
            self._callbacks["exit"]()

    def _run_loop(self) -> None:
        """Run the tkinter main loop."""
        self._create_window()
        self._root.mainloop()

    def set_callback(self, action: str, callback: Callable) -> None:
        """Register a callback."""
        self._callbacks[action] = callback

    def set_state(self, state: str) -> None:
        """Update the display state."""
        self._state = state

        if self._root is None:
            return

        def update():
            if self._label is None:
                return

            if state == self.STATE_IDLE:
                self._label.config(
                    text="Ready\n(Hold F9)",
                    fg="#4CAF50"  # Green
                )
            elif state == self.STATE_RECORDING:
                self._label.config(
                    text="Listening...\n(Release F9)",
                    fg="#F44336"  # Red
                )
            elif state == self.STATE_PROCESSING:
                self._label.config(
                    text="Transcribing...",
                    fg="#FFC107"  # Yellow
                )

        self._root.after(0, update)

    def update_title(self, title: str) -> None:
        """Update window title."""
        if self._root:
            self._root.after(0, lambda: self._root.title(title))

    def notify(self, title: str, message: str) -> None:
        """Show a brief notification in the window."""
        if self._root is None or self._label is None:
            return

        def show():
            self._label.config(text=f"{title}\n{message}", fg="#2196F3")

            def restore():
                self.set_state(self._state)

            self._root.after(2000, restore)

        self._root.after(0, show)

    def start(self) -> None:
        """Start the GUI in a background thread."""
        if self._thread is not None:
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)  # Wait for window to be created

    def stop(self) -> None:
        """Stop the GUI."""
        if self._root:
            self._root.after(0, self._root.destroy)


if __name__ == "__main__":
    import time

    print("Testing Earhole window...")

    window = StatusWindow()
    window.start()

    time.sleep(2)
    window.set_state(StatusWindow.STATE_RECORDING)

    time.sleep(2)
    window.set_state(StatusWindow.STATE_PROCESSING)

    time.sleep(2)
    window.notify("Done", "Test complete!")

    time.sleep(3)
    window.stop()
