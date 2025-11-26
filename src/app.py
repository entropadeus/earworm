"""
Main STT Application.
Coordinates all components: recording, transcription, typing, and UI.
"""

import threading
import time
import os
import json
from pathlib import Path
from typing import Any, Optional

from .audio_recorder import AudioRecorder, cleanup_temp_file
from .transcriber import Transcriber, ModelSize
from .keyboard_typer import KeyboardTyper
from .hotkey_manager import PushToTalkManager
from .gui import StatusWindow
from pynput.keyboard import Key


class Config:
    """Application configuration."""

    DEFAULT_CONFIG = {
        "model_size": "base",
        "language": None,  # None = auto-detect
        "typing_delay": 0.0,
        "use_clipboard": True,
        "show_notifications": True,
    }

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to user's app data folder
            app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
            config_dir = Path(app_data) / "LocalSTT"
            try:
                config_dir.mkdir(exist_ok=True)
            except OSError as e:
                print(f"Warning: Could not create config directory: {e}")
            self.config_path = config_dir / "config.json"
        else:
            self.config_path = Path(config_path)

        self._config = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    loaded = json.load(f)
                    self._config.update(loaded)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Could not load config: {e}")

    def save(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
        except OSError as e:
            print(f"Warning: Could not save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value
        self.save()


class STTApp:
    """Main Speech-to-Text Application."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

        # Initialize components
        self.recorder = AudioRecorder()
        self.transcriber = Transcriber(
            model_size=self.config.get("model_size", "base")
        )
        self.typer = KeyboardTyper(
            typing_delay=self.config.get("typing_delay", 0.0)
        )
        # Push-to-talk with F9 key
        self.hotkey_manager = PushToTalkManager(trigger_key=Key.f9)
        self.gui = StatusWindow()

        # State
        self._is_recording = False
        self._processing = False
        self._lock = threading.Lock()
        self._running = False

        # Wire up callbacks
        self._setup_callbacks()

    def _setup_callbacks(self) -> None:
        """Connect all the callback handlers."""
        # Push-to-talk callbacks (hold Right Alt to record)
        self.hotkey_manager.set_callbacks(
            on_start=self.start_recording,
            on_stop=self.stop_recording
        )

        # Tray callbacks
        self.gui.set_callback("toggle_recording", self.toggle_recording)
        self.gui.set_callback("exit", self.stop)

    def start_recording(self) -> None:
        """Start recording audio (called on key press)."""
        with self._lock:
            if self._processing or self._is_recording:
                return
            self._is_recording = True

        self.recorder.start()
        self.gui.set_state(StatusWindow.STATE_RECORDING)
        self.gui.update_title("Earhole - Recording...")
        print("Recording started... (release F9 to stop)")

    def stop_recording(self) -> None:
        """Stop recording and process (called on key release)."""
        with self._lock:
            if not self._is_recording:
                return
            self._is_recording = False
            self._processing = True

        self.gui.set_state(StatusWindow.STATE_PROCESSING)
        self.gui.update_title("Earhole - Processing...")
        print("Recording stopped, processing...")

        # Process in background thread
        threading.Thread(target=self._process_audio, daemon=True).start()

    def toggle_recording(self) -> None:
        """Toggle recording on/off (for tray menu)."""
        with self._lock:
            if self._processing:
                return
            is_recording = self._is_recording

        if is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def _process_audio(self) -> None:
        """Process recorded audio: transcribe and type."""
        audio_path = None
        try:
            # Get the recorded audio file
            audio_path = self.recorder.stop()

            if not audio_path:
                print("No audio recorded!")
                return

            # Transcribe
            print(f"Transcribing audio file: {audio_path}")
            text = self.transcriber.transcribe(
                audio_path,
                language=self.config.get("language")
            )

            if text:
                print(f"Transcription: {text}")

                # Small delay to ensure focus is back on the original window
                time.sleep(0.1)

                # Type the text
                self.typer.type_text(
                    text,
                    use_clipboard=self.config.get("use_clipboard", True)
                )

                if self.config.get("show_notifications"):
                    # Truncate long text for notification
                    preview = text[:50] + "..." if len(text) > 50 else text
                    self.gui.notify("Transcribed", preview)
            else:
                print("No speech detected in audio")
                if self.config.get("show_notifications"):
                    self.gui.notify("No Speech", "No speech was detected")

        except Exception as e:
            print(f"Error processing audio: {e}")
            if self.config.get("show_notifications"):
                self.gui.notify("Error", str(e))

        finally:
            # Clean up temp file
            if audio_path:
                cleanup_temp_file(audio_path)

            # Reset state
            with self._lock:
                self._processing = False
            self.gui.set_state(StatusWindow.STATE_IDLE)
            self.gui.update_title("Earhole - Ready")

    def cancel_recording(self) -> None:
        """Cancel the current recording without processing."""
        with self._lock:
            if not self._is_recording:
                return

            self._is_recording = False
            self.recorder.stop()  # Discard the audio
            self.gui.set_state(StatusWindow.STATE_IDLE)
            self.gui.update_title("Earhole - Ready")

            print("Recording cancelled")

            if self.config.get("show_notifications"):
                self.gui.notify("Cancelled", "Recording was cancelled")

    def preload_model(self) -> None:
        """Pre-load the Whisper model (avoid delay on first use)."""
        print("Pre-loading Whisper model...")
        self.gui.update_title("Earhole - Loading model...")

        def load():
            try:
                self.transcriber.load_model()
                print("Model loaded successfully!")
                self.gui.update_title("Earhole - Ready")
                if self.config.get("show_notifications"):
                    self.gui.notify(
                        "Ready",
                        "Model loaded. Hold F9 to record."
                    )
            except Exception as e:
                print(f"Error loading model: {e}")
                self.gui.notify("Error", f"Failed to load model: {e}")

        threading.Thread(target=load, daemon=True).start()

    def start(self) -> None:
        """Start the application."""
        if self._running:
            return

        self._running = True
        print("Starting Earhole...")

        # Start components
        self.gui.start()
        self.hotkey_manager.start()

        # Pre-load the model in background
        self.preload_model()

        print("Earhole is running!")
        print("Hold F9 to record, release to transcribe")

    def stop(self) -> None:
        """Stop the application."""
        if not self._running:
            return

        print("Stopping Earhole...")
        self._running = False

        # Stop components
        self.hotkey_manager.stop()

        if self._is_recording:
            self.recorder.stop()

        self.gui.stop()
        print("Earhole stopped.")

    def run(self) -> None:
        """Run the application (blocking)."""
        self.start()

        try:
            # Keep running until stopped
            while self._running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main():
    """Entry point for the application."""
    import argparse

    parser = argparse.ArgumentParser(description="Local Speech-to-Text")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        help="Whisper model size (default: base)"
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Language code (e.g., 'en', 'es'). Default: auto-detect"
    )
    parser.add_argument(
        "--no-notifications",
        action="store_true",
        help="Disable desktop notifications"
    )

    args = parser.parse_args()

    # Load config
    config = Config()

    # Override with command line args
    if args.model:
        config.set("model_size", args.model)
    if args.language:
        config.set("language", args.language)
    if args.no_notifications:
        config.set("show_notifications", False)

    # Create and run app
    app = STTApp(config)
    app.run()


if __name__ == "__main__":
    main()
