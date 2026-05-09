# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Tests for TipTrack tip controller helpers.

"""Tests for FreeCAD mutation wrappers that do not require FreeCAD."""

from types import SimpleNamespace


class _Document:
    def __init__(self):
        self.recompute_count = 0

    def recompute(self):
        self.recompute_count += 1


def test_set_tip_updates_body_and_recomputes(mock_freecad):
    """Setting a tip mutates the Body and recomputes its document."""
    document = _Document()
    feature = SimpleNamespace(Name="Pad", Document=document)
    body = SimpleNamespace(Tip=None, Document=document)

    from freecad.TipTrack.tip_controller import set_tip

    set_tip(body, feature)

    assert body.Tip is feature
    assert document.recompute_count == 1


def test_toggle_suppression_flips_property_and_recomputes(mock_freecad):
    """Suppression toggles only when the feature exposes the property."""
    document = _Document()
    feature = SimpleNamespace(Suppressed=False, Document=document)

    from freecad.TipTrack.tip_controller import toggle_suppression

    assert toggle_suppression(feature) is True
    assert feature.Suppressed is True
    assert document.recompute_count == 1


def test_toggle_suppression_rejects_unsupported_features(mock_freecad):
    """Features without Suppressed get a clear failure."""
    feature = SimpleNamespace()

    from freecad.TipTrack.tip_controller import toggle_suppression

    try:
        toggle_suppression(feature)
    except ValueError as exc:
        assert "does not support suppression" in str(exc)
    else:
        raise AssertionError("Expected unsupported suppression to fail")
