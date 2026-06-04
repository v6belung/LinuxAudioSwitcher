from __future__ import annotations

from linux_audio_switcher import audio, config as cfg
from linux_audio_switcher.audio import AudioDevice


class CarouselError(Exception):
    pass


def advance_output() -> AudioDevice:
    """Switch to the next configured output device. Returns the new device."""
    conf = cfg.load()
    names = conf.output_devices
    if not names:
        raise CarouselError(
            "No output devices configured. Run 'las config' to set up your carousel."
        )

    all_sinks = audio.list_sinks()
    available = {s.name for s in all_sinks}
    current = audio.get_default_sink()

    next_name = _next_available(names, available, current)
    if next_name is None:
        raise CarouselError(
            "None of the configured output devices are currently available."
        )

    audio.set_default_sink(next_name)
    return _find_device(all_sinks, next_name)


def advance_input() -> AudioDevice:
    """Switch to the next configured input device. Returns the new device."""
    conf = cfg.load()
    names = conf.input_devices
    if not names:
        raise CarouselError(
            "No input devices configured. Run 'las config' to set up your carousel."
        )

    all_sources = audio.list_sources()
    available = {s.name for s in all_sources}
    current = audio.get_default_source()

    next_name = _next_available(names, available, current)
    if next_name is None:
        raise CarouselError(
            "None of the configured input devices are currently available."
        )

    audio.set_default_source(next_name)
    return _find_device(all_sources, next_name)


def _next_available(names: list[str], available: set[str], current: str) -> str | None:
    """
    Find the next name in `names` after `current` that is in `available`.
    Skips unavailable entries (e.g. disconnected Bluetooth).
    If current is not in names, starts from index 0.
    """
    try:
        start = names.index(current)
    except ValueError:
        start = -1

    for i in range(1, len(names) + 1):
        candidate = names[(start + i) % len(names)]
        if candidate in available:
            return candidate
    return None


def _find_device(devices: list[AudioDevice], name: str) -> AudioDevice:
    for d in devices:
        if d.name == name:
            return d
    return AudioDevice(index=-1, name=name, description=name)
