from __future__ import annotations

from linux_audio_switcher import audio, carousel, config as cfg, notify

try:
    import pystray
    from PIL import Image, ImageDraw
    _DEPS_OK = True
except ImportError:
    _DEPS_OK = False


def run_daemon() -> None:
    if not _DEPS_OK:
        raise RuntimeError(
            "pystray and Pillow are required for the tray daemon.\n"
            "Install: pip install pystray Pillow"
        )
    icon = pystray.Icon(
        "linux-audio-switcher",
        _make_icon(),
        "Linux Audio Switcher",
        pystray.Menu(_menu_items),
    )
    icon.run()


def _menu_items():
    """
    Generator called each time the menu is opened — reads fresh state every time.
    Yields MenuItems for all sinks/sources with carousel checkmarks.
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

    output_set = set(conf.output_devices)
    input_set = set(conf.input_devices)

    # Output header
    out_desc = next((s.description for s in sinks if s.name == default_sink), default_sink)
    yield pystray.MenuItem(f"Output: {out_desc}", None, enabled=False)

    for sink in sinks:
        name = sink.name
        yield pystray.MenuItem(
            f"  {sink.description}",
            lambda icon, item, n=name: _toggle_output(n),
            checked=name in output_set,
        )

    yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem("Next Output", _on_next_output)
    yield pystray.Menu.SEPARATOR

    # Input header
    in_desc = next((s.description for s in sources if s.name == default_source), default_source)
    yield pystray.MenuItem(f"Input: {in_desc}", None, enabled=False)

    for source in sources:
        name = source.name
        yield pystray.MenuItem(
            f"  {source.description}",
            lambda icon, item, n=name: _toggle_input(n),
            checked=name in input_set,
        )

    yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem("Next Input", _on_next_input)
    yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem("Quit", lambda icon, _: icon.stop())


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


def _on_next_output(icon: "pystray.Icon", _item: "pystray.MenuItem") -> None:
    try:
        device = carousel.advance_output()
        notify.notify_output(device.description)
    except (audio.AudioError, carousel.CarouselError) as e:
        notify.notify_output(f"Error: {e}")


def _on_next_input(icon: "pystray.Icon", _item: "pystray.MenuItem") -> None:
    try:
        device = carousel.advance_input()
        notify.notify_input(device.description)
    except (audio.AudioError, carousel.CarouselError) as e:
        notify.notify_input(f"Error: {e}")


def _make_icon() -> "Image.Image":
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Speaker body (rectangle)
    draw.rectangle([8, 22, 26, 42], fill=(255, 255, 255, 255))
    # Speaker cone (polygon)
    draw.polygon([(26, 22), (46, 10), (46, 54), (26, 42)], fill=(255, 255, 255, 255))
    # Sound wave arcs
    draw.arc([48, 16, 62, 48], -40, 40, fill=(255, 255, 255, 210), width=3)
    draw.arc([54, 22, 62, 42], -40, 40, fill=(255, 255, 255, 160), width=2)
    return img
