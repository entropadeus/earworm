"""
Streaming coordinator module for real-time speech-to-text.

Coordinates the pipeline between audio capture, transcription, and typing
using multiple threads with queue-based communication.

Thread Architecture:
- Main thread: Handles hotkeys and UI updates
- Audio thread: Captures audio via sounddevice (managed by AudioRecorder)
- Transcription thread: Processes audio chunks via StreamingTranscriber
- Typing thread: Types confirmed words via KeyboardTyper
"""

import threading
import queue
import time
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum, auto


class StreamingState(Enum):
    """States for the streaming coordinator."""
    IDLE = auto()
    STARTING = auto()
    STREAMING = auto()
    STOPPING = auto()
    ERROR = auto()


@dataclass
class StreamingStats:
    """Statistics for monitoring streaming performance."""
    words_typed: int = 0
    words_corrected: int = 0
    chunks_processed: int = 0
    start_time: float = 0.0
    errors: int = 0

    def get_duration(self) -> float:
        """Get streaming duration in seconds."""
        if self.start_time == 0:
            return 0.0
        return time.time() - self.start_time

    def get_words_per_minute(self) -> float:
        """Calculate words per minute."""
        duration = self.get_duration()
        if duration < 1:
            return 0.0
        return (self.words_typed / duration) * 60


