# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: FreeCAD GUI smoke test for TipTrack.

"""Run inside the FreeCAD GUI to validate TipTrack timeline scrubbing and playback.

Covers renamed feature labels, tip rollback/restore, step navigation, play-to-end,
rapid scrubbing, and a through-pocket: scrubbing before the pocket restores a
larger ``Body.Shape.Volume``, scrubbing forward applies the hole again.
Cards follow ``Body.Group`` order (object Names stay as created;
labels are what you see). The PartDesign Body is not shown as its own timeline card.

Artifacts write PNG composites (3D viewport + TipTrack dock) under ``artifacts/``.

Optional env: ``TIPTRACK_REPO_ROOT``, ``TIPTRACK_ARTIFACT_DIR`` (defaults: repo root
and ``<repo>/artifacts``).

Test steps 1–22 from the TipTrack Playback Scrubber spec:
  1–10  Model creation (PartDesign Body, two Pads, a through-Pocket).
  11    Rename key features so the timeline shows human-readable labels.
  12    Assert timeline card order and labels.
  13–14 Scrub to pre-history (slider ``0``): ``Body.Tip`` cleared, geometry hidden, blank viewport.
  15–16 Scrub to BaseSketch (first card); then BasePad with padded solid restored.
  17–18 Scrub to ThroughHole; assert full holed model is restored.
  19–20 Step-back and step-forward; assert Tip and volume at each step.
  21–22 Playback from pre-history; assert it walks through to ThroughHole and stops.

Throughout: after every scrub the playhead triangle must sit at the **right** boundary
of the active card for positions ``1..N``, or just left of the first card at position ``0``.
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


def _top_horizontal_face_subname(part_feat) -> str:
    """Pick an upward-facing planar face at maximum Z (pad top)."""
    best_i: int | None = None
    best_z: float | None = None
    for i, face in enumerate(part_feat.Shape.Faces):
        surf = face.Surface
        if not isinstance(surf, Part.Plane):
            continue
        axis = surf.Axis
        if axis.Length < 1e-8:
            continue
        ln = axis.Length
        nz = axis.z / ln
        if nz < 0.65:
            continue
        zcm = face.CenterOfMass.z
        if best_z is None or zcm > best_z:
            best_z = zcm
            best_i = i
    if best_i is None:
        raise AssertionError("Could not locate top planar face for hole sketch")
    return f"Face{best_i + 1}"


def add_center_through_hole(body, pad_target, doc):
    """Circular pocket through the stacked pads (hole only when pocket is tip)."""
    sub = _top_horizontal_face_subname(pad_target)
    sketch_hole = body.newObject("Sketcher::SketchObject", "HoleSketch")

    attach_attempts = (
        [(pad_target, (sub,))],
        [(pad_target, [sub])],
    )
    last_err: Exception | None = None
    for support in attach_attempts:
        sketch_hole.AttachmentSupport = support
        sketch_hole.MapMode = "FlatFace"
        try:
            doc.recompute()
            break
        except Exception as exc:
            last_err = exc
            sketch_hole.AttachmentSupport = []
    else:
        raise AssertionError(f"Hole sketch attachment failed: {last_err!r}")

    sketch_hole.addGeometry(
        Part.Circle(App.Vector(5, 5, 0), App.Vector(0, 0, 1), 2.5),
        False,
    )
    doc.recompute()

    pocket = body.newObject("PartDesign::Pocket", "HolePocket")
    pocket.Profile = sketch_hole
    pocket.Length = 40
    body.Tip = pocket
    doc.recompute()
    return sketch_hole, pocket


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
    prepare_demo_view_colors(body)
    return doc, body, sketch, pad, sketch2, pad2


def timeline_card_labels(dock: TipTrackDock, body) -> list[str]:
    """Labels for timeline features, in Body.Group order (matches scrubber order)."""
    _ = dock
    return [str(f.Label) for f in body.Group]


def assert_playhead_right_of_card(dock: TipTrackDock, card_index: int, label: str) -> None:
    """Verify the visual playhead sits at the right boundary of card *card_index*.

    The playhead triangle/line must be in the gap to the right of the active card
    (not centred on it) so the visual boundary between active and future history is clear.
    """
    scrubber = dock.strip._timeline_scrubber
    expected = scrubber.playhead_center_for_position(card_index + 1)
    actual = scrubber.playhead_center_x()
    if actual != expected:
        raise AssertionError(
            f"Playhead at '{label}' (card idx {card_index}): "
            f"expected right-of-card x={expected}, got x={actual}"
        )


def assert_playhead_prehistory(dock: TipTrackDock, label: str) -> None:
    """Verify the playhead is in the pre-history slot (before the first card)."""
    scrubber = dock.strip._timeline_scrubber
    expected = scrubber.playhead_center_for_position(0)
    actual = scrubber.playhead_center_x()
    if actual != expected:
        raise AssertionError(
            f"Playhead at '{label}': expected pre-history x={expected}, got x={actual}"
        )


def prepare_demo_view_colors(body) -> None:
    """Make the Body geometry readable on white or black capture backgrounds."""
    for obj in getattr(body, "Group", []) or []:
        vo = getattr(obj, "ViewObject", None)
        if vo is None:
            continue
        if hasattr(vo, "ShapeColor"):
            vo.ShapeColor = (0.95, 0.35, 0.08)
        if hasattr(vo, "DisplayMode"):
            try:
                vo.DisplayMode = "Shaded"
            except Exception:
                pass


def screenshot(
    main_window,
    doc,
    body,
    dock: TipTrackDock,
    name: str,
    *,
    show_body_geometry: bool = True,
) -> str:
    """Stack the rendered 3D view above the TipTrack dock (viewport + timeline strip)."""
    # Scroll timeline to beginning so all feature cards are visible from the left.
    try:
        dock.strip._scroll_area.horizontalScrollBar().setValue(0)
    except Exception:
        pass

    frame_model(doc, body, show_body_geometry=show_body_geometry)
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

    # Grab the dock widget directly — avoids clipping when cropping from the main window.
    dock_px = dock.grab() if dock.isVisible() else None
    scrubber = dock.strip._timeline_scrubber
    log(
        f"screenshot dock size={dock.width()}x{dock.height()} "
        f"scrubber size={scrubber.width()}x{scrubber.height()} "
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
                dock_img = dock_img.scaledToWidth(
                    target_w, QtCore.Qt.SmoothTransformation
                )

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
                raise AssertionError(f"Failed to save composite screenshot: {out_path}")
            log(f"screenshot composite {out_path}")
            return str(out_path)

    _unlink_tmp()

    # Fallback: capture the main window.
    window_px = main_window.grab()
    if not window_px.save(str(out_path)):
        raise AssertionError(f"Failed to save screenshot: {out_path}")
    log(f"screenshot window fallback {out_path}")
    return str(out_path)


def frame_model(doc, body, *, show_body_geometry: bool = True) -> None:
    """Make the Body visible and framed in the active document's 3D view."""
    doc_name = getattr(doc, "Name", None)
    if doc_name is None:
        return
    try:
        Gui.getDocument(doc_name)
    except Exception:
        return

    Gui.setActiveDocument(doc_name)

    if show_body_geometry:
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


