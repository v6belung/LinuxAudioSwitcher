from __future__ import annotations

from unittest.mock import patch

from linux_audio_switcher import notify


class TestNotify:
    def test_calls_notify_send(self):
        with patch("subprocess.run") as mock_run:
            notify._send("Title", "Body")
        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "notify-send"
        assert "Title" in cmd
        assert "Body" in cmd

    def test_includes_app_name(self):
        with patch("subprocess.run") as mock_run:
            notify._send("Title", "Body")
        cmd = mock_run.call_args.args[0]
        assert any("Linux Audio Switcher" in arg for arg in cmd)

    def test_silent_when_notify_send_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            notify._send("Title", "Body")  # must not raise

    def test_silent_on_nonzero_exit(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            notify._send("Title", "Body")  # check=False, must not raise

    def test_notify_output_sends_correct_summary(self):
        with patch("linux_audio_switcher.notify._send") as mock_send:
            notify.notify_output("USB Speaker")
        mock_send.assert_called_once_with("Audio Output", "USB Speaker")

    def test_notify_input_sends_correct_summary(self):
        with patch("linux_audio_switcher.notify._send") as mock_send:
            notify.notify_input("USB Mic")
        mock_send.assert_called_once_with("Audio Input", "USB Mic")
