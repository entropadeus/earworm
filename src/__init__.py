# Earworm - Local Speech-to-Text Application
#
# A privacy-focused, local speech-to-text application featuring:
# - Push-to-talk recording with Whisper transcription
# - Voice command processing (punctuation, formatting, editing)
# - Smart punctuation restoration
# - Preview window for text review before pasting

from .app import STTApp, Config, main
from .audio_recorder import AudioRecorder, cleanup_temp_file
from .transcriber import Transcriber, ModelSize
from .keyboard_typer import KeyboardTyper
from .hotkey_manager import HotkeyManager, PushToTalkManager
from .gui import StatusWindow
from .text_processor import (
    TextProcessingPipeline,
    VoiceCommandProcessor,
    SmartPunctuator,
    VoiceCommand,
    CommandAction,
    CommandResult,
    process_transcription,
)
from .preview_window import (
    PreviewWindow,
    PreviewManager,
    PreviewWindowConfig,
    PreviewResult,
    PreviewAction,
)

__version__ = "2.0.0"
__all__ = [
    # Main app
    "STTApp",
    "Config",
    "main",
    # Audio
    "AudioRecorder",
    "cleanup_temp_file",
    # Transcription
    "Transcriber",
    "ModelSize",
    # Input
    "KeyboardTyper",
    "HotkeyManager",
    "PushToTalkManager",
    # GUI
    "StatusWindow",
    # Text processing
    "TextProcessingPipeline",
    "VoiceCommandProcessor",
    "SmartPunctuator",
    "VoiceCommand",
    "CommandAction",
    "CommandResult",
    "process_transcription",
    # Preview
    "PreviewWindow",
    "PreviewManager",
    "PreviewWindowConfig",
    "PreviewResult",
    "PreviewAction",
]
