from __future__ import annotations

import signal

from linux_audio_switcher import audio, carousel, config as cfg, notify

try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('XApp', '1.0')
    from gi.repository import Gtk, XApp
    _DEPS_OK = True
except (ImportError, ValueError):
    _DEPS_OK = False


def run_daemon() -> None:
    if not _DEPS_OK:
        raise RuntimeError(
            "XApp and GTK are required for the tray daemon.\n"
            "Install: sudo apt install gir1.2-xapp-1.0 gir1.2-gtk-3.0"
        )

    icon = XApp.StatusIcon()
    icon.set_icon_name("audio-volume-high")
    icon.set_tooltip_text("Linux Audio Switcher")
    icon.set_visible(True)

    menu = Gtk.Menu()
    menu.connect("map", _on_menu_map)
    icon.set_primary_menu(menu)

    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())

    Gtk.main()


def _on_menu_map(menu: "Gtk.Menu") -> None:
    """Rebuild the menu with fresh audio state each time it opens."""
    for child in menu.get_children():
        menu.remove(child)

    try:
        sinks = audio.list_sinks()
        sources = audio.list_sources()
        default_sink = audio.get_default_sink()
        default_source = audio.get_default_source()
        conf = cfg.load()
    except audio.AudioError as e:
        item = Gtk.MenuItem(label=f"Error: {e}")
        item.set_sensitive(False)
        menu.append(item)
        menu.show_all()
        return

    output_set = set(conf.output_devices)
    input_set = set(conf.input_devices)

    # ── Output section ─────────────────────────────────────────────────────
    out_desc = next((s.description for s in sinks if s.name == default_sink), default_sink)
    _append_header(menu, f"Output: {out_desc}")

    for sink in sinks:
        name = sink.name
        item = Gtk.CheckMenuItem(label=f"  {sink.description}")
        item.set_active(name in output_set)
        item.connect("activate", lambda w, n=name: _toggle_output(n))
        menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())
    item = Gtk.MenuItem(label="Next Output")
    item.connect("activate", lambda w: _on_next_output())
    menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())

    # ── Input section ──────────────────────────────────────────────────────
    in_desc = next((s.description for s in sources if s.name == default_source), default_source)
    _append_header(menu, f"Input: {in_desc}")

    for source in sources:
        name = source.name
        item = Gtk.CheckMenuItem(label=f"  {source.description}")
        item.set_active(name in input_set)
        item.connect("activate", lambda w, n=name: _toggle_input(n))
        menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())
    item = Gtk.MenuItem(label="Next Input")
    item.connect("activate", lambda w: _on_next_input())
    menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())
    item = Gtk.MenuItem(label="Quit")
    item.connect("activate", lambda w: Gtk.main_quit())
    menu.append(item)

    menu.show_all()


def _append_header(menu: "Gtk.Menu", label: str) -> None:
    item = Gtk.MenuItem(label=label)
    item.set_sensitive(False)
    menu.append(item)


def _toggle_output(name: str) -> None:
    conf = cfg.load()
    if name in conf.output_devices:
        conf.output_devices.remove(name)
    else:
        conf.output_devices.append(name)
    cfg.save(conf)


def _toggle_input(name: str) -> None:
    conf = cfg.load()
    if name in conf.input_devices:
        conf.input_devices.remove(name)
    else:
        conf.input_devices.append(name)
    cfg.save(conf)


def _on_next_output() -> None:
    try:
        device = carousel.advance_output()
        notify.notify_output(device.description)
    except (audio.AudioError, carousel.CarouselError) as e:
        notify.notify_output(f"Error: {e}")


def _on_next_input() -> None:
    try:
        device = carousel.advance_input()
        notify.notify_input(device.description)
    except (audio.AudioError, carousel.CarouselError) as e:
        notify.notify_input(f"Error: {e}")
