#!/usr/bin/env python3
"""
Dictation App for Ubuntu Linux
Press Alt+D to toggle dictation on/off.
Speaks into microphone, transcribes with faster-whisper, types into focused app.
"""

import subprocess
import threading
import queue
import sys
import os
import numpy as np
import evdev
from evdev import ecodes
import pyaudio
import webrtcvad
from faster_whisper import WhisperModel

# Set ydotool socket path for Wayland
if not os.environ.get('YDOTOOL_SOCKET'):
    os.environ['YDOTOOL_SOCKET'] = f"/run/user/{os.getuid()}/.ydotool_socket"

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION_MS = 30  # 30ms chunks for VAD
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
FORMAT = pyaudio.paInt16
SILENCE_THRESHOLD = 1.5  # seconds of silence before sending


class DictationApp:
    def __init__(self):
        self.recording = False
        self.lock = threading.Lock()
        self.shutdown_flag = False
        self.record_thread = None
        self.word_count = 0

        # Hotkey state
        self.alt_pressed = False
        self.keyboard_device = None

        # Audio
        self.audio = None
        self.stream = None
        self.vad = webrtcvad.Vad(2)  # Aggressiveness 0-3, 2 is balanced

        # Typing queue — ensures text is pasted sequentially
        self.text_queue = queue.Queue()
        self.type_thread = threading.Thread(target=self._type_loop, daemon=True)
        self.type_thread.start()

        # Whisper model
        print("[INFO] Loading Whisper model (first run downloads ~1GB)...")
        self.whisper = WhisperModel("base.en", device="cpu", compute_type="int8")
        print("[INFO] Model loaded.")

    def _type_loop(self):
        """Dedicated thread that types text sequentially from the queue."""
        while True:
            text = self.text_queue.get()
            if text is None:
                break
            self._do_type(text)

    def _do_type(self, text: str) -> bool:
        """Type text using ydotool with --key-delay 0 for fast output."""
        if not text:
            return True
        try:
            subprocess.run(
                ["ydotool", "type", "--key-delay", "0", "--", text],
                check=True, capture_output=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to type: {e}")
            return False
        except FileNotFoundError:
            print("[ERROR] ydotool not found. Run setup.sh first.")
            return False

    def type_text(self, text: str) -> bool:
        """Queue text for typing. Returns True immediately."""
        if not text:
            return True
        self.text_queue.put(text)
        return True

    def on_recording_start(self):
        """Called when recording starts."""
        print("\n[DICTATING] Speak now... (Alt+D to stop)")

    def on_recording_stop(self):
        """Called when recording stops."""
        pass

    def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio using faster-whisper locally."""
        try:
            # Convert raw bytes to float32 numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            segments, _ = self.whisper.transcribe(audio_np, language="en", beam_size=1)
            text = " ".join(seg.text.strip() for seg in segments)
            return text.strip()
        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}")
            return ""

    def start_recording(self):
        """Start streaming dictation."""
        with self.lock:
            if self.recording:
                return
            self.recording = True
            self.shutdown_flag = False

        self.word_count = 0

        # Initialize audio
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
        except Exception as e:
            print(f"[ERROR] Failed to initialize audio: {e}")
            with self.lock:
                self.recording = False
            return

        self.on_recording_start()

        # Start recording in background thread
        self.record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.record_thread.start()

    def _record_loop(self):
        """Recording loop that runs in background thread."""
        try:
            audio_buffer = []
            silence_chunks = 0
            speech_detected = False
            chunks_per_second = 1000 // CHUNK_DURATION_MS
            silence_chunks_threshold = int(SILENCE_THRESHOLD * chunks_per_second)

            while self.recording:
                try:
                    chunk = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                except Exception as e:
                    print(f"[ERROR] Audio read error: {e}")
                    break

                # Check if chunk contains speech
                is_speech = self.vad.is_speech(chunk, SAMPLE_RATE)

                if is_speech:
                    audio_buffer.append(chunk)
                    silence_chunks = 0
                    speech_detected = True
                elif speech_detected:
                    audio_buffer.append(chunk)
                    silence_chunks += 1

                    # If enough silence after speech, transcribe
                    if silence_chunks >= silence_chunks_threshold:
                        if audio_buffer and self.recording:
                            audio_data = b''.join(audio_buffer)
                            text = self.transcribe_audio(audio_data)
                            if text:
                                self.type_text(text + " ")
                                self.word_count += len(text.split())
                                print(f"[TRANSCRIBED] {text}")

                        # Reset for next utterance
                        audio_buffer = []
                        silence_chunks = 0
                        speech_detected = False

        except Exception as e:
            print(f"[ERROR] Recording error: {e}")
        finally:
            self._shutdown_audio()

    def _shutdown_audio(self):
        """Safely shutdown audio resources."""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.audio:
            try:
                self.audio.terminate()
            except Exception:
                pass
            self.audio = None

    def stop_recording(self):
        """Stop streaming dictation."""
        with self.lock:
            if not self.recording:
                return
            self.recording = False

        print(f"[DONE] Typed {self.word_count} words")

        # Wait for record thread to finish
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=5.0)
            if self.record_thread.is_alive():
                print("[WARN] Record thread did not stop in time")

    def toggle_recording(self):
        """Toggle recording on/off."""
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def find_keyboard_devices(self):
        """Find all keyboard devices from /dev/input/."""
        keyboards = []
        # Skip virtual/daemon devices to avoid feedback loops
        skip = ("ydotool", "RustDesk")
        for path in evdev.list_devices():
            device = evdev.InputDevice(path)
            if any(s in device.name for s in skip):
                continue
            capabilities = device.capabilities()
            if ecodes.EV_KEY in capabilities:
                keys = capabilities[ecodes.EV_KEY]
                if ecodes.KEY_D in keys and ecodes.KEY_LEFTALT in keys:
                    keyboards.append(device)
        return keyboards

    def keyboard_listener(self):
        """Listen for keyboard events on all keyboards using evdev."""
        import selectors

        keyboards = self.find_keyboard_devices()
        if not keyboards:
            print("[ERROR] No keyboard devices found. Make sure you're in the 'input' group.")
            return

        for kb in keyboards:
            print(f"[INFO] Listening on keyboard: {kb.name}")

        sel = selectors.DefaultSelector()
        for kb in keyboards:
            sel.register(kb, selectors.EVENT_READ)

        try:
            while True:
                for key, mask in sel.select():
                    device = key.fileobj
                    for event in device.read():
                        if event.type == ecodes.EV_KEY:
                            key_event = evdev.categorize(event)

                            # Track Alt key state
                            if key_event.scancode in (ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT):
                                if key_event.keystate == key_event.key_down:
                                    self.alt_pressed = True
                                elif key_event.keystate == key_event.key_up:
                                    self.alt_pressed = False

                            # Check for D key press while Alt is held
                            elif key_event.scancode == ecodes.KEY_D:
                                if key_event.keystate == key_event.key_down and self.alt_pressed:
                                    threading.Thread(target=self.toggle_recording).start()
        except Exception as e:
            print(f"[ERROR] Keyboard listener error: {e}")

    def check_ydotool(self) -> bool:
        """Check if ydotool is available and working."""
        try:
            subprocess.run(
                ["ydotool", "--help"],
                check=True, capture_output=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def run(self):
        """Run the dictation app."""
        print("=" * 50)
        print("       DICTATION APP FOR UBUNTU")
        print("       (faster-whisper)")
        print("=" * 50)
        print()

        # Check ydotool
        if not self.check_ydotool():
            print("[ERROR] ydotool not available.")
            print("Make sure ydotoold is running and you're in the 'input' group.")
            print("Run: sudo ydotoold &")
            sys.exit(1)

        print("Ready! Press Alt+D to toggle dictation.")
        print("Press Ctrl+C to exit.")
        print()

        # Start keyboard listener using evdev (works on Wayland)
        try:
            self.keyboard_listener()
        except KeyboardInterrupt:
            print("\nExiting...")
            with self.lock:
                self.recording = False
            self._shutdown_audio()
            if self.record_thread and self.record_thread.is_alive():
                self.record_thread.join(timeout=5.0)


def main():
    app = DictationApp()
    app.run()


if __name__ == "__main__":
    main()
