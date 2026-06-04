from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

import pytest

from linux_audio_switcher import carousel
from linux_audio_switcher.audio import AudioDevice
from linux_audio_switcher.carousel import CarouselError
from linux_audio_switcher.config import Config

SINKS = [
    AudioDevice(60, "sink.usb", "USB Speaker"),
    AudioDevice(62, "sink.iec", "IEC958 Digital"),
    AudioDevice(80, "sink.hdmi", "HDMI Audio"),
]
SOURCES = [
    AudioDevice(61, "source.usb", "USB Mic"),
    AudioDevice(63, "source.pci", "Built-in Mic"),
]


class TestAdvanceOutput:
    def _run(self, conf, sinks, current):
        with ExitStack() as stack:
            stack.enter_context(patch("linux_audio_switcher.config.load", return_value=conf))
            stack.enter_context(patch("linux_audio_switcher.audio.list_sinks", return_value=sinks))
            stack.enter_context(patch("linux_audio_switcher.audio.get_default_sink", return_value=current))
            mock_set = stack.enter_context(patch("linux_audio_switcher.audio.set_default_sink"))
            device = carousel.advance_output()
        return device, mock_set

    def test_advances_to_next(self):
        conf = Config(output_devices=["sink.usb", "sink.iec", "sink.hdmi"], input_devices=[])
        device, mock_set = self._run(conf, SINKS, "sink.usb")
        assert device.name == "sink.iec"
        mock_set.assert_called_once_with("sink.iec")

    def test_wraps_around(self):
        conf = Config(output_devices=["sink.usb", "sink.iec", "sink.hdmi"], input_devices=[])
        device, mock_set = self._run(conf, SINKS, "sink.hdmi")
        assert device.name == "sink.usb"

    def test_current_not_in_carousel_starts_from_first(self):
        conf = Config(output_devices=["sink.usb", "sink.iec"], input_devices=[])
        device, _ = self._run(conf, SINKS, "sink.hdmi")
        assert device.name == "sink.usb"

    def test_single_device_returns_same(self):
        conf = Config(output_devices=["sink.usb"], input_devices=[])
        device, mock_set = self._run(conf, SINKS, "sink.usb")
        assert device.name == "sink.usb"
        mock_set.assert_called_once_with("sink.usb")

    def test_skips_unavailable_device(self):
        conf = Config(output_devices=["sink.usb", "sink.bt", "sink.iec"], input_devices=[])
        # sink.bt not in SINKS (unavailable)
        device, _ = self._run(conf, SINKS, "sink.usb")
        assert device.name == "sink.iec"

    def test_raises_when_no_devices_configured(self):
        conf = Config(output_devices=[], input_devices=[])
        with ExitStack() as stack:
            stack.enter_context(patch("linux_audio_switcher.config.load", return_value=conf))
            stack.enter_context(patch("linux_audio_switcher.audio.list_sinks", return_value=SINKS))
            stack.enter_context(patch("linux_audio_switcher.audio.get_default_sink", return_value="sink.usb"))
            with pytest.raises(CarouselError, match="No output devices"):
                carousel.advance_output()

    def test_raises_when_all_unavailable(self):
        conf = Config(output_devices=["sink.bt1", "sink.bt2"], input_devices=[])
        with ExitStack() as stack:
            stack.enter_context(patch("linux_audio_switcher.config.load", return_value=conf))
            stack.enter_context(patch("linux_audio_switcher.audio.list_sinks", return_value=SINKS))
            stack.enter_context(patch("linux_audio_switcher.audio.get_default_sink", return_value="sink.usb"))
            with pytest.raises(CarouselError, match="currently available"):
                carousel.advance_output()

    def test_returns_device_with_description(self):
        conf = Config(output_devices=["sink.usb", "sink.iec"], input_devices=[])
        device, _ = self._run(conf, SINKS, "sink.usb")
        assert device.description == "IEC958 Digital"

    def test_returns_name_only_when_device_not_in_list(self):
        conf = Config(output_devices=["sink.usb", "sink.new"], input_devices=[])
        available_sinks = SINKS + [AudioDevice(99, "sink.new", "sink.new")]
        device, _ = self._run(conf, available_sinks, "sink.usb")
        assert device.name == "sink.new"


class TestAdvanceInput:
    def _run(self, conf, sources, current):
        with ExitStack() as stack:
            stack.enter_context(patch("linux_audio_switcher.config.load", return_value=conf))
            stack.enter_context(patch("linux_audio_switcher.audio.list_sources", return_value=sources))
            stack.enter_context(patch("linux_audio_switcher.audio.get_default_source", return_value=current))
            mock_set = stack.enter_context(patch("linux_audio_switcher.audio.set_default_source"))
            device = carousel.advance_input()
        return device, mock_set

    def test_advances_to_next(self):
        conf = Config(output_devices=[], input_devices=["source.usb", "source.pci"])
        device, mock_set = self._run(conf, SOURCES, "source.usb")
        assert device.name == "source.pci"
        mock_set.assert_called_once_with("source.pci")

    def test_wraps_around(self):
        conf = Config(output_devices=[], input_devices=["source.usb", "source.pci"])
        device, _ = self._run(conf, SOURCES, "source.pci")
        assert device.name == "source.usb"

    def test_raises_when_no_devices_configured(self):
        conf = Config(output_devices=[], input_devices=[])
        with ExitStack() as stack:
            stack.enter_context(patch("linux_audio_switcher.config.load", return_value=conf))
            stack.enter_context(patch("linux_audio_switcher.audio.list_sources", return_value=SOURCES))
            stack.enter_context(patch("linux_audio_switcher.audio.get_default_source", return_value="source.usb"))
            with pytest.raises(CarouselError, match="No input devices"):
                carousel.advance_input()


class TestNextAvailable:
    def test_basic_advance(self):
        assert carousel._next_available(["a", "b", "c"], {"a", "b", "c"}, "a") == "b"

    def test_skips_unavailable(self):
        assert carousel._next_available(["a", "b", "c"], {"a", "c"}, "a") == "c"

    def test_wraps(self):
        assert carousel._next_available(["a", "b", "c"], {"a", "b", "c"}, "c") == "a"

    def test_all_unavailable_returns_none(self):
        assert carousel._next_available(["a", "b"], set(), "a") is None

    def test_current_not_in_list(self):
        assert carousel._next_available(["a", "b", "c"], {"a", "b", "c"}, "x") == "a"