class StreamingCoordinator:
    """
    Coordinates real-time streaming transcription pipeline.

    Manages the flow: Audio -> Transcription -> Typing
    with proper thread coordination and error handling.
    """

    def __init__(
        self,
        streaming_transcriber,  # StreamingTranscriber instance
        keyboard_typer,         # KeyboardTyper instance
        text_processor=None,    # Optional TextProcessingPipeline
        on_word_typed: Optional[Callable[[str], None]] = None,
        on_tentative_update: Optional[Callable[[str], None]] = None,
        on_state_change: Optional[Callable[[StreamingState], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        enable_corrections: bool = True
    ):
        """
        Initialize the streaming coordinator.

        Args:
            streaming_transcriber: StreamingTranscriber for real-time transcription
            keyboard_typer: KeyboardTyper for typing output
            text_processor: Optional text processor for voice commands
            on_word_typed: Callback when a word is typed
            on_tentative_update: Callback for tentative text updates
            on_state_change: Callback for state changes
            on_error: Callback for errors
            enable_corrections: If True, auto-correct revised words
        """
        self._transcriber = streaming_transcriber
        self._typer = keyboard_typer
        self._text_processor = text_processor

        # Callbacks
        self._on_word_typed = on_word_typed
        self._on_tentative_update = on_tentative_update
        self._on_state_change = on_state_change
        self._on_error = on_error
        self._enable_corrections = enable_corrections

        # State
        self._state = StreamingState.IDLE
        self._state_lock = threading.Lock()

        # Word tracking for corrections
        self._typed_words: List[str] = []
        self._typed_words_lock = threading.Lock()

        # Queues
        self._word_queue: queue.Queue = queue.Queue()

        # Threads
        self._typing_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Statistics
        self._stats = StreamingStats()

        # Configure transcriber callbacks
        self._transcriber._on_confirmed_words = self._on_words_confirmed
        self._transcriber._on_tentative_update = self._on_tentative
        self._transcriber._on_error = self._handle_transcriber_error

    @property
    def state(self) -> StreamingState:
        """Get current streaming state."""
        with self._state_lock:
            return self._state

    @property
    def stats(self) -> StreamingStats:
        """Get streaming statistics."""
        return self._stats

    def _set_state(self, new_state: StreamingState) -> None:
        """Set state and notify callback."""
        with self._state_lock:
            if self._state != new_state:
                self._state = new_state
                if self._on_state_change:
                    try:
                        self._on_state_change(new_state)
                    except Exception as e:
                        print(f"State change callback error: {e}")

    def start_streaming(self) -> bool:
        """
        Start the streaming pipeline.

        Returns:
            True if started successfully, False otherwise.
        """
        if self.state != StreamingState.IDLE:
            return False

        try:
            self._set_state(StreamingState.STARTING)

            # Reset state
            self._stop_event.clear()
            with self._typed_words_lock:
                self._typed_words.clear()

            # Clear queues
            while not self._word_queue.empty():
                try:
                    self._word_queue.get_nowait()
                except queue.Empty:
                    break

            # Reset stats
            self._stats = StreamingStats(start_time=time.time())

            # Start transcriber
            self._transcriber.start()

            # Start typing thread
            self._typing_thread = threading.Thread(
                target=self._typing_loop,
                daemon=True,
                name="StreamingTyper"
            )
            self._typing_thread.start()

            self._set_state(StreamingState.STREAMING)
            return True

        except Exception as e:
            self._set_state(StreamingState.ERROR)
            if self._on_error:
                self._on_error(e)
            return False

    def stop_streaming(self) -> str:
        """
        Stop the streaming pipeline and return final text.

        Returns:
            Complete transcribed text.
        """
        if self.state not in (StreamingState.STREAMING, StreamingState.STARTING):
            with self._typed_words_lock:
                return " ".join(self._typed_words)

        self._set_state(StreamingState.STOPPING)

        # Stop transcriber and get final results
        # Note: _final_transcription() already queues words via callback, so we don't
        # need to queue the unconfirmed words here (they would be duplicates)
        final_text, unconfirmed = self._transcriber.stop()

        # NOW set stop event - after queuing final words
        self._stop_event.set()

        # Wait for typing thread to finish
        if self._typing_thread:
            self._typing_thread.join(timeout=5.0)
            self._typing_thread = None

        self._set_state(StreamingState.IDLE)

        with self._typed_words_lock:
            return " ".join(self._typed_words)

    def feed_audio(self, audio_chunk) -> None:
        """
        Feed audio data to the transcriber.

        This is called by AudioRecorder's on_chunk callback.

        Args:
            audio_chunk: numpy array of audio data
        """
        if self.state == StreamingState.STREAMING:
            self._transcriber.feed_audio(audio_chunk)

    def is_active(self) -> bool:
        """Check if streaming is currently active."""
        return self.state == StreamingState.STREAMING

    def _on_words_confirmed(self, words: List[str]) -> None:
        """Handle confirmed words from transcriber."""
        for word in words:
            self._word_queue.put(word)

    def _on_tentative(self, tentative_text: str) -> None:
        """Handle tentative text update from transcriber."""
        if self._on_tentative_update:
            try:
                self._on_tentative_update(tentative_text)
            except Exception as e:
                print(f"Tentative update callback error: {e}")

    def _handle_transcriber_error(self, error: Exception) -> None:
        """Handle error from transcriber."""
        self._stats.errors += 1
        if self._on_error:
            self._on_error(error)

    def _typing_loop(self) -> None:
        """Main loop for typing confirmed words."""
        while not self._stop_event.is_set() or not self._word_queue.empty():
            try:
                # Get word from queue with timeout
                try:
                    word = self._word_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Process through text processor if available
                processed_word = word
                if self._text_processor:
                    try:
                        processed_word = self._process_word(word)
                        if processed_word is None:
                            # Word was a command that was executed
                            continue
                    except Exception as e:
                        print(f"Text processor error: {e}")
                        processed_word = word

                # Type the word
                if processed_word:
                    self._type_word(processed_word)

            except Exception as e:
                self._stats.errors += 1
                if self._on_error:
                    self._on_error(e)

    def _process_word(self, word: str) -> Optional[str]:
        """
        Process a word through the text processor.

        Returns:
            Processed word, or None if it was a command.
        """
        # TODO: Implement streaming-aware text processing
        # For now, return word as-is
        return word

    def _type_word(self, word: str) -> None:
        """Type a single word and track it."""
        try:
            self._typer.type_word(word, add_space=True)

            with self._typed_words_lock:
                self._typed_words.append(word)

            self._stats.words_typed += 1

            if self._on_word_typed:
                try:
                    self._on_word_typed(word)
                except Exception as e:
                    print(f"Word typed callback error: {e}")

        except Exception as e:
            self._stats.errors += 1
            if self._on_error:
                self._on_error(e)

    def correct_words(self, old_words: List[str], new_words: List[str]) -> None:
        """
        Correct previously typed words.

        Args:
            old_words: Words to remove
            new_words: Words to type instead
        """
        if not self._enable_corrections:
            return

        try:
            self._typer.replace_words(old_words, new_words)

            with self._typed_words_lock:
                # Remove old words from tracking
                for _ in old_words:
                    if self._typed_words:
                        self._typed_words.pop()
                # Add new words to tracking
                self._typed_words.extend(new_words)

            self._stats.words_corrected += len(old_words)

        except Exception as e:
            if self._on_error:
                self._on_error(e)

    def get_typed_text(self) -> str:
        """Get all typed text so far."""
        with self._typed_words_lock:
            return " ".join(self._typed_words)


# Factory function for easy setup
def create_streaming_pipeline(
    whisper_model,
    keyboard_typer,
    chunk_duration: float = 1.0,
    buffer_duration: float = 5.0,
    agreement_threshold: int = 2,
    language: Optional[str] = None,
    **kwargs
) -> StreamingCoordinator:
    """
    Create a complete streaming pipeline.

    Args:
        whisper_model: Loaded faster-whisper model
        keyboard_typer: KeyboardTyper instance
        chunk_duration: How often to run transcription
        buffer_duration: Audio context buffer size
        agreement_threshold: Iterations before confirming words
        language: Language code or None for auto
        **kwargs: Additional arguments for StreamingCoordinator

    Returns:
        Configured StreamingCoordinator
    """
    from streaming_transcriber import StreamingTranscriber

    transcriber = StreamingTranscriber(
        model=whisper_model,
        chunk_duration=chunk_duration,
        buffer_duration=buffer_duration,
        agreement_threshold=agreement_threshold,
        language=language
    )

    return StreamingCoordinator(
        streaming_transcriber=transcriber,
        keyboard_typer=keyboard_typer,
        **kwargs
    )
