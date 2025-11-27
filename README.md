# Earworm 👂

Stop typing. Start talking. Your computer transcribes it. That's it. Fully local, no cloud, no tracking.

## What is it?

Earworm is a desktop app that listens to your microphone, figures out what the hell you just said, and automatically types it wherever you are. No cloud, no bullshit, no privacy-stealing. It runs 100% locally using OpenAI's **Whisper** model.

Use it when:
- You wanna dictate instead of type (because who doesn't?)
- Your wrists need a goddamn break
- You're lazy (relatable)
- You're actually busy and can't type
- The keyboard is across the room and you're comfortable
- You just feel like talking to your computer like a normal person

## What's New in v2.0

### Voice Commands
Say commands while dictating to control formatting:
- **Punctuation**: "period", "comma", "question mark", "exclamation point"
- **Formatting**: "new line", "new paragraph", "tab"
- **Editing**: "delete that", "undo", "scratch that"
- **Symbols**: "at sign", "hashtag", "dollar sign", "open paren", "close paren"
- **Quotes**: "open quote", "close quote", "single quote"

### Smart Punctuation
Earworm now automatically adds punctuation:
- Capitalizes sentences
- Adds periods at sentence ends
- Detects questions and adds question marks
- Inserts commas at natural pauses
- Removes filler words (optional)

### Preview Window
Review your transcription before it's typed:
- Edit text inline before accepting
- Press **Enter** to accept, **Escape** to cancel
- Press **Tab** to re-record
- Copy to clipboard without pasting
- Auto-accept timer (optional)

## How it works

Press and hold **F9**, talk, release F9. Preview window shows up. Hit Enter to paste. Done.

More detailed:
1. Hold F9
2. Say what you want to type (including voice commands like "period" or "new line")
3. Release F9
4. Preview window shows the transcription with smart punctuation
5. Press Enter to accept, Escape to cancel, or edit the text first
6. Text gets typed into whatever window you were just in

No account, no API keys, no internet required after you download the model once.

The app lives in your system tray. Open it with the icon, configure if you need to, then just use F9.

## Why I built this

Honest answer? My wrists were fucked from typing all day. Also, every voice-to-text solution out there is either:
- A privacy nightmare that sends your voice to some company
- Slow as hell with annoying lag
- Only works with one specific app
- Some combination of all three

So I made Earworm. It:
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

### Voice Commands Reference

| Say This | You Get |
|----------|---------|
| "period" / "full stop" | . |
| "comma" | , |
| "question mark" | ? |
| "exclamation mark" | ! |
| "colon" | : |
| "semicolon" | ; |
| "new line" | Line break |
| "new paragraph" | Double line break |
| "open quote" / "close quote" | " |
| "open paren" / "close paren" | ( ) |
| "open bracket" / "close bracket" | [ ] |
| "open brace" / "close brace" | { } |
| "at sign" | @ |
| "hashtag" / "hash" | # |
| "dollar sign" | $ |
| "ampersand" | & |
| "asterisk" / "star" | * |
| "hyphen" / "dash" | - |
| "underscore" | _ |
| "forward slash" | / |
| "backslash" | \ |
| "delete that" / "scratch that" | Deletes last chunk |
| "undo" | Undoes last action |
| "capitalize" | Capitalizes next word |
| "all caps" | UPPERCASES next word |
| "no space" | No space before next |

### Preview Window Shortcuts

| Key | Action |
|-----|--------|
| Enter | Accept and paste text |
| Escape | Cancel and discard |
| Tab | Re-record |
| Ctrl+C | Copy to clipboard |
| Ctrl+Enter | Accept (alternative) |
| Ctrl+Z | Undo edit |
| Ctrl+Y | Redo edit |

### Command line options

```bash
python main.py --model small --language en --no-preview
```

**Core options:**
- `--model` — Whisper model: `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`. Default: `base`
- `--language` — Language code like `en`, `es`, `fr`. Default: auto-detect
- `--no-notifications` — Disable notification popups

**Feature toggles:**
- `--no-voice-commands` — Disable voice command processing
- `--no-punctuation` — Disable smart punctuation
- `--no-preview` — Skip preview, type directly

**Preview options:**
- `--auto-accept N` — Auto-accept after N seconds (0 = disabled)
- `--theme dark|light` — Preview window theme

### Config file

Earworm saves settings to:
- **Windows**: `%APPDATA%\Earworm\config.json`
- **macOS/Linux**: `~/.config/Earworm/config.json`

Full config options:

```json
{
  "model_size": "base",
  "language": null,
  "typing_delay": 0.0,
  "use_clipboard": true,
  "show_notifications": true,

  "enable_voice_commands": true,

  "enable_smart_punctuation": true,
  "auto_capitalize": true,
  "auto_periods": true,
  "auto_commas": true,
  "remove_fillers": false,

  "enable_preview": true,
  "preview_auto_accept_delay": 0.0,
  "preview_theme": "dark",
  "preview_position": "center",
  "preview_font_size": 12,
  "preview_show_shortcuts": true
}
```

**Core settings:**
- `model_size` — Whisper model size
- `language` — Language code (null = auto-detect)
- `typing_delay` — Delay between keystrokes (seconds)
- `use_clipboard` — Use clipboard paste (faster)
- `show_notifications` — Show desktop notifications

**Voice commands:**
- `enable_voice_commands` — Process voice commands like "period", "new line"

**Smart punctuation:**
- `enable_smart_punctuation` — Auto-add punctuation
- `auto_capitalize` — Capitalize sentence starts
- `auto_periods` — Add periods at sentence ends
- `auto_commas` — Add commas at natural pauses
- `remove_fillers` — Remove "um", "uh", etc.

**Preview window:**
- `enable_preview` — Show preview before typing
- `preview_auto_accept_delay` — Auto-accept seconds (0 = disabled)
- `preview_theme` — "dark" or "light"
- `preview_position` — "center", "cursor", or "bottom-right"
- `preview_font_size` — Text font size
- `preview_show_shortcuts` — Show keyboard hints

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

### Voice commands not working
Make sure `enable_voice_commands` is `true` in your config. Speak clearly and pause slightly around commands. If you want literal text like "period", say "literal period".

### Punctuation is wrong
Smart punctuation uses heuristics and isn't perfect. You can disable it with `--no-punctuation` or `enable_smart_punctuation: false`. The preview window lets you fix any mistakes before pasting.

### Model won't load
You probably don't have enough disk space. The models take 500MB to 3GB depending on which one you use. Delete the cache if you need space: `~/.cache/huggingface/hub/` on Linux/Mac or `%USERPROFILE%\.cache\huggingface\hub\` on Windows.

### Machine is dying under load
Don't use `large` on a potato computer. Use `base` or `tiny`. If you have a GPU, use that. If you don't, close some stuff and try again.

## Making it faster

**Pick the right model for your machine.** `base` is good. `tiny` is faster but less accurate. `large` is super accurate but slow. If you have a GPU, use it.

**Use clipboard paste** (it's on by default). It's way faster than typing character by character. Only turn it off if some weird app doesn't like clipboard.

**Set a language** if you always speak the same one. Auto-detect works but locked languages are a bit faster.

**Disable preview for speed** if you trust the transcription: `--no-preview`

**The model pre-loads when you start the app** so you don't hit a 30-second delay on first use. Nice.

## Building a standalone executable

Want to bundle it into a `.exe` so you don't need Python installed?

```bash
python build.py
```

Grabs everything, packages it up, puts the `Earworm.exe` in the `dist/` folder. No Python needed to run it after that.

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

**How do I type literal words like "period" or "comma"?**
Say "literal period" or "literal comma" to get the actual word instead of punctuation.

**Can I add custom voice commands?**
The architecture supports it. Edit the `custom_voice_commands` in config or extend `VoiceCommandProcessor` in code.

**Why does the preview window exist?**
It lets you catch mistakes before they're typed. You can edit, re-record, or cancel. Disable it with `--no-preview` if you want raw speed.

---

Built because I got tired of typing. You probably will too.
