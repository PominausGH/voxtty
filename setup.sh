#!/bin/bash
set -e

echo "=== Voxtty Setup ==="

# Install system dependencies
echo "[1/6] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    ydotool \
    portaudio19-dev \
    python3-venv \
    python3-pip \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    libnotify-bin

# Enable and start ydotoold service (needed for Wayland)
echo "[2/6] Setting up ydotool daemon..."
sudo systemctl enable ydotoold
sudo systemctl start ydotoold

# Add user to input group (needed for keyboard listener)
echo "[3/6] Adding user to input group..."
sudo usermod -aG input "$USER"

# Create Python virtual environment with system site-packages (needed for python3-gi)
echo "[4/6] Creating Python virtual environment..."
cd "$(dirname "$0")"
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create config dir + API key template (for optional AI cleanup)
echo "[5/6] Setting up AI cleanup config directory..."
mkdir -p ~/.config/voxtty
if [ ! -f ~/.config/voxtty/env ]; then
    cat > ~/.config/voxtty/env <<'EOF'
# Optional: enables the AI cleanup pass (set cleanup_enabled=true in config.json).
# Paste your Anthropic API key after the = sign, then restart the service.
ANTHROPIC_API_KEY=
EOF
    chmod 600 ~/.config/voxtty/env
    echo "  Created ~/.config/voxtty/env (add your API key there to enable AI cleanup)."
fi

# Install and enable systemd user service
echo "[6/6] Installing systemd user service..."
mkdir -p ~/.config/systemd/user
INSTALL_DIR="$(pwd)"
sed -e "s|__VOXTTY_INSTALL_DIR__|$INSTALL_DIR|g" \
    -e "s|__VOXTTY_UID__|$(id -u)|g" \
    voxtty.service > ~/.config/systemd/user/voxtty.service
systemctl --user daemon-reload
systemctl --user enable voxtty.service
systemctl --user start voxtty.service

echo ""
echo "=== Setup Complete ==="
echo ""
echo "IMPORTANT: Log out and back in for group changes to take effect."
echo ""
echo "Service management:"
echo "  systemctl --user status voxtty   # check status"
echo "  systemctl --user restart voxtty  # restart"
echo "  systemctl --user stop voxtty     # stop"
echo "  journalctl --user -u voxtty -f   # live logs"
echo ""
echo "Logs also saved to: ~/.local/share/voxtty/voxtty.log"
echo ""
echo "Press Alt+D to toggle dictation on/off."
