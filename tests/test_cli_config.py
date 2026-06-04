from __future__ import annotations

import sys
from contextlib import ExitStack
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from linux_audio_switcher.audio import AudioDevice
from linux_audio_switcher.cli import cmd_config
from linux_audio_switcher.config import Config

SINKS = [
    AudioDevice(60, "sink.usb", "USB Speaker"),
    AudioDevice(62, "sink.hdmi", "HDMI Audio"),
]
SOURCES = [
    AudioDevice(61, "source.usb", "USB Mic"),
    AudioDevice(63, "source.pci", "Built-in Mic"),
]


def _args(action=None, device=None):
    a = MagicMock()
    a.config_action = action
    a.device = device
    return a


def _run(action, device, conf_before):
    """
    Run cmd_config with the given action and device.
    Returns (saved_conf, stdout, exit_code).
    """
    saved = []
    stdout_capture = StringIO()

    def mock_save(c):
        saved.append(c)

    with ExitStack() as stack:
        stack.enter_context(patch("linux_audio_switcher.cli.cfg.load", return_value=conf_before))
        stack.enter_context(patch("linux_audio_switcher.cli.cfg.save", side_effect=mock_save))
        stack.enter_context(patch("linux_audio_switcher.cli.audio.list_sinks", return_value=SINKS))
        stack.enter_context(patch("linux_audio_switcher.cli.audio.list_sources", return_value=SOURCES))
        stack.enter_context(patch("sys.stdout", stdout_capture))

        try:
            cmd_config(_args(action, device))
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

    return saved[0] if saved else None, stdout_capture.getvalue(), exit_code


# ── add-output ────────────────────────────────────────────────────────────────

class TestAddOutput:
    def test_adds_known_device(self):
        conf = Config(output_devices=["sink.usb"], input_devices=[])
        saved, out, code = _run("add-output", "sink.hdmi", conf)
        assert code == 0
        assert saved.output_devices == ["sink.usb", "sink.hdmi"]

    def test_duplicate_is_noop(self):
        conf = Config(output_devices=["sink.usb"], input_devices=[])
        saved, out, code = _run("add-output", "sink.usb", conf)
        assert code == 0
        assert saved is None  # save was not called

    def test_unknown_device_warns_but_adds(self, capsys):
        conf = Config(output_devices=[], input_devices=[])
        saved, out, code = _run("add-output", "sink.bt", conf)
        assert code == 0
        assert saved is not None
        assert "sink.bt" in saved.output_devices

    def test_does_not_modify_input(self):
        conf = Config(output_devices=[], input_devices=["source.usb"])
        saved, out, code = _run("add-output", "sink.hdmi", conf)
        assert saved.input_devices == ["source.usb"]


# ── remove-output ─────────────────────────────────────────────────────────────

class TestRemoveOutput:
    def test_removes_existing_device(self):
        conf = Config(output_devices=["sink.usb", "sink.hdmi"], input_devices=[])
        saved, out, code = _run("remove-output", "sink.usb", conf)
        assert code == 0
        assert saved.output_devices == ["sink.hdmi"]

    def test_missing_device_exits_nonzero(self):
        conf = Config(output_devices=["sink.usb"], input_devices=[])
        saved, out, code = _run("remove-output", "sink.hdmi", conf)
        assert code != 0
        assert saved is None

    def test_does_not_modify_input(self):
        conf = Config(output_devices=["sink.usb", "sink.hdmi"], input_devices=["source.usb"])
        saved, out, code = _run("remove-output", "sink.hdmi", conf)
        assert saved.input_devices == ["source.usb"]


# ── add-input ─────────────────────────────────────────────────────────────────

class TestAddInput:
    def test_adds_known_device(self):
        conf = Config(output_devices=[], input_devices=["source.usb"])
        saved, out, code = _run("add-input", "source.pci", conf)
        assert code == 0
        assert saved.input_devices == ["source.usb", "source.pci"]

    def test_duplicate_is_noop(self):
        conf = Config(output_devices=[], input_devices=["source.usb"])
        saved, out, code = _run("add-input", "source.usb", conf)
        assert saved is None

    def test_does_not_modify_output(self):
        conf = Config(output_devices=["sink.usb"], input_devices=[])
        saved, out, code = _run("add-input", "source.pci", conf)
        assert saved.output_devices == ["sink.usb"]


# ── remove-input ──────────────────────────────────────────────────────────────

class TestRemoveInput:
    def test_removes_existing_device(self):
        conf = Config(output_devices=[], input_devices=["source.usb", "source.pci"])
        saved, out, code = _run("remove-input", "source.pci", conf)
        assert code == 0
        assert saved.input_devices == ["source.usb"]

    def test_missing_device_exits_nonzero(self):
        conf = Config(output_devices=[], input_devices=["source.usb"])
        saved, out, code = _run("remove-input", "source.pci", conf)
        assert code != 0
        assert saved is None


# ── show (no action) ──────────────────────────────────────────────────────────

class TestConfigShow:
    def test_prints_carousel_contents(self):
        conf = Config(
            output_devices=["sink.usb"],
            input_devices=["source.usb"],
        )
        _, out, code = _run(None, None, conf)
        assert code == 0
        assert "USB Speaker" in out
        assert "USB Mic" in out

    def test_empty_carousel_shows_hint(self):
        conf = Config(output_devices=[], input_devices=[])
        _, out, code = _run(None, None, conf)
        assert "add-output" in out
        assert "add-input" in out
