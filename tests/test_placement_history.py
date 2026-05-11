# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Tests for TipTrack placement history helpers.

"""Tests for placement snapshot storage and unified timeline assembly."""

from types import SimpleNamespace


class _Body:
    """Minimal Body stand-in that supports addProperty/setEditorMode + getattr."""

    def __init__(self, *, group=None, tip=None, placement=None):
        self.Group = list(group or [])
        self.Tip = tip
        self.Placement = placement
        self._added: list[tuple] = []
        self._editor_modes: dict[str, int] = {}

    def addProperty(self, property_type, name, group, description):
        self._added.append((property_type, name, group, description))
        setattr(self, name, "")

    def setEditorMode(self, name, mode):
        self._editor_modes[name] = mode


def _feature(name):
    return SimpleNamespace(Name=name, Label=name)


def _placement(base=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0), angle_rad=0.0):
    base_vec = SimpleNamespace(x=base[0], y=base[1], z=base[2])
    axis_vec = SimpleNamespace(x=axis[0], y=axis[1], z=axis[2])
    rotation = SimpleNamespace(Axis=axis_vec, Angle=angle_rad)
    return SimpleNamespace(Base=base_vec, Rotation=rotation)


def test_ensure_property_adds_hidden_string_property(mock_freecad):
    """ensure_property writes the JSON string property and hides it from the editor."""
    body = _Body()

    from freecad.TipTrack.placement_history import (
        PROPERTY_NAME,
        PROPERTY_TYPE,
        ensure_property,
    )

    ensure_property(body)
    assert len(body._added) == 1
    prop_type, prop_name, _group, _desc = body._added[0]
    assert prop_type == PROPERTY_TYPE
    assert prop_name == PROPERTY_NAME
    assert body._editor_modes.get(PROPERTY_NAME) == 2


def test_ensure_property_is_idempotent(mock_freecad):
    """ensure_property does not re-add the property when it already exists."""
    body = _Body()

    from freecad.TipTrack.placement_history import ensure_property

    ensure_property(body)
    ensure_property(body)
    assert len(body._added) == 1


def test_placement_to_dict_serializes_base_and_rotation(mock_freecad):
    """placement_to_dict converts axis/angle to axis + degrees."""
    placement = _placement(base=(1.0, 2.0, 3.0), axis=(0.0, 0.0, 1.0), angle_rad=3.141592653589793)

    from freecad.TipTrack.placement_history import placement_to_dict

    data = placement_to_dict(placement)
    assert data["base"] == [1.0, 2.0, 3.0]
    assert data["rot"][:3] == [0.0, 0.0, 1.0]
    assert abs(data["rot"][3] - 180.0) < 1e-6


def test_append_snapshot_stores_anchor_from_tip(mock_freecad):
    """append_snapshot uses Body.Tip.Name as the anchor when no anchor is given."""
    tip = _feature("Pad")
    body = _Body(group=[_feature("Sketch"), tip], tip=tip, placement=_placement())

    from freecad.TipTrack.placement_history import append_snapshot, get_snapshots

    snap = append_snapshot(body, body.Placement)
    assert snap is not None
    assert snap["anchor"] == "Pad"
    assert snap["label"] == "Moved"

    stored = get_snapshots(body)
    assert len(stored) == 1
    assert stored[0]["id"] == snap["id"]


def test_record_baseline_if_missing_only_runs_once(mock_freecad):
    """record_baseline_if_missing adds exactly one baseline per Body."""
    body = _Body(placement=_placement(base=(5.0, 0.0, 0.0)))

    from freecad.TipTrack.placement_history import (
        BASELINE_SNAPSHOT_LABEL,
        get_snapshots,
        record_baseline_if_missing,
    )

    first = record_baseline_if_missing(body)
    assert first is not None
    assert first["label"] == BASELINE_SNAPSHOT_LABEL
    assert get_snapshots(body)[0]["base"] == [5.0, 0.0, 0.0]

    again = record_baseline_if_missing(body)
    assert again is None
    assert len(get_snapshots(body)) == 1


def test_record_baseline_anchors_to_current_tip(mock_freecad):
    """Baseline anchor is the current Body.Tip.Name."""
    pad = _feature("Pad")
    body = _Body(group=[_feature("Sketch"), pad], tip=pad, placement=_placement())

    from freecad.TipTrack.placement_history import (
        get_snapshots,
        record_baseline_if_missing,
    )

    record_baseline_if_missing(body)
    assert get_snapshots(body)[0]["anchor"] == "Pad"


def test_record_baseline_with_empty_body_uses_empty_anchor(mock_freecad):
    """A Body with no Tip stores baseline with an empty anchor (pre-history slot)."""
    body = _Body(placement=_placement())

    from freecad.TipTrack.placement_history import (
        get_snapshots,
        record_baseline_if_missing,
    )

    record_baseline_if_missing(body)
    assert get_snapshots(body)[0]["anchor"] == ""


