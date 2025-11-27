"""
Streaming transcription module using faster-whisper with local agreement policy.

Implements real-time speech-to-text by:
1. Maintaining a rolling audio buffer for context
2. Processing audio chunks continuously during recording
3. Using local agreement policy to confirm words before emitting

Based on concepts from: https://github.com/ufal/whisper_streaming
"""

import numpy as np
import threading
import queue
import time
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Generator, Callable, Any
from faster_whisper import WhisperModel


@dataclass
class WordInfo:
    """Individual word with timing and confidence."""
    word: str
    start: float
    end: float
    probability: float = 1.0


@dataclass
class TranscriptionResult:
    """Result from a single transcription pass."""
    words: List[WordInfo]
    text: str
    chunk_id: int
    timestamp: float = field(default_factory=time.time)


class AudioRingBuffer:
    """
    Ring buffer for audio data with fixed duration.

    Maintains a sliding window of audio for providing context to Whisper.
    """

    def __init__(self, duration: float, sample_rate: int = 16000):
        """
        Initialize ring buffer.

        Args:
            duration: Buffer duration in seconds
            sample_rate: Audio sample rate in Hz
        """
        self.duration = duration
        self.sample_rate = sample_rate
        self.max_samples = int(duration * sample_rate)
        self._buffer = np.zeros(self.max_samples, dtype=np.float32)
        self._write_pos = 0
        self._total_samples = 0
        self._lock = threading.Lock()

    def append(self, audio: np.ndarray) -> None:
        """Append audio data to the buffer."""
        with self._lock:
            audio = audio.flatten().astype(np.float32)
            n_samples = len(audio)

            if n_samples >= self.max_samples:
                # Audio larger than buffer - keep only the latest
                self._buffer[:] = audio[-self.max_samples:]
                self._write_pos = 0
                self._total_samples = self.max_samples
            else:
                # Wrap around if needed
                end_pos = self._write_pos + n_samples
                if end_pos <= self.max_samples:
                    self._buffer[self._write_pos:end_pos] = audio
                else:
                    # Split across boundary
                    first_part = self.max_samples - self._write_pos
                    self._buffer[self._write_pos:] = audio[:first_part]
                    self._buffer[:n_samples - first_part] = audio[first_part:]

                self._write_pos = end_pos % self.max_samples
                self._total_samples = min(self._total_samples + n_samples, self.max_samples)

    def get_audio(self) -> np.ndarray:
        """Get all audio in the buffer in chronological order."""
        with self._lock:
            if self._total_samples < self.max_samples:
                # Buffer not full yet
                return self._buffer[:self._total_samples].copy()
            else:
                # Buffer is full, need to reorder
                return np.concatenate([
                    self._buffer[self._write_pos:],
                    self._buffer[:self._write_pos]
                ])

    def get_duration(self) -> float:
        """Get current audio duration in seconds."""
        with self._lock:
            return self._total_samples / self.sample_rate

    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._buffer.fill(0)
            self._write_pos = 0
            self._total_samples = 0


