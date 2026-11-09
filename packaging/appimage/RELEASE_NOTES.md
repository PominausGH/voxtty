Private, local-first voice dictation for Linux. Press **Alt+D**, speak, and your words are typed into whatever app has focus. Transcription runs on your machine; no audio leaves it.

### New: one-file AppImage

No compiler, no Python setup. Runs on x86_64 distros from 2022 onwards (Ubuntu 22.04+, Fedora 36+, Debian 12+, Arch).

```bash
# Typing and the hotkey need these from your system (Debian/Ubuntu shown):
sudo apt install ydotool libnotify-bin
sudo systemctl enable --now ydotoold
sudo usermod -aG input "$USER"

mkdir -p ~/Applications && cd ~/Applications
curl -LO https://github.com/PominausGH/voxtty/releases/latest/download/Voxtty-x86_64.AppImage
chmod +x Voxtty-x86_64.AppImage
./Voxtty-x86_64.AppImage --install-service
```

Log out and back in (for the `input` group), then press Alt+D anywhere. The first run downloads the Whisper model (about 500 MB).

Verify the download: `sha256sum -c Voxtty-x86_64.AppImage.sha256`

### Fixes
- Voxtty no longer crashes at startup on desktops without the GTK or AppIndicator typelibs; the tray icon falls back to another backend instead.
- `--install-service` from an AppImage registers the AppImage file itself.

Full install options, including from source: see the [README](https://github.com/PominausGH/voxtty#installation-linux).
