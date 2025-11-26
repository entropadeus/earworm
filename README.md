# Earhole 👂

Stop typing. Start talking. Your computer transcribes it. That's it. Fully local, no cloud, no tracking.

## What is it?

Earhole is a desktop app that listens to your microphone, figures out what the hell you just said, and automatically types it wherever you are. No cloud, no bullshit, no privacy-stealing. It runs 100% locally using OpenAI's **Whisper** model.

Use it when:
- You wanna dictate instead of type (because who doesn't?)
- Your wrists need a goddamn break
- You're lazy (relatable)
- You're actually busy and can't type
- The keyboard is across the room and you're comfortable
- You just feel like talking to your computer like a normal person

## How it works

Press and hold **F9**, talk, release F9. Text shows up. Done.

More detailed:
1. Hold F9
2. Say what you want to type
3. Release F9
4. It transcribes and types it into whatever window you were just in

No account, no API keys, no internet required after you download the model once.

The app lives in your system tray. Open it with the icon, configure if you need to, then just use F9.

## Why I built this

Honest answer? My wrists were fucked from typing all day. Also, every voice-to-text solution out there is either:
- A privacy nightmare that sends your voice to some company
- Slow as hell with annoying lag
- Only works with one specific app
- Some combination of all three

So I made Earhole. It:
- **Stays local** — your voice never leaves your computer
- **Actually works** — no lag, just press F9 and talk
- **Works everywhere** — any app that takes text input
- **Is simple** — because complicated software sucks
- **Doesn't track you** — I don't have a backend to stick your data in

Basically a tool that does one thing well instead of 10 things poorly.

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

## Getting started

Clone it, set up a venv, install deps, run it.

```bash
git clone https://github.com/entropadeus/earhole.git
cd earhole

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install everything
pip install -r requirements.txt

# Run
python main.py
```

That's it. The app will load the Whisper model on first run (takes a minute or two depending on your hardware) then you're ready.

If you've got an NVIDIA GPU and want to use it:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Using it

Just run `python main.py` and it starts. F9 to record, done.

First time it runs, it'll download the Whisper model (couple minutes depending on your internet). After that it loads instantly.

### Command line options if you need them
```bash
python main.py --model small --language en
```

- `--model` — Which Whisper model to use. Options: `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`. Default is `base` which is a good middle ground.
- `--language` — Language code like `en`, `es`, `fr`. Defaults to auto-detect which is fine.
- `--no-notifications` — Shut up the notification popups

### Config file
Earhole saves settings to:
- **Windows**: `%APPDATA%\LocalSTT\config.json`
- **macOS/Linux**: `~/.config/LocalSTT/config.json`

You can edit it directly if you want to tweak stuff:
- `model_size` — Model size (default: base)
- `language` — Language code (null means auto-detect)
- `typing_delay` — How fast to type (in seconds, default 0)
- `use_clipboard` — Use clipboard to paste (default true, faster)
- `show_notifications` — Show desktop notifications (default true)

## What it uses

All listed in `requirements.txt`:
- **faster-whisper** — The speech recognition engine (fast version of Whisper)
- **sounddevice** — Grabs audio from your mic
- **numpy** — Math stuff
- **pynput** — Keyboard hotkeys and keyboard simulation
- **pyperclip** — Clipboard access (for pasting)
- **pystray** — System tray icon
- **Pillow** — Image handling

## If something breaks

### Can't record audio
Check that your microphone actually works. Go to system settings and make sure it's set as the default. If you're still stuck, run `python -c "from src.audio_recorder import AudioRecorder; AudioRecorder.list_devices()"` to see what devices you have.

Also make sure you're actually holding F9. Sometimes people just forget.

### Recording is slow
Smaller models are faster. If you're using `large-v3`, yeah it's gonna be slow. Switch to `base` and you'll be fine. GPU helps a lot if you have one.

### Text won't type into my app
Some apps are locked down and block keyboard simulation (banks, corporate stuff, remote desktop). Try setting `use_clipboard` to `false` in the config to type character by character instead of pasting.

Some antivirus software also blocks this, so if that's you, you'll need to whitelist the app.

### Model won't load
You probably don't have enough disk space. The models take 500MB to 3GB depending on which one you use. Delete the cache if you need space: `~/.cache/huggingface/hub/` on Linux/Mac or `%USERPROFILE%\.cache\huggingface\hub\` on Windows.

### Machine is dying under load
Don't use `large` on a potato computer. Use `base` or `tiny`. If you have a GPU, use that. If you don't, close some stuff and try again.

## Making it faster

**Pick the right model for your machine.** `base` is good. `tiny` is faster but less accurate. `large` is super accurate but slow. If you have a GPU, use it.

**Use clipboard paste** (it's on by default). It's way faster than typing character by character. Only turn it off if some weird app doesn't like clipboard.

**Set a language** if you always speak the same one. Auto-detect works but locked languages are a bit faster.

**The model pre-loads when you start the app** so you don't hit a 30-second delay on first use. Nice.

## Building a standalone executable

Want to bundle it into a `.exe` so you don't need Python installed?

```bash
python build_exe.py
```

Grabs everything, packages it up, puts the `.exe` in the `dist/` folder. No Python needed to run it after that.

## Limitations

- **Push-to-talk only** — You hold F9 to record. No "always listening" background mode. This is intentional for privacy and to avoid accidental transcriptions.
- **Local only** — Runs on the machine you're using. Can't send audio to another computer.
- **English works best** — Whisper is trained mostly on English. Other languages work but aren't as good.
- **Some apps block it** — Anything with locked-down input (banks, corporate security, remote desktop) won't let you use keyboard simulation. Deal with it.

## Contributing

Found a bug? Have an idea? Open an issue or PR.

## License

MIT. Do whatever you want with it.

## Thanks to

- [OpenAI Whisper](https://github.com/openai/whisper) — Makes the transcription magic happen
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) — Makes it actually usable
- [pynput](https://github.com/moses-palmer/pynput) — Handles the keyboard stuff

## FAQ

**My voice is being recorded and sold, right?**
Nope. It's local only. Everything stays on your computer. No servers, no tracking, no bullshit. That's the whole point.

**What languages does it work with?**
99 languages. It auto-detects by default. If you always speak one language, you can lock it in the settings.

**Does it work on Mac?**
Yep, Linux and Mac too. F9 might not work on Mac keyboards, but you can remap it if you want. Functionality is the same.

**How accurate is the transcription?**
Pretty damn good if you speak clearly. Better with good audio. The bigger models (`medium`, `large`) are scary accurate. Smaller ones are fine but make more mistakes.

**Can I toggle recording instead of holding F9?**
No. Push-to-talk only. That's intentional—it's simpler and you always know when you're recording.

**Will this work with my app?**
Probably. Works with anything that takes text input. Doesn't work with locked-down security stuff like banking sites or corporate remote desktops. Those apps actively block keyboard simulation.

---

Built because I got tired of typing. You probably will too.
