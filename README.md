# Voxtty

Private, local-first voice dictation for Linux and Windows. Press **Alt+D**, speak, and your words are typed into whatever app has focus — transcribed entirely on your own machine.

Site: [voxtty.com](https://voxtty.com)

## Features

- **Local transcription** — runs [faster-whisper](https://github.com/SYSTRAN/faster-whisper) on-device; no audio ever leaves your machine
- **Global hotkey (Alt+D)** — press to start dictating, press again to stop, from anywhere
- **Types into any focused app** — terminal, browser, editor, chat, anything
- **Voice activity detection** — knows when you've stopped talking, no fixed timers
- **Offline rule-based cleanup** — punctuation/capitalization/spacing fixes, on by default, no network calls
- **Custom word replacements** — teach it names, jargon, and spellings (case-insensitive), applied locally
- **System tray icon** — runs quietly in the background via a systemd user service, starts on login
- **Optional wake word** ("hey Jarvis") — experimental alternative to the hotkey; may false-trigger in some environments, Alt+D is the reliable trigger
- **Optional AI cleanup** — opt-in only, sends the transcript text (never audio) to the Claude API to strip fillers and polish punctuation; off by default, requires your own Anthropic API key

## Requirements

- **Linux**: x86_64, `ydotool` for typing, membership of the `input` group for the hotkey. Building from source also needs Python 3.10+ and `portaudio`
- **Windows**: Windows 10/11, Python 3.10+
- A microphone

## Installation (Linux)

### AppImage (easiest)

One file, nothing to compile. Works on x86_64 distros from 2022 onwards
(Ubuntu 22.04+, Fedora 36+, Debian 12+, Arch).

```bash
# 1. Typing and the hotkey need two things from your system. Debian / Ubuntu:
sudo apt install ydotool libnotify-bin
sudo systemctl enable --now ydotoold          # without it nothing is typed
sudo usermod -aG input "$USER"                # without it Alt+D never fires
#    Fedora: sudo dnf install ydotool libnotify   (then the same two lines)

# 2. Download the AppImage and register it to start at login.
mkdir -p ~/Applications && cd ~/Applications
curl -LO https://github.com/PominausGH/voxtty/releases/latest/download/Voxtty-x86_64.AppImage
chmod +x Voxtty-x86_64.AppImage
./Voxtty-x86_64.AppImage --install-service
```

**Log out and back in** for the `input` group to take effect, then press
**Alt+D** anywhere. The first run downloads the Whisper speech model (about
500 MB), so give it a minute. Keep the AppImage where it is: the login
service points at that file.

If it won't start with a FUSE error, install your distro's `fuse3` package, or
run it as `./Voxtty-x86_64.AppImage --appimage-extract-and-run`.

### From source

```bash
git clone https://github.com/PominausGH/voxtty.git
cd voxtty
./setup.sh
```

`setup.sh` installs system dependencies (`ydotool`, `portaudio`, etc.), adds you to the `input` group, creates a Python virtual environment, and installs Voxtty as a **systemd user service** that starts automatically on login.

**Log out and back in** after setup for the `input` group change to take effect. Then press **Alt+D** anywhere to start dictating.

### With pipx

For a source install, `setup.sh` is the easier path because it installs the
system packages for you. If you would rather manage it yourself, three of Voxtty's dependencies
(`evdev`, `PyAudio`, `webrtcvad`) publish no wheels and are compiled at install
time, so you need a compiler and the relevant headers **first**:

```bash
# 1. System packages. The compiler and headers are required because evdev,
#    PyAudio and webrtcvad publish no wheels and are built at install time.
#    Debian / Ubuntu:
sudo apt install gcc python3-dev portaudio19-dev ydotool \
                 python3-gi python3-gi-cairo gir1.2-gtk-3.0 libnotify-bin
#    Fedora:
#    sudo dnf install gcc python3-devel portaudio-devel ydotool \
#                     python3-gobject gtk3 libnotify

# 2. Start the ydotool daemon — without it Voxtty cannot type.
sudo systemctl enable --now ydotoold

# 3. Join the input group — without it the Alt+D hotkey cannot read the keyboard.
sudo usermod -aG input "$USER"

# 4. Install and register the service.
pipx install voxtty
voxtty --install-service
```

**Log out and back in** for the `input` group to take effect, then press
**Alt+D** anywhere.

All four steps matter: skip 1 and the install fails with compiler errors; skip 2
and nothing is typed; skip 3 and the hotkey never fires. `voxtty
--install-service` warns you about 2 and 3 if it detects them missing.

### Arch Linux

A `voxtty-git` PKGBUILD lives in [`packaging/aur/`](packaging/aur/). It is not
on the AUR yet — Arch has suspended new AUR account registration while dealing
with a wave of malicious package uploads — so build it directly for now:

```bash
git clone https://github.com/PominausGH/voxtty.git
cd voxtty/packaging/aur
makepkg -si
systemctl --user enable --now voxtty.service
```

## Installation (Windows)

```powershell
git clone https://github.com/PominausGH/voxtty.git
cd voxtty
.\setup.bat
```

`setup.bat`/`setup.ps1` creates a Python virtual environment, installs dependencies, and registers a **Task Scheduler** task (runs at logon, under your own user, no elevation) that starts Voxtty automatically. Press **Alt+D** anywhere to start dictating.

A few Windows-specific things worth knowing:
- Alt+D is also a built-in "focus the address bar" shortcut in most browsers and File Explorer — both will fire together, same as the non-exclusive hook behavior on Linux.
- A global keyboard hook plus synthetic keystroke injection is a common antivirus/SmartScreen heuristic for keylogger-style tools. Voxtty isn't code-signed yet, so don't be surprised if your AV flags it on first run — it's a false positive from the technique, not the intent.
- Logs and the AI-cleanup API key file both live under `%LOCALAPPDATA%\voxtty` (Windows has no XDG-style data/config split).

## Usage (Linux)

```bash
systemctl --user status voxtty    # check status
systemctl --user restart voxtty   # restart
systemctl --user stop voxtty      # stop
journalctl --user -u voxtty -f    # live logs
```

Logs are also saved to `~/.local/share/voxtty/voxtty.log`.

`toggle_voxtty.sh` can be bound to a custom keyboard shortcut (e.g. in GNOME Settings) as an alternative to Alt+D. This is Linux-only — Alt+D's global hook works uniformly across Windows desktop sessions, so there's no equivalent need on Windows.

## Usage (Windows)

```powershell
schtasks /Query /TN Voxtty    # check status
schtasks /End /TN Voxtty      # stop
schtasks /Run /TN Voxtty      # start
```

Logs are saved to `%LOCALAPPDATA%\voxtty\voxtty.log`.

## Configuration

Voxtty writes a `config.json` in the repo directory on first run (git-ignored — your local settings, not committed). Notable options:

- `whisper_model` — Whisper model size (default `small.en`)
- `microphone_name` — substring to match your preferred input device
- `wake_word` / `wake_word_threshold` — experimental voice-triggered start, off the hotkey
- `rule_cleanup_enabled` — local, offline punctuation/formatting cleanup (default `true`)
- `cleanup_enabled` — opt-in AI cleanup pass via the Claude API (default `false`)
- `word_replacements` — a `{"heard": "typed"}` map for custom dictionary entries

To enable AI cleanup, set `cleanup_enabled: true` in `config.json` and put your Anthropic API key in the `env` file created by setup (`~/.config/voxtty/env` on Linux, `%LOCALAPPDATA%\voxtty\env` on Windows), then restart.

## Pricing

This repo is the free, open-source core — full local dictation, no license gate. A paid Pro tier is planned but not on sale yet — see [voxtty.com/#pricing](https://voxtty.com/#pricing).

## License

MIT — see [LICENSE](LICENSE).
