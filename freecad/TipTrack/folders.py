# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline folder metadata helpers for TipTrack.

"""Serialize TipTrack-only folder metadata on a PartDesign Body."""

import json

PROPERTY_NAME = "Group_TipTrackFolders"
PROPERTY_TYPE = "App::PropertyString"
PROPERTY_GROUP = "TipTrack"


def ensure_folder_property(body) -> None:
    """Ensure body has the JSON string property used for folder metadata."""
    if hasattr(body, PROPERTY_NAME):
        return

    add_property = getattr(body, "addProperty", None)
    if add_property is None:
        return
    add_property(PROPERTY_TYPE, PROPERTY_NAME, PROPERTY_GROUP, "TipTrack folders")
    setattr(body, PROPERTY_NAME, "[]")


def get_folders(body) -> list[dict]:
    """Return TipTrack folder metadata stored on body."""
    raw_value = getattr(body, PROPERTY_NAME, "[]")
    try:
        value = json.loads(raw_value or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def set_folders(body, folders: list[dict]) -> None:
    """Persist TipTrack folder metadata on body."""
    ensure_folder_property(body)
    setattr(body, PROPERTY_NAME, json.dumps(folders, sort_keys=True))