class LocalAgreementPolicy:
    """
    Implements local agreement policy for word confirmation.

    Words are only confirmed when they appear identically in N consecutive
    transcription passes, ensuring stability before typing.
    """

    def __init__(self, threshold: int = 2):
        """
        Initialize the agreement policy.

        Args:
            threshold: Number of consecutive agreements needed to confirm a word
        """
        self.threshold = threshold
        self._history: List[List[str]] = []
        self._confirmed_count = 0
        self._lock = threading.Lock()

    def add_transcription(self, words: List[str]) -> List[str]:
        """
        Add a new transcription and return newly confirmed words.

        Args:
            words: List of words from latest transcription

        Returns:
            List of newly confirmed words (may be empty)
        """
        with self._lock:
            self._history.append(words)

            # Keep only recent history needed for agreement
            if len(self._history) > self.threshold:
                self._history = self._history[-self.threshold:]

            if len(self._history) < self.threshold:
                return []

            # Find longest common prefix across all recent transcriptions
            confirmed = self._find_agreement()

            # Return only newly confirmed words
            new_confirmed = confirmed[self._confirmed_count:]
            self._confirmed_count = len(confirmed)

            return new_confirmed

    def _find_agreement(self) -> List[str]:
        """Find words that agree across all recent transcriptions."""
        if not self._history:
            return []

        # Find minimum length
        min_len = min(len(words) for words in self._history)

        # Find longest agreeing prefix
        agreed = []
        for i in range(min_len):
            words_at_i = [h[i] for h in self._history]
            if all(w == words_at_i[0] for w in words_at_i):
                agreed.append(words_at_i[0])
            else:
                break

        return agreed

    def get_tentative(self) -> List[str]:
        """Get words that are not yet confirmed (tentative)."""
        with self._lock:
            if not self._history:
                return []
            latest = self._history[-1]
            return latest[self._confirmed_count:]

    def get_confirmed_count(self) -> int:
        """Get number of confirmed words so far."""
        with self._lock:
            return self._confirmed_count

    def reset(self) -> None:
        """Reset the policy state."""
        with self._lock:
            self._history.clear()
            self._confirmed_count = 0