def test_get_snapshots_recovers_from_invalid_json(mock_freecad):
    """Corrupt history JSON does not crash readers."""
    body = _Body()
    setattr(body, "Group_TipTrackPlacements", "{not json")

    from freecad.TipTrack.placement_history import get_snapshots

    assert get_snapshots(body) == []


def test_remove_snapshot_drops_entry(mock_freecad):
    """remove_snapshot removes by id and returns True only when something changed."""
    body = _Body(placement=_placement())

    from freecad.TipTrack.placement_history import (
        append_snapshot,
        get_snapshots,
        remove_snapshot,
    )

    snap = append_snapshot(body, body.Placement)
    assert snap is not None
    assert remove_snapshot(body, snap["id"]) is True
    assert get_snapshots(body) == []
    assert remove_snapshot(body, snap["id"]) is False


def test_rename_snapshot_updates_label(mock_freecad):
    """rename_snapshot updates the label and falls back to default on empty input."""
    body = _Body(placement=_placement())

    from freecad.TipTrack.placement_history import (
        DEFAULT_SNAPSHOT_LABEL,
        append_snapshot,
        find_snapshot,
        rename_snapshot,
    )

    snap = append_snapshot(body, body.Placement)
    assert snap is not None
    assert rename_snapshot(body, snap["id"], "Custom") is True
    assert find_snapshot(body, snap["id"])["label"] == "Custom"
    assert rename_snapshot(body, snap["id"], "   ") is True
    assert find_snapshot(body, snap["id"])["label"] == DEFAULT_SNAPSHOT_LABEL


def test_build_items_interleaves_features_and_snapshots(mock_freecad):
    """Snapshots sit after their anchor; empty-anchor snapshots go to the front."""
    sketch = _feature("Sketch")
    pad = _feature("Pad")
    pocket = _feature("Pocket")
    body = _Body(group=[sketch, pad, pocket])

    # Pre-set the property with three snapshots: baseline (no anchor), move-after-Pad,
    # move-anchored-to-deleted-feature.
    import json

    snaps = [
        {
            "id": "a",
            "anchor": "",
            "base": [0, 0, 0],
            "rot": [0, 0, 1, 0],
            "label": "Baseline",
            "ts": "t0",
        },
        {
            "id": "b",
            "anchor": "Pad",
            "base": [10, 0, 0],
            "rot": [0, 0, 1, 0],
            "label": "Right",
            "ts": "t1",
        },
        {
            "id": "c",
            "anchor": "Missing",
            "base": [0, 5, 0],
            "rot": [0, 0, 1, 0],
            "label": "Stale",
            "ts": "t2",
        },
    ]
    setattr(body, "Group_TipTrackPlacements", json.dumps(snaps))

    from freecad.TipTrack.placement_history import KIND_PLACEMENT, build_items

    items = build_items(body)
    # Expected ordering: a, c (orphan), Sketch, Pad, b, Pocket
    assert [item.kind for item in items] == [
        "placement",
        "placement",
        "feature",
        "feature",
        "placement",
        "feature",
    ]
    assert items[0].snapshot["id"] == "a"
    assert items[1].snapshot["id"] == "c"
    assert items[4].snapshot["id"] == "b"
    assert items[4].kind == KIND_PLACEMENT


def test_build_items_with_empty_history_returns_features_only(mock_freecad):
    """No snapshots means the item list is just the features."""
    sketch = _feature("Sketch")
    body = _Body(group=[sketch])

    from freecad.TipTrack.placement_history import build_items

    items = build_items(body)
    assert len(items) == 1
    assert items[0].is_feature
    assert items[0].feature is sketch


def test_feature_index_to_item_position_maps_through_placements(mock_freecad):
    """Mapping accounts for placement cards interleaved between features."""
    sketch = _feature("Sketch")
    pad = _feature("Pad")
    pocket = _feature("Pocket")
    body = _Body(group=[sketch, pad, pocket])

    import json

    setattr(
        body,
        "Group_TipTrackPlacements",
        json.dumps(
            [
                {"id": "a", "anchor": "", "base": [0, 0, 0], "rot": [0, 0, 1, 0]},
                {"id": "b", "anchor": "Pad", "base": [10, 0, 0], "rot": [0, 0, 1, 0]},
            ]
        ),
    )

    from freecad.TipTrack.placement_history import (
        build_items,
        feature_index_to_item_position,
    )

    items = build_items(body)
    assert feature_index_to_item_position(items, 0) == 2  # Sketch sits at item 1 (after baseline)
    assert feature_index_to_item_position(items, 1) == 3  # Pad
    assert feature_index_to_item_position(items, 2) == 5  # Pocket (after Pad+move)
