# Linux Audio Switcher

Cycles through a configurable list of audio output and input devices using keyboard shortcuts. Inspired by [SoundSwitch](https://soundswitch.aaflalo.me/) on Windows.

## Features

- Two independent device carousels — one for **output** (playback), one for **input** (recording)
- Works on **PipeWire** and **PulseAudio** (auto-detected)
- Skips unavailable devices (e.g. disconnected Bluetooth) automatically
- **System tray icon** showing the active device with a menu to configure the carousel
- **Desktop notifications** on every switch
- Hotkey integration via your DE's own shortcut system — works on Cinnamon, GNOME, KDE, and anything else
- Config file at `~/.config/linux-audio-switcher/config.toml` — bootstrapped automatically on first run

## Installation

```bash
git clone https://github.com/v6belung/LinuxAudioSwitcher.git
cd LinuxAudioSwitcher
bash install.sh
```

The script:
1. Stops any running daemon
2. Installs the `las` command to `~/.local/bin/`
3. Drops an autostart entry so the tray icon starts with your desktop session
4. Launches the daemon immediately — no re-login needed

## Keyboard shortcuts

After installing, bind two shortcuts in your DE's keyboard settings:

| Action | Command | Suggested key |
|--------|---------|---------------|
| Next output device | `las next-output` | `Ctrl+F9` |
| Next input device | `las next-input` | `Ctrl+F10` |

**Cinnamon:** System Settings → Keyboard → Shortcuts → Custom Shortcuts  
**GNOME:** Settings → Keyboard → Custom Shortcuts  
**KDE:** System Settings → Shortcuts → Custom Shortcuts

## Tray icon

Click the speaker icon in the panel to open the menu:

- **Checkbox** next to a device — toggles whether it is included in the carousel (fires a notification confirming the change)
- **Device name** — immediately switches to that device
- **Next Output / Next Input** — same as the hotkey
- Active device shown in **bold** with a `▶` prefix
- Tooltip shows the current output and input device names

**Desktop support:** The tray uses `XApp.StatusIcon` natively on Cinnamon / Linux Mint. On other desktops install `pystray` (`pip install pystray`) for a compatible fallback — on GNOME you also need the [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/).

## Configuration

`~/.config/linux-audio-switcher/config.toml` is created on first run with all detected devices. Edit it to reorder devices or remove ones you never want to cycle through.

```toml
[output]
devices = [
    "alsa_output.usb-Audioengine_Audioengine_2_-00.analog-stereo",
    "alsa_output.pci-0000_01_00.1.hdmi-stereo",
]

[input]
devices = [
    "alsa_input.usb-046d_0823_542194A0-00.analog-stereo",
]
```

Run `las list` to see device names for all currently detected devices.

## CLI reference

```
las list                            List all detected audio devices
las next-output                     Cycle to the next output device
las next-input                      Cycle to the next input device
las daemon                          Start the tray icon (autostart handles this after install)
las config                          Show current carousel configuration
las config add-output <device>      Add a device to the output carousel
las config remove-output <device>   Remove a device from the output carousel
las config add-input <device>       Add a device to the input carousel
las config remove-input <device>    Remove a device from the input carousel
```

Use `las list` to get the exact device names to pass to `las config add-*`.

## Requirements

- Linux with PipeWire or PulseAudio (`pactl`)
- Python 3.11+
- `gir1.2-xapp-1.0` and `gir1.2-gtk-3.0` (pre-installed on Linux Mint / Cinnamon)
- `notify-send` for desktop notifications (pre-installed on most distros)
