# Voxtty

Voice dictation for Ubuntu Linux with real-time streaming transcription.

Press **Ctrl+Shift+D** to start dictating. Words appear as you speak, not after you stop.

## Features

- **Streaming transcription** - See words appear in real-time as you speak
- **Works anywhere** - Types into any focused application
- **Local processing** - Uses Whisper AI model, no cloud required
- **Smart corrections** - Handles transcription updates with minimal disruption

## Requirements

- Ubuntu Linux (tested on 22.04+)
- Python 3.10+
- `ydotool` for typing into applications
- `portaudio` for audio capture

## Installation

```bash
# Install system dependencies
sudo apt-get install portaudio19-dev ydotool

# Start ydotool daemon (required for typing)
sudo ydotoold &

# Add yourself to input group (logout/login required)
sudo usermod -aG input $USER

# Clone and setup
git clone https://github.com/PominausGH/dictation-app.git
cd dictation-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
source venv/bin/activate
python voxtty.py
```

1. Press **Ctrl+Shift+D** to start dictating
2. Speak into your microphone
3. Watch words appear in the focused application
4. Press **Ctrl+Shift+D** again to stop
5. Press **Ctrl+C** to exit the app

## How It Works

Uses [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) for streaming Whisper transcription. As you speak, the transcription updates continuously. A `TextDiffer` component calculates the minimal corrections needed (backspaces + new text) to update what's been typed.

## Configuration

Edit `voxtty.py` to adjust:

- `model="tiny"` - Whisper model size (tiny/base/small/medium/large)
- `realtime_processing_pause=0.1` - Update frequency in seconds
- `max_backspaces=20` - Maximum corrections before skipping

## License

MIT
