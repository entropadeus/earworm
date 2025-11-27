"""
Audio recording module using sounddevice.
Records from the default microphone until stopped.
"""

import numpy as np
import sounddevice as sd
import threading
import queue
from typing import Optional
import tempfile
import wave
import os


class AudioRecorder:
    """Records audio from the microphone and saves to a temporary WAV file."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        """
        Args:
            sample_rate: Audio sample rate in Hz. Whisper expects 16kHz.
            channels: Number of audio channels. Mono (1) is fine for speech.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self._recording = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._audio_data: list = []
        self._stream: Optional[sd.InputStream] = None
        self._record_thread: Optional[threading.Thread] = None

        # Audio level monitoring
        self._current_level: float = 0.0
        self._level_callback: Optional[callable] = None

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info: dict, status: sd.CallbackFlags) -> None:
        """Callback function for the audio stream."""
        if status:
            print(f"Audio status: {status}")

        # Put a copy of the audio data into the queue
        self._audio_queue.put(indata.copy())

        # Calculate audio level (RMS)
        rms = np.sqrt(np.mean(indata ** 2))
        # Normalize to 0-1 range (typical speech is 0.01-0.3 RMS)
        self._current_level = min(1.0, rms * 5)

        # Call level callback if set
        if self._level_callback:
            try:
                self._level_callback(self._current_level)
            except Exception:
                pass  # Don't crash on callback errors

    def _record_loop(self) -> None:
        """Background thread that collects audio data from the queue."""
        while self._recording:
            try:
                data = self._audio_queue.get(timeout=0.1)
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

    def get_audio_level(self) -> float:
        """Get the current audio input level (0.0 to 1.0)."""
        return self._current_level

    def set_level_callback(self, callback: callable) -> None:
        """
        Set a callback to receive real-time audio level updates.

        Args:
            callback: Function that takes a float (0.0-1.0) as argument
        """
        self._level_callback = callback

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
