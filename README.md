# Voxtty

Private, local-first voice dictation for Linux. Press **Alt+D**, speak, and your words are typed into whatever app has focus — transcribed entirely on your own machine.

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

- Ubuntu Linux (Wayland), Python 3.10+
- `ydotool` for typing into applications
- `portaudio` for audio capture
- A microphone

## Installation

```bash
git clone https://github.com/PominausGH/voxtty.git
cd voxtty
./setup.sh
```

`setup.sh` installs system dependencies (`ydotool`, `portaudio`, etc.), adds you to the `input` group, creates a Python virtual environment, and installs Voxtty as a **systemd user service** that starts automatically on login.

**Log out and back in** after setup for the `input` group change to take effect. Then press **Alt+D** anywhere to start dictating.

## Usage

```bash
systemctl --user status voxtty    # check status
systemctl --user restart voxtty   # restart
systemctl --user stop voxtty      # stop
journalctl --user -u voxtty -f    # live logs
```

Logs are also saved to `~/.local/share/voxtty/voxtty.log`.

`toggle_voxtty.sh` can be bound to a custom keyboard shortcut (e.g. in GNOME Settings) as an alternative to Alt+D.

## Configuration

Voxtty writes a `config.json` in the repo directory on first run (git-ignored — your local settings, not committed). Notable options:

- `whisper_model` — Whisper model size (default `small.en`)
- `microphone_name` — substring to match your preferred input device
- `wake_word` / `wake_word_threshold` — experimental voice-triggered start, off the hotkey
- `rule_cleanup_enabled` — local, offline punctuation/formatting cleanup (default `true`)
- `cleanup_enabled` — opt-in AI cleanup pass via the Claude API (default `false`)
- `word_replacements` — a `{"heard": "typed"}` map for custom dictionary entries

To enable AI cleanup, set `cleanup_enabled: true` in `config.json` and put your Anthropic API key in `~/.config/voxtty/env` (created by `setup.sh`), then restart the service.

## Pricing

This repo is the free, open-source core — full local dictation, no license gate. See [voxtty.com/#pricing](https://voxtty.com/#pricing) for the current Pro roadmap.

## License

MIT — see [LICENSE](LICENSE).