def main() -> None:
    """Run the integration smoke test and close FreeCAD."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    main_window = Gui.getMainWindow()
    main_window.resize(1280, 820)

    # Steps 1–10: create a PartDesign Body with two Pads and a through-Pocket.
    doc, body, sketch, pad, sketch2, pad2 = create_padded_body()
    sketch_hole, pocket = add_center_through_hole(body, pad2, doc)
    prepare_demo_view_colors(body)
    doc.recompute()
    log(f"FreeCAD version {'.'.join(App.Version()[:3])}")
    log(f"created body group {[obj.Name for obj in body.Group]}")
    log(f"pad volumes {round(pad.Shape.Volume, 3)}, {round(pad2.Shape.Volume, 3)}")
    log(
        f"after through-pocket tip volume={round(body.Shape.Volume, 3)} "
        f"(hole removes material vs pad stack)"
    )
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

    item_names = [f.Name for f in body.Group]
    if item_names != [
        "Sketch",
        "Pad",
        "Sketch001",
        "Pad001",
        "HoleSketch",
        "HolePocket",
    ]:
        raise AssertionError(f"Unexpected timeline item order: {item_names}")
    if dock.body is not body:
        raise AssertionError("Dock did not resolve the created Body")

    # Step 11: rename features to human-readable labels.
    dock.rename_feature(sketch, "BaseSketch")
    dock.rename_feature(pad, "BasePad")
    dock.rename_feature(sketch2, "SecondSketch")
    dock.rename_feature(sketch_hole, "HoleProfile")
    dock.rename_feature(pocket, "ThroughHole")
    QtWidgets.QApplication.processEvents()

    # Step 12: verify timeline card order and labels.
    expected_labels = [
        "BaseSketch",
        "BasePad",
        "SecondSketch",
        "Pad001",
        "HoleProfile",
        "ThroughHole",
    ]
    if timeline_card_labels(dock, body) != expected_labels:
        raise AssertionError(
            "Timeline labels after rename do not match: "
            f"{timeline_card_labels(dock, body)!r}"
        )
    log(f"step 12 timeline labels OK: {expected_labels}")

    doc.recompute()
    features = dock.strip.visible_features()
    last_idx = len(features) - 1
    max_pos = len(features)

    # Capture reference volumes before any scrubbing.
    dock.scrub_to_index(last_idx)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pocket:
        raise AssertionError("Expected ThroughHole pocket at full timeline tip")
    assert_playhead_right_of_card(dock, last_idx, "ThroughHole")
    final_volume = round(body.Shape.Volume, 3)

    dock.scrub_to_index(3)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pad2:
        raise AssertionError("Scrub before hole features should leave Pad001 as tip")
    assert_playhead_right_of_card(dock, 3, "Pad001")
    vol_before_hole = round(body.Shape.Volume, 3)
    if vol_before_hole <= final_volume:
        raise AssertionError(
            "Solid before pocket must be larger than solid after pocket is applied "
            f"(got {vol_before_hole} vs {final_volume})"
        )

    dock.scrub_to_index(last_idx)
    QtWidgets.QApplication.processEvents()
    if round(body.Shape.Volume, 3) != final_volume:
        raise AssertionError("Scrubbing forward did not restore holed volume")
    assert_playhead_right_of_card(dock, last_idx, "ThroughHole")

    log(f"volumes slider_check pad_stack={vol_before_hole} with_hole={final_volume}")

    frames = []
    frames.append(
        screenshot(main_window, doc, body, dock, "freecad_tiptrack_frame_00_initial.png")
    )

    # Steps 13–14: slider position 0 = pre-history (no tip, hidden Body, blank viewport).
    log("step 13 scrub to pre-history (slider 0)")
    dock._scrubber.setValue(0)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not None:
        raise AssertionError("Pre-history scrubber position did not clear Body.Tip")
    if dock._selected_feature is not None:
        raise AssertionError("Pre-history should clear timeline selection")
    if body.ViewObject.Visibility:
        raise AssertionError("Pre-history should hide the Body in the 3D view")
    for feat in body.Group:
        vo = getattr(feat, "ViewObject", None)
        if vo is not None and getattr(vo, "Visibility", False):
            raise AssertionError(
                f"Pre-history should hide all Body.Group features; {feat.Name} is still visible"
            )
    assert_playhead_prehistory(dock, "pre-history")
    log("step 14 pre-history: tip cleared, geometry hidden, playhead left of first card")
    frames.append(
        screenshot(
            main_window,
            doc,
            body,
            dock,
            "freecad_tiptrack_frame_01_scrub_sketch.png",
            show_body_geometry=False,
        )
    )

    # Steps 15–16: scrub to BaseSketch (first card, position 1); Tip still None; then BasePad.
    log("step 15 scrub to BaseSketch (position 1)")
    dock._scrubber.setValue(1)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not None:
        raise AssertionError("Scrub to first sketch should leave Body.Tip unset")
    if dock._selected_feature is not sketch:
        raise AssertionError("Scrubber selection did not sync to BaseSketch")
    if body.ViewObject.Visibility:
        raise AssertionError("Body should stay hidden at sketch-only scrub")
    sk_vo = getattr(sketch, "ViewObject", None)
    if sk_vo is None or not sk_vo.Visibility:
        raise AssertionError("BaseSketch should be visible at slider position 1")
    for feat in body.Group:
        if feat is sketch:
            continue
        vo = getattr(feat, "ViewObject", None)
        if vo is not None and getattr(vo, "Visibility", False):
            raise AssertionError(
                f"Sketch-only scrub should hide {feat.Name} in the 3D view"
            )
    assert_playhead_right_of_card(dock, 0, "BaseSketch")
    log("step 15b scrub to BasePad (position 2)")
    dock._scrubber.setValue(2)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pad:
        raise AssertionError("Scrubber did not update Body.Tip to BasePad")
    if round(body.Shape.Volume, 3) != round(pad.Shape.Volume, 3):
        raise AssertionError("Solid volume at BasePad tip does not match Pad shape")
    assert_playhead_right_of_card(dock, 1, "BasePad")
    log("step 16 BasePad solid restored; playhead right of BasePad OK")
    if not body.ViewObject.Visibility:
        raise AssertionError("Body should be visible again with a solid PartDesign tip")
    frames.append(
        screenshot(
            main_window, doc, body, dock, "freecad_tiptrack_frame_02_scrub_pad.png"
        )
    )

    # Pad001 tip (feature index 3) — second pad stacked; pocket not yet applied.
    dock._scrubber.setValue(4)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pad2:
        raise AssertionError("Scrubber did not update Body.Tip to Pad001")
    if round(body.Shape.Volume, 3) != vol_before_hole:
        raise AssertionError("Pad001 tip volume mismatch after slider scrub")
    assert_playhead_right_of_card(dock, 3, "Pad001")
    frames.append(
        screenshot(
            main_window,
            doc,
            body,
            dock,
            "freecad_tiptrack_frame_03_two_pads_no_hole.png",
        )
    )

    # Steps 17–18: scrub to ThroughHole (full history, slider ``max_pos``).
    log(f"step 17 scrub to ThroughHole (slider position {max_pos})")
    dock._scrubber.setValue(max_pos)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pocket:
        raise AssertionError("Scrubber did not restore ThroughHole as tip")
    if round(body.Shape.Volume, 3) != final_volume:
        raise AssertionError("Holed volume mismatch after scrub forward")
    assert_playhead_right_of_card(dock, last_idx, "ThroughHole")
    log("step 18 ThroughHole restored; playhead right of ThroughHole OK")
    frames.append(
        screenshot(
            main_window,
            doc,
            body,
            dock,
            "freecad_tiptrack_frame_04_full_with_hole.png",
        )
    )

    # Rapid scrubbing — no corruption; final model must be intact afterwards.
    for _ in range(40):
        dock._scrubber.setValue(0)
        QtWidgets.QApplication.processEvents()
        dock._scrubber.setValue(max_pos)
        QtWidgets.QApplication.processEvents()
    if round(body.Shape.Volume, 3) != final_volume or body.Tip is not pocket:
        raise AssertionError("Model diverged after rapid scrubbing")

    # Steps 19–20: step-back and step-forward from ThroughHole tip.
    log("step 19 step-back from ThroughHole")
    dock.scrub_to_index(last_idx)
    QtWidgets.QApplication.processEvents()
    dock.select_adjacent_feature(-1)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pad2:
        raise AssertionError("Step back did not roll tip to Pad001 (hole suppressed)")
    if round(body.Shape.Volume, 3) != vol_before_hole:
        raise AssertionError(
            "Step back did not restore Pad001-only volume (hole should not cut)"
        )
    step_back_pos = dock.strip._timeline_scrubber.playhead_position()
    step_back_card = step_back_pos - 1
    assert_playhead_right_of_card(
        dock, step_back_card, f"step-back card {step_back_card}"
    )
    log(f"step 20a step-back at card {step_back_card}; playhead right OK")

    dock.select_adjacent_feature(1)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pocket:
        raise AssertionError("Step forward did not restore ThroughHole tip")
    if round(body.Shape.Volume, 3) != final_volume:
        raise AssertionError("Step forward did not restore holed volume")
    assert_playhead_right_of_card(dock, last_idx, "ThroughHole")
    log("step 20b step-forward restored ThroughHole; playhead right OK")

    # Steps 21–22: playback from pre-history walks positions 0..N and stops at full tip.
    log("step 21 start playback from pre-history (slider 0)")
    dock.scrub_to_position(0)
    QtWidgets.QApplication.processEvents()
    dock._play_button.setChecked(True)
    dock._toggle_playback()
    if not dock._play_button.isChecked():
        raise AssertionError("Play did not start")
    guard = 0
    while dock._play_button.isChecked() and guard < max_pos + 10:
        dock._play_timer.timeout.emit()
        QtWidgets.QApplication.processEvents()
        guard += 1
    if dock._play_button.isChecked():
        raise AssertionError("Playback did not stop at final feature")
    if body.Tip is not pocket:
        raise AssertionError("Playback did not finish on ThroughHole tip")
    if round(body.Shape.Volume, 3) != final_volume:
        raise AssertionError("Volume changed after playback")
    assert_playhead_right_of_card(dock, last_idx, "ThroughHole")
    log("step 22 playback finished at ThroughHole; playhead right OK")

    frames.append(
        screenshot(
            main_window,
            doc,
            body,
            dock,
            "freecad_tiptrack_frame_05_playback_done.png",
        )
    )

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
        "volume_before_through_hole": vol_before_hole,
        "volume_with_through_hole": final_volume,
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
