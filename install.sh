#!/usr/bin/env bash
set -euo pipefail

AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/linux-audio-switcher.desktop"
LAS_BIN="$HOME/.local/bin/las"

echo "=== Linux Audio Switcher ==="
echo ""

# ── Detect system type ────────────────────────────────────────────────────────
# /run/ostree-booted is set by the kernel on any ostree-based system
# (Bazzite, Fedora Silverblue, Kinoite, Aurora, etc.)
IMMUTABLE=false
[ -f /run/ostree-booted ] && IMMUTABLE=true

if [ "$IMMUTABLE" = true ]; then
    echo "Detected: immutable / ostree system"
fi

# ── Stop any running daemon ───────────────────────────────────────────────────
if pgrep -f "las daemon" > /dev/null 2>&1; then
    pkill -f "las daemon" && echo "Stopped running daemon."
fi

# ── Install Python package ────────────────────────────────────────────────────
echo "Installing..."

INSTALL_METHOD=""

if command -v pipx > /dev/null 2>&1; then
    # pipx: preferred on all systems, required on immutable
    if pipx list 2>/dev/null | grep -q "linux-audio-switcher"; then
        pipx upgrade linux-audio-switcher --quiet
    else
        pipx install . --quiet
    fi
    echo "  → $LAS_BIN (via pipx)"
    INSTALL_METHOD=pipx

elif [ "$IMMUTABLE" = true ]; then
    echo ""
    echo "ERROR: This is an immutable system and pipx was not found."
    echo ""
    echo "Install pipx first, then re-run this script:"
    echo ""
    echo "  pip install --user pipx --break-system-packages"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "  source ~/.bashrc"
    echo "  bash install.sh"
    echo ""
    exit 1

else
    pip install --user --break-system-packages --quiet .
    echo "  → $LAS_BIN (via pip)"
    INSTALL_METHOD=pip
fi

# ── Install pystray if XApp.StatusIcon is not available ──────────────────────
# XApp is pre-installed on Cinnamon / Linux Mint.
# On other desktops (KDE, GNOME, Bazzite, etc.) pystray is the tray backend.
XAPP_OK=false
if python3 -c "
import gi
gi.require_version('XApp', '1.0')
from gi.repository import XApp
" 2>/dev/null; then
    XAPP_OK=true
fi

if [ "$XAPP_OK" = false ]; then
    echo "Installing tray backend (pystray — XApp not available on this desktop)..."
    if [ "$INSTALL_METHOD" = pipx ]; then
        pipx inject linux-audio-switcher "pystray>=0.19" "Pillow>=10.0" --quiet
    else
        pip install --user --break-system-packages --quiet "pystray>=0.19" "Pillow>=10.0"
    fi
    echo "  → pystray installed"

    # On GNOME, pystray icons are invisible without the AppIndicator extension.
    GNOME_DETECTED=false
    echo "${XDG_CURRENT_DESKTOP:-}" | grep -qi "gnome" && GNOME_DETECTED=true

    if [ "$GNOME_DETECTED" = true ]; then
        APPINDICATOR_OK=false
        if command -v gnome-extensions > /dev/null 2>&1; then
            if gnome-extensions list --enabled 2>/dev/null \
                | grep -qi "appindicator\|ubuntu-appindicator\|KStatusNotifierItem"; then
                APPINDICATOR_OK=true
            fi
        fi
        if [ "$APPINDICATOR_OK" = false ]; then
            echo ""
            echo "  NOTE: GNOME detected — the tray icon needs the AppIndicator extension"
            echo "  to be visible. Install it from:"
            echo "  https://extensions.gnome.org/extension/615/appindicator-support/"
            echo ""
            echo "  The las hotkey commands (las next-output / las next-input) work"
            echo "  without the extension."
        fi
    fi
fi

# ── Autostart .desktop file ───────────────────────────────────────────────────
echo "Setting up autostart..."
mkdir -p "$AUTOSTART_DIR"
# Resolved binary path ensures the file works regardless of login-shell PATH
cat > "$DESKTOP_FILE" <<DESKTOPEOF
[Desktop Entry]
Type=Application
Name=Linux Audio Switcher
Comment=Audio device carousel — cycles output/input devices via hotkey
Exec=$LAS_BIN daemon
Icon=audio-volume-high
Terminal=false
Categories=AudioVideo;
X-GNOME-Autostart-enabled=true
DESKTOPEOF
echo "  → $DESKTOP_FILE"

# ── Start daemon now (no re-login needed) ────────────────────────────────────
echo "Starting daemon..."
setsid "$LAS_BIN" daemon > /dev/null 2>&1 &
disown
sleep 0.8
if pgrep -f "las daemon" > /dev/null 2>&1; then
    echo "  → running (PID $(pgrep -f 'las daemon' | head -1))"
else
    echo "  → WARNING: daemon did not start. Try: $LAS_BIN daemon"
fi

# ── Hotkey setup reminder ─────────────────────────────────────────────────────
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
