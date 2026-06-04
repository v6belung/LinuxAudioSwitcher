from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from linux_audio_switcher import audio

PACTL_INFO = """\
Server String: /run/user/1000/pulse/native
Server Name: PulseAudio (on PipeWire 1.0.5)
Default Sink: alsa_output.usb-Audioengine-00.analog-stereo
Default Source: alsa_input.usb-046d_0823-00.analog-stereo
"""

PACTL_INFO_PLAIN_PA = """\
Server Name: PulseAudio
Default Sink: alsa_output.pci.analog-stereo
Default Source: alsa_input.pci.analog-stereo
"""

PACTL_LIST_SINKS = """\
Sink #60
\tState: SUSPENDED
\tName: alsa_output.usb-Audioengine-00.analog-stereo
\tDescription: Audioengine 2+ Analog Stereo
\tDriver: PipeWire

Sink #62
\tState: SUSPENDED
\tName: alsa_output.pci-0000_16_00.6.iec958-stereo
\tDescription: Built-in Audio Digital Stereo (IEC958)
\tDriver: PipeWire
"""

PACTL_LIST_SOURCES = """\
Source #60
\tState: SUSPENDED
\tName: alsa_output.usb-Audioengine-00.analog-stereo.monitor
\tDescription: Monitor of Audioengine 2+ Analog Stereo
\tDriver: PipeWire

Source #61
\tState: SUSPENDED
\tName: alsa_input.usb-046d_0823-00.analog-stereo
\tDescription: Logitech Webcam Microphone
\tDriver: PipeWire

Source #63
\tState: SUSPENDED
\tName: alsa_input.pci-0000_16_00.6.analog-stereo
\tDescription: Built-in Audio Analog Stereo
\tDriver: PipeWire
"""

PACTL_LIST_SINK_INPUTS_SHORT = """\
4\t60\t67\talsa_output.usb-Audioengine-00.analog-stereo\tfloat32le 2ch 48000Hz
5\t60\t68\talsa_output.usb-Audioengine-00.analog-stereo\tfloat32le 2ch 48000Hz
"""

PACTL_LIST_SOURCE_OUTPUTS_SHORT = """\
2\t61\t12\talsa_input.usb-046d_0823-00.analog-stereo\ts16le 2ch 32000Hz
"""


def _make_run(output: str):
    result = MagicMock()
    result.stdout = output
    result.returncode = 0
    return result


class TestDetectBackend:
    def test_pipewire(self):
        with patch("subprocess.run", return_value=_make_run(PACTL_INFO)):
            assert audio.detect_backend() == "pipewire"

    def test_pulseaudio(self):
        with patch("subprocess.run", return_value=_make_run(PACTL_INFO_PLAIN_PA)):
            assert audio.detect_backend() == "pulseaudio"


class TestListSinks:
    def test_returns_all_sinks(self):
        with patch("subprocess.run", return_value=_make_run(PACTL_LIST_SINKS)):
            sinks = audio.list_sinks()
        assert len(sinks) == 2

    def test_sink_fields(self):
        with patch("subprocess.run", return_value=_make_run(PACTL_LIST_SINKS)):
            sinks = audio.list_sinks()
        assert sinks[0].index == 60
        assert sinks[0].name == "alsa_output.usb-Audioengine-00.analog-stereo"
        assert sinks[0].description == "Audioengine 2+ Analog Stereo"

    def test_str_returns_description(self):
        with patch("subprocess.run", return_value=_make_run(PACTL_LIST_SINKS)):
            sinks = audio.list_sinks()
        assert str(sinks[0]) == "Audioengine 2+ Analog Stereo"


class TestListSources:
    def test_excludes_monitors(self):
        with patch("subprocess.run", return_value=_make_run(PACTL_LIST_SOURCES)):
            sources = audio.list_sources()
        assert len(sources) == 2
        assert all(not s.name.endswith(".monitor") for s in sources)

    def test_source_fields(self):
        with patch("subprocess.run", return_value=_make_run(PACTL_LIST_SOURCES)):
            sources = audio.list_sources()
        assert sources[0].name == "alsa_input.usb-046d_0823-00.analog-stereo"
        assert sources[0].description == "Logitech Webcam Microphone"


class TestGetDefaults:
    def test_get_default_sink(self):
        with patch("subprocess.run", return_value=_make_run(PACTL_INFO)):
            assert audio.get_default_sink() == "alsa_output.usb-Audioengine-00.analog-stereo"

    def test_get_default_source(self):
        with patch("subprocess.run", return_value=_make_run(PACTL_INFO)):
            assert audio.get_default_source() == "alsa_input.usb-046d_0823-00.analog-stereo"


class TestSetDefaults:
    def test_set_default_sink_calls_pactl(self):
        sink_inputs = _make_run(PACTL_LIST_SINK_INPUTS_SHORT)
        set_result = _make_run("")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [set_result, sink_inputs, set_result, set_result]
            audio.set_default_sink("alsa_output.pci-0000_16_00.6.iec958-stereo")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls[0] == ["pactl", "set-default-sink", "alsa_output.pci-0000_16_00.6.iec958-stereo"]

    def test_set_default_sink_moves_streams(self):
        sink_inputs = _make_run(PACTL_LIST_SINK_INPUTS_SHORT)
        set_result = _make_run("")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [set_result, sink_inputs, set_result, set_result]
            audio.set_default_sink("alsa_output.pci-0000_16_00.6.iec958-stereo")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert ["pactl", "move-sink-input", "4", "alsa_output.pci-0000_16_00.6.iec958-stereo"] in calls
        assert ["pactl", "move-sink-input", "5", "alsa_output.pci-0000_16_00.6.iec958-stereo"] in calls

    def test_set_default_source_calls_pactl(self):
        source_outputs = _make_run(PACTL_LIST_SOURCE_OUTPUTS_SHORT)
        set_result = _make_run("")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [set_result, source_outputs, set_result]
            audio.set_default_source("alsa_input.pci-0000_16_00.6.analog-stereo")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls[0] == ["pactl", "set-default-source", "alsa_input.pci-0000_16_00.6.analog-stereo"]


class TestAudioError:
    def test_pactl_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(audio.AudioError, match="pactl not found"):
                audio.list_sinks()

    def test_pactl_nonzero_exit(self):
        err = subprocess.CalledProcessError(1, "pactl", stderr="No such entity")
        with patch("subprocess.run", side_effect=err):
            with pytest.raises(audio.AudioError):
                audio.list_sinks()
