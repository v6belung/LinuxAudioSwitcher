from __future__ import annotations

import signal

from linux_audio_switcher import audio, carousel, config as cfg, notify

try:
    import gi
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gtk', '3.0')
    gi.require_version('XApp', '1.0')
    from gi.repository import Gdk, GLib, Gtk, XApp
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
    icon.connect("button-release-event", _on_icon_click)

    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())

    Gtk.main()


def _on_icon_click(
    icon: "XApp.StatusIcon",
    x: int,
    y: int,
    button: int,
    time: int,
    position: int,
) -> None:
    # Build a fresh menu on every click — no stale state, correct sizing
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

    # ── Output ─────────────────────────────────────────────────────────────
    _append_header(menu, "Output")
    for sink in sinks:
        menu.append(_device_item(
            label=sink.description,
            in_carousel=sink.name in output_set,
            is_active=sink.name == default_sink,
            on_carousel_toggle=lambda n=sink.name: _toggle_output(n),
            on_activate=lambda n=sink.name: _activate_sink(n),
        ))

    menu.append(Gtk.SeparatorMenuItem())
    item = Gtk.MenuItem(label="Next Output")
    item.connect("activate", lambda _: _on_next_output())
    menu.append(item)
    menu.append(Gtk.SeparatorMenuItem())

    # ── Input ──────────────────────────────────────────────────────────────
    _append_header(menu, "Input")
    for source in sources:
        menu.append(_device_item(
            label=source.description,
            in_carousel=source.name in input_set,
            is_active=source.name == default_source,
            on_carousel_toggle=lambda n=source.name: _toggle_input(n),
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
    A custom menu row:

        [checkbox]  ▶ Device Name (bold if active)

    GTK menus use a pointer grab — child widget event handlers don't fire.
    Both click targets route through MenuItem.activate. We distinguish them
    by querying the pointer position at activate time and comparing it against
    the checkbox widget's screen bounds.

    Checkbox click → toggle carousel membership (visual state updates, menu closes)
    Label click    → set device as default (notification fired, menu closes)
    """
    item = Gtk.MenuItem()

    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    box.set_border_width(2)

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
    Return True if the current pointer position overlaps the checkbox widget.

    Uses screen-absolute coordinates throughout:
    - translate_coordinates walks the full widget hierarchy from check → menu toplevel
    - get_origin() gives the menu window's screen position
    - Gdk.Device.get_position() gives the pointer's screen position
    Falls back to False (label action) if any widget is not yet realized.
    """
    pointer = Gdk.Display.get_default().get_default_seat().get_pointer()
    _screen, ptr_x, ptr_y = pointer.get_position()

    # check.get_toplevel() → the GtkMenu (which is a GtkWindow)
    toplevel = check.get_toplevel()
    ok, check_in_top_x, check_in_top_y = check.translate_coordinates(toplevel, 0, 0)
    if not ok:
        return False

    top_win = toplevel.get_window()
    if top_win is None:
        return False

    win_x, win_y = top_win.get_origin()
    alloc = check.get_allocation()

    check_screen_x = win_x + check_in_top_x
    check_screen_y = win_y + check_in_top_y

    return (check_screen_x <= ptr_x <= check_screen_x + alloc.width and
            check_screen_y <= ptr_y <= check_screen_y + alloc.height)


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


def _activate_sink(name: str) -> None:
    try:
        audio.set_default_sink(name)
        desc = next((s.description for s in audio.list_sinks() if s.name == name), name)
        notify.notify_output(desc)
    except audio.AudioError as e:
        notify.notify_output(f"Error: {e}")


def _activate_source(name: str) -> None:
    try:
        audio.set_default_source(name)
        desc = next((s.description for s in audio.list_sources() if s.name == name), name)
        notify.notify_input(desc)
    except audio.AudioError as e:
        notify.notify_input(f"Error: {e}")


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
