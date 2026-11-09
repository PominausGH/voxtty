#!/usr/bin/env bash
# Runs inside ubuntu:22.04. Called by build.sh; not meant to be run directly.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20250818/cpython-3.12.11+20250818-x86_64-unknown-linux-gnu-install_only.tar.gz"
PY_SHA="98229938166f51deff81b00d71455fac84a57290b71089bd5fe673738557f053"
PA_URL="https://files.portaudio.com/archives/pa_stable_v190700_20210406.tgz"
PA_SHA="47efbf42c77c19a05d22e627d42873e991ec0c1357219c0d74ce6a2948cb2def"
AIT_URL="https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage"
AIT_SHA="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"

apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    ca-certificates curl gcc g++ make pkg-config file \
    libasound2-dev libgirepository1.0-dev libcairo2-dev >/dev/null

WORK=/build
APPDIR=$WORK/AppDir
mkdir -p "$WORK" "$APPDIR/usr/lib"
cd "$WORK"

fetch() {  # url sha256 outfile
    curl -fsSL -o "$3" "$1"
    echo "$2  $3" | sha256sum -c --quiet -
}

# 1. Portable CPython (self-contained, relocatable).
fetch "$PY_URL" "$PY_SHA" python.tar.gz
tar -xzf python.tar.gz -C "$APPDIR/usr"          # -> usr/python/
PY="$APPDIR/usr/python/bin/python3"

# 2. PortAudio, ALSA only. PipeWire and PulseAudio both expose an ALSA
#    "default" device, and leaving JACK out avoids bundling libjack.
fetch "$PA_URL" "$PA_SHA" pa.tgz
tar -xzf pa.tgz
(cd portaudio && ./configure -q --prefix="$WORK/pa" --without-jack --without-oss \
    --disable-static >/dev/null && make -s -j"$(nproc)" >/dev/null 2>&1 && make -s install >/dev/null)
cp -L "$WORK/pa/lib/libportaudio.so.2" "$APPDIR/usr/lib/"

# 3. Voxtty and its dependencies. Copy the source first: pip writes
#    build metadata into the tree and /src is mounted read-only.
mkdir -p "$WORK/src"
tar -C /src --exclude=./venv --exclude=./dist --exclude=./docs --exclude=./.git \
    --exclude='*.egg-info' -cf - . | tar -C "$WORK/src" -xf -
VERSION="$("$PY" -c "import tomllib;print(tomllib.load(open('$WORK/src/pyproject.toml','rb'))['project']['version'])")"

# The portable Python was built with clang; use the gcc we installed.
export CC=gcc CXX=g++ LDSHARED="gcc -shared"
export CFLAGS="-I$WORK/pa/include" LDFLAGS="-L$WORK/pa/lib"
"$PY" -m pip install -q --no-cache-dir --upgrade pip
# PyGObject gives pystray the AppIndicator tray (GNOME/KDE). It uses the
# host's typelibs at runtime; if those are missing pystray falls back to X11.
# <3.51 because later versions need girepository-2.0, which 22.04 lacks.
"$PY" -m pip install -q --no-cache-dir "$WORK/src[cleanup]" "PyGObject>=3.42,<3.51"

# Trim things the app never uses.
rm -rf "$APPDIR/usr/python/lib/python3.12/site-packages/pip" \
       "$APPDIR/usr/python/lib/python3.12/ensurepip" \
       "$APPDIR/usr/python/lib/python3.12/idlelib" \
       "$APPDIR/usr/python/lib/python3.12/tkinter" \
       "$APPDIR/usr/python/lib/python3.12/turtledemo"
find "$APPDIR" -name '__pycache__' -prune -exec rm -rf {} +
"$PY" -m compileall -q -j0 "$APPDIR/usr/python/lib/python3.12" >/dev/null || true

# Fail the build here rather than ship an AppImage that cannot import.
# No display here, so use pystray's dummy tray; the real backends are
# exercised on a desktop (see packaging/appimage/README.md).
PYSTRAY_BACKEND=dummy LD_LIBRARY_PATH="$APPDIR/usr/lib" "$PY" -I -c "
import faster_whisper, numpy, pyaudio, webrtcvad, evdev, pystray, PIL, anthropic, platformdirs, gi
import voxtty.app
print('imports ok; portaudio:', pyaudio.get_portaudio_version_text())
"

# 4. AppDir metadata.
cp /src/packaging/appimage/AppRun "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp /src/packaging/appimage/voxtty.desktop "$APPDIR/voxtty.desktop"
"$PY" /src/packaging/appimage/make_icon.py "$APPDIR/voxtty.png"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp "$APPDIR/voxtty.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/voxtty.png"
ln -sf voxtty.png "$APPDIR/.DirIcon"

# 5. Pack. No FUSE in a container, so appimagetool runs extracted.
fetch "$AIT_URL" "$AIT_SHA" appimagetool
chmod +x appimagetool
# Unversioned name so releases/latest/download/Voxtty-x86_64.AppImage is a
# stable link; the version is in the release tag and `--version`.
OUTFILE="/out/Voxtty-x86_64.AppImage"
echo "building Voxtty $VERSION"
ARCH=x86_64 ./appimagetool --appimage-extract-and-run --no-appstream -n "$APPDIR" "$OUTFILE" >/dev/null 2>&1 \
    || ARCH=x86_64 ./appimagetool --appimage-extract-and-run --no-appstream -n "$APPDIR" "$OUTFILE"
(cd /out && sha256sum "$(basename "$OUTFILE")" > "$(basename "$OUTFILE").sha256")
chown "${HOST_UID:-0}:${HOST_GID:-0}" "$OUTFILE" "$OUTFILE.sha256"
echo "built $OUTFILE"
