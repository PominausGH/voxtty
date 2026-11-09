#!/usr/bin/env bash
# Build Voxtty-x86_64.AppImage inside an Ubuntu 22.04 container.
# 22.04 sets the glibc floor, so the AppImage runs on distros from 2022 on.
#
#   packaging/appimage/build.sh            # output in ./dist
#   OUT=/some/dir packaging/appimage/build.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${OUT:-$ROOT/dist}"
mkdir -p "$OUT"

docker run --rm \
    -v "$ROOT":/src:ro \
    -v "$OUT":/out \
    -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
    ubuntu:22.04 \
    bash /src/packaging/appimage/build-in-container.sh

ls -lh "$OUT"/Voxtty-x86_64.AppImage
