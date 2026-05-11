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


def test_scrub_tip_to_position_zero_clears_tip(mock_freecad):
    """Position 0 clears Body.Tip and recomputes."""
    document = _Document()
    sketch = SimpleNamespace(Name="Sketch", TypeId="Sketcher::SketchObject")
    pad = SimpleNamespace(Name="Pad", TypeId="PartDesign::Pad")
    body = SimpleNamespace(Group=[sketch, pad], Tip=pad, Document=document)

    from freecad.TipTrack.tip_controller import scrub_tip_to_position

    assert scrub_tip_to_position(body, 0) is None
    assert body.Tip is None
    assert document.recompute_count == 1


def test_scrub_tip_to_position_one_sketch_only(mock_freecad):
    """Position 1 reaches the first sketch (no PartDesign tip yet)."""
    document = _Document()
    sketch = SimpleNamespace(Name="Sketch", TypeId="Sketcher::SketchObject")
    pad = SimpleNamespace(Name="Pad", TypeId="PartDesign::Pad")
    body = SimpleNamespace(Group=[sketch, pad], Tip=pad, Document=document)

    from freecad.TipTrack.tip_controller import scrub_tip_to_position

    assert scrub_tip_to_position(body, 1) is None
    assert body.Tip is None
    assert document.recompute_count == 1


def test_scrub_tip_to_position_two_restores_pad(mock_freecad):
    """Position 2 restores the first Pad in a [Sketch, Pad] body."""
    document = _Document()
    sketch = SimpleNamespace(Name="Sketch", TypeId="Sketcher::SketchObject")
    pad = SimpleNamespace(Name="Pad", TypeId="PartDesign::Pad")
    body = SimpleNamespace(Group=[sketch, pad], Tip=None, Document=document)

    from freecad.TipTrack.tip_controller import scrub_tip_to_position

    assert scrub_tip_to_position(body, 2) is pad
    assert body.Tip is pad
    assert document.recompute_count == 1


def test_hide_body_and_all_group_features_marks_invisible(mock_freecad):
    """hide_body_and_all_group_features turns off Body and every Group ViewObject."""
    vo_b = SimpleNamespace(Visibility=True)
    vo_a = SimpleNamespace(Visibility=True)
    vo_b_feat = SimpleNamespace(Visibility=True)
    a = SimpleNamespace(Name="A", ViewObject=vo_a)
    b = SimpleNamespace(Name="B", ViewObject=vo_b_feat)
    body = SimpleNamespace(Name="Body", Group=[a, b], ViewObject=vo_b)

    from freecad.TipTrack.tip_controller import hide_body_and_all_group_features

    hide_body_and_all_group_features(body)
    assert vo_b.Visibility is False
    assert vo_a.Visibility is False
    assert vo_b_feat.Visibility is False


def test_sketch_only_visibility_pattern(mock_freecad):
    """Sketch-only view: hide body and group, then show only the head feature."""
    vo_body = SimpleNamespace(Visibility=True)
    vo_sk = SimpleNamespace(Visibility=True)
    vo_pad = SimpleNamespace(Visibility=True)
    sketch = SimpleNamespace(Name="Sketch", ViewObject=vo_sk)
    pad = SimpleNamespace(Name="Pad", ViewObject=vo_pad)
    body = SimpleNamespace(Group=[sketch, pad], ViewObject=vo_body)

    from freecad.TipTrack.tip_controller import (
        capture_body_group_visibility,
        hide_captured_viewobjects,
        restore_captured_visibility,
        set_viewobject_visibility,
    )

    cap = capture_body_group_visibility(body)
    hide_captured_viewobjects(cap)
    set_viewobject_visibility(sketch, True)
    assert vo_body.Visibility is False
    assert vo_sk.Visibility is True
    assert vo_pad.Visibility is False

    restore_captured_visibility(cap)
    assert vo_body.Visibility is True
    assert vo_sk.Visibility is True
    assert vo_pad.Visibility is True


