# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Body tip mutation helpers for TipTrack.

"""Small wrappers around FreeCAD mutations that affect Body history."""

from contextlib import contextmanager

import FreeCAD as App

from freecad.TipTrack.body_resolver import safe_getattr
from freecad.TipTrack.placement_history import (
    KIND_FEATURE,
    KIND_PLACEMENT,
    TimelineItem,
)

# Re-entrancy guard for the observer: bumped while TipTrack itself is writing
# body.Placement so the observer can skip its own scrub-induced changes.
_placement_capture_suspended = 0


def is_placement_capture_suspended() -> bool:
    """True while TipTrack is actively writing body.Placement (do not capture)."""
    return _placement_capture_suspended > 0


@contextmanager
def suspend_placement_capture():
    """Context manager bracketing mutations that must not trigger snapshots."""
    global _placement_capture_suspended
    _placement_capture_suspended += 1
    try:
        yield
    finally:
        _placement_capture_suspended = max(0, _placement_capture_suspended - 1)


def _document_for(obj):
    return getattr(obj, "Document", None) or getattr(App, "ActiveDocument", None)


def _recompute(obj) -> None:
    document = _document_for(obj)
    if document is not None:
        document.recompute()


def set_tip(body, feature) -> None:
    """Set body.Tip to feature and recompute the document."""
    if body is None:
        raise ValueError("Cannot set tip without an active Body.")
    if feature is None:
        raise ValueError("Cannot set tip without a feature.")

    body.Tip = feature
    _recompute(body)


def can_be_tip(feature) -> bool:
    """Return whether feature is a safe Body.Tip target."""
    type_id = str(getattr(feature, "TypeId", ""))
    return type_id.startswith("PartDesign::") and type_id != "PartDesign::Body"


def tip_for_scrub_index(body, index: int):
    """Return the nearest safe tip target at or before Body.Group[index]."""
    features = list(getattr(body, "Group", []) or [])
    if not features:
        return None

    safe_index = max(0, min(index, len(features) - 1))
    for feature in reversed(features[: safe_index + 1]):
        if can_be_tip(feature):
            return feature
    return None


def scrub_tip_to_position(body, position: int):
    """Roll the Body to a timeline slider position and return the feature used as Tip.

    Position ``0`` clears ``Body.Tip`` (pre-history). Positions ``1..N`` map to
    features ``Group[0]..Group[N-1]`` by setting Tip to the nearest safe
    PartDesign tip at or before ``Group[position - 1]``.
    """
    if body is None:
        raise ValueError("Cannot scrub without an active Body.")

    features = list(getattr(body, "Group", []) or [])
    n = len(features)
    pos = max(0, min(int(position), n))
    if pos == 0:
        body.Tip = None
        _recompute(body)
        return None

    tip_target = tip_for_scrub_index(body, pos - 1)
    body.Tip = tip_target
    _recompute(body)
    return tip_target


def scrub_tip_to_index(body, index: int):
    """Roll body to feature ``Group[index]`` (same as ``scrub_tip_to_position(body, index + 1)``)."""
    if body is None:
        raise ValueError("Cannot scrub without an active Body.")

    features = list(getattr(body, "Group", []) or [])
    if not features:
        return scrub_tip_to_position(body, 0)

    safe_index = max(0, min(int(index), len(features) - 1))
    return scrub_tip_to_position(body, safe_index + 1)


def capture_body_group_visibility(body):
    """Snapshot ``ViewObject.Visibility`` for the Body and its ``Group`` children."""
    if body is None:
        return []
    items = [body] + list(getattr(body, "Group", []) or [])
    capture = []
    for obj in items:
        vo = safe_getattr(obj, "ViewObject", None)
        if vo is None or not hasattr(vo, "Visibility"):
            continue
        capture.append((obj, bool(safe_getattr(vo, "Visibility", True))))
    return capture


def hide_captured_viewobjects(capture) -> None:
    """Force every captured object invisible (used at pre-history position)."""
    for obj, _ in capture:
        vo = safe_getattr(obj, "ViewObject", None)
        if vo is not None and hasattr(vo, "Visibility"):
            vo.Visibility = False


def restore_captured_visibility(capture) -> None:
    """Restore visibilities from :func:`capture_body_group_visibility`."""
    for obj, vis in capture:
        vo = safe_getattr(obj, "ViewObject", None)
        if vo is not None and hasattr(vo, "Visibility"):
            vo.Visibility = vis


def apply_scrub_visibility(capture, body, position: int, head_feature, tip_target) -> None:
    """Show the viewport state that matches a scrubber position.

    Scrub mode hides every captured Body/group object first, then reveals only
    the objects needed for the active rollback state. This keeps future sketches
    from leaking into earlier solid states while still allowing the current
    sketch to be previewed on top of the previous solid.
    """
    if not capture:
        return

    hide_captured_viewobjects(capture)
    pos = int(position)
    if pos <= 0:
        return

    if tip_target is not None:
        set_viewobject_visibility(body, True)
        set_viewobject_visibility(tip_target, True)
        if head_feature is not tip_target:
            set_viewobject_visibility(head_feature, True)
        return

    set_viewobject_visibility(body, True)
    set_viewobject_visibility(head_feature, True)


