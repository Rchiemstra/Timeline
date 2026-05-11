# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Body tip mutation helpers for TipTrack.

"""Small wrappers around FreeCAD mutations that affect Body history."""

import FreeCAD as App

from freecad.TipTrack.body_resolver import safe_getattr


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
