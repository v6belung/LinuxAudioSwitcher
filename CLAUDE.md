# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Linux Audio Switcher (`las`) — a CLI + system tray daemon that cycles through configurable lists
("carousels") of audio output and input devices on PipeWire/PulseAudio, for binding to keyboard
shortcuts (like SoundSwitch on Windows).

## Commands

```bash
# Run the full test suite
python3 -m pytest -q

# Run a single test file / class / test
python3 -m pytest tests/test_audio.py -q
python3 -m pytest tests/test_audio.py::TestGetDefaultsViaWpctl -q
python3 -m pytest tests/test_audio.py::TestGetDefaultsViaWpctl::test_wpctl_overrides_stale_pactl_info -q

# Install the editable package + dev deps (pytest)
pip install -e ".[dev]"

# Run the CLI / daemon directly without installing
python3 -m linux_audio_switcher list
python3 -m linux_audio_switcher daemon
```

There is no separate lint/build step; `pyproject.toml` only declares the `las` console script
(`linux_audio_switcher.cli:main`) and pytest config (`testpaths = ["tests"]`).

## Architecture

All logic lives in `linux_audio_switcher/`, with `cli.py` as the entry point dispatching to
`argparse` subcommands (`list`, `next-output`, `next-input`, `daemon`, `config ...`).

- **`audio.py`** — the only module that shells out to `pactl`/`wpctl`. Wraps all subprocess calls
  in `_pactl()`, raising `AudioError` on failure. Key functions: `list_sinks()` / `list_sources()`
  (sources exclude `*.monitor` entries), `get_default_sink()` / `get_default_source()`,
  `set_default_sink()` / `set_default_source()` (which also move active streams via
  `_move_all_sink_inputs` / `_move_all_source_outputs`).

  `get_default_sink/source` are intentionally layered: PipeWire's `pactl info` can report a
  placeholder (`@DEFAULT_SINK@`/`@DEFAULT_SOURCE@`) or a stale value even after
  `set-default-*` succeeds. So these functions first try `_wpctl_default()` (parses wpctl's
  "Default Configured Node Names" table, which reflects changes immediately), then fall back to
  parsing `pactl info`, then to `_fallback_default()` (picks a RUNNING device, or the first
  non-monitor device, from `pactl list sinks/sources`).

- **`config.py`** — loads/saves `~/.config/linux-audio-switcher/config.toml` (`[output].devices`
  and `[input].devices`, lists of `pactl` device names). On first run with no config file,
  `_bootstrap()` populates both lists from all currently detected devices. TOML is hand-written
  via `_to_toml()` (no writer dependency).

- **`carousel.py`** — `advance_output()` / `advance_input()` step to the next *available* device
  in the configured carousel after the current default, skipping devices not currently present
  (e.g. disconnected Bluetooth) via `_next_available()`. Raises `CarouselError` if the carousel is
  empty or no configured device is available.

- **`tray.py`** — GTK3/XApp system tray daemon (`run_daemon()`). Only active if `gi` +
  `XApp`/`Gtk`/`Gdk` 3.0 are importable (`_XAPP` flag); otherwise `run_daemon()` raises with an
  install hint. The tray menu is rebuilt fresh on every click (`_build_menu`), listing all sinks
  and sources with a checkbox (carousel membership) and a `▶`-prefixed bold label for the active
  device.

  `_device_item()` builds a custom `[checkbox] label` row inside a single `Gtk.MenuItem` — GTK
  menu popups grab the pointer, so child-widget signal handlers never fire. Instead, the
  `MenuItem`'s own `button-release-event` is checked via `_click_is_on_checkbox()`
  (screen-coordinate comparison against the checkbox's allocation, with extra hit-area padding):
  if the click was on the checkbox, it's toggled and the event is consumed (`return True`) so the
  menu stays open; otherwise the click falls through to `activate`, which switches the device and
  closes the menu as normal.

- **`notify.py`** — thin wrapper around `notify-send`; silently no-ops if it's not installed.

### Testing conventions

Tests mock `subprocess.run` directly (see `tests/test_audio.py`'s `_make_run()` helper and
canned `pactl`/`wpctl` output strings) rather than mocking `audio._pactl`. When adding
`get_default_sink/source` fallback paths, mock the call chain in order:
`wpctl status` → `pactl info` → `pactl list sinks/sources`.

`tests/test_tray.py` constructs real (unrealized) GTK widgets via `_device_item()` — this works
headless since GTK widgets don't need a display until `show()`/realize. Checkbox-vs-label click
behavior is tested by emitting `button-release-event`/`activate` signals with
`_click_is_on_checkbox` patched.
