"""
Whisper transcription module using faster-whisper.
Handles model loading and audio-to-text conversion.
"""

from faster_whisper import WhisperModel
from typing import Optional, Literal
import os


# Model size options (larger = more accurate but slower)
ModelSize = Literal["tiny", "base", "small", "medium", "large-v2", "large-v3"]


class Transcriber:
    """Transcribes audio files using Whisper."""

    def __init__(
        self,
        model_size: ModelSize = "base",
        device: str = "auto",
        compute_type: str = "auto"
    ):
        """
        Initialize the transcriber with a Whisper model.

        Args:
            model_size: Size of the Whisper model. Options:
                - "tiny": ~39M params, fastest, least accurate
                - "base": ~74M params, good balance for most use
                - "small": ~244M params, better accuracy
                - "medium": ~769M params, high accuracy
                - "large-v2"/"large-v3": ~1.5B params, best accuracy
            device: "cuda", "cpu", or "auto" (auto-detect)
            compute_type: "float16", "int8", "float32", or "auto"
        """
        self.model_size = model_size
        self._model: Optional[WhisperModel] = None
        self._device = device
        self._compute_type = compute_type

    def load_model(self) -> None:
        """Load the Whisper model. Called automatically on first transcription."""
        if self._model is not None:
            return

        print(f"Loading Whisper model '{self.model_size}'...")

        # Determine device (default to CPU for reliability)
        device = "cpu" if self._device == "auto" else self._device

        # Determine compute type based on device
        if self._compute_type == "auto":
            compute_type = "int8" if device == "cpu" else "float16"
        else:
            compute_type = self._compute_type

        self._model = WhisperModel(
            self.model_size,
            device=device,
            compute_type=compute_type
        )
        print("Model loaded successfully!")

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: Literal["transcribe", "translate"] = "transcribe"
    ) -> str:
        """
        Transcribe an audio file to text.

        Args:
            audio_path: Path to the audio file (WAV, MP3, etc.)
            language: Language code (e.g., "en", "es"). None = auto-detect.
            task: "transcribe" for same-language, "translate" to English.

        Returns:
            Transcribed text as a string.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Lazy load the model
        self.load_model()

        # Transcribe
        segments, info = self._model.transcribe(
            audio_path,
            language=language,
            task=task,
            beam_size=5,
            vad_filter=True,  # Filter out silence
            vad_parameters=dict(
                min_silence_duration_ms=500,
            )
        )

        # Combine all segments into one string
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        result = " ".join(text_parts)

        # Log detected language if auto-detected
        if language is None and info.language:
            print(f"Detected language: {info.language} "
                  f"(probability: {info.language_probability:.2f})")

        return result

    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model is not None


def get_recommended_model(has_gpu: bool = False) -> ModelSize:
    """
    Get the recommended model size based on hardware.

    Args:
        has_gpu: Whether a CUDA-capable GPU is available.

    Returns:
        Recommended model size string.
    """
    if has_gpu:
        return "small"  # Good balance on GPU
    else:
        return "base"  # Fast enough on CPU


if __name__ == "__main__":
    # Quick test
    import sys

    print("Testing transcriber...")

    # Check if a test file was provided
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        print("Usage: python transcriber.py <audio_file>")
        print("No audio file provided, just testing model load...")
        test_file = None

    transcriber = Transcriber(model_size="base", device="auto")

    if test_file:
        print(f"\nTranscribing: {test_file}")
        result = transcriber.transcribe(test_file)
        print(f"\nResult:\n{result}")
    else:
        transcriber.load_model()
        print("Model loaded successfully!")
