# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: FreeCAD GUI smoke test for TipTrack.

"""Run this script inside FreeCAD GUI to smoke-test TipTrack integration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
import Part

REPO_ROOT = Path(os.environ.get("TIPTRACK_REPO_ROOT", "/work"))
ARTIFACT_DIR = Path(os.environ.get("TIPTRACK_ARTIFACT_DIR", "/work/artifacts"))

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import freecad as freecad_namespace
except ImportError:
    freecad_namespace = None
if freecad_namespace is not None and hasattr(freecad_namespace, "__path__"):
    namespace_path = str(REPO_ROOT / "freecad")
    if namespace_path not in freecad_namespace.__path__:
        freecad_namespace.__path__.append(namespace_path)

from freecad.TipTrack.Qt.Gui import QtWidgets  # noqa: E402
from freecad.TipTrack.dock import TipTrackDock  # noqa: E402
import freecad.TipTrack.init_gui as tiptrack_init_gui  # noqa: E402
from freecad.TipTrack.reorder import can_move  # noqa: E402


def log(message: str) -> None:
    """Print an integration-test line that is easy to grep."""
    print(f"TIPTRACK_INTEGRATION: {message}", flush=True)


def add_rectangle(sketch, x0: float, y0: float, x1: float, y1: float) -> None:
    """Add a closed rectangle to sketch."""
    sketch.addGeometry(
        Part.LineSegment(App.Vector(x0, y0, 0), App.Vector(x1, y0, 0)), False
    )
    sketch.addGeometry(
        Part.LineSegment(App.Vector(x1, y0, 0), App.Vector(x1, y1, 0)), False
    )
    sketch.addGeometry(
        Part.LineSegment(App.Vector(x1, y1, 0), App.Vector(x0, y1, 0)), False
    )
    sketch.addGeometry(
        Part.LineSegment(App.Vector(x0, y1, 0), App.Vector(x0, y0, 0)), False
    )


def create_padded_body():
    """Create a simple PartDesign Body with two Pad features."""
    doc = App.newDocument("TipTrackIntegration")
    body = doc.addObject("PartDesign::Body", "Body")

    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    add_rectangle(sketch, 0, 0, 10, 10)

    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 10
    body.Tip = pad

    sketch2 = body.newObject("Sketcher::SketchObject", "Sketch001")
    add_rectangle(sketch2, 2, 2, 8, 8)

    pad2 = body.newObject("PartDesign::Pad", "Pad001")
    pad2.Profile = sketch2
    pad2.Length = 5
    body.Tip = pad2

    doc.recompute()
    return doc, body, sketch, pad, sketch2, pad2


def screenshot(main_window, name: str) -> str:
    """Grab the main FreeCAD window into ARTIFACT_DIR/name."""
    QtWidgets.QApplication.processEvents()
    path = ARTIFACT_DIR / name
    pixmap = main_window.grab()
    if not pixmap.save(str(path)):
        raise AssertionError(f"Failed to save screenshot: {path}")
    log(f"screenshot {path}")
    return str(path)


def frame_model(body) -> None:
    """Make the generated Body visible and framed in the active 3D view."""
    body.ViewObject.Visibility = True
    tip = getattr(body, "Tip", None)
    if tip is not None and hasattr(tip, "ViewObject"):
        tip.ViewObject.Visibility = True

    active_view = Gui.ActiveDocument.ActiveView
    active_view.viewAxometric()
    if hasattr(active_view, "fitAll"):
        active_view.fitAll()
    else:
        Gui.SendMsgToActiveView("ViewFit")
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def main() -> None:
    """Run the integration smoke test and close FreeCAD."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    main_window = Gui.getMainWindow()
    main_window.resize(1280, 820)

    doc, body, sketch, pad, sketch2, pad2 = create_padded_body()
    log(f"FreeCAD version {'.'.join(App.Version()[:3])}")
    log(f"created body group {[obj.Name for obj in body.Group]}")
    log(f"pad volumes {round(pad.Shape.Volume, 3)}, {round(pad2.Shape.Volume, 3)}")
    frame_model(body)

    tiptrack_init_gui._install()
    QtWidgets.QApplication.processEvents()

    dock = main_window.findChild(TipTrackDock, "TipTrackTimelineDock")
    if dock is None:
        raise AssertionError("TipTrack dock was not installed")

    dock.show()
    dock.raise_()
    dock.refresh()
    frame_model(body)
    QtWidgets.QApplication.processEvents()

    item_names = list(dock.strip._items_by_name)
    if item_names != ["Sketch", "Pad", "Sketch001", "Pad001"]:
        raise AssertionError(f"Unexpected timeline item order: {item_names}")
    if dock.body is not body:
        raise AssertionError("Dock did not resolve the created Body")

    frames = []
    frames.append(screenshot(main_window, "freecad_tiptrack_frame_00_initial.png"))

    dock.strip.select_feature(pad)
    frames.append(screenshot(main_window, "freecad_tiptrack_frame_01_select_pad.png"))

    dock.set_tip_to_feature(pad)
    if body.Tip is not pad:
        raise AssertionError("Set as tip did not update Body.Tip to Pad")
    frames.append(screenshot(main_window, "freecad_tiptrack_frame_02_tip_pad.png"))

    dock.set_tip_to_feature(pad2)
    if body.Tip is not pad2:
        raise AssertionError("Set as tip did not update Body.Tip to Pad001")

    dock.rename_feature(sketch, "BaseSketch")
    if sketch.Label != "BaseSketch":
        raise AssertionError("Rename did not update Sketch.Label")
    frames.append(screenshot(main_window, "freecad_tiptrack_frame_03_renamed.png"))

    ok, reason = can_move(body, pad, 0)
    if ok:
        raise AssertionError("Dependency check allowed Pad to move before Sketch")
    log(f"dependency rejection: {reason}")

    fcstd_path = ARTIFACT_DIR / "tiptrack_integration.FCStd"
    doc.saveAs(str(fcstd_path))
    log(f"saved {fcstd_path}")

    summary = {
        "body_group": [obj.Name for obj in body.Group],
        "dock_body": getattr(dock.body, "Name", None),
        "frames": frames,
        "model": str(fcstd_path),
        "pad_volume": round(pad.Shape.Volume, 3),
        "pad001_volume": round(pad2.Shape.Volume, 3),
        "tip": body.Tip.Name,
    }
    (ARTIFACT_DIR / "tiptrack_integration_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    log("PASS")

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


try:
    main()
except Exception as exc:
    log(f"FAIL: {exc!r}")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "tiptrack_integration_failure.txt").write_text(
        traceback.format_exc(),
        encoding="utf-8",
    )
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)
