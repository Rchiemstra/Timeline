# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Body tip mutation helpers for TipTrack.

"""Small wrappers around FreeCAD mutations that affect Body history."""

import FreeCAD as App


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


def scrub_tip_to_index(body, index: int):
    """Roll body back to index and return the feature used as Body.Tip."""
    if body is None:
        raise ValueError("Cannot scrub without an active Body.")

    tip_target = tip_for_scrub_index(body, index)
    body.Tip = tip_target
    _recompute(body)
    return tip_target


def toggle_suppression(feature) -> bool:
    """Toggle feature.Suppressed and recompute, returning the new value."""
    if not hasattr(feature, "Suppressed"):
        raise ValueError("This feature does not support suppression.")

    feature.Suppressed = not bool(feature.Suppressed)
    _recompute(feature)
    return bool(feature.Suppressed)