def test_visibility_capture_hide_restore_preserves_values(mock_freecad):
    """Pre-history hide/restore round-trips Body and feature visibility flags."""
    document = _Document()
    vo_b = SimpleNamespace(Visibility=True)
    vo_s = SimpleNamespace(Visibility=False)
    vo_p = SimpleNamespace(Visibility=True)
    sketch = SimpleNamespace(Name="Sketch", ViewObject=vo_s)
    pad = SimpleNamespace(Name="Pad", ViewObject=vo_p)
    body = SimpleNamespace(Name="Body", Group=[sketch, pad], ViewObject=vo_b, Document=document)

    from freecad.TipTrack.tip_controller import (
        capture_body_group_visibility,
        hide_captured_viewobjects,
        restore_captured_visibility,
    )

    cap = capture_body_group_visibility(body)
    hide_captured_viewobjects(cap)
    assert vo_b.Visibility is False
    assert vo_s.Visibility is False
    assert vo_p.Visibility is False

    restore_captured_visibility(cap)
    assert vo_b.Visibility is True
    assert vo_s.Visibility is False
    assert vo_p.Visibility is True


def test_apply_scrub_visibility_matches_five_frame_demo_states(mock_freecad):
    """Scrub visibility reveals only the geometry for the active timeline state."""
    vo_body = SimpleNamespace(Visibility=True)
    vo_square = SimpleNamespace(Visibility=True)
    vo_cube = SimpleNamespace(Visibility=True)
    vo_hole_sketch = SimpleNamespace(Visibility=True)
    vo_hole_pocket = SimpleNamespace(Visibility=True)
    square = SimpleNamespace(Name="SquareSketch", ViewObject=vo_square)
    cube = SimpleNamespace(Name="CubePad", ViewObject=vo_cube)
    hole_sketch = SimpleNamespace(Name="HoleSketch", ViewObject=vo_hole_sketch)
    hole_pocket = SimpleNamespace(Name="HolePocket", ViewObject=vo_hole_pocket)
    body = SimpleNamespace(
        Name="Body",
        Group=[square, cube, hole_sketch, hole_pocket],
        ViewObject=vo_body,
    )

    from freecad.TipTrack.tip_controller import (
        apply_scrub_visibility,
        capture_body_group_visibility,
    )

    cap = capture_body_group_visibility(body)

    apply_scrub_visibility(cap, body, 0, None, None)
    assert [vo_body.Visibility, vo_square.Visibility, vo_cube.Visibility] == [
        False,
        False,
        False,
    ]
    assert vo_hole_sketch.Visibility is False
    assert vo_hole_pocket.Visibility is False

    apply_scrub_visibility(cap, body, 1, square, None)
    assert vo_body.Visibility is True
    assert vo_square.Visibility is True
    assert vo_cube.Visibility is False
    assert vo_hole_sketch.Visibility is False
    assert vo_hole_pocket.Visibility is False

    apply_scrub_visibility(cap, body, 2, cube, cube)
    assert vo_body.Visibility is True
    assert vo_square.Visibility is False
    assert vo_cube.Visibility is True
    assert vo_hole_sketch.Visibility is False
    assert vo_hole_pocket.Visibility is False

    apply_scrub_visibility(cap, body, 3, hole_sketch, cube)
    assert vo_body.Visibility is True
    assert vo_square.Visibility is False
    assert vo_cube.Visibility is True
    assert vo_hole_sketch.Visibility is True
    assert vo_hole_pocket.Visibility is False

    apply_scrub_visibility(cap, body, 4, hole_pocket, hole_pocket)
    assert vo_body.Visibility is True
    assert vo_square.Visibility is False
    assert vo_cube.Visibility is False
    assert vo_hole_sketch.Visibility is False
    assert vo_hole_pocket.Visibility is True


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
