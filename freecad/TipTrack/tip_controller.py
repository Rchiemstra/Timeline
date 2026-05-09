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


def toggle_suppression(feature) -> bool:
    """Toggle feature.Suppressed and recompute, returning the new value."""
    if not hasattr(feature, "Suppressed"):
        raise ValueError("This feature does not support suppression.")

    feature.Suppressed = not bool(feature.Suppressed)
    _recompute(feature)
    return bool(feature.Suppressed)

