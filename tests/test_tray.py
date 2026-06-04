from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from linux_audio_switcher.tray import _click_is_on_checkbox

# ── Geometry used across tests ──────────────────────────────────────────────
# Window origin on screen: (50, 100)
# Check widget position within toplevel: (15, 15)  ← from translate_coordinates
# → checkbox screen bounds: x ∈ [65, 85],  y ∈ [115, 135]  (20 × 20 px)

WIN_ORIGIN = (1, 50, 100)    # (depth, x, y) — real PyGObject shape
TRANSLATE   = (15, 15)       # (dest_x, dest_y) — real PyGObject shape (no bool)
CHECK_W, CHECK_H = 20, 20
CHECK_X = 50 + 15            # = 65
CHECK_Y = 100 + 15           # = 115


def _make_check(translate=TRANSLATE, win_origin=WIN_ORIGIN, w=CHECK_W, h=CHECK_H):
    """Build a mock Gtk.CheckButton with realistic geometry returns."""
    check = MagicMock()
    check.translate_coordinates.return_value = translate

    alloc = MagicMock()
    alloc.width = w
    alloc.height = h
    check.get_allocation.return_value = alloc

    toplevel = MagicMock()
    toplevel.get_window.return_value.get_origin.return_value = win_origin
    check.get_toplevel.return_value = toplevel

    return check


@contextmanager
def _ptr(x, y):
    """Patch Gdk pointer position to screen coords (x, y)."""
    mock_gdk = MagicMock()
    (mock_gdk.Display.get_default.return_value
     .get_default_seat.return_value
     .get_pointer.return_value
     .get_position.return_value) = (None, x, y)   # (screen, x, y)
    with patch("linux_audio_switcher.tray.Gdk", mock_gdk):
        yield


def _hit(ptr_x, ptr_y, **check_kwargs):
    item = MagicMock()
    check = _make_check(**check_kwargs)
    with _ptr(ptr_x, ptr_y):
        return _click_is_on_checkbox(item, check)


# ── Positive cases ───────────────────────────────────────────────────────────

class TestInsideCheckbox:
    def test_top_left_corner(self):
        assert _hit(CHECK_X, CHECK_Y) is True

    def test_center(self):
        assert _hit(CHECK_X + 10, CHECK_Y + 10) is True

    def test_bottom_right_corner(self):
        assert _hit(CHECK_X + CHECK_W, CHECK_Y + CHECK_H) is True


# ── Negative cases ───────────────────────────────────────────────────────────

class TestOutsideCheckbox:
    def test_one_pixel_right(self):
        assert _hit(CHECK_X + CHECK_W + 1, CHECK_Y + 10) is False

    def test_one_pixel_left(self):
        assert _hit(CHECK_X - 1, CHECK_Y + 10) is False

    def test_one_pixel_below(self):
        assert _hit(CHECK_X + 10, CHECK_Y + CHECK_H + 1) is False

    def test_one_pixel_above(self):
        assert _hit(CHECK_X + 10, CHECK_Y - 1) is False

    def test_far_right_label_area(self):
        assert _hit(CHECK_X + 200, CHECK_Y + 10) is False


# ── Edge / error cases ───────────────────────────────────────────────────────

class TestFallbacks:
    def test_translate_returns_none(self):
        assert _hit(CHECK_X + 5, CHECK_Y + 5, translate=None) is False

    def test_translate_returns_empty(self):
        assert _hit(CHECK_X + 5, CHECK_Y + 5, translate=()) is False

    def test_get_window_returns_none(self):
        item = MagicMock()
        check = _make_check()
        check.get_toplevel.return_value.get_window.return_value = None
        with _ptr(CHECK_X + 5, CHECK_Y + 5):
            assert _click_is_on_checkbox(item, check) is False

    def test_exception_in_gdk_call(self):
        item = MagicMock()
        check = MagicMock()
        check.get_toplevel.side_effect = RuntimeError("not realized")
        with _ptr(CHECK_X + 5, CHECK_Y + 5):
            assert _click_is_on_checkbox(item, check) is False

    def test_different_window_position(self):
        """Changing window origin shifts check bounds correctly."""
        # Window at (200, 300), check at (10, 10) within toplevel → screen (210, 310)
        assert _hit(215, 315, translate=(10, 10), win_origin=(1, 200, 300)) is True
        assert _hit(231, 315, translate=(10, 10), win_origin=(1, 200, 300)) is False
