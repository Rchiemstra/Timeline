# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Placement history storage and timeline assembly for TipTrack.

"""Body Placement snapshots and unified timeline-item assembly.

A *placement snapshot* records ``body.Placement`` at a moment in time, anchored
to the feature that was ``body.Tip`` when the snapshot was taken. Snapshots are
persisted as a JSON-string property on the Body (same convention as
:mod:`freecad.TipTrack.folders`) so they survive save/reopen and travel with
the Body across documents.

Timeline assembly interleaves the Body's feature list with placement snapshots
in chronological order. Snapshots whose anchor is empty (or refers to a feature
no longer present) are placed before the first feature; otherwise each snapshot
sits immediately after its anchor feature, preserving the order in which they
were captured.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Iterable

PROPERTY_NAME = "Group_TipTrackPlacements"
PROPERTY_TYPE = "App::PropertyString"
PROPERTY_GROUP = "TipTrack"

KIND_FEATURE = "feature"
KIND_PLACEMENT = "placement"

PLACEMENT_TYPE_ID = "TipTrack::PlacementSnapshot"
DEFAULT_SNAPSHOT_LABEL = "Moved"
BASELINE_SNAPSHOT_LABEL = "Baseline"


def _safe_attr(obj, name, default=None):
    try:
        return getattr(obj, name, default)
    except ReferenceError:
        return default


def ensure_property(body) -> None:
    """Ensure body has the JSON string property used for placement snapshots."""
    if body is None:
        return
    if hasattr(body, PROPERTY_NAME):
        return

    add_property = getattr(body, "addProperty", None)
    if add_property is None:
        return
    add_property(
        PROPERTY_TYPE,
        PROPERTY_NAME,
        PROPERTY_GROUP,
        "TipTrack placement snapshots",
    )
    setattr(body, PROPERTY_NAME, "[]")
    set_editor_mode = getattr(body, "setEditorMode", None)
    if set_editor_mode is not None:
        try:
            set_editor_mode(PROPERTY_NAME, 2)
        except Exception:
            pass


def _coerce_snapshot(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    base = raw.get("base") or [0.0, 0.0, 0.0]
    rot = raw.get("rot") or [0.0, 0.0, 1.0, 0.0]
    try:
        base = [float(base[0]), float(base[1]), float(base[2])]
        rot = [float(rot[0]), float(rot[1]), float(rot[2]), float(rot[3])]
    except (TypeError, ValueError, IndexError):
        return None
    return {
        "id": str(raw.get("id") or uuid.uuid4().hex),
        "anchor": str(raw.get("anchor") or ""),
        "base": base,
        "rot": rot,
        "label": str(raw.get("label") or DEFAULT_SNAPSHOT_LABEL),
        "ts": str(raw.get("ts") or ""),
    }


def get_snapshots(body) -> list[dict]:
    """Return the ordered list of placement snapshots stored on body."""
    if body is None:
        return []
    raw_value = _safe_attr(body, PROPERTY_NAME, "[]") or "[]"
    try:
        values = json.loads(raw_value)
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    coerced = []
    for entry in values:
        snap = _coerce_snapshot(entry)
        if snap is not None:
            coerced.append(snap)
    return coerced


def set_snapshots(body, snapshots: Iterable[dict]) -> None:
    """Persist snapshots on body (replaces the full list)."""
    if body is None:
        return
    ensure_property(body)
    coerced = [s for s in (_coerce_snapshot(s) for s in snapshots) if s is not None]
    setattr(body, PROPERTY_NAME, json.dumps(coerced, sort_keys=True))


def placement_to_dict(placement) -> dict:
    """Serialize a FreeCAD ``Placement`` into snapshot-compatible primitives.

    Accepts anything exposing ``Base`` (with ``.x``, ``.y``, ``.z`` or iterable)
    and ``Rotation`` (with ``Axis`` and ``Angle``). Returns a dict with keys
    ``base`` (``[x, y, z]``) and ``rot`` (``[ax, ay, az, angle_degrees]``).
    """
    base = _safe_attr(placement, "Base", None)
    bx, by, bz = _xyz(base)

    rotation = _safe_attr(placement, "Rotation", None)
    axis = _safe_attr(rotation, "Axis", None)
    ax, ay, az = _xyz(axis, default=(0.0, 0.0, 1.0))
    angle = float(_safe_attr(rotation, "Angle", 0.0) or 0.0)
    angle_deg = angle * 180.0 / 3.141592653589793

    return {"base": [bx, by, bz], "rot": [ax, ay, az, angle_deg]}


def _xyz(vec, default=(0.0, 0.0, 0.0)):
    if vec is None:
        return default
    x = _safe_attr(vec, "x", None)
    if x is not None:
        return (
            float(x or 0.0),
            float(_safe_attr(vec, "y", 0.0) or 0.0),
            float(_safe_attr(vec, "z", 0.0) or 0.0),
        )
    try:
        return (float(vec[0]), float(vec[1]), float(vec[2]))
    except (TypeError, ValueError, IndexError):
        return default


def snapshot_for_placement(placement, *, anchor: str, label: str | None = None) -> dict:
    """Build a snapshot dict from a FreeCAD ``Placement`` value."""
    base_rot = placement_to_dict(placement)
    return {
        "id": uuid.uuid4().hex,
        "anchor": str(anchor or ""),
        "base": base_rot["base"],
        "rot": base_rot["rot"],
        "label": str(label or DEFAULT_SNAPSHOT_LABEL),
        "ts": _now_iso(),
    }


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def tip_anchor_name(body) -> str:
    """Return the Name of ``body.Tip`` (or ``""`` when no tip is set)."""
    tip = _safe_attr(body, "Tip", None)
    if tip is None:
        return ""
    return str(_safe_attr(tip, "Name", "") or "")


def append_snapshot(
    body,
    placement,
    *,
    anchor: str | None = None,
    label: str | None = None,
) -> dict | None:
    """Append a snapshot of placement to body and persist.

    Returns the new snapshot dict, or ``None`` when body cannot carry the
    property (e.g. tests without ``addProperty``).
    """
    if body is None:
        return None
    ensure_property(body)
    if not hasattr(body, PROPERTY_NAME):
        return None

    anchor_value = anchor if anchor is not None else tip_anchor_name(body)
    snap = snapshot_for_placement(placement, anchor=anchor_value, label=label)
    snaps = get_snapshots(body)
    snaps.append(snap)
    set_snapshots(body, snaps)
    return snap


def remove_snapshot(body, snapshot_id: str) -> bool:
    """Remove the snapshot with snapshot_id; return True when something was removed."""
    if body is None or not snapshot_id:
        return False
    snaps = get_snapshots(body)
    new_snaps = [s for s in snaps if s["id"] != snapshot_id]
    if len(new_snaps) == len(snaps):
        return False
    set_snapshots(body, new_snaps)
    return True


def rename_snapshot(body, snapshot_id: str, label: str) -> bool:
    """Rename the snapshot with snapshot_id; return True on success."""
    if body is None or not snapshot_id:
        return False
    cleaned = (label or "").strip() or DEFAULT_SNAPSHOT_LABEL
    snaps = get_snapshots(body)
    changed = False
    for snap in snaps:
        if snap["id"] == snapshot_id:
            snap["label"] = cleaned
            changed = True
            break
    if changed:
        set_snapshots(body, snaps)
    return changed


def find_snapshot(body, snapshot_id: str) -> dict | None:
    """Return the snapshot dict matching snapshot_id, or None."""
    if not snapshot_id:
        return None
    for snap in get_snapshots(body):
        if snap["id"] == snapshot_id:
            return snap
    return None


def record_baseline_if_missing(body) -> dict | None:
    """Record a baseline snapshot for body when no snapshots exist yet.

    Returns the new baseline snapshot, or ``None`` when one already exists or
    the body cannot carry the property. Called once per Body when TipTrack first
    observes it so the timeline can scrub back to the original placement.
    """
    if body is None:
        return None
    ensure_property(body)
    if not hasattr(body, PROPERTY_NAME):
        return None
    if get_snapshots(body):
        return None
    placement = _safe_attr(body, "Placement", None)
    if placement is None:
        return None
    return append_snapshot(
        body,
        placement,
        anchor=tip_anchor_name(body),
        label=BASELINE_SNAPSHOT_LABEL,
    )


class TimelineItem:
    """One entry in the unified TipTrack timeline.

    Items wrap either a real FreeCAD feature (``kind == KIND_FEATURE``) or a
    placement snapshot dict (``kind == KIND_PLACEMENT``). The widgets in
    :mod:`freecad.TipTrack.strip` and :mod:`freecad.TipTrack.timeline_scrubber`
    treat the two kinds uniformly for layout and selection, and branch only
    when applying scrub effects (tip target vs. Body placement).
    """

    __slots__ = ("kind", "feature", "snapshot")

    def __init__(self, kind: str, *, feature=None, snapshot: dict | None = None):
        self.kind = kind
        self.feature = feature
        self.snapshot = snapshot

    @classmethod
    def for_feature(cls, feature) -> "TimelineItem":
        return cls(KIND_FEATURE, feature=feature)

    @classmethod
    def for_snapshot(cls, snapshot: dict) -> "TimelineItem":
        return cls(KIND_PLACEMENT, snapshot=snapshot)

    @property
    def is_feature(self) -> bool:
        return self.kind == KIND_FEATURE

    @property
    def is_placement(self) -> bool:
        return self.kind == KIND_PLACEMENT

    @property
    def name(self) -> str:
        if self.is_feature:
            return str(_safe_attr(self.feature, "Name", "") or "")
        return f"placement::{(self.snapshot or {}).get('id', '')}"

    @property
    def label(self) -> str:
        if self.is_feature:
            return str(
                _safe_attr(self.feature, "Label", None)
                or _safe_attr(self.feature, "Name", "")
                or ""
            )
        return str((self.snapshot or {}).get("label") or DEFAULT_SNAPSHOT_LABEL)

    @property
    def type_id(self) -> str:
        if self.is_feature:
            return str(_safe_attr(self.feature, "TypeId", "") or "")
        return PLACEMENT_TYPE_ID


def build_items(body, *, features: Iterable | None = None) -> list[TimelineItem]:
    """Interleave body.Group features with stored placement snapshots.

    Snapshots are placed:

    * before the first feature when their ``anchor`` is empty,
    * after their anchor feature when the anchor is present in ``body.Group``,
    * before the first feature when the anchor refers to a missing feature
      (its anchor was deleted), so they always remain reachable on the strip.

    Snapshots sharing the same anchor preserve insertion order.
    """
    feats = (
        list(features)
        if features is not None
        else list(_safe_attr(body, "Group", []) or [])
    )
    snaps = get_snapshots(body)
    feature_names = {
        str(_safe_attr(f, "Name", "") or ""): index for index, f in enumerate(feats)
    }

    pre_history: list[dict] = []
    after_feature: dict[int, list[dict]] = {}
    for snap in snaps:
        anchor = snap["anchor"]
        if not anchor or anchor not in feature_names:
            pre_history.append(snap)
            continue
        after_feature.setdefault(feature_names[anchor], []).append(snap)

    items: list[TimelineItem] = [TimelineItem.for_snapshot(s) for s in pre_history]
    for index, feat in enumerate(feats):
        items.append(TimelineItem.for_feature(feat))
        for snap in after_feature.get(index, []):
            items.append(TimelineItem.for_snapshot(snap))
    return items


def features_only(items: Iterable[TimelineItem]) -> list:
    """Return just the FreeCAD features from a list of timeline items."""
    return [item.feature for item in items if item.is_feature]


def feature_index_to_item_position(items: list[TimelineItem], feature_index: int) -> int:
    """Map a Body.Group index to its 1-based slider position in items.

    Returns ``0`` when ``feature_index`` is negative or there are no features.
    """
    if feature_index < 0:
        return 0
    seen = -1
    for item_index, item in enumerate(items):
        if item.is_feature:
            seen += 1
            if seen == feature_index:
                return item_index + 1
    return 0


def item_position_to_feature_gap(items: list[TimelineItem], item_gap_index: int) -> int:
    """Map an item-level gap index to a Body.Group gap index.

    Used by drag-and-drop reorder: the strip computes a gap between items
    (which include placement cards), but ``move_feature`` operates on
    ``Body.Group`` only.
    """
    feature_gap = 0
    for item in items[:item_gap_index]:
        if item.is_feature:
            feature_gap += 1
    return feature_gap