def hide_body_and_all_group_features(body) -> None:
    """Set ``ViewObject.Visibility`` False on the Body and every object in ``Body.Group``."""
    if body is None:
        return
    for obj in [body] + list(getattr(body, "Group", []) or []):
        vo = safe_getattr(obj, "ViewObject", None)
        if vo is not None and hasattr(vo, "Visibility"):
            vo.Visibility = False


def set_viewobject_visibility(obj, visible: bool) -> None:
    """Assign ``ViewObject.Visibility`` when the object exposes a ViewObject."""
    vo = safe_getattr(obj, "ViewObject", None)
    if vo is not None and hasattr(vo, "Visibility"):
        vo.Visibility = bool(visible)


def toggle_suppression(feature) -> bool:
    """Toggle feature.Suppressed and recompute, returning the new value."""
    if not hasattr(feature, "Suppressed"):
        raise ValueError("This feature does not support suppression.")

    feature.Suppressed = not bool(feature.Suppressed)
    _recompute(feature)
    return bool(feature.Suppressed)


def build_placement_from_snapshot(snapshot: dict):
    """Construct a FreeCAD ``Placement`` from a stored snapshot dict.

    Returns ``None`` when the running FreeCAD build does not expose
    ``Vector``/``Rotation``/``Placement`` (e.g. headless tests without the
    real ``FreeCAD`` module).
    """
    if not snapshot:
        return None
    base = snapshot.get("base") or [0.0, 0.0, 0.0]
    rot = snapshot.get("rot") or [0.0, 0.0, 1.0, 0.0]

    vector_factory = getattr(App, "Vector", None)
    rotation_factory = getattr(App, "Rotation", None)
    placement_factory = getattr(App, "Placement", None)
    if vector_factory is None or rotation_factory is None or placement_factory is None:
        return None

    try:
        base_vec = vector_factory(float(base[0]), float(base[1]), float(base[2]))
        axis_vec = vector_factory(float(rot[0]), float(rot[1]), float(rot[2]))
        rotation = rotation_factory(axis_vec, float(rot[3]))
        return placement_factory(base_vec, rotation)
    except Exception:
        return None


def apply_snapshot_placement(body, snapshot: dict) -> bool:
    """Assign body.Placement from snapshot inside a capture-suspend scope.

    Returns ``True`` when ``body.Placement`` was assigned, ``False`` otherwise
    (e.g. body has no ``Placement``, the snapshot is empty, or FreeCAD's
    placement factories are unavailable in the current environment).
    """
    if body is None or not snapshot or not hasattr(body, "Placement"):
        return False
    placement = build_placement_from_snapshot(snapshot)
    if placement is None:
        return False
    with suspend_placement_capture():
        body.Placement = placement
    return True


def _latest_of_kind(items: list, position: int, kind: str):
    last = None
    for item in items[:position]:
        if item.kind == kind:
            last = item
    return last


def _latest_feature_item_safe_tip(items: list, position: int):
    """Return the latest feature item in items[:position] that can be a Tip."""
    last = None
    for item in items[:position]:
        if item.kind == KIND_FEATURE and can_be_tip(item.feature):
            last = item
    return last


def scrub_items_to_position(body, items, position: int) -> tuple:
    """Roll body to a unified-timeline slider position.

    The unified timeline interleaves PartDesign features with placement
    snapshots (see :mod:`freecad.TipTrack.placement_history`). For each
    slider position, the Body tip is set to the nearest preceding safe
    PartDesign feature, and the Body placement is set to the nearest
    preceding placement snapshot (if any).

    Returns ``(tip_target, applied_snapshot)``: either may be ``None``.
    Position ``0`` clears the tip and restores the earliest placement
    snapshot (the baseline) so the timeline's pre-history matches the
    Body's original placement.
    """
    if body is None:
        raise ValueError("Cannot scrub without an active Body.")

    items = list(items or [])
    n = len(items)
    pos = max(0, min(int(position), n))

    if pos == 0:
        with suspend_placement_capture():
            body.Tip = None
        baseline_item = next(
            (item for item in items if item.kind == KIND_PLACEMENT), None
        )
        applied = None
        if baseline_item is not None:
            if apply_snapshot_placement(body, baseline_item.snapshot):
                applied = baseline_item.snapshot
        _recompute(body)
        return (None, applied)

    tip_item = _latest_feature_item_safe_tip(items, pos)
    tip_target = tip_item.feature if tip_item is not None else None
    placement_item = _latest_of_kind(items, pos, KIND_PLACEMENT)
    applied_snapshot = placement_item.snapshot if placement_item is not None else None

    with suspend_placement_capture():
        body.Tip = tip_target
    if applied_snapshot is not None:
        apply_snapshot_placement(body, applied_snapshot)
    _recompute(body)
    return (tip_target, applied_snapshot)


def head_item_at_position(items: list, position: int) -> TimelineItem | None:
    """Return the item directly under the playhead for unified slider position."""
    if position <= 0 or not items:
        return None
    safe = max(0, min(int(position), len(items)))
    return items[safe - 1]