class StreamingTranscriber:
    """
    Real-time streaming transcription using faster-whisper with local agreement.

    Processes audio chunks continuously during recording and emits confirmed
    words as they become stable across multiple transcription passes.
    """

    def __init__(
        self,
        model: WhisperModel,
        chunk_duration: float = 1.0,
        buffer_duration: float = 5.0,
        agreement_threshold: int = 2,
        sample_rate: int = 16000,
        language: Optional[str] = None,
        on_confirmed_words: Optional[Callable[[List[str]], None]] = None,
        on_tentative_update: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ):
        """
        Initialize streaming transcriber.

        Args:
            model: Loaded faster-whisper model
            chunk_duration: How often to run transcription (seconds)
            buffer_duration: Audio context buffer size (seconds)
            agreement_threshold: Iterations before confirming words
            sample_rate: Audio sample rate
            language: Language code or None for auto-detect
            on_confirmed_words: Callback when words are confirmed
            on_tentative_update: Callback for tentative text updates
            on_error: Callback for errors
        """
        self._model = model
        self._chunk_duration = chunk_duration
        self._buffer_duration = buffer_duration
        self._sample_rate = sample_rate
        self._language = language

        # Callbacks
        self._on_confirmed_words = on_confirmed_words
        self._on_tentative_update = on_tentative_update
        self._on_error = on_error

        # Audio buffer
        self._audio_buffer = AudioRingBuffer(buffer_duration, sample_rate)

        # Agreement policy
        self._agreement = LocalAgreementPolicy(agreement_threshold)

        # State
        self._is_running = False
        self._transcription_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._chunk_id = 0

        # Results
        self._confirmed_words: List[str] = []
        self._all_words: List[str] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the streaming transcription."""
        if self._is_running:
            return

        self._is_running = True
        self._stop_event.clear()
        self._audio_buffer.clear()
        self._agreement.reset()
        self._confirmed_words.clear()
        self._all_words.clear()
        self._chunk_id = 0

        # Start transcription thread
        self._transcription_thread = threading.Thread(
            target=self._transcription_loop,
            daemon=True,
            name="StreamingTranscriber"
        )
        self._transcription_thread.start()

    def stop(self) -> Tuple[str, List[str]]:
        """
        Stop streaming and return final results.

        Returns:
            Tuple of (final_complete_text, unconfirmed_words)
        """
        if not self._is_running:
            return "", []

        self._is_running = False
        self._stop_event.set()

        # Wait for transcription thread
        if self._transcription_thread:
            self._transcription_thread.join(timeout=2.0)

        # Do one final transcription pass to catch remaining words
        self._final_transcription()

        with self._lock:
            final_text = " ".join(self._confirmed_words)
            tentative = self._agreement.get_tentative()

        return final_text, tentative

    def feed_audio(self, audio_chunk: np.ndarray) -> None:
        """Feed audio data to the transcriber."""
        if self._is_running:
            self._audio_buffer.append(audio_chunk)

    def get_confirmed_words(self) -> List[str]:
        """Get all confirmed words so far."""
        with self._lock:
            return self._confirmed_words.copy()

    def get_tentative_text(self) -> str:
        """Get current tentative (unconfirmed) text."""
        tentative = self._agreement.get_tentative()
        return " ".join(tentative)

    def _transcription_loop(self) -> None:
        """Main transcription loop running in background thread."""
        last_transcription = time.time()

        while not self._stop_event.is_set():
            try:
                # Wait for chunk duration
                elapsed = time.time() - last_transcription
                if elapsed < self._chunk_duration:
                    time.sleep(min(0.1, self._chunk_duration - elapsed))
                    continue

                # Check if we have enough audio
                audio_duration = self._audio_buffer.get_duration()
                if audio_duration < 0.5:
                    time.sleep(0.1)
                    continue

                # Run transcription
                self._process_chunk()
                last_transcription = time.time()

            except Exception as e:
                if self._on_error:
                    self._on_error(e)

    def _process_chunk(self) -> None:
        """Process current audio buffer and emit confirmed words."""
        # Get audio from buffer
        audio = self._audio_buffer.get_audio()
        if len(audio) == 0:
            return

        self._chunk_id += 1

        try:
            # Transcribe with word timestamps
            segments, info = self._model.transcribe(
                audio,
                language=self._language,
                word_timestamps=True,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300)
            )

            # Extract words
            words = []
            for segment in segments:
                if segment.words:
                    for word_info in segment.words:
                        words.append(word_info.word.strip())
                else:
                    # Fallback: split segment text
                    words.extend(segment.text.strip().split())

            # Apply agreement policy
            new_confirmed = self._agreement.add_transcription(words)

            if new_confirmed:
                with self._lock:
                    self._confirmed_words.extend(new_confirmed)

                # Notify callback
                if self._on_confirmed_words:
                    self._on_confirmed_words(new_confirmed)

            # Update tentative
            if self._on_tentative_update:
                tentative = " ".join(self._agreement.get_tentative())
                self._on_tentative_update(tentative)

        except Exception as e:
            if self._on_error:
                self._on_error(e)

    def _final_transcription(self) -> None:
        """Do final transcription pass to catch remaining words."""
        audio = self._audio_buffer.get_audio()
        if len(audio) == 0:
            return

        try:
            segments, info = self._model.transcribe(
                audio,
                language=self._language,
                word_timestamps=True,
                beam_size=5,
                vad_filter=True
            )

            words = []
            for segment in segments:
                if segment.words:
                    for word_info in segment.words:
                        words.append(word_info.word.strip())
                else:
                    words.extend(segment.text.strip().split())

            # In final pass, confirm ALL remaining words that weren't typed yet
            already_confirmed = self._agreement.get_confirmed_count()
            remaining = words[already_confirmed:]

            if remaining:
                with self._lock:
                    self._confirmed_words.extend(remaining)

                if self._on_confirmed_words:
                    self._on_confirmed_words(remaining)

        except Exception as e:
            if self._on_error:
                self._on_error(e)


# Convenience function for testing
def create_streaming_transcriber(
    model_size: str = "base",
    device: str = "auto",
    **kwargs
) -> StreamingTranscriber:
    """
    Create a streaming transcriber with a new model.

    For production use, prefer passing an existing model to share resources.
    """
    from transcriber import Transcriber

    transcriber = Transcriber(model_size=model_size, device=device)
    transcriber.load_model()

    return StreamingTranscriber(model=transcriber._model, **kwargs)
