#!/usr/bin/env bash
set -euo pipefail

AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/linux-audio-switcher.desktop"
LAS_BIN="$HOME/.local/bin/las"

echo "=== Linux Audio Switcher ==="
echo ""

# ── Stop any running daemon ─────────────────────────────────────────────────
if pgrep -f "las daemon" > /dev/null 2>&1; then
    pkill -f "las daemon" && echo "Stopped running daemon."
fi

# ── Install Python package ──────────────────────────────────────────────────
echo "Installing..."
pip install --user --break-system-packages --quiet .
echo "  → $LAS_BIN"

# ── Autostart .desktop file ─────────────────────────────────────────────────
echo "Setting up autostart..."
mkdir -p "$AUTOSTART_DIR"
# Write with the resolved binary path so it works regardless of PATH at login
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Linux Audio Switcher
Comment=Audio device carousel — cycles output/input devices via hotkey
Exec=$LAS_BIN daemon
Icon=audio-volume-high
Terminal=false
Categories=AudioVideo;
X-GNOME-Autostart-enabled=true
EOF
echo "  → $DESKTOP_FILE"

# ── Start daemon now (no re-login needed) ──────────────────────────────────
echo "Starting daemon..."
setsid "$LAS_BIN" daemon > /dev/null 2>&1 &
disown
sleep 0.8
if pgrep -f "las daemon" > /dev/null 2>&1; then
    echo "  → running (PID $(pgrep -f 'las daemon' | head -1))"
else
    echo "  → WARNING: daemon did not start. Try: $LAS_BIN daemon"
fi

# ── Hotkey setup reminder ───────────────────────────────────────────────────
echo ""
echo "Set up keyboard shortcuts to cycle devices:"
echo ""
echo "  Cinnamon:  System Settings → Keyboard → Shortcuts → Custom Shortcuts"
echo "  GNOME:     Settings → Keyboard → Custom Shortcuts"
echo "  KDE:       System Settings → Shortcuts → Custom Shortcuts"
echo ""
echo "  Command: $LAS_BIN next-output   (e.g. bind to Ctrl+F9)"
echo "  Command: $LAS_BIN next-input    (e.g. bind to Ctrl+F10)"
echo ""
echo "Done. Look for the speaker icon in your panel."
