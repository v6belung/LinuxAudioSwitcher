from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


@dataclass
class AudioDevice:
    index: int
    name: str
    description: str

    def __str__(self) -> str:
        return self.description


class AudioError(Exception):
    pass


def _pactl(*args: str) -> str:
    try:
        result = subprocess.run(
            ["pactl", *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise AudioError(f"pactl {' '.join(args)} failed: {e.stderr.strip()}") from e
    except FileNotFoundError:
        raise AudioError("pactl not found — is PulseAudio or PipeWire installed?")


def detect_backend() -> str:
    """Return 'pipewire' or 'pulseaudio'."""
    info = _pactl("info")
    return "pipewire" if "PipeWire" in info else "pulseaudio"


def _parse_device_blocks(output: str) -> list[dict[str, str]]:
    """
    Parse pactl list sinks/sources output.
    Each block starts with 'Sink #N' or 'Source #N'.
    Only captures top-level properties (single tab indent).
    """
    devices: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in output.splitlines():
        header = re.match(r'^(?:Sink|Source) #(\d+)', line)
        if header:
            if current is not None:
                devices.append(current)
            current = {"_index": header.group(1)}
            continue

        if current is not None and re.match(r'^\t[^\t]', line) and ': ' in line:
            key, _, value = line.strip().partition(': ')
            current[key] = value

    if current is not None:
        devices.append(current)

    return devices


def list_sinks() -> list[AudioDevice]:
    raw = _pactl("list", "sinks")
    return [
        AudioDevice(
            index=int(d["_index"]),
            name=d.get("Name", ""),
            description=d.get("Description", d.get("Name", "")),
        )
        for d in _parse_device_blocks(raw)
    ]


def list_sources() -> list[AudioDevice]:
    """List real input sources, excluding monitor loopbacks."""
    raw = _pactl("list", "sources")
    return [
        AudioDevice(
            index=int(d["_index"]),
            name=d.get("Name", ""),
            description=d.get("Description", d.get("Name", "")),
        )
        for d in _parse_device_blocks(raw)
        if not d.get("Name", "").endswith(".monitor")
    ]


def get_default_sink() -> str:
    info = _pactl("info")
    m = re.search(r'^Default Sink: (.+)$', info, re.MULTILINE)
    return m.group(1).strip() if m else ""


def get_default_source() -> str:
    info = _pactl("info")
    m = re.search(r'^Default Source: (.+)$', info, re.MULTILINE)
    return m.group(1).strip() if m else ""


def set_default_sink(name: str) -> None:
    _pactl("set-default-sink", name)
    _move_all_sink_inputs(name)


def set_default_source(name: str) -> None:
    _pactl("set-default-source", name)
    _move_all_source_outputs(name)


def _move_all_sink_inputs(sink_name: str) -> None:
    """Move all active playback streams to the new sink."""
    raw = _pactl("list", "sink-inputs", "short")
    for line in raw.splitlines():
        parts = line.split()
        if parts:
            try:
                _pactl("move-sink-input", parts[0], sink_name)
            except AudioError:
                pass  # stream may have ended between list and move


def _move_all_source_outputs(source_name: str) -> None:
    """Move all active recording streams to the new source."""
    raw = _pactl("list", "source-outputs", "short")
    for line in raw.splitlines():
        parts = line.split()
        if parts:
            try:
                _pactl("move-source-output", parts[0], source_name)
            except AudioError:
                pass
