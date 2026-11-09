"""Linux backend — evdev for the Alt+D hotkey, ydotool for typing, notify-send for notifications."""

import logging
import os
import selectors
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import evdev
from evdev import ecodes

from .base import Backend

log = logging.getLogger("voxtty.linux")


_UNIT_TEMPLATE = """[Unit]
Description=Voxtty - Voice dictation with Alt+D hotkey
After=graphical-session.target sound.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart={exec_path}
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus
Environment=YDOTOOL_SOCKET=/run/user/{uid}/.ydotool_socket
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=graphical-session.target
"""


class LinuxBackend(Backend):
    def __init__(self, key_delay_ms: int = 0) -> None:
        if not os.environ.get("YDOTOOL_SOCKET"):
            os.environ["YDOTOOL_SOCKET"] = f"/run/user/{os.getuid()}/.ydotool_socket"
        self._alt_pressed = False
        # 0 is right for local apps. Remote sessions (RDP/VNC/Citrix via
        # Remmina, etc.) forward each keystroke over the network and drop or
        # reorder zero-delay bursts, so they need a few ms of spacing.
        self.key_delay_ms = max(0, int(key_delay_ms))

    # ── Readiness ────────────────────────────────────────────────────────────

    def check_ready(self) -> tuple[bool, Optional[str]]:
        try:
            subprocess.run(["ydotool", "--help"], check=True, capture_output=True)
            return True, None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False, "ydotool unavailable — run: sudo ydotoold &"

    # ── Autostart (systemd user service) ─────────────────────────────────────

    _UNIT_NAME = "voxtty.service"

    @staticmethod
    def _unit_path() -> Path:
        return Path.home() / ".config" / "systemd" / "user" / LinuxBackend._UNIT_NAME

    @staticmethod
    def _console_script() -> Optional[Path]:
        """Locate the installed `voxtty` entry point.

        sys.executable's directory is checked first: under pipx that is the
        managed venv holding the real script, while `voxtty` on PATH is only a
        symlink into it.

        Under an AppImage, $APPIMAGE is the .AppImage file itself; anything
        inside the app is a temporary mount that vanishes when it exits.
        """
        appimage = os.environ.get("APPIMAGE")
        if appimage and Path(appimage).is_file():
            return Path(appimage)
        candidate = Path(sys.executable).parent / "voxtty"
        if candidate.exists():
            return candidate
        found = shutil.which("voxtty")
        return Path(found) if found else None

    @staticmethod
    def _systemctl(*args: str) -> tuple[bool, str]:
        try:
            r = subprocess.run(
                ["systemctl", "--user", *args], capture_output=True, text=True, timeout=30
            )
            return r.returncode == 0, (r.stderr or r.stdout).strip()
        except FileNotFoundError:
            return False, "systemctl not found — this system does not use systemd."
        except subprocess.SubprocessError as e:
            return False, f"systemctl failed: {e}"

    @staticmethod
    def _preflight() -> list[str]:
        """Problems that leave Voxtty installed but non-functional.

        Not fatal — the service is still worth installing, since both of these
        are fixed outside Voxtty and take effect on the next start.
        """
        problems = []
        try:
            import grp

            in_input = "input" in {grp.getgrgid(g).gr_name for g in os.getgroups()}
        except Exception:
            in_input = True  # Cannot determine it; do not cry wolf.
        if not in_input:
            problems.append(
                "You are not in the 'input' group, so the Alt+D hotkey cannot read\n"
                "  the keyboard. Fix:  sudo usermod -aG input $USER\n"
                "  then log out and back in for it to take effect."
            )

        socket = os.environ.get("YDOTOOL_SOCKET", "")
        if socket and not Path(socket).exists():
            problems.append(
                "ydotoold is not running, so Voxtty cannot type. Fix:\n"
                "  sudo systemctl enable --now ydotoold"
            )
        return problems

    def install_service(self) -> tuple[bool, str]:
        exec_path = self._console_script()
        if exec_path is None:
            return False, (
                "Could not find the 'voxtty' console script. Install the package "
                "first (pipx install voxtty), then re-run --install-service."
            )
        unit = self._unit_path()
        try:
            unit.parent.mkdir(parents=True, exist_ok=True)
            unit.write_text(_UNIT_TEMPLATE.format(exec_path=exec_path, uid=os.getuid()))
        except OSError as e:
            return False, f"Could not write {unit}: {e}"

        ok, msg = self._systemctl("daemon-reload")
        if not ok:
            return False, msg
        ok, msg = self._systemctl("enable", "--now", self._UNIT_NAME)
        if not ok:
            return False, f"Unit written to {unit}, but enabling it failed: {msg}"

        msg = f"Installed and started {unit}"
        if not self.check_ready()[0]:
            msg += "\n\nWARNING: ydotool is not installed — Voxtty cannot type without it."
        for problem in self._preflight():
            msg += f"\n\nWARNING: {problem}"
        return True, msg

    def uninstall_service(self) -> tuple[bool, str]:
        unit = self._unit_path()
        self._systemctl("disable", "--now", self._UNIT_NAME)
        try:
            unit.unlink(missing_ok=True)
        except OSError as e:
            return False, f"Could not remove {unit}: {e}"
        self._systemctl("daemon-reload")
        return True, f"Removed {unit}"

    # ── Notifications ────────────────────────────────────────────────────────

    def notify(self, summary: str, body: str = "") -> None:
        try:
            subprocess.run(
                ["notify-send", "-a", "Voxtty", "-t", "2000", summary, body],
                capture_output=True, timeout=2,
            )
        except Exception:
            pass

    # ── Typing ───────────────────────────────────────────────────────────────

    def type_text(self, text: str) -> None:
        if not text:
            return
        try:
            subprocess.run(
                ["ydotool", "type", "--key-delay", str(self.key_delay_ms), "--", text],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            log.error(f"ydotool type failed: {e}")
        except FileNotFoundError:
            log.error("ydotool not found — run setup.sh first.")

    # ── Keyboard ─────────────────────────────────────────────────────────────

    def _find_keyboards(self) -> list[evdev.InputDevice]:
        skip = ("ydotool", "RustDesk")
        keyboards = []
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if any(s in dev.name for s in skip):
                continue
            caps = dev.capabilities()
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                if ecodes.KEY_D in keys and ecodes.KEY_LEFTALT in keys:
                    keyboards.append(dev)
        return keyboards

    def run_hotkey_listener(
        self, on_toggle: Callable[[], None], should_stop: Callable[[], bool]
    ) -> None:
        sel = selectors.DefaultSelector()
        registered: dict[str, evdev.InputDevice] = {}

        def refresh_devices() -> None:
            """(Re)scan for keyboards and register any not already watched.

            Wireless receivers drop out on power-save and come back with the
            same path, so we poll periodically to recover them. A dead device
            is dropped in the read loop below; this re-adds it once it returns.
            """
            try:
                found = {kb.path: kb for kb in self._find_keyboards()}
            except Exception as e:
                log.warning(f"Keyboard scan failed: {e}")
                return
            for path, kb in found.items():
                if path in registered:
                    kb.close()  # already watching this one
                    continue
                try:
                    sel.register(kb, selectors.EVENT_READ)
                    registered[path] = kb
                    log.info(f"Keyboard: {kb.name}")
                except Exception as e:
                    log.warning(f"Could not watch {kb.name}: {e}")
                    kb.close()

        def drop_device(kb: evdev.InputDevice) -> None:
            try:
                sel.unregister(kb)
            except Exception:
                pass
            registered.pop(kb.path, None)
            try:
                kb.close()
            except Exception:
                pass
            # The key-up never arrives for a device that vanished mid-chord,
            # so a held Alt would latch on and make bare 'D' a hotkey.
            self._alt_pressed = False

        refresh_devices()
        if not registered:
            log.error("No keyboard devices found — check 'input' group membership.")
            return

        last_scan = time.monotonic()
        try:
            while not should_stop():
                try:
                    # Periodically re-scan so reconnected keyboards come back.
                    if time.monotonic() - last_scan > 5.0:
                        refresh_devices()
                        last_scan = time.monotonic()

                    for key, _ in sel.select(timeout=1.0):
                        kb = key.fileobj
                        try:
                            events = kb.read()
                        except OSError as e:
                            # A single device vanished (Errno 19). Drop it and
                            # keep the loop alive for the other keyboards.
                            log.warning(f"Keyboard '{kb.name}' lost ({e}); will retry.")
                            drop_device(kb)
                            continue
                        for event in events:
                            if event.type != ecodes.EV_KEY:
                                continue
                            ke = evdev.categorize(event)
                            if ke.scancode in (ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT):
                                # Autorepeat emits key_hold while Alt stays down,
                                # so only key_up may clear this. Devices send hold
                                # events even when they report no EV_REP.
                                self._alt_pressed = ke.keystate != ke.key_up
                            elif ke.scancode == ecodes.KEY_D and ke.keystate == ke.key_down:
                                if self._alt_pressed:
                                    threading.Thread(target=on_toggle, daemon=True).start()
                except OSError as e:
                    # Any other device-churn error — a rescan opening a device
                    # that's mid-removal, or epoll itself faulting on a fd pulled
                    # out from under select() — must not kill the listener (this
                    # is what died at the ENODEV crash). Purge everything and
                    # rescan; the live keyboards re-register, dead ones stay out
                    # until they reconnect. An empty selector waits out its
                    # timeout without erroring, so this never busy-loops.
                    log.warning(f"Keyboard listener recovered from {e}; rescanning.")
                    for kb in list(registered.values()):
                        drop_device(kb)
                    last_scan = 0.0
        except Exception as e:
            log.error(f"Keyboard listener error: {e}", exc_info=True)
        finally:
            for kb in list(registered.values()):
                drop_device(kb)
            sel.close()
