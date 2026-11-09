# AppImage build

```bash
packaging/appimage/build.sh        # -> dist/Voxtty-x86_64.AppImage (+ .sha256)
```

Needs Docker. The build runs in `ubuntu:22.04`, which sets the glibc floor
(runs on distros from 2022 onwards). Pushing a `v*` tag runs the same build in
GitHub Actions (`.github/workflows/release.yml`) and publishes a release.

What goes in:

| Part | Source |
|---|---|
| Python 3.12 | python-build-standalone, pinned by sha256 |
| PortAudio 19.7 | built from source, ALSA only (PipeWire/Pulse expose ALSA "default") |
| Voxtty + deps | `pip install .[cleanup]`, plus PyGObject for the AppIndicator tray |

What stays on the host: `ydotool`/`ydotoold` (typing), the `input` group
(hotkey), `notify-send`, and the GTK/AppIndicator typelibs (tray; Voxtty falls
back to the X11 tray if they're missing).

The build checks that everything imports, using pystray's dummy tray because
the container has no display. Before a release, run the AppImage on a desktop
and confirm the tray icon, mic and Alt+D work.
