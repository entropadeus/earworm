"""
Transcription Preview Window for Earworm.

Provides a floating preview of transcribed text before it's pasted,
allowing users to:
- Accept (Enter) - paste the text
- Cancel (Escape) - discard
- Re-record (Tab/F9) - re-record
- Edit inline - modify text before accepting
- Copy to clipboard (Ctrl+C) - copy without pasting
"""

import tkinter as tk
from tkinter import ttk, font as tkfont
import threading
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum, auto


class PreviewAction(Enum):
    """Possible user actions in the preview window."""
    ACCEPT = auto()          # Accept and paste text
    CANCEL = auto()          # Cancel/discard
    RERECORD = auto()        # Re-record audio
    COPY_ONLY = auto()       # Copy to clipboard without pasting
    EDIT = auto()            # Text was edited


@dataclass
class PreviewResult:
    """Result from the preview window interaction."""
    action: PreviewAction
    text: str                # Final text (may be edited)
    original_text: str       # Original transcription


class PreviewWindowConfig:
    """Configuration for the preview window."""

    def __init__(
        self,
        auto_accept_delay: float = 0.0,      # 0 = disabled, >0 = auto-accept after N seconds
        show_shortcuts: bool = True,          # Show keyboard shortcut hints
        font_size: int = 12,                  # Text font size
        max_width: int = 600,                 # Maximum window width
        max_height: int = 400,                # Maximum window height
        position: str = "center",             # "center", "cursor", "bottom-right"
        theme: str = "dark",                  # "dark" or "light"
    ):
        self.auto_accept_delay = auto_accept_delay
        self.show_shortcuts = show_shortcuts
        self.font_size = font_size
        self.max_width = max_width
        self.max_height = max_height
        self.position = position
        self.theme = theme


