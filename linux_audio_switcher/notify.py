from __future__ import annotations

import subprocess

_APP_NAME = "Linux Audio Switcher"
_EXPIRE_MS = 2000


def notify_output(description: str) -> None:
    _send("Audio Output", description)


def notify_input(description: str) -> None:
    _send("Audio Input", description)


def _send(summary: str, body: str) -> None:
    try:
        subprocess.run(
            [
                "notify-send",
                f"--app-name={_APP_NAME}",
                f"--expire-time={_EXPIRE_MS}",
                "--urgency=low",
                "--icon=audio-volume-high",
                summary,
                body,
            ],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass  # notify-send not installed — silently skip
