# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Reorder integration smoke test for TipTrack.

"""Run inside the FreeCAD GUI to validate timeline drag/reorder in TipTrack.

Tests steps 1-15 + invalid-reorder cases from the Reorder spec:
  1-8   Build Body → BaseSketch → BasePad → PillarSketch → PillarPad.
  9     Verify initial Group order and timeline cards.
  10-11 Valid reorder: move PillarSketch before BaseSketch via move_feature +
        dock.strip.featureMoved signal; verify Group order, Tip, volume.
  12-13 Scrub backward and forward through the reordered timeline; verify
        model state and playhead position at each step.
  14-15 Save document; verify file is written.

  Invalid reorder cases (dependency-breaking moves):
    - BasePad before BaseSketch (Pad depends on its Sketch).
    - PillarPad before PillarSketch (Pad depends on its Sketch).
    - PillarPad before BasePad (Pad depends on its base solid).
  After each rejection: verify Group is unchanged and scrubber still works.

Artifacts are written to ARTIFACT_DIR (default: <repo>/artifacts).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
import Part

_REPO_FALLBACK = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(os.environ.get("TIPTRACK_REPO_ROOT", str(_REPO_FALLBACK)))
ARTIFACT_DIR = Path(
    os.environ.get("TIPTRACK_ARTIFACT_DIR", str(REPO_ROOT / "artifacts"))
)

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

from freecad.TipTrack.Qt.Gui import QtCore, QtGui, QtWidgets  # noqa: E402
from freecad.TipTrack.dock import TipTrackDock  # noqa: E402
import freecad.TipTrack.init_gui as tiptrack_init_gui  # noqa: E402
from freecad.TipTrack.reorder import can_move, move_feature  # noqa: E402


def log(message: str) -> None:
    print(f"TIPTRACK_INTEGRATION: {message}", flush=True)


def add_rectangle(sketch, x0: float, y0: float, x1: float, y1: float) -> None:
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


def assert_playhead_right_of_card(dock: TipTrackDock, index: int, label: str) -> None:
    """Verify the visual playhead is at the right boundary of card at *index*."""
    scrubber = dock.strip._timeline_scrubber
    expected = scrubber.playhead_center_for_position(index + 1)
    actual = scrubber.playhead_center_x()
    if actual != expected:
        raise AssertionError(
            f"Playhead at '{label}' (idx {index}): "
            f"expected right-of-card x={expected}, got x={actual}"
        )


def create_reorder_body():
    """Four-feature body: BaseSketch → BasePad → PillarSketch → PillarPad.

    PillarSketch is on the XY plane with no face attachment, so it has no
    intra-body dependencies and can be freely moved to an earlier position.
    The two pad shapes are positioned so they never overlap:
      BasePad:   (0,0)–(10,10) × 10 mm  = 1 000 mm³
      PillarPad: (20,20)–(25,25) × 8 mm = 200 mm³ additional volume
    """
    doc = App.newDocument("TipTrackReorder")
    body = doc.addObject("PartDesign::Body", "Body")

    base_sketch = body.newObject("Sketcher::SketchObject", "BaseSketch")
    add_rectangle(base_sketch, 0, 0, 10, 10)

    base_pad = body.newObject("PartDesign::Pad", "BasePad")
    base_pad.Profile = base_sketch
    base_pad.Length = 10
    body.Tip = base_pad

    # PillarSketch on origin XY plane — no face attachment, movable past BasePad.
    pillar_sketch = body.newObject("Sketcher::SketchObject", "PillarSketch")
    add_rectangle(pillar_sketch, 20, 20, 25, 25)

    pillar_pad = body.newObject("PartDesign::Pad", "PillarPad")
    pillar_pad.Profile = pillar_sketch
    pillar_pad.Length = 8
    body.Tip = pillar_pad

    doc.recompute()
    return doc, body, base_sketch, base_pad, pillar_sketch, pillar_pad


def prepare_demo_view_colors(body) -> None:
    for obj in getattr(body, "Group", []) or []:
        vo = getattr(obj, "ViewObject", None)
        if vo is None:
            continue
        if hasattr(vo, "ShapeColor"):
            vo.ShapeColor = (0.20, 0.55, 0.95)
        if hasattr(vo, "DisplayMode"):
            try:
                vo.DisplayMode = "Shaded"
            except Exception:
                pass


def frame_model(doc, body) -> None:
    doc_name = getattr(doc, "Name", None)
    if doc_name is None:
        return
    try:
        Gui.getDocument(doc_name)
    except Exception:
        return
    Gui.setActiveDocument(doc_name)
    body.ViewObject.Visibility = True
    tip = getattr(body, "Tip", None)
    if tip is not None and hasattr(tip, "ViewObject"):
        tip.ViewObject.Visibility = True
    Gui.Selection.clearSelection()
    try:
        Gui.Selection.addSelection(body)
    except Exception:
        Gui.Selection.addSelection(doc.Name, body.Name)
    gui_doc = Gui.ActiveDocument
    if gui_doc is None:
        return
    active_view = gui_doc.ActiveView
    if active_view is None:
        return
    active_view.viewAxometric()
    if hasattr(active_view, "fitAll"):
        active_view.fitAll()
    else:
        Gui.SendMsgToActiveView("ViewFit")
    redraw = getattr(active_view, "redraw", None)
    if callable(redraw):
        redraw()
    Gui.updateGui()
    for _ in range(6):
        QtWidgets.QApplication.processEvents()


def screenshot(main_window, doc, body, dock: TipTrackDock, name: str) -> str:
    try:
        dock.strip._scroll_area.horizontalScrollBar().setValue(0)
    except Exception:
        pass

    frame_model(doc, body)
    dock.raise_()
    dock.show()
    for _ in range(4):
        QtWidgets.QApplication.processEvents()

    out_path = ARTIFACT_DIR / name
    tmp_vp = ARTIFACT_DIR / f".viewport_tmp_{Path(name).stem}.png"

    gui_doc = Gui.ActiveDocument
    active_view = gui_doc.ActiveView if gui_doc else None
    save_image = getattr(active_view, "saveImage", None) if active_view else None

    vp_saved = False
    if callable(save_image):
        try:
            save_image(str(tmp_vp), 1280, 960, "Black")
            vp_saved = tmp_vp.is_file()
        except Exception as exc:
            log(f"saveImage failed ({exc!r})")

    QtWidgets.QApplication.processEvents()

    dock_px = dock.grab() if dock.isVisible() else None
    scrubber = dock.strip._timeline_scrubber
    log(
        f"screenshot dock={dock.width()}x{dock.height()} "
        f"scrubber={scrubber.width()}x{scrubber.height()} "
        f"features={len(scrubber._features)}"
    )

    def _unlink_tmp() -> None:
        try:
            tmp_vp.unlink(missing_ok=True)
        except OSError:
            pass

    if vp_saved:
        vp_img = QtGui.QImage(str(tmp_vp))
        if not vp_img.isNull():
            target_w = vp_img.width()
            dock_img = dock_px.toImage() if (dock_px and not dock_px.isNull()) else None
            if dock_img and dock_img.width() != target_w:
                dock_img = dock_img.scaledToWidth(target_w, QtCore.Qt.SmoothTransformation)
            dock_h = dock_img.height() if dock_img else 0
            try:
                rgb_fmt = QtGui.QImage.Format.Format_RGB32  # type: ignore[attr-defined]
            except AttributeError:
                rgb_fmt = QtGui.QImage.Format_RGB32
            composite = QtGui.QImage(target_w, vp_img.height() + dock_h, rgb_fmt)
            composite.fill(QtGui.QColor(32, 32, 32))
            painter = QtGui.QPainter(composite)
            painter.drawImage(0, 0, vp_img)
            if dock_img:
                painter.drawImage(0, vp_img.height(), dock_img)
            painter.end()
            _unlink_tmp()
            if not composite.save(str(out_path)):
                raise AssertionError(f"Failed to save composite: {out_path}")
            log(f"screenshot composite {out_path}")
            return str(out_path)

    _unlink_tmp()
    window_px = main_window.grab()
    if not window_px.save(str(out_path)):
        raise AssertionError(f"Failed to save screenshot: {out_path}")
    log(f"screenshot window fallback {out_path}")
    return str(out_path)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    main_window = Gui.getMainWindow()
    main_window.resize(1280, 820)

    # Steps 1-8: build the model.
    doc, body, base_sketch, base_pad, pillar_sketch, pillar_pad = create_reorder_body()
    prepare_demo_view_colors(body)
    doc.recompute()
    log(f"FreeCAD version {'.'.join(App.Version()[:3])}")
    log(f"body group {[f.Name for f in body.Group]}")
    base_pad_volume = round(base_pad.Shape.Volume, 3)
    full_volume = round(body.Shape.Volume, 3)
    log(f"base_pad_volume={base_pad_volume} full_volume={full_volume}")
    frame_model(doc, body)

    tiptrack_init_gui._install()
    QtWidgets.QApplication.processEvents()

    dock = main_window.findChild(TipTrackDock, "TipTrackTimelineDock")
    if dock is None:
        raise AssertionError("TipTrack dock was not installed")

    dock.show()
    dock.raise_()
    dock.refresh()
    frame_model(doc, body)
    QtWidgets.QApplication.processEvents()

    # Step 9: verify initial Group order and timeline cards.
    initial_names = [f.Name for f in body.Group]
    if initial_names != ["BaseSketch", "BasePad", "PillarSketch", "PillarPad"]:
        raise AssertionError(f"Unexpected initial order: {initial_names}")
    if dock.body is not body:
        raise AssertionError("Dock did not resolve the created Body")
    visible_initial = [f.Name for f in dock.strip.visible_features()]
    if visible_initial != initial_names:
        raise AssertionError(f"Dock strip mismatch: {visible_initial!r}")
    log(f"step 9 initial order OK: {initial_names}")

    dock.scrub_to_index(len(initial_names) - 1)
    QtWidgets.QApplication.processEvents()
    assert_playhead_right_of_card(dock, 3, "PillarPad")

    frames = []
    frames.append(
        screenshot(main_window, doc, body, dock, "freecad_tiptrack_reorder_frame_00_initial.png")
    )

    # ── VALID REORDER ─────────────────────────────────────────────────────────
    # Step 10: confirm can_move permits moving PillarSketch to position 0.
    ok, reason = can_move(body, pillar_sketch, 0)
    if not ok:
        raise AssertionError(f"Expected PillarSketch movable to index 0: {reason}")
    log("step 10 can_move(PillarSketch, 0)=True")

    # Step 11: perform the move and update the dock via featureMoved signal path.
    move_feature(body, pillar_sketch, 0)
    dock.strip.featureMoved.emit(pillar_sketch, 0)
    QtWidgets.QApplication.processEvents()

    new_group = list(body.Group)
    new_names = [f.Name for f in new_group]
    log(f"step 11 group after reorder: {new_names}")

    pillar_sketch_pos = new_names.index("PillarSketch")
    base_sketch_pos = new_names.index("BaseSketch")
    base_pad_pos = new_names.index("BasePad")
    pillar_pad_pos = new_names.index("PillarPad")

    if pillar_sketch_pos >= base_pad_pos:
        raise AssertionError(
            f"PillarSketch ({pillar_sketch_pos}) should be before BasePad ({base_pad_pos})"
        )
    if base_pad_pos <= base_sketch_pos:
        raise AssertionError(
            f"BasePad ({base_pad_pos}) should be after BaseSketch ({base_sketch_pos})"
        )
    if pillar_pad_pos <= base_pad_pos or pillar_pad_pos <= pillar_sketch_pos:
        raise AssertionError(
            f"PillarPad ({pillar_pad_pos}) should come after both BasePad and PillarSketch"
        )

    visible_after = [f.Name for f in dock.strip.visible_features()]
    if visible_after != new_names:
        raise AssertionError(
            f"Dock strip not updated after reorder: {visible_after!r} != {new_names!r}"
        )
    log("step 11 dock strip reflects new order OK")

    if round(body.Shape.Volume, 3) != full_volume:
        raise AssertionError(
            f"Volume changed unexpectedly after reorder: "
            f"{round(body.Shape.Volume, 3)} != {full_volume}"
        )

    frames.append(
        screenshot(main_window, doc, body, dock, "freecad_tiptrack_reorder_frame_01_after_move.png")
    )

    # Steps 12-13: scrub backward and forward through the reordered timeline.
    features = dock.strip.visible_features()
    last_idx = len(features) - 1
    base_pad_scrub_idx = next(i for i, f in enumerate(features) if f is base_pad)

    log(f"step 12 scrub backward to BasePad (index {base_pad_scrub_idx})")
    dock.scrub_to_index(base_pad_scrub_idx)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not base_pad:
        raise AssertionError(
            f"Expected BasePad as Tip at index {base_pad_scrub_idx}, got {getattr(body.Tip, 'Name', None)}"
        )
    if round(body.Shape.Volume, 3) != base_pad_volume:
        raise AssertionError(
            f"BasePad volume mismatch: {round(body.Shape.Volume, 3)} != {base_pad_volume}"
        )
    assert_playhead_right_of_card(dock, base_pad_scrub_idx, "BasePad")
    log("step 12 BasePad solid restored; playhead right OK")

    frames.append(
        screenshot(main_window, doc, body, dock, "freecad_tiptrack_reorder_frame_02_scrub_basepad.png")
    )

    log(f"step 13 scrub forward to PillarPad (index {last_idx})")
    dock.scrub_to_index(last_idx)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pillar_pad:
        raise AssertionError(
            f"Expected PillarPad as Tip at last index, got {getattr(body.Tip, 'Name', None)}"
        )
    if round(body.Shape.Volume, 3) != full_volume:
        raise AssertionError(
            f"Full volume mismatch after scrub forward: {round(body.Shape.Volume, 3)} != {full_volume}"
        )
    assert_playhead_right_of_card(dock, last_idx, "PillarPad")
    log("step 13 full model restored; playhead right OK")

    frames.append(
        screenshot(main_window, doc, body, dock, "freecad_tiptrack_reorder_frame_03_scrub_pillarpad.png")
    )

    # Steps 14-15: save the document and verify the file is written.
    fcstd_path = ARTIFACT_DIR / "tiptrack_reorder.FCStd"
    doc.saveAs(str(fcstd_path))
    if not fcstd_path.is_file():
        raise AssertionError("Save failed: FCStd file not written")
    log(f"step 15 saved {fcstd_path}")

    # ── INVALID REORDER CASES ─────────────────────────────────────────────────
    group_snapshot = list(body.Group)

    # Invalid: move BasePad before BaseSketch (Pad depends on its Sketch).
    ok, reason = can_move(body, base_pad, 0)
    if ok:
        raise AssertionError("Expected BasePad→before BaseSketch to be rejected")
    if list(body.Group) != group_snapshot:
        raise AssertionError("Group modified by rejected can_move (BasePad→0)")
    log(f"invalid-1 BasePad before BaseSketch rejected: {reason!r}")

    # Invalid: move PillarPad before PillarSketch (Pad depends on its Sketch).
    ok, reason = can_move(body, pillar_pad, 0)
    if ok:
        raise AssertionError("Expected PillarPad before PillarSketch to be rejected")
    if list(body.Group) != group_snapshot:
        raise AssertionError("Group modified by rejected can_move (PillarPad→0)")
    log(f"invalid-2 PillarPad before PillarSketch rejected: {reason!r}")

    # Invalid: move PillarPad before BasePad (PillarPad uses BasePad as base solid).
    ok, reason = can_move(body, pillar_pad, base_pad_pos)
    if ok:
        raise AssertionError("Expected PillarPad before BasePad to be rejected")
    if list(body.Group) != group_snapshot:
        raise AssertionError("Group modified by rejected can_move (PillarPad→base_pad_pos)")
    log(f"invalid-3 PillarPad before BasePad rejected: {reason!r}")

    # Verify the scrubber still works correctly after all rejected moves.
    dock.scrub_to_index(0)
    QtWidgets.QApplication.processEvents()
    dock.scrub_to_index(last_idx)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pillar_pad:
        raise AssertionError("Scrubber broken after rejected moves")
    if round(body.Shape.Volume, 3) != full_volume:
        raise AssertionError("Volume changed after rejected moves")
    assert_playhead_right_of_card(dock, last_idx, "PillarPad")
    log("invalid-4 scrubber intact after all rejected moves; playhead right OK")

    frames.append(
        screenshot(
            main_window, doc, body, dock, "freecad_tiptrack_reorder_frame_04_invalid_rejected.png"
        )
    )

    summary = {
        "body_group_initial": ["BaseSketch", "BasePad", "PillarSketch", "PillarPad"],
        "body_group_after_reorder": new_names,
        "dock_body": getattr(dock.body, "Name", None),
        "frames": frames,
        "model": str(fcstd_path),
        "base_pad_volume": base_pad_volume,
        "full_volume": full_volume,
        "tip": body.Tip.Name,
    }
    (ARTIFACT_DIR / "tiptrack_reorder_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
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
    (ARTIFACT_DIR / "tiptrack_reorder_failure.txt").write_text(
        traceback.format_exc(), encoding="utf-8"
    )
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)
