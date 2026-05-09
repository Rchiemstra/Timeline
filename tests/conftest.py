# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Test fixtures for TipTrack.

"""Shared pytest fixtures for TipTrack tests."""

from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _DocumentObserver:
    """Small stand-in for FreeCAD's App.DocumentObserver."""


@pytest.fixture
def mock_freecad(monkeypatch):
    """Install minimal FreeCAD and FreeCADGui modules in sys.modules."""
    for module_name in (
        "freecad.TipTrack.body_resolver",
        "freecad.TipTrack.observer",
        "freecad.TipTrack.tip_controller",
    ):
        sys.modules.pop(module_name, None)

    app = SimpleNamespace(
        ActiveDocument=None,
        DocumentObserver=_DocumentObserver,
        GuiUp=False,
    )
    gui = SimpleNamespace(ActiveDocument=None)

    monkeypatch.setitem(sys.modules, "FreeCAD", app)
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)

    return app, gui
