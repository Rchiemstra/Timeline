# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Tests for TipTrack folder metadata helpers.

"""Tests for TipTrack-only folder metadata stored on Bodies."""


class _Body:
    def __init__(self):
        self.added = []

    def addProperty(self, property_type, name, group, description):
        self.added.append((property_type, name, group, description))


def test_set_folders_adds_property_and_serializes_json(mock_freecad):
    """Folder metadata is stored as deterministic JSON."""
    body = _Body()
    folders = [{"name": "Setup", "start": "Sketch", "end": "Pad"}]

    from freecad.TipTrack.folders import PROPERTY_NAME, get_folders, set_folders

    set_folders(body, folders)

    assert len(body.added) == 1
    assert getattr(body, PROPERTY_NAME)
    assert get_folders(body) == folders


def test_get_folders_recovers_from_invalid_json(mock_freecad):
    """Invalid metadata should not break timeline rendering."""
    body = _Body()
    body.Group_TipTrackFolders = "{bad json"

    from freecad.TipTrack.folders import get_folders

    assert get_folders(body) == []
