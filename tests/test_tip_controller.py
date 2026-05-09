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


def test_tip_for_scrub_index_uses_nearest_partdesign_feature(mock_freecad):
    """Scrubbing to a sketch rolls back to the previous valid PartDesign tip."""
    sketch = SimpleNamespace(Name="Sketch", TypeId="Sketcher::SketchObject")
    pad = SimpleNamespace(Name="Pad", TypeId="PartDesign::Pad")
    sketch2 = SimpleNamespace(Name="Sketch001", TypeId="Sketcher::SketchObject")
    body = SimpleNamespace(Group=[sketch, pad, sketch2])

    from freecad.TipTrack.tip_controller import tip_for_scrub_index

    assert tip_for_scrub_index(body, 0) is None
    assert tip_for_scrub_index(body, 1) is pad
    assert tip_for_scrub_index(body, 2) is pad


def test_scrub_tip_to_index_updates_tip_and_recomputes(mock_freecad):
    """The scrubber helper can clear the tip before the first solid feature."""
    document = _Document()
    sketch = SimpleNamespace(Name="Sketch", TypeId="Sketcher::SketchObject")
    pad = SimpleNamespace(Name="Pad", TypeId="PartDesign::Pad")
    body = SimpleNamespace(Group=[sketch, pad], Tip=pad, Document=document)

    from freecad.TipTrack.tip_controller import scrub_tip_to_index

    assert scrub_tip_to_index(body, 0) is None
    assert body.Tip is None
    assert document.recompute_count == 1

    assert scrub_tip_to_index(body, 1) is pad
    assert body.Tip is pad
    assert document.recompute_count == 2
