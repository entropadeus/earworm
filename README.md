# Earhole 👂

A lightweight, local speech-to-text application that converts your voice into text in real-time. No cloud, no privacy concerns—just press a key and dictate.

## What is it?

Earhole is a desktop application that listens to your microphone, transcribes speech to text, and automatically types it into whatever application you're currently using. It uses OpenAI's **Whisper** model for offline speech recognition, running entirely on your machine.

Perfect for:
- Dictating emails, messages, and documents
- Hands-free text input when your hands are busy
- Quick voice notes into any text field
- Accessibility features for users who prefer voice input
- Anyone tired of typing

## How it works

1. **Hold F9** on your keyboard to start recording
2. **Speak clearly** into your microphone
3. **Release F9** to stop recording and begin transcription
4. **The text appears** automatically typed into your active window

That's it. No account creation, no API keys, no internet connection required.

### The flow:
```
Hold F9 → Record audio → Release F9 → Transcribe → Auto-type text
```

The application runs in your system tray, staying out of your way until you need it.

## Why I built it

I got tired of typing. I wanted something that:
- **Works offline** - no data sent to cloud services
- **Is fast** - minimal latency between speaking and typing
- **Is reliable** - works with any application that accepts text input
- **Is simple** - one keystroke to use, no configuration needed
- **Respects privacy** - everything stays on my machine

The Whisper model is incredibly good at transcription, and faster-whisper makes it run efficiently even on CPU-only machines. Combining that with hotkey detection and keyboard simulation gave me exactly what I needed.

## System Requirements

### Minimum
- **OS**: Windows 7+, macOS 10.13+, or Linux (Ubuntu 18.04+)
- **Python**: 3.7 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 2GB free space (for model + environment)
- **Microphone**: Any working audio input device

### Recommended
- **RAM**: 8GB+
- **GPU**: NVIDIA GPU with CUDA (optional, for faster transcription)
- **Disk**: SSD (faster model loading)

### Disk Space by Model Size
- `tiny`: ~40MB (fastest, least accurate)
- `base`: ~140MB (recommended for most users)
- `small`: ~466MB (better accuracy)
- `medium`: ~1.5GB (high accuracy)
- `large-v3`: ~2.9GB (best accuracy, slowest)

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/earhole.git
cd earhole
```

### 2. Create a virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

For **GPU acceleration** (NVIDIA only):
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 4. Run the application
```bash
python main.py
```

## Usage

### Basic usage
```bash
python main.py
```
This starts Earhole with default settings (base model, auto-detect language).

### Command-line options
```bash
python main.py --model base --language en --no-notifications
```

**Available options:**
- `--model {tiny,base,small,medium,large-v2,large-v3}` — Whisper model size (default: base)
- `--language {en,es,fr,de,...}` — Language code (default: auto-detect)
- `--no-notifications` — Disable desktop notifications

### Keyboard shortcuts
- **F9** — Hold to record, release to transcribe and type
- **System tray icon** — Right-click for menu options

### Configuration
Settings are saved to:
- **Windows**: `%APPDATA%\LocalSTT\config.json`
- **macOS/Linux**: `~/.config/LocalSTT/config.json` (or `~/.LocalSTT/config.json`)

You can manually edit this file to adjust:
- `model_size` — Default Whisper model
- `language` — Default language (null for auto-detect)
- `typing_delay` — Delay between keystrokes in seconds
- `use_clipboard` — Use clipboard paste for typing (faster, more reliable)
- `show_notifications` — Desktop notifications

## Dependencies

- **faster-whisper** — Fast Whisper transcription engine
- **sounddevice** — Microphone audio capture
- **numpy** — Numerical operations
- **pynput** — Keyboard hotkeys and text simulation
- **pyperclip** — Clipboard management
- **pystray** — System tray integration
- **Pillow** — Image handling for tray icon

See `requirements.txt` for version details.

## Troubleshooting

### "No audio recorded" error
- Check that your microphone is working and not muted
- Make sure your audio input device is set as default in system settings
- Try listing audio devices: `python -m src.audio_recorder`

### Transcription is slow
- Use a smaller model (`tiny` or `base`) for speed
- Add a GPU for 3-5x faster transcription
- Pre-load the model on startup to avoid first-use delay

### Text isn't typing into my application
- Some apps don't accept simulated keyboard input (e.g., browser consoles, remote applications)
- Try enabling `use_clipboard: false` in config to use slower character-by-character typing
- Some security software may block keyboard simulation

### "Model failed to load" error
- You may not have enough disk space
- Try deleting the model cache: `~/.cache/huggingface/hub/` (Linux/macOS) or `%USERPROFILE%\.cache\huggingface\hub\` (Windows)
- Ensure you have at least 2GB free space

### High CPU/RAM usage
- Larger models (medium, large) consume more resources
- Switch to a smaller model for your machine's capabilities
- Close other applications to free up RAM

## Performance Tips

1. **Pre-load the model** — The first transcription loads the model (5-30 seconds depending on hardware). Earhole does this on startup automatically.

2. **Use clipboard mode** (default) — Faster and more reliable than character-by-character typing. Disable if an app doesn't accept clipboard paste.

3. **Choose the right model**:
   - **CPU-only machines**: Use `tiny` or `base`
   - **Mid-range hardware**: Use `base` or `small`
   - **High-end with GPU**: Use `small`, `medium`, or `large-v3`

4. **Language setting** — Specifying a language avoids auto-detection and makes transcription slightly faster.

## Building a Standalone Executable

You can package Earhole into a standalone `.exe` for Windows:

```bash
python build_exe.py
```

The executable will be in the `dist/` folder. No Python installation needed to run it.

## Known Limitations

- **Push-to-talk only** — You hold F9 while speaking. Continuous voice activation is not supported.
- **Local machine only** — Works on the machine running the application (no remote audio input).
- **English-biased** — While Whisper supports 99 languages, it performs best with English.
- **Special characters** — Some non-ASCII characters may not type correctly into certain applications.

## Contributing

Found a bug? Have a feature request? Feel free to open an issue or pull request.

## License

MIT License — use it, modify it, share it freely.

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) — The amazing speech recognition model
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) — High-performance Whisper implementation
- [pynput](https://github.com/moses-palmer/pynput) — Cross-platform keyboard/mouse control

## FAQ

**Q: Does my voice data get sent anywhere?**
A: No. Everything runs locally on your machine. No internet connection is required after the Whisper model is downloaded.

**Q: Which language does it recognize?**
A: Whisper supports 99 languages. By default, it auto-detects. You can specify a language in settings.

**Q: Can I use this on macOS?**
A: Yes! Earhole is cross-platform. Some keyboard shortcuts may need adjustment for macOS.

**Q: How accurate is it?**
A: Very accurate for clear speech. Accuracy depends on audio quality, background noise, and the Whisper model you use. The larger models (medium, large) are more accurate but slower.

**Q: Can I pause/resume recording instead of holding F9?**
A: The current design is push-to-talk (hold to record). This is intentional to keep things simple and predictable. Toggle mode might be added in the future.

**Q: Does it work with every application?**
A: Most applications that accept text input work great. Some security-restricted apps (banking sites in browsers, remote desktop clients, etc.) may not accept simulated keyboard input.

---

Built with ❤️ for people who want to speak, not type.
