from __future__ import annotations

import signal

from linux_audio_switcher import audio, carousel, config as cfg, notify

# ── Backend detection ─────────────────────────────────────────────────────
_XAPP = False
_PYSTRAY = False

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    gi.require_version('XApp', '1.0')
    from gi.repository import Gdk, GLib, Gtk, XApp
    _XAPP = True
except (ImportError, ValueError):
    pass

if not _XAPP:
    try:
        import pystray
        from PIL import Image, ImageDraw
        _PYSTRAY = True
    except ImportError:
        pass

# XApp StatusIcon reference kept for tooltip updates after device switches
_icon: "XApp.StatusIcon | None" = None


def run_daemon() -> None:
    if _XAPP:
        _run_xapp()
    elif _PYSTRAY:
        _run_pystray()
    else:
        raise RuntimeError(
            "No tray backend available.\n"
            "Cinnamon / Linux Mint:  sudo apt install gir1.2-xapp-1.0\n"
            "GNOME:                  pip install pystray  (also install AppIndicator GNOME extension)\n"
            "KDE:                    pip install pystray"
        )


# ── XApp backend (Cinnamon / Linux Mint) ─────────────────────────────────

def _run_xapp() -> None:
    global _icon
    icon = XApp.StatusIcon()
    icon.set_icon_name("audio-volume-high")
    icon.set_visible(True)
    _icon = icon
    _update_tooltip()
    icon.connect("button-release-event", _on_icon_click)

    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())

    try:
        Gtk.main()
    except Exception as e:
        raise RuntimeError(f"Tray daemon error: {e}") from e


def _on_icon_click(
    icon: "XApp.StatusIcon",
    x: int, y: int, button: int, time: int, position: int,
) -> None:
    menu = _build_menu()
    menu.show_all()
    menu.popup(None, None, None, None, button, time)


def _build_menu() -> "Gtk.Menu":
    menu = Gtk.Menu()

    try:
        sinks = audio.list_sinks()
        sources = audio.list_sources()
        default_sink = audio.get_default_sink()
        default_source = audio.get_default_source()
        conf = cfg.load()
    except audio.AudioError as e:
        err = Gtk.MenuItem(label=f"Error: {e}")
        err.set_sensitive(False)
        menu.append(err)
        return menu

    output_set = set(conf.output_devices)
    input_set = set(conf.input_devices)

    _append_header(menu, "Output")
    for sink in sinks:
        menu.append(_device_item(
            label=sink.description,
            in_carousel=sink.name in output_set,
            is_active=sink.name == default_sink,
            on_carousel_toggle=lambda n=sink.name, d=sink.description: _toggle_output(n, d),
            on_activate=lambda n=sink.name: _activate_sink(n),
        ))
    menu.append(Gtk.SeparatorMenuItem())
    item = Gtk.MenuItem(label="Next Output")
    item.connect("activate", lambda _: _on_next_output())
    menu.append(item)
    menu.append(Gtk.SeparatorMenuItem())

    _append_header(menu, "Input")
    for source in sources:
        menu.append(_device_item(
            label=source.description,
            in_carousel=source.name in input_set,
            is_active=source.name == default_source,
            on_carousel_toggle=lambda n=source.name, d=source.description: _toggle_input(n, d),
            on_activate=lambda n=source.name: _activate_source(n),
        ))
    menu.append(Gtk.SeparatorMenuItem())
    item = Gtk.MenuItem(label="Next Input")
    item.connect("activate", lambda _: _on_next_input())
    menu.append(item)
    menu.append(Gtk.SeparatorMenuItem())

    quit_item = Gtk.MenuItem(label="Quit")
    quit_item.connect("activate", lambda _: Gtk.main_quit())
    menu.append(quit_item)

    return menu


def _append_header(menu: "Gtk.Menu", text: str) -> None:
    item = Gtk.MenuItem()
    label = Gtk.Label()
    label.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
    label.set_xalign(0.0)
    label.set_margin_start(4)
    item.add(label)
    item.set_sensitive(False)
    menu.append(item)


