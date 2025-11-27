"""
Audio recording module using sounddevice.
Records from the default microphone until stopped.
"""

import numpy as np
import sounddevice as sd
import threading
import queue
from typing import Optional, Callable
import tempfile
import wave
import os


class AudioRecorder:
    """Records audio from the microphone and saves to a temporary WAV file."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        on_chunk: Optional[Callable[[np.ndarray], None]] = None
    ):
        """
        Args:
            sample_rate: Audio sample rate in Hz. Whisper expects 16kHz.
            channels: Number of audio channels. Mono (1) is fine for speech.
            on_chunk: Optional callback invoked for each audio chunk during recording.
                      Used for real-time streaming transcription.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self._on_chunk = on_chunk
        self._recording = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._audio_data: list = []
        self._stream: Optional[sd.InputStream] = None
        self._record_thread: Optional[threading.Thread] = None
        self._data_lock = threading.Lock()

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info: dict, status: sd.CallbackFlags) -> None:
        """Callback function for the audio stream."""
        # Put a copy of the audio data into the queue
        chunk = indata.copy()
        self._audio_queue.put(chunk)

        # Real-time callback for streaming mode
        if self._on_chunk:
            try:
                self._on_chunk(chunk)
            except Exception:
                pass  # Silently ignore callback errors

    def _record_loop(self) -> None:
        """Background thread that collects audio data from the queue."""
        while self._recording:
            try:
                data = self._audio_queue.get(timeout=0.1)
                with self._data_lock:
                    self._audio_data.append(data)
            except queue.Empty:
                continue

    def start(self) -> None:
        """Start recording audio from the microphone."""
        if self._recording:
            return

        self._recording = True
        self._audio_data = []

        # Clear the queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        # Start the audio stream
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.float32,
            callback=self._audio_callback
        )
        self._stream.start()

        # Start the collection thread
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()

    def stop(self) -> Optional[str]:
        """
        Stop recording and save audio to a temporary WAV file.

        Returns:
            Path to the temporary WAV file, or None if no audio was recorded.
        """
        if not self._recording:
            return None

        self._recording = False

        # Stop the stream
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Wait for the collection thread to finish
        if self._record_thread:
            self._record_thread.join(timeout=1.0)
            self._record_thread = None

        # Drain remaining items from queue
        while not self._audio_queue.empty():
            try:
                data = self._audio_queue.get_nowait()
                self._audio_data.append(data)
            except queue.Empty:
                break

        # Check if we have any audio
        if not self._audio_data:
            return None

        # Concatenate all audio chunks
        audio = np.concatenate(self._audio_data, axis=0)

        # Convert float32 [-1, 1] to int16
        audio_int16 = (audio * 32767).astype(np.int16)

        # Save to temporary WAV file
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
            prefix="stt_recording_"
        )
        temp_path = temp_file.name
        temp_file.close()

        with wave.open(temp_path, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())

        return temp_path

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    def get_accumulated_audio(self) -> Optional[np.ndarray]:
        """
        Get all recorded audio so far without stopping.

        Thread-safe access to accumulated audio data during recording.
        Useful for streaming transcription scenarios.

        Returns:
            Concatenated audio as numpy array, or None if no audio yet.
        """
        with self._data_lock:
            if not self._audio_data:
                return None
            return np.concatenate(self._audio_data, axis=0)

    def set_on_chunk(self, callback: Optional[Callable[[np.ndarray], None]]) -> None:
        """
        Set or update the on_chunk callback.

        Args:
            callback: Function to call with each audio chunk, or None to disable.
        """
        self._on_chunk = callback

    @staticmethod
    def list_devices() -> None:
        """Print available audio input devices."""
        print("Available audio devices:")
        print(sd.query_devices())


def cleanup_temp_file(filepath: str) -> None:
    """Delete a temporary audio file."""
    try:
        if filepath and os.path.exists(filepath):
            os.unlink(filepath)
    except OSError as e:
        print(f"Warning: Could not delete temp file {filepath}: {e}")


if __name__ == "__main__":
    # Quick test
    import time

    print("Testing audio recorder...")
    AudioRecorder.list_devices()

    recorder = AudioRecorder()
    print("\nRecording for 3 seconds...")
    recorder.start()
    time.sleep(3)
    filepath = recorder.stop()

    if filepath:
        print(f"Audio saved to: {filepath}")
        print(f"File size: {os.path.getsize(filepath)} bytes")
        cleanup_temp_file(filepath)
        print("Temp file cleaned up.")
    else:
        print("No audio recorded!")
