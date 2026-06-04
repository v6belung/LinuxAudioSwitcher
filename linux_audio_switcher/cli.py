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
    from linux_audio_switcher import tray
    try:
        tray.run_daemon()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config(_args: argparse.Namespace) -> None:
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
        print("  (empty — run 'las list' and edit the config file)")

    print("\nInput carousel:")
    if conf.input_devices:
        for name in conf.input_devices:
            desc = source_map.get(name, "(not currently detected)")
            print(f"  {desc}")
            print(f"    {name}")
    else:
        print("  (empty — run 'las list' and edit the config file)")

    print(f"\nEdit {path} to reorder or remove devices.")
    print("The tray icon (las daemon) also lets you toggle devices via checkmarks.")


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
    sub.add_parser("config", help="Show carousel configuration")

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
