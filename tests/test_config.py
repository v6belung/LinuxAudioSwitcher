from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from linux_audio_switcher import config
from linux_audio_switcher.audio import AudioDevice
from linux_audio_switcher.config import Config

MOCK_SINKS = [
    AudioDevice(60, "sink.usb", "USB Speaker"),
    AudioDevice(62, "sink.hdmi", "HDMI Audio"),
]
MOCK_SOURCES = [
    AudioDevice(61, "source.usb", "USB Mic"),
]

SAMPLE_TOML = (
    "[output]\n"
    'devices = [\n'
    '    "sink.usb",\n'
    '    "sink.hdmi",\n'
    "]\n"
    "\n"
    "[input]\n"
    'devices = [\n'
    '    "source.usb",\n'
    "]\n"
)


class TestLoadConfig:
    def test_load_from_existing_file(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text(SAMPLE_TOML)
        with patch("linux_audio_switcher.config.config_path", return_value=f):
            c = config.load()
        assert c.output_devices == ["sink.usb", "sink.hdmi"]
        assert c.input_devices == ["source.usb"]

    def test_bootstrap_when_no_file(self, tmp_path):
        f = tmp_path / "config.toml"
        with patch("linux_audio_switcher.config.config_path", return_value=f):
            with patch("linux_audio_switcher.audio.list_sinks", return_value=MOCK_SINKS):
                with patch("linux_audio_switcher.audio.list_sources", return_value=MOCK_SOURCES):
                    c = config.load()
        assert c.output_devices == ["sink.usb", "sink.hdmi"]
        assert c.input_devices == ["source.usb"]

    def test_bootstrap_saves_file(self, tmp_path):
        f = tmp_path / "config.toml"
        with patch("linux_audio_switcher.config.config_path", return_value=f):
            with patch("linux_audio_switcher.audio.list_sinks", return_value=MOCK_SINKS):
                with patch("linux_audio_switcher.audio.list_sources", return_value=MOCK_SOURCES):
                    config.load()
        assert f.exists()

    def test_empty_devices_section(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[output]\ndevices = []\n\n[input]\ndevices = []\n")
        with patch("linux_audio_switcher.config.config_path", return_value=f):
            c = config.load()
        assert c.output_devices == []
        assert c.input_devices == []


class TestSaveConfig:
    def test_creates_parent_directories(self, tmp_path):
        f = tmp_path / "subdir" / "config.toml"
        with patch("linux_audio_switcher.config.config_path", return_value=f):
            config.save(Config(output_devices=["sink.usb"], input_devices=[]))
        assert f.exists()

    def test_roundtrip(self, tmp_path):
        f = tmp_path / "config.toml"
        original = Config(output_devices=["sink.usb", "sink.hdmi"], input_devices=["source.usb"])
        with patch("linux_audio_switcher.config.config_path", return_value=f):
            config.save(original)
            loaded = config.load()
        assert loaded.output_devices == original.output_devices
        assert loaded.input_devices == original.input_devices

    def test_toml_output_format(self):
        c = Config(output_devices=["sink.usb", "sink.hdmi"], input_devices=["source.usb"])
        assert config._to_toml(c) == SAMPLE_TOML

    def test_empty_list_inline(self):
        c = Config(output_devices=[], input_devices=[])
        toml = config._to_toml(c)
        assert "devices = []" in toml

    def test_escapes_special_characters(self):
        c = Config(output_devices=['sink.with"quote'], input_devices=[])
        toml = config._to_toml(c)
        assert '\\"' in toml
