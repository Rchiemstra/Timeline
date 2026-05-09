# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Phase 0 smoke tests for TipTrack.

"""Smoke tests for the Phase 0 package scaffold."""


def test_tiptrack_package_imports(mock_freecad):
    """The namespace package imports without a running FreeCAD instance."""
    import freecad.TipTrack as tiptrack

    assert tiptrack.__name__ == "freecad.TipTrack"


def test_observer_imports_with_mocked_freecad(mock_freecad):
    """Observer stubs can be imported in a normal Python test process."""
    from freecad.TipTrack.observer import TipTrackObserver

    observer = TipTrackObserver(dock=object())

    assert observer.dock is not None