def _device_item(
    label: str,
    in_carousel: bool,
    is_active: bool,
    on_carousel_toggle: callable,
    on_activate: callable,
) -> "Gtk.MenuItem":
    """
    Custom menu row:   [checkbox]  ▶ Device Name

    GTK menus use a pointer grab — child widget event handlers never fire.
    Both clicks route through MenuItem.activate; _click_is_on_checkbox uses
    screen-coordinate comparison to distinguish checkbox from label area.

    margin_start(8) keeps the checkbox away from the panel edge and widens
    the effective click target. _click_is_on_checkbox adds 8px on the right
    side of the checkbox allocation for further forgiveness.
    """
    item = Gtk.MenuItem()
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    box.set_border_width(2)
    box.set_margin_start(8)

    check = Gtk.CheckButton()
    check.set_active(in_carousel)
    check.set_can_focus(False)
    box.pack_start(check, False, False, 0)

    escaped = GLib.markup_escape_text(label)
    name_label = Gtk.Label()
    name_label.set_markup(f"<b>▶ {escaped}</b>" if is_active else f"  {escaped}")
    name_label.set_halign(Gtk.Align.START)
    name_label.set_xalign(0.0)
    box.pack_start(name_label, True, True, 0)

    item.add(box)

    def on_item_activate(widget):
        if _click_is_on_checkbox(widget, check):
            check.set_active(not check.get_active())
            on_carousel_toggle()
        else:
            on_activate()

    item.connect("activate", on_item_activate)
    return item


def _click_is_on_checkbox(item: "Gtk.MenuItem", check: "Gtk.CheckButton") -> bool:
    """
    Return True if the pointer overlaps (or is near) the checkbox widget.

    Hit area extends 8px past the checkbox's right edge for click forgiveness.

    Confirmed PyGObject return shapes (Python 3.12, GTK 3):
      translate_coordinates() → (dest_x, dest_y)    2-tuple, no bool
      get_origin()            → (depth, x, y)        3-tuple, discard depth
      get_position()          → (screen, x, y)       3-tuple
    Falls back to False (→ label action) on any error.
    """
    try:
        pointer = Gdk.Display.get_default().get_default_seat().get_pointer()
        _screen, ptr_x, ptr_y = pointer.get_position()

        toplevel = check.get_toplevel()
        coords = check.translate_coordinates(toplevel, 0, 0)
        if not coords or len(coords) < 2:
            return False
        check_x, check_y = coords

        top_win = toplevel.get_window()
        if top_win is None:
            return False

        _, win_x, win_y = top_win.get_origin()
        alloc = check.get_allocation()

        check_screen_x = win_x + check_x
        check_screen_y = win_y + check_y

        return (check_screen_x <= ptr_x <= check_screen_x + alloc.width + 8 and
                check_screen_y <= ptr_y <= check_screen_y + alloc.height)
    except Exception:
        return False


def _update_tooltip() -> None:
    """Update the tray icon tooltip with the current output and input device names."""
    global _icon
    if _icon is None:
        return
    try:
        default_sink = audio.get_default_sink()
        default_source = audio.get_default_source()
        sinks = audio.list_sinks()
        sources = audio.list_sources()
        out = next((s.description for s in sinks if s.name == default_sink), default_sink)
        inp = next((s.description for s in sources if s.name == default_source), default_source)
        _icon.set_tooltip_text(f"Out: {out}\nIn:  {inp}")
    except audio.AudioError:
        pass


# ── Shared action handlers (XApp + pystray) ───────────────────────────────

def _toggle_output(name: str, description: str) -> None:
    conf = cfg.load()
    if name in conf.output_devices:
        conf.output_devices.remove(name)
        cfg.save(conf)
        notify.notify_output(f"Removed from carousel: {description}")
    else:
        conf.output_devices.append(name)
        cfg.save(conf)
        notify.notify_output(f"Added to carousel: {description}")


