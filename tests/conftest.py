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


# Stable stubs so modules that bind `import FreeCADGui as Gui` keep the same object
# across tests while `mock_freecad` repatches `sys.modules`.
_fc_app = SimpleNamespace(
    ActiveDocument=None,
    DocumentObserver=_DocumentObserver,
    GuiUp=False,
)
_fc_gui = SimpleNamespace(ActiveDocument=None)


def _reset_fc_stubs() -> None:
    _fc_app.ActiveDocument = None
    _fc_app.GuiUp = False
    _fc_gui.ActiveDocument = None
    for key in tuple(vars(_fc_gui).keys()):
        if key != "ActiveDocument":
            delattr(_fc_gui, key)


@pytest.fixture
def mock_freecad(monkeypatch):
    """Install minimal FreeCAD and FreeCADGui modules in sys.modules."""
    for module_name in (
        "freecad.TipTrack.body_resolver",
        "freecad.TipTrack.observer",
        "freecad.TipTrack.reorder",
        "freecad.TipTrack.tip_controller",
    ):
        sys.modules.pop(module_name, None)

    _reset_fc_stubs()

    monkeypatch.setitem(sys.modules, "FreeCAD", _fc_app)
    monkeypatch.setitem(sys.modules, "FreeCADGui", _fc_gui)

    return _fc_app, _fc_gui