class PreviewWindow:
    """
    Floating preview window for transcription review.

    Features:
    - Editable text area with the transcription
    - Keyboard shortcuts for quick actions
    - Auto-accept timer (optional)
    - Dark/light theme support
    - Remembers position within session
    """

    # Theme colors
    THEMES = {
        "dark": {
            "bg": "#1a1a1a",
            "bg_secondary": "#252525",
            "fg": "#ffffff",
            "fg_dim": "#888888",
            "accent": "#00d26a",
            "accent_hover": "#00ff80",
            "border": "#333333",
            "text_bg": "#1e1e1e",
            "text_fg": "#e0e0e0",
            "button_bg": "#2d2d2d",
            "button_fg": "#ffffff",
            "button_accept": "#00d26a",
            "button_cancel": "#ff4757",
            "button_rerecord": "#ffa502",
        },
        "light": {
            "bg": "#f5f5f5",
            "bg_secondary": "#ffffff",
            "fg": "#333333",
            "fg_dim": "#666666",
            "accent": "#00a854",
            "accent_hover": "#00cc66",
            "border": "#cccccc",
            "text_bg": "#ffffff",
            "text_fg": "#333333",
            "button_bg": "#e0e0e0",
            "button_fg": "#333333",
            "button_accept": "#00a854",
            "button_cancel": "#ff4757",
            "button_rerecord": "#ff9500",
        }
    }

    def __init__(self, config: Optional[PreviewWindowConfig] = None):
        """
        Initialize the preview window.

        Args:
            config: Window configuration options
        """
        self.config = config or PreviewWindowConfig()
        self._colors = self.THEMES.get(self.config.theme, self.THEMES["dark"])

        self._root: Optional[tk.Toplevel] = None
        self._text_widget: Optional[tk.Text] = None
        self._result: Optional[PreviewResult] = None
        self._result_event = threading.Event()

        self._original_text = ""
        self._auto_accept_timer = None
        self._countdown_label: Optional[tk.Label] = None
        self._countdown_seconds = 0

        # For dragging
        self._drag_x = 0
        self._drag_y = 0

        # Callbacks
        self._on_rerecord: Optional[Callable] = None

        # Stored position for session persistence
        self._last_position: Optional[tuple] = None

    def show(
        self,
        text: str,
        parent: Optional[tk.Tk] = None,
        on_rerecord: Optional[Callable] = None
    ) -> PreviewResult:
        """
        Show the preview window with transcribed text.

        This method blocks until the user takes an action.

        Args:
            text: Transcribed text to preview
            parent: Parent Tk window (if any)
            on_rerecord: Callback to trigger re-recording

        Returns:
            PreviewResult with the user's action and final text
        """
        self._original_text = text
        self._on_rerecord = on_rerecord
        self._result = None
        self._result_event.clear()

        # Create and show window in main thread or via after()
        if parent and parent.winfo_exists():
            parent.after(0, lambda: self._create_window(text, parent))
        else:
            # Create our own root if no parent
            self._create_standalone_window(text)

        # Wait for result
        self._result_event.wait()
        return self._result

    def show_async(
        self,
        text: str,
        callback: Callable[[PreviewResult], None],
        parent: Optional[tk.Tk] = None,
        on_rerecord: Optional[Callable] = None
    ) -> None:
        """
        Show the preview window asynchronously.

        Args:
            text: Transcribed text to preview
            callback: Function to call with result when user acts
            parent: Parent Tk window
            on_rerecord: Callback for re-recording
        """
        self._original_text = text
        self._on_rerecord = on_rerecord

        def on_complete(result: PreviewResult):
            callback(result)

        self._async_callback = on_complete

        if parent:
            parent.after(0, lambda: self._create_window(text, parent))
        else:
            threading.Thread(
                target=lambda: self._create_standalone_window(text),
                daemon=True
            ).start()

    def _create_standalone_window(self, text: str) -> None:
        """Create a standalone preview window with its own root."""
        root = tk.Tk()
        root.withdraw()  # Hide the root window
        self._create_window(text, root)
        root.mainloop()

    def _create_window(self, text: str, parent: tk.Tk) -> None:
        """Create the preview window UI."""
        self._root = tk.Toplevel(parent)
        self._root.title("Earworm - Preview")
        self._root.attributes('-topmost', True)
        self._root.overrideredirect(True)  # Borderless

        # Configure colors
        self._root.configure(bg=self._colors["bg"])

        # Calculate size based on text
        width, height = self._calculate_size(text)

        # Position window
        x, y = self._calculate_position(parent, width, height)
        self._root.geometry(f"{width}x{height}+{x}+{y}")

        # Create main frame with border
        main_frame = tk.Frame(
            self._root,
            bg=self._colors["bg"],
            highlightbackground=self._colors["border"],
            highlightthickness=2
        )
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header with drag support
        self._create_header(main_frame)

        # Text area
        self._create_text_area(main_frame, text)

        # Shortcut hints
        if self.config.show_shortcuts:
            self._create_shortcuts_bar(main_frame)

        # Button bar
        self._create_buttons(main_frame)

        # Bind keyboard shortcuts
        self._bind_shortcuts()

        # Start auto-accept timer if configured
        if self.config.auto_accept_delay > 0:
            self._start_auto_accept()

        # Focus text widget
        self._text_widget.focus_set()

        # Handle window close
        self._root.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _calculate_size(self, text: str) -> tuple:
        """Calculate appropriate window size based on text content."""
        # Estimate based on character count and line breaks
        lines = text.count('\n') + 1
        max_line_len = max(len(line) for line in text.split('\n')) if text else 20

        # Approximate character width in pixels
        char_width = self.config.font_size * 0.6
        line_height = self.config.font_size * 1.8

        # Calculate dimensions with padding
        text_width = min(int(max_line_len * char_width) + 40, self.config.max_width)
        text_height = min(int(lines * line_height) + 60, 200)  # Text area height

        # Total height includes header, buttons, shortcuts
        total_height = text_height + 120  # Header + buttons + padding
        if self.config.show_shortcuts:
            total_height += 30

        width = max(400, text_width)
        height = min(total_height, self.config.max_height)

        return width, height

    def _calculate_position(self, parent: tk.Tk, width: int, height: int) -> tuple:
        """Calculate window position."""
        # Use last position if available
        if self._last_position:
            return self._last_position

        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()

        if self.config.position == "center":
            x = (screen_w - width) // 2
            y = (screen_h - height) // 2
        elif self.config.position == "cursor":
            x = parent.winfo_pointerx() - width // 2
            y = parent.winfo_pointery() - height // 2
        else:  # bottom-right
            x = screen_w - width - 20
            y = screen_h - height - 60

        # Ensure on screen
        x = max(0, min(x, screen_w - width))
        y = max(0, min(y, screen_h - height))

        return x, y

    def _create_header(self, parent: tk.Frame) -> None:
        """Create the header with title and drag support."""
        header = tk.Frame(parent, bg=self._colors["bg_secondary"], height=32)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Title
        title = tk.Label(
            header,
            text="Transcription Preview",
            font=("Segoe UI", 11, "bold"),
            fg=self._colors["fg"],
            bg=self._colors["bg_secondary"]
        )
        title.pack(side=tk.LEFT, padx=12, pady=6)

        # Countdown label (if auto-accept)
        if self.config.auto_accept_delay > 0:
            self._countdown_label = tk.Label(
                header,
                text="",
                font=("Segoe UI", 9),
                fg=self._colors["accent"],
                bg=self._colors["bg_secondary"]
            )
            self._countdown_label.pack(side=tk.RIGHT, padx=12)

        # Close button
        close_btn = tk.Label(
            header,
            text="\u00d7",  # ×
            font=("Segoe UI", 14),
            fg=self._colors["fg_dim"],
            bg=self._colors["bg_secondary"],
            cursor="hand2"
        )
        close_btn.pack(side=tk.RIGHT, padx=8)
        close_btn.bind("<Button-1>", lambda e: self._on_cancel())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=self._colors["button_cancel"]))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=self._colors["fg_dim"]))

        # Drag support
        header.bind("<Button-1>", self._start_drag)
        header.bind("<B1-Motion>", self._drag)
        title.bind("<Button-1>", self._start_drag)
        title.bind("<B1-Motion>", self._drag)

    def _create_text_area(self, parent: tk.Frame, text: str) -> None:
        """Create the editable text area."""
        text_frame = tk.Frame(parent, bg=self._colors["bg"])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 4))

        # Text widget with scrollbar
        self._text_widget = tk.Text(
            text_frame,
            font=("Consolas", self.config.font_size),
            bg=self._colors["text_bg"],
            fg=self._colors["text_fg"],
            insertbackground=self._colors["accent"],
            selectbackground=self._colors["accent"],
            selectforeground="#ffffff",
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=10,
            pady=8,
            undo=True,  # Enable undo support
            maxundo=50
        )

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self._text_widget.yview)
        self._text_widget.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Insert text and select all for easy replacement
        self._text_widget.insert("1.0", text)
        self._text_widget.tag_add(tk.SEL, "1.0", tk.END)
        self._text_widget.mark_set(tk.INSERT, "1.0")

        # Track modifications
        self._text_widget.bind("<<Modified>>", self._on_text_modified)

    def _create_shortcuts_bar(self, parent: tk.Frame) -> None:
        """Create the keyboard shortcuts hint bar."""
        shortcuts_frame = tk.Frame(parent, bg=self._colors["bg"])
        shortcuts_frame.pack(fill=tk.X, padx=12, pady=(0, 4))

        shortcuts = [
            ("Enter", "Accept"),
            ("Esc", "Cancel"),
            ("Tab", "Re-record"),
            ("Ctrl+C", "Copy"),
        ]

        for key, action in shortcuts:
            hint = tk.Label(
                shortcuts_frame,
                text=f"{key}: {action}",
                font=("Segoe UI", 8),
                fg=self._colors["fg_dim"],
                bg=self._colors["bg"]
            )
            hint.pack(side=tk.LEFT, padx=(0, 16))

    def _create_buttons(self, parent: tk.Frame) -> None:
        """Create the action buttons."""
        button_frame = tk.Frame(parent, bg=self._colors["bg"])
        button_frame.pack(fill=tk.X, padx=12, pady=(4, 12))

        # Button style configuration
        btn_config = {
            "font": ("Segoe UI", 10),
            "relief": tk.FLAT,
            "cursor": "hand2",
            "padx": 16,
            "pady": 6,
        }

        # Cancel button
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            bg=self._colors["button_bg"],
            fg=self._colors["button_fg"],
            activebackground=self._colors["button_cancel"],
            activeforeground="#ffffff",
            command=self._on_cancel,
            **btn_config
        )
        cancel_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._add_hover_effect(cancel_btn, self._colors["button_cancel"])

        # Re-record button
        rerecord_btn = tk.Button(
            button_frame,
            text="Re-record",
            bg=self._colors["button_bg"],
            fg=self._colors["button_fg"],
            activebackground=self._colors["button_rerecord"],
            activeforeground="#ffffff",
            command=self._on_rerecord_click,
            **btn_config
        )
        rerecord_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._add_hover_effect(rerecord_btn, self._colors["button_rerecord"])

        # Copy button
        copy_btn = tk.Button(
            button_frame,
            text="Copy Only",
            bg=self._colors["button_bg"],
            fg=self._colors["button_fg"],
            activebackground=self._colors["accent"],
            activeforeground="#ffffff",
            command=self._on_copy_only,
            **btn_config
        )
        copy_btn.pack(side=tk.LEFT)
        self._add_hover_effect(copy_btn, self._colors["accent"])

        # Accept button (right-aligned, prominent)
        accept_btn = tk.Button(
            button_frame,
            text="Accept & Paste",
            bg=self._colors["button_accept"],
            fg="#ffffff",
            activebackground=self._colors["accent_hover"],
            activeforeground="#ffffff",
            command=self._on_accept,
            **btn_config
        )
        accept_btn.pack(side=tk.RIGHT)
        self._add_hover_effect(accept_btn, self._colors["accent_hover"], default=self._colors["button_accept"])

    def _add_hover_effect(self, button: tk.Button, hover_color: str, default: str = None) -> None:
        """Add hover effect to a button."""
        if default is None:
            default = self._colors["button_bg"]

        button.bind("<Enter>", lambda e: button.config(bg=hover_color))
        button.bind("<Leave>", lambda e: button.config(bg=default))

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        # Enter to accept (Ctrl+Enter if in text widget to allow normal Enter)
        self._root.bind("<Return>", self._on_enter_key)
        self._root.bind("<KP_Enter>", self._on_enter_key)

        # Escape to cancel
        self._root.bind("<Escape>", lambda e: self._on_cancel())

        # Tab to re-record
        self._root.bind("<Tab>", lambda e: self._on_rerecord_click() or "break")

        # Ctrl+C for copy (in addition to default behavior)
        self._root.bind("<Control-c>", self._on_ctrl_c)

        # Ctrl+Enter to accept (alternative)
        self._root.bind("<Control-Return>", lambda e: self._on_accept())

        # Ctrl+Z/Y for undo/redo in text widget
        self._text_widget.bind("<Control-z>", lambda e: self._text_widget.edit_undo() or "break")
        self._text_widget.bind("<Control-y>", lambda e: self._text_widget.edit_redo() or "break")

    def _on_enter_key(self, event) -> Optional[str]:
        """Handle Enter key - accept unless cursor is in text for multi-line."""
        # If Shift is held, allow newline in text
        if event.state & 0x1:  # Shift
            return None  # Allow default behavior

        # Accept the text
        self._on_accept()
        return "break"

    def _on_ctrl_c(self, event) -> None:
        """Handle Ctrl+C - copy selected or all text."""
        # If text is selected, default copy behavior works
        # If no selection, copy all
        try:
            self._text_widget.selection_get()
        except tk.TclError:
            # No selection, copy all
            text = self._get_current_text()
            self._root.clipboard_clear()
            self._root.clipboard_append(text)

    def _start_drag(self, event) -> None:
        """Start window drag."""
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag(self, event) -> None:
        """Drag the window."""
        x = self._root.winfo_x() + (event.x - self._drag_x)
        y = self._root.winfo_y() + (event.y - self._drag_y)
        self._root.geometry(f"+{x}+{y}")
        self._last_position = (x, y)

    def _on_text_modified(self, event) -> None:
        """Handle text modification."""
        # Reset the modified flag
        self._text_widget.edit_modified(False)

        # Cancel auto-accept if user is editing
        if self._auto_accept_timer:
            self._root.after_cancel(self._auto_accept_timer)
            self._auto_accept_timer = None
            if self._countdown_label:
                self._countdown_label.config(text="")

    def _start_auto_accept(self) -> None:
        """Start the auto-accept countdown."""
        self._countdown_seconds = int(self.config.auto_accept_delay)
        self._update_countdown()

    def _update_countdown(self) -> None:
        """Update the countdown display."""
        if self._countdown_seconds <= 0:
            self._on_accept()
            return

        if self._countdown_label:
            self._countdown_label.config(text=f"Auto-accept in {self._countdown_seconds}s")

        self._countdown_seconds -= 1
        self._auto_accept_timer = self._root.after(1000, self._update_countdown)

    def _get_current_text(self) -> str:
        """Get the current text from the widget."""
        return self._text_widget.get("1.0", tk.END).rstrip('\n')

    def _on_accept(self) -> None:
        """Accept the text and close."""
        self._cancel_timer()
        text = self._get_current_text()

        self._result = PreviewResult(
            action=PreviewAction.ACCEPT,
            text=text,
            original_text=self._original_text
        )

        self._close_window()

    def _on_cancel(self) -> None:
        """Cancel and close."""
        self._cancel_timer()

        self._result = PreviewResult(
            action=PreviewAction.CANCEL,
            text="",
            original_text=self._original_text
        )

        self._close_window()

    def _on_rerecord_click(self) -> None:
        """Handle re-record button click."""
        self._cancel_timer()

        self._result = PreviewResult(
            action=PreviewAction.RERECORD,
            text="",
            original_text=self._original_text
        )

        # Call re-record callback if provided
        if self._on_rerecord:
            self._on_rerecord()

        self._close_window()

    def _on_copy_only(self) -> None:
        """Copy to clipboard without pasting."""
        text = self._get_current_text()

        # Copy to clipboard
        self._root.clipboard_clear()
        self._root.clipboard_append(text)

        self._cancel_timer()

        self._result = PreviewResult(
            action=PreviewAction.COPY_ONLY,
            text=text,
            original_text=self._original_text
        )

        self._close_window()

    def _cancel_timer(self) -> None:
        """Cancel the auto-accept timer."""
        if self._auto_accept_timer:
            self._root.after_cancel(self._auto_accept_timer)
            self._auto_accept_timer = None

    def _close_window(self) -> None:
        """Close the window and signal completion."""
        if self._root:
            self._root.destroy()
            self._root = None

        self._result_event.set()

        # Call async callback if set
        if hasattr(self, '_async_callback') and self._async_callback:
            self._async_callback(self._result)
            self._async_callback = None


