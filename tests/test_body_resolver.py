# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Tests for TipTrack Body resolution.

"""Tests for active PartDesign Body resolution."""

from types import SimpleNamespace


def _obj(name, type_id="PartDesign::Feature", group=None):
    return SimpleNamespace(
        Name=name,
        Label=name,
        TypeId=type_id,
        Group=list(group or []),
    )


def _body(name, group=None):
    return _obj(name, "PartDesign::Body", group)


def _configure(mock_freecad, *, objects, selection=None, active_body=None):
    app, gui = mock_freecad
    document = SimpleNamespace(Objects=objects)
    active_view = SimpleNamespace(getActiveObject=lambda role: active_body)
    gui.ActiveDocument = SimpleNamespace(Document=document, ActiveView=active_view)
    gui.Selection = SimpleNamespace(getSelection=lambda: list(selection or []))
    app.ActiveDocument = document
    return app, gui


def test_selected_feature_body_wins(mock_freecad):
    """Selected features resolve to their containing Body."""
    sketch = _obj("Sketch")
    pad = _obj("Pad")
    first = _body("Body", [sketch])
    second = _body("Body001", [pad])
    _configure(mock_freecad, objects=[first, second, sketch, pad], selection=[pad])

    from freecad.TipTrack.body_resolver import get_active_body

    assert get_active_body() is second


def test_active_view_body_is_fallback(mock_freecad):
    """The active PartDesign Body is used when selection does not identify one."""
    first = _body("Body")
    second = _body("Body001")
    _configure(mock_freecad, objects=[first, second], active_body=second)

    from freecad.TipTrack.body_resolver import get_active_body

    assert get_active_body() is second


def test_first_body_is_last_fallback(mock_freecad):
    """The first document Body is used when no better signal exists."""
    first = _body("Body")
    second = _body("Body001")
    _configure(mock_freecad, objects=[first, second])

    from freecad.TipTrack.body_resolver import get_active_body

    assert get_active_body() is first


def test_no_gui_document_returns_none(mock_freecad):
    """No active GUI document means there is no active Body."""
    from freecad.TipTrack.body_resolver import get_active_body

    assert get_active_body() is None
