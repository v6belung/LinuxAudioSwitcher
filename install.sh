#!/usr/bin/env bash
set -euo pipefail

AUTOSTART_DIR="$HOME/.config/autostart"
SYSTEMD_DIR="$HOME/.config/systemd/user"
BIN="$HOME/.local/bin/las"

# ── Install Python package ──────────────────────────────────────────────────
echo "Installing linux-audio-switcher..."
pip install --user --break-system-packages --quiet .
echo "  → $BIN"

# ── Check PATH ──────────────────────────────────────────────────────────────
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/.local/bin"; then
    echo ""
    echo "  WARNING: $HOME/.local/bin is not in your PATH."
    echo "  Add this to your ~/.bashrc or ~/.profile:"
    echo '    export PATH="$HOME/.local/bin:$PATH"'
fi

# ── Autostart method ────────────────────────────────────────────────────────
echo ""
echo "How should the tray daemon start on login?"
echo "  1) XDG autostart  (works on Cinnamon, GNOME, KDE — recommended)"
echo "  2) systemd user service"
echo "  3) Skip (I'll start it manually with 'las daemon')"
read -rp "Choice [1/2/3]: " choice

case "$choice" in
1)
    mkdir -p "$AUTOSTART_DIR"
    cp linux-audio-switcher.desktop "$AUTOSTART_DIR/"
    echo "  → $AUTOSTART_DIR/linux-audio-switcher.desktop"
    echo "  Daemon will start automatically at next login."
    ;;
2)
    mkdir -p "$SYSTEMD_DIR"
    cp linux-audio-switcher.service "$SYSTEMD_DIR/"
    systemctl --user daemon-reload
    systemctl --user enable linux-audio-switcher.service
    echo "  → $SYSTEMD_DIR/linux-audio-switcher.service (enabled)"
    echo "  Start now: systemctl --user start linux-audio-switcher"
    ;;
3)
    echo "  Skipped. Run 'las daemon &' to start the tray icon manually."
    ;;
*)
    echo "  Invalid choice — skipped autostart setup."
    ;;
esac

# ── Hotkey instructions ─────────────────────────────────────────────────────
echo ""
echo "Set up keyboard shortcuts to use the carousels:"
echo ""
echo "  Cinnamon:  System Settings → Keyboard → Shortcuts → Custom Shortcuts"
echo "  GNOME:     Settings → Keyboard → Custom Shortcuts"
echo "  KDE:       System Settings → Shortcuts → Custom Shortcuts"
echo ""
echo "  Add two shortcuts:"
echo "    las next-output   →  (your preferred key, e.g. Ctrl+F9)"
echo "    las next-input    →  (your preferred key, e.g. Ctrl+F10)"
echo ""
echo "Done. Test with: las list"
