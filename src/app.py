"""
Main STT Application.
Coordinates all components: recording, transcription, text processing, preview, and typing.
"""

import threading
import time
import os
import json
from pathlib import Path
from typing import Any, Optional, Dict, List

from audio_recorder import AudioRecorder, cleanup_temp_file
from transcriber import Transcriber, ModelSize
from keyboard_typer import KeyboardTyper
from hotkey_manager import PushToTalkManager
from gui import StatusWindow
from text_processor import TextProcessingPipeline, VoiceCommandProcessor, SmartPunctuator
from preview_window import PreviewManager, PreviewWindowConfig, PreviewResult, PreviewAction
from streaming_transcriber import StreamingTranscriber
from streaming_coordinator import StreamingCoordinator, StreamingState
from pynput.keyboard import Key


class Config:
    """
    Application configuration with support for all features.

    Configuration is persisted to a JSON file and supports:
    - Core transcription settings
    - Voice command settings
    - Smart punctuation settings
    - Preview window settings
    """

    DEFAULT_CONFIG = {
        # Core settings
        "model_size": "base",
        "language": None,  # None = auto-detect
        "typing_delay": 0.0,
        "use_clipboard": True,
        "show_notifications": True,

        # Voice commands
        "enable_voice_commands": True,

        # Smart punctuation
        "enable_smart_punctuation": True,
        "auto_capitalize": True,
        "auto_periods": True,
        "auto_commas": True,
        "remove_fillers": False,  # Remove "um", "uh", etc.

        # Preview window
        "enable_preview": True,
        "preview_auto_accept_delay": 0.0,  # 0 = disabled
        "preview_theme": "dark",
        "preview_position": "center",
        "preview_font_size": 12,
        "preview_show_shortcuts": True,

        # Advanced
        "custom_voice_commands": [],  # List of custom command definitions

        # Streaming mode (real-time transcription)
        "enable_streaming": True,              # Enable real-time streaming mode
        "streaming_chunk_duration": 1.0,       # Seconds between transcription passes
        "streaming_buffer_duration": 5.0,      # Audio context buffer size
        "streaming_agreement_threshold": 2,    # Iterations before confirming words
        "streaming_enable_corrections": True,  # Auto-correct revised words
    }

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to user's app data folder
            app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
            config_dir = Path(app_data) / "Earworm"
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
                    # Merge with defaults to handle new config options
                    for key, value in loaded.items():
                        if key in self.DEFAULT_CONFIG:
                            self._config[key] = value
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

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple configuration values at once."""
        for key, value in updates.items():
            if key in self.DEFAULT_CONFIG:
                self._config[key] = value
        self.save()


class STTApp:
    """
    Main Speech-to-Text Application.

    Features:
    - Push-to-talk recording with F9
    - Local transcription with Whisper
    - Voice command processing
    - Smart punctuation
    - Preview window for review before pasting
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

        # Initialize core components
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

        # Text processing pipeline
        self.text_processor = self._create_text_processor()

        # Preview manager (will be configured after GUI starts)
        self.preview_manager = self._create_preview_manager()

        # State
        self._is_recording = False
        self._processing = False
        self._lock = threading.Lock()
        self._running = False

        # For re-recording support
        self._pending_rerecord = False

        # Streaming mode components (initialized after model loads)
        self._streaming_transcriber: Optional[StreamingTranscriber] = None
        self._streaming_coordinator: Optional[StreamingCoordinator] = None
        self._streaming_mode = False  # True when streaming is active

        # Wire up callbacks
        self._setup_callbacks()

    def _create_text_processor(self) -> TextProcessingPipeline:
        """Create and configure the text processing pipeline."""
        pipeline = TextProcessingPipeline(
            enable_voice_commands=self.config.get("enable_voice_commands", True),
            enable_smart_punctuation=self.config.get("enable_smart_punctuation", True)
        )

        # Configure punctuator
        pipeline.configure(
            auto_capitalize=self.config.get("auto_capitalize", True),
            auto_periods=self.config.get("auto_periods", True),
            auto_commas=self.config.get("auto_commas", True),
            remove_fillers=self.config.get("remove_fillers", False)
        )

        return pipeline

    def _create_preview_manager(self) -> PreviewManager:
        """Create and configure the preview manager."""
        preview_config = PreviewWindowConfig(
            auto_accept_delay=self.config.get("preview_auto_accept_delay", 0.0),
            show_shortcuts=self.config.get("preview_show_shortcuts", True),
            font_size=self.config.get("preview_font_size", 12),
            position=self.config.get("preview_position", "center"),
            theme=self.config.get("preview_theme", "dark")
        )

        manager = PreviewManager(config=preview_config)
        manager.enabled = self.config.get("enable_preview", True)

        return manager

    def _setup_callbacks(self) -> None:
        """Connect all the callback handlers."""
        # Push-to-talk callbacks (hold F9 to record)
        self.hotkey_manager.set_callbacks(
            on_start=self.start_recording,
            on_stop=self.stop_recording
        )

        # Tray callbacks
        self.gui.set_callback("toggle_recording", self.toggle_recording)
        self.gui.set_callback("exit", self.stop)

    def _init_streaming(self) -> None:
        """Initialize streaming components after model is loaded."""
        if not self.config.get("enable_streaming", True):
            print("Streaming mode disabled in config")
            return

        if not self.transcriber.is_loaded():
            print("Warning: Cannot init streaming - model not loaded")
            return

        try:
            # Create streaming transcriber sharing the loaded model
            self._streaming_transcriber = StreamingTranscriber(
                model=self.transcriber._model,
                chunk_duration=self.config.get("streaming_chunk_duration", 1.0),
                buffer_duration=self.config.get("streaming_buffer_duration", 5.0),
                agreement_threshold=self.config.get("streaming_agreement_threshold", 2),
                language=self.config.get("language")
            )

            # Create streaming coordinator
            self._streaming_coordinator = StreamingCoordinator(
                streaming_transcriber=self._streaming_transcriber,
                keyboard_typer=self.typer,
                text_processor=self.text_processor,
                on_word_typed=self._on_streaming_word,
                on_tentative_update=self._on_streaming_tentative,
                on_state_change=self._on_streaming_state_change,
                on_error=self._on_streaming_error,
                enable_corrections=self.config.get("streaming_enable_corrections", True)
            )

            print("Streaming mode initialized successfully")

        except Exception as e:
            print(f"Error initializing streaming: {e}")
            import traceback
            traceback.print_exc()
            self._streaming_transcriber = None
            self._streaming_coordinator = None

    def _on_streaming_word(self, word: str) -> None:
        """Callback when a word is typed in streaming mode."""
        # Could update UI or log here
        pass

    def _on_streaming_tentative(self, tentative: str) -> None:
        """Callback for tentative text updates."""
        # Could show tentative text in UI
        if tentative:
            self.gui.update_title(f"Earworm - ...{tentative[-30:]}")

    def _on_streaming_state_change(self, state: StreamingState) -> None:
        """Callback for streaming state changes."""
        if state == StreamingState.STREAMING:
            self.gui.set_state(StatusWindow.STATE_RECORDING)
        elif state == StreamingState.STOPPING:
            self.gui.set_state(StatusWindow.STATE_PROCESSING)
        elif state == StreamingState.IDLE:
            self.gui.set_state(StatusWindow.STATE_IDLE)

    def _on_streaming_error(self, error: Exception) -> None:
        """Callback for streaming errors."""
        print(f"Streaming error: {error}")
        if self.config.get("show_notifications"):
            self.gui.notify("Streaming Error", str(error))

    def start_recording(self) -> None:
        """Start recording audio (called on key press)."""
        with self._lock:
            if self._processing or self._is_recording:
                return
            self._is_recording = True

        # Check if streaming mode is available and enabled
        use_streaming = (
            self.config.get("enable_streaming", True) and
            self._streaming_coordinator is not None
        )

        if use_streaming:
            # Streaming mode: type words as they're transcribed
            self._streaming_mode = True

            # Create recorder with streaming callback
            self.recorder = AudioRecorder(
                on_chunk=self._streaming_coordinator.feed_audio
            )
            self.recorder.start()

            # Start the streaming pipeline
            self._streaming_coordinator.start_streaming()

            self.gui.set_state(StatusWindow.STATE_RECORDING)
            self.gui.update_title("Earworm - Streaming...")
            print("Streaming started... (release F9 to stop)")
        else:
            # Batch mode: record all then transcribe
            self._streaming_mode = False
            self.recorder = AudioRecorder()
            self.recorder.start()
            self.gui.set_state(StatusWindow.STATE_RECORDING)
            self.gui.update_title("Earworm - Recording...")
            print("Recording started... (release F9 to stop)")

    def stop_recording(self) -> None:
        """Stop recording and process (called on key release)."""
        with self._lock:
            if not self._is_recording:
                return
            self._is_recording = False
            self._processing = True

        if self._streaming_mode:
            # Streaming mode: finalize and clean up
            self.gui.set_state(StatusWindow.STATE_PROCESSING)
            self.gui.update_title("Earworm - Finalizing...")
            print("Streaming stopped, finalizing...")
            threading.Thread(target=self._finalize_streaming, daemon=True).start()
        else:
            # Batch mode: process the recorded audio
            self.gui.set_state(StatusWindow.STATE_PROCESSING)
            self.gui.update_title("Earworm - Processing...")
            print("Recording stopped, processing...")
            threading.Thread(target=self._process_audio, daemon=True).start()

    def _finalize_streaming(self) -> None:
        """Finalize streaming transcription."""
        audio_path = None
        try:
            # Stop the streaming coordinator (types any remaining words)
            final_text = self._streaming_coordinator.stop_streaming()

            # Stop the audio recorder
            audio_path = self.recorder.stop()

            # Clean up temp audio file
            if audio_path:
                cleanup_temp_file(audio_path)

            # Get stats
            stats = self._streaming_coordinator.stats
            print(f"Streaming complete: {stats.words_typed} words typed, "
                  f"{stats.words_corrected} corrections, "
                  f"{stats.get_words_per_minute():.1f} WPM")

            if self.config.get("show_notifications") and final_text:
                preview = final_text[:50] + "..." if len(final_text) > 50 else final_text
                self.gui.notify("Transcribed", preview)

        except Exception as e:
            print(f"Error finalizing streaming: {e}")
            import traceback
            traceback.print_exc()
            if self.config.get("show_notifications"):
                self.gui.notify("Error", str(e))

            # Clean up on error
            if audio_path:
                cleanup_temp_file(audio_path)

        finally:
            self._streaming_mode = False
            self._finish_processing()

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
        """Process recorded audio: transcribe, process text, preview, and type."""
        audio_path = None
        try:
            # Get the recorded audio file
            audio_path = self.recorder.stop()

            if not audio_path:
                print("No audio recorded!")
                self._finish_processing()
                return

            # Transcribe
            print(f"Transcribing audio file: {audio_path}")
            raw_text = self.transcriber.transcribe(
                audio_path,
                language=self.config.get("language")
            )

            if not raw_text:
                print("No speech detected in audio")
                if self.config.get("show_notifications"):
                    self.gui.notify("No Speech", "No speech was detected")
                self._finish_processing(audio_path)
                return

            print(f"Raw transcription: {raw_text}")

            # Process through text pipeline (voice commands + smart punctuation)
            processed_text, commands = self.text_processor.process(raw_text)
            print(f"Processed text: {processed_text}")

            if commands:
                print(f"Voice commands executed: {[c.action.name for c in commands]}")

            # Clean up audio file before preview (we don't need it anymore)
            if audio_path:
                cleanup_temp_file(audio_path)
                audio_path = None

            # Show preview or type directly
            if self.config.get("enable_preview", True):
                self._show_preview(processed_text)
            else:
                self._type_text(processed_text)

        except Exception as e:
            print(f"Error processing audio: {e}")
            import traceback
            traceback.print_exc()
            if self.config.get("show_notifications"):
                self.gui.notify("Error", str(e))
            self._finish_processing(audio_path)

    def _show_preview(self, text: str) -> None:
        """Show the preview window for text review."""
        # Set the parent window for positioning
        if self.gui._root:
            self.preview_manager.set_parent(self.gui._root)

        def on_preview_complete(result: PreviewResult):
            """Handle preview window result."""
            if result.action == PreviewAction.ACCEPT:
                self._type_text(result.text)
            elif result.action == PreviewAction.COPY_ONLY:
                print(f"Text copied to clipboard: {result.text[:50]}...")
                if self.config.get("show_notifications"):
                    self.gui.notify("Copied", "Text copied to clipboard")
                self._finish_processing()
            elif result.action == PreviewAction.RERECORD:
                print("Re-recording requested")
                self._finish_processing()
                # Start recording again immediately
                self.gui._root.after(100, self.start_recording)
            elif result.action == PreviewAction.CANCEL:
                print("Preview cancelled")
                self._finish_processing()

        def on_rerecord():
            """Callback for re-record button."""
            # This is called from the preview window
            pass  # The actual re-recording is triggered in on_preview_complete

        self.preview_manager.show_preview(
            text=text,
            on_complete=on_preview_complete,
            on_rerecord=on_rerecord
        )

    def _type_text(self, text: str) -> None:
        """Type the processed text into the active window."""
        if not text:
            self._finish_processing()
            return

        # Small delay to ensure focus is back on the original window
        time.sleep(0.1)

        # Type the text
        self.typer.type_text(
            text,
            use_clipboard=self.config.get("use_clipboard", True)
        )

        print(f"Typed: {text}")

        if self.config.get("show_notifications"):
            # Truncate long text for notification
            preview = text[:50] + "..." if len(text) > 50 else text
            self.gui.notify("Transcribed", preview)

        self._finish_processing()

    def _finish_processing(self, audio_path: Optional[str] = None) -> None:
        """Finish processing and reset state."""
        # Clean up temp file if still exists
        if audio_path:
            cleanup_temp_file(audio_path)

        # Reset state
        with self._lock:
            self._processing = False

        self.gui.set_state(StatusWindow.STATE_IDLE)
        self.gui.update_title("Earworm - Ready")

    def cancel_recording(self) -> None:
        """Cancel the current recording without processing."""
        with self._lock:
            if not self._is_recording:
                return

            self._is_recording = False
            self.recorder.stop()  # Discard the audio
            self.gui.set_state(StatusWindow.STATE_IDLE)
            self.gui.update_title("Earworm - Ready")

            print("Recording cancelled")

            if self.config.get("show_notifications"):
                self.gui.notify("Cancelled", "Recording was cancelled")

    def preload_model(self) -> None:
        """Pre-load the Whisper model (avoid delay on first use)."""
        print("Pre-loading Whisper model...")
        self.gui.update_title("Earworm - Loading model...")

        def load():
            try:
                self.transcriber.load_model()
                print("Model loaded successfully!")

                # Initialize streaming mode after model is loaded
                if self.config.get("enable_streaming", True):
                    print("Initializing streaming mode...")
                    self._init_streaming()

                self.gui.update_title("Earworm - Ready")

                mode = "streaming" if self._streaming_coordinator else "batch"
                if self.config.get("show_notifications"):
                    self.gui.notify(
                        "Ready",
                        f"Model loaded ({mode} mode). Hold F9 to record."
                    )
            except Exception as e:
                print(f"Error loading model: {e}")
                self.gui.notify("Error", f"Failed to load model: {e}")

        threading.Thread(target=load, daemon=True).start()

    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration and reconfigure components.

        Args:
            updates: Dictionary of config key-value pairs to update
        """
        self.config.update(updates)

        # Reconfigure text processor
        self.text_processor.configure(
            enable_voice_commands=self.config.get("enable_voice_commands", True),
            enable_smart_punctuation=self.config.get("enable_smart_punctuation", True),
            auto_capitalize=self.config.get("auto_capitalize", True),
            auto_periods=self.config.get("auto_periods", True),
            auto_commas=self.config.get("auto_commas", True),
            remove_fillers=self.config.get("remove_fillers", False)
        )

        # Reconfigure preview manager
        self.preview_manager.enabled = self.config.get("enable_preview", True)
        self.preview_manager.configure(
            auto_accept_delay=self.config.get("preview_auto_accept_delay", 0.0),
            show_shortcuts=self.config.get("preview_show_shortcuts", True),
            font_size=self.config.get("preview_font_size", 12),
            position=self.config.get("preview_position", "center"),
            theme=self.config.get("preview_theme", "dark")
        )

        # Update typer
        self.typer.typing_delay = self.config.get("typing_delay", 0.0)

    def start(self) -> None:
        """Start the application."""
        if self._running:
            return

        self._running = True
        print("Starting Earworm...")

        # Start components
        self.gui.start()
        self.hotkey_manager.start()

        # Pre-load the model in background
        self.preload_model()

        print("Earworm is running!")
        print("Hold F9 to record, release to transcribe")
        print("\nFeatures enabled:")
        print(f"  - Streaming mode: {self.config.get('enable_streaming', True)}")
        print(f"  - Voice commands: {self.config.get('enable_voice_commands', True)}")
        print(f"  - Smart punctuation: {self.config.get('enable_smart_punctuation', True)}")
        print(f"  - Preview window: {self.config.get('enable_preview', True)} (batch mode only)")

    def stop(self) -> None:
        """Stop the application."""
        if not self._running:
            return

        print("Stopping Earworm...")
        self._running = False

        # Close any open preview window
        self.preview_manager.close_current()

        # Stop components
        self.hotkey_manager.stop()

        if self._is_recording:
            self.recorder.stop()

        self.gui.stop()
        print("Earworm stopped.")

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

    parser = argparse.ArgumentParser(
        description="Earworm - Local Speech-to-Text with Voice Commands"
    )

    # Core options
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

    # Feature toggles
    parser.add_argument(
        "--no-voice-commands",
        action="store_true",
        help="Disable voice command processing"
    )
    parser.add_argument(
        "--no-punctuation",
        action="store_true",
        help="Disable smart punctuation"
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Disable preview window (type directly)"
    )

    # Preview options
    parser.add_argument(
        "--auto-accept",
        type=float,
        default=None,
        help="Auto-accept preview after N seconds (0 = disabled)"
    )
    parser.add_argument(
        "--theme",
        type=str,
        choices=["dark", "light"],
        default=None,
        help="Preview window theme"
    )

    # Streaming options
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Disable real-time streaming (use batch mode)"
    )
    parser.add_argument(
        "--streaming-chunk",
        type=float,
        default=None,
        help="Streaming chunk duration in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--streaming-buffer",
        type=float,
        default=None,
        help="Streaming audio buffer duration in seconds (default: 5.0)"
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
    if args.no_voice_commands:
        config.set("enable_voice_commands", False)
    if args.no_punctuation:
        config.set("enable_smart_punctuation", False)
    if args.no_preview:
        config.set("enable_preview", False)
    if args.no_streaming:
        config.set("enable_streaming", False)
    if args.streaming_chunk is not None:
        config.set("streaming_chunk_duration", args.streaming_chunk)
    if args.streaming_buffer is not None:
        config.set("streaming_buffer_duration", args.streaming_buffer)
    if args.auto_accept is not None:
        config.set("preview_auto_accept_delay", args.auto_accept)
    if args.theme:
        config.set("preview_theme", args.theme)

    # Create and run app
    app = STTApp(config)
    app.run()


if __name__ == "__main__":
    main()
