# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Tests for TipTrack observer placement-change routing.

"""Observer must forward Body.Placement changes to the dock for capture."""

from types import SimpleNamespace


class _DockSpy:
    """Minimal dock stand-in that records observer-forwarded events."""

    def __init__(self):
        self.body = None
        self.placement_changes: list = []
        self.body_creations: list = []
        self.refresh_calls = 0

    def refresh(self):
        self.refresh_calls += 1

    def handle_body_placement_change(self, body):
        self.placement_changes.append(body)

    def handle_body_created(self, body):
        self.body_creations.append(body)


def _body(name="Body"):
    return SimpleNamespace(Name=name, Label=name, TypeId="PartDesign::Body", Group=[])


def _other_obj(name="Sketch"):
    return SimpleNamespace(
        Name=name,
        Label=name,
        TypeId="Sketcher::SketchObject",
        Group=[],
    )


def test_observer_forwards_body_placement_change_to_dock(mock_freecad):
    """slotChangedObject(body, 'Placement') hits dock.handle_body_placement_change."""
    dock = _DockSpy()
    body = _body()

    from freecad.TipTrack.observer import TipTrackObserver

    observer = TipTrackObserver(dock)
    observer.slotChangedObject(body, "Placement")

    assert dock.placement_changes == [body]
    # Placement changes should NOT trigger a generic refresh by themselves; the
    # dock's capture handler is responsible for refreshing once the snapshot is
    # appended.
    assert dock.refresh_calls == 0


def test_observer_ignores_placement_on_non_body(mock_freecad):
    """A Placement change on a sketch must not produce a placement-capture event."""
    dock = _DockSpy()
    sketch = _other_obj()

    from freecad.TipTrack.observer import TipTrackObserver

    observer = TipTrackObserver(dock)
    observer.slotChangedObject(sketch, "Placement")

    assert dock.placement_changes == []


def test_observer_records_baseline_on_body_creation(mock_freecad):
    """slotCreatedObject for a body calls dock.handle_body_created so baseline runs."""
    dock = _DockSpy()
    body = _body()

    from freecad.TipTrack.observer import TipTrackObserver

    observer = TipTrackObserver(dock)
    observer.slotCreatedObject(body)

    assert dock.body_creations == [body]


def test_observer_still_refreshes_on_group_changes(mock_freecad):
    """Non-Placement property changes continue to refresh the dock as before."""
    dock = _DockSpy()
    dock.body = _body()

    from freecad.TipTrack.observer import TipTrackObserver

    observer = TipTrackObserver(dock)
    observer.slotChangedObject(dock.body, "Group")

    assert dock.refresh_calls == 1
