from __future__ import annotations

import argparse
import sys

from linux_audio_switcher import audio, carousel, notify
from linux_audio_switcher import config as cfg


def cmd_list(_args: argparse.Namespace) -> None:
    try:
        backend = audio.detect_backend()
        sinks = audio.list_sinks()
        sources = audio.list_sources()
        default_sink = audio.get_default_sink()
        default_source = audio.get_default_source()
    except audio.AudioError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Backend: {backend}\n")

    print("Output devices (sinks):")
    for s in sinks:
        marker = "*" if s.name == default_sink else " "
        print(f"  [{marker}] {s.description}")
        print(f"       {s.name}")

    print("\nInput devices (sources):")
    for s in sources:
        marker = "*" if s.name == default_source else " "
        print(f"  [{marker}] {s.description}")
        print(f"       {s.name}")


def cmd_next_output(_args: argparse.Namespace) -> None:
    try:
        device = carousel.advance_output()
    except (audio.AudioError, carousel.CarouselError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    notify.notify_output(device.description)
    print(f"Output: {device.description}")


def cmd_next_input(_args: argparse.Namespace) -> None:
    try:
        device = carousel.advance_input()
    except (audio.AudioError, carousel.CarouselError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    notify.notify_input(device.description)
    print(f"Input: {device.description}")


def cmd_daemon(_args: argparse.Namespace) -> None:
    import os
    # tray.py's module-level backend detection runs `from gi.repository import Gtk`
    # the moment tray is imported (line below). On Wayland that locks GTK into the
    # Wayland-native GDK backend, which causes:
    #   Gtk-CRITICAL: gtk_widget_get_scale_factor: assertion 'GTK_IS_WIDGET' failed
    # because AppIndicator tries to query a scale factor through a path that only
    # exists in X11-mode GTK. Setting GDK_BACKEND=x11 here — before the import —
    # forces GTK to use XWayland instead. os.environ.setdefault preserves any
    # explicit user override and is a no-op on non-Wayland sessions.
    if (os.environ.get("XDG_SESSION_TYPE") == "wayland" or
            "WAYLAND_DISPLAY" in os.environ):
        os.environ.setdefault("GDK_BACKEND", "x11")

    from linux_audio_switcher import tray
    try:
        tray.run_daemon()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config(args: argparse.Namespace) -> None:
    action = getattr(args, "config_action", None)
    if action is None:
        _config_show()
        return

    device = args.device
    try:
        sinks = audio.list_sinks()
        sources = audio.list_sources()
    except audio.AudioError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if action in ("add-output", "remove-output"):
        _config_modify(
            device=device,
            kind="output",
            remove=(action == "remove-output"),
            known={s.name for s in sinks},
            known_list=sinks,
        )
    else:
        _config_modify(
            device=device,
            kind="input",
            remove=(action == "remove-input"),
            known={s.name for s in sources},
            known_list=sources,
        )


def _config_modify(device, kind, remove, known, known_list) -> None:
    if device not in known:
        print(f"Warning: '{device}' not in currently detected {kind} devices.", file=sys.stderr)
        print(f"Known {kind} devices:", file=sys.stderr)
        for d in known_list:
            print(f"  {d.name}", file=sys.stderr)

    conf = cfg.load()
    devices = conf.output_devices if kind == "output" else conf.input_devices

    if remove:
        if device not in devices:
            print(f"Not in {kind} carousel: {device}", file=sys.stderr)
            sys.exit(1)
        devices.remove(device)
        cfg.save(conf)
        print(f"Removed from {kind} carousel: {device}")
    else:
        if device in devices:
            print(f"Already in {kind} carousel: {device}")
            return
        devices.append(device)
        cfg.save(conf)
        print(f"Added to {kind} carousel: {device}")


def _config_show() -> None:
    try:
        conf = cfg.load()
        sinks = audio.list_sinks()
        sources = audio.list_sources()
    except audio.AudioError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    path = cfg.config_path()
    sink_map = {s.name: s.description for s in sinks}
    source_map = {s.name: s.description for s in sources}

    print(f"Config: {path}\n")

    print("Output carousel:")
    if conf.output_devices:
        for name in conf.output_devices:
            desc = sink_map.get(name, "(not currently detected)")
            print(f"  {desc}")
            print(f"    {name}")
    else:
        print("  (empty — use 'las config add-output <name>')")

    print("\nInput carousel:")
    if conf.input_devices:
        for name in conf.input_devices:
            desc = source_map.get(name, "(not currently detected)")
            print(f"  {desc}")
            print(f"    {name}")
    else:
        print("  (empty — use 'las config add-input <name>')")

    print(f"\nEdit {path} directly, or use:")
    print("  las config add-output <name>     las config remove-output <name>")
    print("  las config add-input <name>      las config remove-input <name>")
    print("  las list                         (to see device names)")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="las",
        description="Linux Audio Switcher — cycle audio devices with a hotkey",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser("list", help="List detected audio devices")
    sub.add_parser("next-output", help="Cycle to the next output (playback) device")
    sub.add_parser("next-input", help="Cycle to the next input (recording) device")
    sub.add_parser("daemon", help="Start the system tray icon daemon")

    config_parser = sub.add_parser("config", help="Show or edit carousel configuration")
    config_sub = config_parser.add_subparsers(dest="config_action", metavar="<action>")
    for action in ("add-output", "remove-output", "add-input", "remove-input"):
        p = config_sub.add_parser(action, help=f"{action} a device to/from the carousel")
        p.add_argument("device", metavar="<device-name>", help="pactl device name (see 'las list')")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "next-output":
        cmd_next_output(args)
    elif args.command == "next-input":
        cmd_next_input(args)
    elif args.command == "daemon":
        cmd_daemon(args)
    elif args.command == "config":
        cmd_config(args)
    else:
        parser.print_help()