class PreviewManager:
    """
    Manager for the preview window, handling integration with the main app.

    This provides a higher-level interface for showing previews and
    coordinating with the main application flow.
    """

    def __init__(
        self,
        config: Optional[PreviewWindowConfig] = None,
        parent: Optional[tk.Tk] = None
    ):
        """
        Initialize the preview manager.

        Args:
            config: Preview window configuration
            parent: Parent Tk window for positioning
        """
        self.config = config or PreviewWindowConfig()
        self._parent = parent
        self._current_window: Optional[PreviewWindow] = None
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def set_parent(self, parent: tk.Tk) -> None:
        """Set the parent window reference."""
        self._parent = parent

    def show_preview(
        self,
        text: str,
        on_complete: Callable[[PreviewResult], None],
        on_rerecord: Optional[Callable] = None
    ) -> None:
        """
        Show a preview of the transcribed text.

        Args:
            text: Transcribed text to preview
            on_complete: Callback when user completes an action
            on_rerecord: Callback to trigger re-recording
        """
        if not self._enabled:
            # If preview is disabled, auto-accept
            result = PreviewResult(
                action=PreviewAction.ACCEPT,
                text=text,
                original_text=text
            )
            on_complete(result)
            return

        # Create new preview window
        self._current_window = PreviewWindow(self.config)

        # Show asynchronously
        if self._parent:
            self._current_window.show_async(
                text=text,
                callback=on_complete,
                parent=self._parent,
                on_rerecord=on_rerecord
            )
        else:
            # Run in thread if no parent
            def run_preview():
                result = self._current_window.show(
                    text=text,
                    on_rerecord=on_rerecord
                )
                on_complete(result)

            threading.Thread(target=run_preview, daemon=True).start()

    def close_current(self) -> None:
        """Close the current preview window if open."""
        if self._current_window and self._current_window._root:
            self._current_window._on_cancel()

    def configure(
        self,
        auto_accept_delay: Optional[float] = None,
        show_shortcuts: Optional[bool] = None,
        font_size: Optional[int] = None,
        position: Optional[str] = None,
        theme: Optional[str] = None
    ) -> None:
        """Update configuration settings."""
        if auto_accept_delay is not None:
            self.config.auto_accept_delay = auto_accept_delay
        if show_shortcuts is not None:
            self.config.show_shortcuts = show_shortcuts
        if font_size is not None:
            self.config.font_size = font_size
        if position is not None:
            self.config.position = position
        if theme is not None:
            self.config.theme = theme


if __name__ == "__main__":
    # Test the preview window
    print("Testing Preview Window...")

    def on_result(result: PreviewResult):
        print(f"\nResult:")
        print(f"  Action: {result.action.name}")
        print(f"  Text: '{result.text}'")
        print(f"  Original: '{result.original_text}'")

    # Create a simple test
    root = tk.Tk()
    root.withdraw()

    manager = PreviewManager(
        config=PreviewWindowConfig(
            auto_accept_delay=0,  # Disable for testing
            show_shortcuts=True,
            theme="dark"
        ),
        parent=root
    )

    test_text = """Hello, this is a test transcription.
It has multiple lines to show how the preview handles longer text.
You can edit this text before accepting it."""

    print("Showing preview window...")
    manager.show_preview(
        text=test_text,
        on_complete=on_result,
        on_rerecord=lambda: print("Re-record requested!")
    )

    root.mainloop()
