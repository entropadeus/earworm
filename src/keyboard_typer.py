"""
Keyboard simulation module using pynput.
Types text into the currently active text field.
"""

from pynput.keyboard import Controller, Key
import time


class KeyboardTyper:
    """Types text into the active text field using keyboard simulation."""

    def __init__(self, typing_delay: float = 0.0):
        """
        Args:
            typing_delay: Delay between keystrokes in seconds.
                          0.0 = instant (recommended for most apps).
                          Small delay (0.01-0.05) helps with some apps.
        """
        self.typing_delay = typing_delay
        self._keyboard = Controller()

    def type_text(self, text: str, use_clipboard: bool = True) -> None:
        """
        Type text into the currently focused text field.

        Args:
            text: The text to type.
            use_clipboard: If True, use clipboard paste (faster, more reliable).
                           If False, simulate individual keystrokes.
        """
        if not text:
            return

        if use_clipboard:
            self._paste_text(text)
        else:
            self._type_characters(text)

    def _paste_text(self, text: str) -> None:
        """Paste text using clipboard (Ctrl+V on Windows)."""
        try:
            import pyperclip
            clipboard_copy = pyperclip.copy
            clipboard_paste = pyperclip.paste
        except ImportError:
            clipboard_copy = ClipboardFallback.copy
            clipboard_paste = ClipboardFallback.paste

        # Save current clipboard content
        try:
            old_clipboard = clipboard_paste()
        except (RuntimeError, OSError):
            old_clipboard = ""

        try:
            # Copy our text to clipboard
            clipboard_copy(text)

            # Small delay to ensure clipboard is ready
            time.sleep(0.05)

            # Press Ctrl+V
            self._keyboard.press(Key.ctrl)
            self._keyboard.press('v')
            self._keyboard.release('v')
            self._keyboard.release(Key.ctrl)

            # Small delay before restoring clipboard
            time.sleep(0.1)

        finally:
            # Restore original clipboard content
            try:
                clipboard_copy(old_clipboard)
            except (RuntimeError, OSError):
                pass

    def _type_characters(self, text: str) -> None:
        """Type text character by character."""
        for char in text:
            self._keyboard.type(char)
            if self.typing_delay > 0:
                time.sleep(self.typing_delay)

    def press_key(self, key: Key) -> None:
        """Press and release a special key."""
        self._keyboard.press(key)
        self._keyboard.release(key)

    def press_enter(self) -> None:
        """Press the Enter key."""
        self.press_key(Key.enter)

    # === Streaming/Word-level methods ===

    def type_word(self, word: str, add_space: bool = True) -> None:
        """
        Type a single word with optional trailing space.

        Uses direct keyboard typing (not clipboard) for better
        compatibility with background threads in streaming mode.

        Args:
            word: The word to type.
            add_space: If True, add a space after the word.
        """
        if not word:
            return
        text = word + (" " if add_space else "")
        # Use pynput's type() method - works from any thread
        self._keyboard.type(text)

    def type_words(self, words: list, add_trailing_space: bool = True) -> None:
        """
        Type multiple words at once.

        Uses direct keyboard typing (not clipboard) for better
        compatibility with background threads in streaming mode.

        Args:
            words: List of words to type.
            add_trailing_space: If True, add space after last word.
        """
        if not words:
            return
        text = " ".join(words)
        if add_trailing_space:
            text += " "
        # Use pynput's type() method - works from any thread
        self._keyboard.type(text)

    def delete_word(self) -> None:
        """Delete the previous word using Ctrl+Backspace."""
        self._keyboard.press(Key.ctrl)
        self._keyboard.press(Key.backspace)
        self._keyboard.release(Key.backspace)
        self._keyboard.release(Key.ctrl)
        time.sleep(0.02)  # Small delay for stability

    def delete_words(self, count: int) -> None:
        """
        Delete N previous words using Ctrl+Backspace.

        Used for auto-correction when Whisper revises earlier words.

        Args:
            count: Number of words to delete.
        """
        for _ in range(count):
            self.delete_word()

    def delete_characters(self, count: int) -> None:
        """
        Delete N previous characters using Backspace.

        Args:
            count: Number of characters to delete.
        """
        for _ in range(count):
            self._keyboard.press(Key.backspace)
            self._keyboard.release(Key.backspace)
            if self.typing_delay > 0:
                time.sleep(self.typing_delay)

    def replace_words(self, old_words: list, new_words: list) -> None:
        """
        Replace old words with new words (for corrections).

        Deletes the old words, then types the new words.

        Args:
            old_words: Words to delete (used to count deletions).
            new_words: Words to type in their place.
        """
        if old_words:
            self.delete_words(len(old_words))
        if new_words:
            self.type_words(new_words, add_trailing_space=True)


class ClipboardFallback:
    """
    Fallback clipboard implementation if pyperclip isn't available.
    Uses Windows-native ctypes calls.
    """

    @staticmethod
    def copy(text: str) -> None:
        """Copy text to Windows clipboard using ctypes."""
        import ctypes
        from ctypes import wintypes

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Convert to wide string
        text_bytes = (text + '\0').encode('utf-16-le')

        # Open clipboard
        if not user32.OpenClipboard(None):
            raise RuntimeError("Cannot open clipboard")

        try:
            user32.EmptyClipboard()

            # Allocate global memory
            h_mem = kernel32.GlobalAlloc(
                GMEM_MOVEABLE,
                len(text_bytes)
            )
            if not h_mem:
                raise RuntimeError("GlobalAlloc failed")

            # Lock and copy
            p_mem = kernel32.GlobalLock(h_mem)
            if not p_mem:
                kernel32.GlobalFree(h_mem)
                raise RuntimeError("GlobalLock failed")

            ctypes.memmove(p_mem, text_bytes, len(text_bytes))
            kernel32.GlobalUnlock(h_mem)

            # Set clipboard data
            if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
                kernel32.GlobalFree(h_mem)
                raise RuntimeError("SetClipboardData failed")

        finally:
            user32.CloseClipboard()

    @staticmethod
    def paste() -> str:
        """Get text from Windows clipboard using ctypes."""
        import ctypes

        CF_UNICODETEXT = 13

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        if not user32.OpenClipboard(None):
            return ""

        try:
            h_mem = user32.GetClipboardData(CF_UNICODETEXT)
            if not h_mem:
                return ""

            p_mem = kernel32.GlobalLock(h_mem)
            if not p_mem:
                return ""

            try:
                text = ctypes.wstring_at(p_mem)
                return text
            finally:
                kernel32.GlobalUnlock(h_mem)

        finally:
            user32.CloseClipboard()


if __name__ == "__main__":
    # Quick test
    import time

    print("Testing keyboard typer...")
    print("You have 3 seconds to click on a text field...")
    time.sleep(3)

    typer = KeyboardTyper()
    typer.type_text("Hello from STT! This is a test message.")

    print("Done! Check your text field.")