def _toggle_input(name: str, description: str) -> None:
    conf = cfg.load()
    if name in conf.input_devices:
        conf.input_devices.remove(name)
        cfg.save(conf)
        notify.notify_input(f"Removed from carousel: {description}")
    else:
        conf.input_devices.append(name)
        cfg.save(conf)
        notify.notify_input(f"Added to carousel: {description}")


def _activate_sink(name: str) -> None:
    try:
        audio.set_default_sink(name)
        desc = next((s.description for s in audio.list_sinks() if s.name == name), name)
        notify.notify_output(desc)
        _update_tooltip()
    except audio.AudioError as e:
        notify.notify_output(f"Error: {e}")


def _activate_source(name: str) -> None:
    try:
        audio.set_default_source(name)
        desc = next((s.description for s in audio.list_sources() if s.name == name), name)
        notify.notify_input(desc)
        _update_tooltip()
    except audio.AudioError as e:
        notify.notify_input(f"Error: {e}")


def _on_next_output() -> None:
    try:
        device = carousel.advance_output()
        notify.notify_output(device.description)
        _update_tooltip()
    except (audio.AudioError, carousel.CarouselError) as e:
        notify.notify_output(f"Error: {e}")


def _on_next_input() -> None:
    try:
        device = carousel.advance_input()
        notify.notify_input(device.description)
        _update_tooltip()
    except (audio.AudioError, carousel.CarouselError) as e:
        notify.notify_input(f"Error: {e}")


# ── pystray backend (GNOME, KDE, other DEs without XApp) ─────────────────

def _run_pystray() -> None:
    icon = pystray.Icon(
        "linux-audio-switcher",
        _make_pystray_icon(),
        "Linux Audio Switcher",
        pystray.Menu(_pystray_menu_items),
    )
    icon.run()


def _pystray_menu_items():
    """
    Dynamic pystray menu for non-XApp desktops (GNOME, KDE, etc.).
    Checkmarks toggle carousel membership; the menu closes after each click
    (pystray limitation vs. the XApp version where the menu stays open).
    """
    try:
        sinks = audio.list_sinks()
        sources = audio.list_sources()
        default_sink = audio.get_default_sink()
        default_source = audio.get_default_source()
        conf = cfg.load()
    except audio.AudioError as e:
        yield pystray.MenuItem(f"Error: {e}", None, enabled=False)
        return

    out_desc = next((s.description for s in sinks if s.name == default_sink), default_sink)
    yield pystray.MenuItem(f"Output: {out_desc}", None, enabled=False)

    for sink in sinks:
        name, desc = sink.name, sink.description
        yield pystray.MenuItem(
            f"  {desc}",
            lambda icon, item, n=name, d=desc: _toggle_output(n, d),
            checked=lambda item, n=name: n in cfg.load().output_devices,
        )

    yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem("Next Output", lambda icon, item: _on_next_output())
    yield pystray.Menu.SEPARATOR

    in_desc = next((s.description for s in sources if s.name == default_source), default_source)
    yield pystray.MenuItem(f"Input: {in_desc}", None, enabled=False)

    for source in sources:
        name, desc = source.name, source.description
        yield pystray.MenuItem(
            f"  {desc}",
            lambda icon, item, n=name, d=desc: _toggle_input(n, d),
            checked=lambda item, n=name: n in cfg.load().input_devices,
        )

    yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem("Next Input", lambda icon, item: _on_next_input())
    yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem("Quit", lambda icon, item: icon.stop())


def _make_pystray_icon() -> "Image.Image":
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([8, 22, 26, 42], fill=(255, 255, 255, 255))
    draw.polygon([(26, 22), (46, 10), (46, 54), (26, 42)], fill=(255, 255, 255, 255))
    draw.arc([48, 16, 62, 48], -40, 40, fill=(255, 255, 255, 210), width=3)
    draw.arc([54, 22, 62, 42], -40, 40, fill=(255, 255, 255, 160), width=2)
    return img
