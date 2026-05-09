# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Active PartDesign Body resolution for TipTrack.

"""Helpers for choosing which PartDesign Body TipTrack should display."""

from collections.abc import Iterable

import FreeCAD as App
import FreeCADGui as Gui

BODY_TYPE_ID = "PartDesign::Body"


def is_body(obj) -> bool:
    """Return True when obj is a PartDesign Body."""
    return getattr(obj, "TypeId", None) == BODY_TYPE_ID


def body_contains(body, obj) -> bool:
    """Return True when obj is the body itself or a direct Body.Group child."""
    if body is obj:
        return True
    return obj in list(getattr(body, "Group", []) or [])


def body_for_object(obj, bodies: Iterable):
    """Return the first body that directly contains obj."""
    if is_body(obj):
        return obj
    for body in bodies:
        if body_contains(body, obj):
            return body
    return None


def _active_app_document():
    gui_doc = getattr(Gui, "ActiveDocument", None)
    if gui_doc is None:
        return None
    return getattr(gui_doc, "Document", None) or getattr(App, "ActiveDocument", None)


def _active_view_body(bodies):
    gui_doc = getattr(Gui, "ActiveDocument", None)
    active_view = getattr(gui_doc, "ActiveView", None)
    get_active_object = getattr(active_view, "getActiveObject", None)
    if get_active_object is None:
        return None

    try:
        body = get_active_object("pdbody")
    except Exception:
        return None

    if body in bodies and is_body(body):
        return body
    return None


def get_active_body():
    """Return the body TipTrack should display, or None if there is no body."""
    document = _active_app_document()
    objects = list(getattr(document, "Objects", []) or []) if document else []
    if not objects:
        return None

    bodies = [obj for obj in objects if is_body(obj)]
    if not bodies:
        return None

    selection = getattr(Gui, "Selection", None)
    get_selection = getattr(selection, "getSelection", None)
    selected_objects = get_selection() if get_selection is not None else []
    for selected in selected_objects:
        body = body_for_object(selected, bodies)
        if body is not None:
            return body

    body = _active_view_body(bodies)
    if body is not None:
        return body

    return bodies[0]

