# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Tests for TipTrack dependency-aware reordering.

"""Tests for feature reorder dependency checks."""

from types import SimpleNamespace


class _Document:
    def __init__(self):
        self.recompute_count = 0

    def recompute(self):
        self.recompute_count += 1


class _Body:
    def __init__(self, features):
        self.Group = list(features)
        self.Document = _Document()

    def removeObject(self, feature):
        self.Group.remove(feature)

    def insertObject(self, feature, target, after=False):
        if target is None:
            self.Group.append(feature)
            return
        index = self.Group.index(target)
        if after:
            index += 1
        self.Group.insert(index, feature)


def _feature(name):
    return SimpleNamespace(Name=name, Label=name, OutList=[], InList=[])


def _link(depender, dependency):
    depender.OutList.append(dependency)
    dependency.InList.append(depender)


def test_can_move_after_own_dependency(mock_freecad):
    """A feature may move while staying after its dependency."""
    sketch = _feature("Sketch")
    pad = _feature("Pad")
    hole = _feature("Hole")
    _link(pad, sketch)
    _link(hole, pad)
    body = _Body([sketch, pad, hole])

    from freecad.TipTrack.reorder import can_move

    assert can_move(body, hole, 2) == (True, "")


def test_cannot_move_before_own_dependency(mock_freecad):
    """A feature cannot be placed before a feature in its OutList."""
    sketch = _feature("Sketch")
    pad = _feature("Pad")
    _link(pad, sketch)
    body = _Body([sketch, pad])

    from freecad.TipTrack.reorder import can_move

    ok, reason = can_move(body, pad, 0)

    assert ok is False
    assert "depends on Sketch" in reason


def test_cannot_move_after_dependent(mock_freecad):
    """A feature cannot move after a feature that depends on it."""
    sketch = _feature("Sketch")
    pad = _feature("Pad")
    hole = _feature("Hole")
    _link(pad, sketch)
    _link(hole, pad)
    body = _Body([sketch, pad, hole])

    from freecad.TipTrack.reorder import can_move

    ok, reason = can_move(body, pad, 2)

    assert ok is False
    assert "Hole depends on Pad" in reason


def test_ignores_dependencies_outside_body(mock_freecad):
    """External dependencies do not constrain Body.Group ordering."""
    external = _feature("Spreadsheet")
    pad = _feature("Pad")
    _link(pad, external)
    body = _Body([pad])

    from freecad.TipTrack.reorder import can_move

    assert can_move(body, pad, 0) == (True, "")


def test_rejects_feature_not_in_body(mock_freecad):
    """Moves for objects outside the active Body are rejected."""
    pad = _feature("Pad")
    loose = _feature("Loose")
    body = _Body([pad])

    from freecad.TipTrack.reorder import can_move

    ok, reason = can_move(body, loose, 0)

    assert ok is False
    assert "not in the active Body" in reason


def test_move_feature_uses_body_insert_api_and_recomputes(mock_freecad):
    """The mutation helper uses removeObject/insertObject and recomputes."""
    sketch = _feature("Sketch")
    pad = _feature("Pad")
    hole = _feature("Hole")
    body = _Body([sketch, pad, hole])

    from freecad.TipTrack.reorder import move_feature

    move_feature(body, hole, 1)

    assert body.Group == [sketch, hole, pad]
    assert body.Document.recompute_count == 1
