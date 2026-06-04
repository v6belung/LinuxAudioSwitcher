from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from linux_audio_switcher import audio


@dataclass
class Config:
    output_devices: list[str] = field(default_factory=list)
    input_devices: list[str] = field(default_factory=list)


def config_path() -> Path:
    return Path.home() / ".config" / "linux-audio-switcher" / "config.toml"


def load() -> Config:
    path = config_path()
    if not path.exists():
        return _bootstrap()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Config(
        output_devices=data.get("output", {}).get("devices", []),
        input_devices=data.get("input", {}).get("devices", []),
    )


def save(conf: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_toml(conf))


def _bootstrap() -> Config:
    """First run: populate config from all currently detected devices and save it."""
    sinks = audio.list_sinks()
    sources = audio.list_sources()
    conf = Config(
        output_devices=[s.name for s in sinks],
        input_devices=[s.name for s in sources],
    )
    save(conf)
    return conf


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _to_toml(conf: Config) -> str:
    def device_list(names: list[str]) -> str:
        if not names:
            return "[]"
        items = "\n".join(f'    "{_escape(n)}",' for n in names)
        return f"[\n{items}\n]"

    return (
        "[output]\n"
        f"devices = {device_list(conf.output_devices)}\n"
        "\n"
        "[input]\n"
        f"devices = {device_list(conf.input_devices)}\n"
    )
