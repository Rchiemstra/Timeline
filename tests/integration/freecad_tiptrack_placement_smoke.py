# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Placement-capture integration smoke test for TipTrack.

"""Run inside the FreeCAD GUI to validate Body Placement timeline capture.

What this exercises end-to-end:

  1-5   Build a PartDesign Body with two features (Sketch + Pad) so the
        timeline has feature cards to interleave with placement cards.
  6     Install the TipTrack dock and confirm a baseline placement snapshot
        is recorded automatically the first time the dock sees the Body.
  7-10  Move ``body.Placement`` twice (translation + translation+rotation),
        flush the dock's debounce timer for each, and verify a new placement
        card lands on the timeline with the right anchor and stored values.
  11-12 Scrub onto the baseline placement card: ``body.Placement`` must equal
        the original baseline, the ``Tip`` matches the baseline's anchor, and
        the unified item list places baseline + features + later placements
        in chronological order.
  13    Scrub to the latest placement card (after Pad) and confirm both the
        tip (Pad) and placement (final translation+rotation) are reapplied.
  14    Scrub to position ``0`` and confirm the baseline placement is
        restored and the tip is cleared.
  15    Save the model, write a summary JSON, and finish.

Artifacts (PNG composites + saved FCStd + summary JSON) write to
``TIPTRACK_ARTIFACT_DIR`` (defaults to ``<repo>/artifacts``).
"""

from __future__ import annotations

import json
import math
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
from freecad.TipTrack.placement_history import (  # noqa: E402
    BASELINE_SNAPSHOT_LABEL,
    DEFAULT_SNAPSHOT_LABEL,
    PROPERTY_NAME,
    get_snapshots,
)
import freecad.TipTrack.init_gui as tiptrack_init_gui  # noqa: E402


def log(message: str) -> None:
    print(f"TIPTRACK_PLACEMENT: {message}", flush=True)


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


def create_placement_body():
    """Two-feature body so the timeline has cards to interleave with placements."""
    doc = App.newDocument("TipTrackPlacement")
    body = doc.addObject("PartDesign::Body", "Body")

    sketch = body.newObject("Sketcher::SketchObject", "BaseSketch")
    add_rectangle(sketch, 0, 0, 10, 10)

    pad = body.newObject("PartDesign::Pad", "BasePad")
    pad.Profile = sketch
    pad.Length = 5
    body.Tip = pad

    doc.recompute()
    return doc, body, sketch, pad


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
        f"items={len(scrubber.items())}"
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


def flush_dock_capture(dock: TipTrackDock) -> None:
    """Force the dock's debounce timer to fire immediately and refresh."""
    dock._placement_capture_timer.stop()
    dock._flush_placement_captures()
    QtWidgets.QApplication.processEvents()


def find_snapshot_by_label(body, label: str) -> dict:
    for snap in get_snapshots(body):
        if snap.get("label") == label:
            return snap
    raise AssertionError(f"No placement snapshot found with label {label!r}")


def assert_placement_close(actual, expected_base, expected_axis, expected_angle_deg, msg):
    """Compare a FreeCAD Placement to expected base/axis/angle (degrees)."""
    base = actual.Base
    if abs(base.x - expected_base[0]) > 1e-3 or abs(base.y - expected_base[1]) > 1e-3 or abs(base.z - expected_base[2]) > 1e-3:
        raise AssertionError(
            f"{msg}: base mismatch got=({base.x:.3f},{base.y:.3f},{base.z:.3f}) "
            f"expected={expected_base}"
        )
    rotation = actual.Rotation
    axis = rotation.Axis
    angle_deg = math.degrees(rotation.Angle)
    if abs(angle_deg - expected_angle_deg) > 1e-2:
        raise AssertionError(
            f"{msg}: angle mismatch got={angle_deg:.3f} expected={expected_angle_deg}"
        )
    if expected_angle_deg != 0.0:
        if (
            abs(axis.x - expected_axis[0]) > 1e-3
            or abs(axis.y - expected_axis[1]) > 1e-3
            or abs(axis.z - expected_axis[2]) > 1e-3
        ):
            raise AssertionError(
                f"{msg}: axis mismatch got=({axis.x:.3f},{axis.y:.3f},{axis.z:.3f}) "
                f"expected={expected_axis}"
            )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    main_window = Gui.getMainWindow()
    main_window.resize(1280, 820)

    # Steps 1-5: build the model.
    doc, body, sketch, pad = create_placement_body()
    prepare_demo_view_colors(body)
    doc.recompute()
    log(f"FreeCAD version {'.'.join(App.Version()[:3])}")
    initial_volume = round(body.Shape.Volume, 3)
    baseline_placement = App.Placement(body.Placement)
    log(
        f"initial_volume={initial_volume} "
        f"baseline_base=({baseline_placement.Base.x:.1f},"
        f"{baseline_placement.Base.y:.1f},{baseline_placement.Base.z:.1f})"
    )
    frame_model(doc, body)

    # Step 6: install dock and confirm baseline snapshot was recorded automatically.
    tiptrack_init_gui._install()
    QtWidgets.QApplication.processEvents()
    dock = main_window.findChild(TipTrackDock, "TipTrackTimelineDock")
    if dock is None:
        raise AssertionError("TipTrack dock was not installed")
    dock.show()
    dock.raise_()
    dock.refresh()
    QtWidgets.QApplication.processEvents()

    if not hasattr(body, PROPERTY_NAME):
        raise AssertionError(f"Body missing {PROPERTY_NAME} property after install")

    baseline_snapshots = get_snapshots(body)
    if len(baseline_snapshots) != 1:
        raise AssertionError(
            f"Expected exactly 1 baseline snapshot after install, got {len(baseline_snapshots)}: "
            f"{baseline_snapshots!r}"
        )
    baseline_snap = baseline_snapshots[0]
    if baseline_snap["label"] != BASELINE_SNAPSHOT_LABEL:
        raise AssertionError(
            f"First snapshot must be the baseline; got label {baseline_snap['label']!r}"
        )
    if baseline_snap["anchor"] != "BasePad":
        raise AssertionError(
            f"Baseline anchor expected BasePad (current Tip), got {baseline_snap['anchor']!r}"
        )
    log(f"step 6 baseline snapshot OK: id={baseline_snap['id'][:8]}")

    frames = []
    frames.append(
        screenshot(
            main_window, doc, body, dock, "freecad_tiptrack_placement_frame_00_baseline.png"
        )
    )

    # Steps 7-8: first move (translation only). Capture and verify.
    body.Placement = App.Placement(
        App.Vector(15.0, 0.0, 0.0),
        App.Rotation(App.Vector(0, 0, 1), 0.0),
    )
    QtWidgets.QApplication.processEvents()
    flush_dock_capture(dock)

    after_first_move = get_snapshots(body)
    if len(after_first_move) != 2:
        raise AssertionError(
            f"Expected 2 snapshots after first move, got {len(after_first_move)}: "
            f"{after_first_move!r}"
        )
    first_move_snap = after_first_move[1]
    if first_move_snap["label"] != DEFAULT_SNAPSHOT_LABEL:
        raise AssertionError(
            f"First move snapshot label expected {DEFAULT_SNAPSHOT_LABEL!r}, "
            f"got {first_move_snap['label']!r}"
        )
    if first_move_snap["anchor"] != "BasePad":
        raise AssertionError(
            f"First move anchor expected BasePad, got {first_move_snap['anchor']!r}"
        )
    if abs(first_move_snap["base"][0] - 15.0) > 1e-3:
        raise AssertionError(
            f"First move base.x expected 15.0, got {first_move_snap['base'][0]}"
        )
    log(f"step 8 first move captured base={first_move_snap['base']!r}")

    frames.append(
        screenshot(
            main_window, doc, body, dock, "freecad_tiptrack_placement_frame_01_first_move.png"
        )
    )

    # Steps 9-10: second move (translation + rotation). Capture and verify.
    body.Placement = App.Placement(
        App.Vector(20.0, 5.0, 0.0),
        App.Rotation(App.Vector(0, 0, 1), 45.0),
    )
    QtWidgets.QApplication.processEvents()
    flush_dock_capture(dock)

    after_second_move = get_snapshots(body)
    if len(after_second_move) != 3:
        raise AssertionError(
            f"Expected 3 snapshots after second move, got {len(after_second_move)}: "
            f"{after_second_move!r}"
        )
    second_move_snap = after_second_move[2]
    if abs(second_move_snap["base"][0] - 20.0) > 1e-3 or abs(second_move_snap["base"][1] - 5.0) > 1e-3:
        raise AssertionError(
            f"Second move base expected (20.0, 5.0, *), got {second_move_snap['base']!r}"
        )
    if abs(second_move_snap["rot"][3] - 45.0) > 1e-2:
        raise AssertionError(
            f"Second move angle expected 45.0 deg, got {second_move_snap['rot'][3]}"
        )
    log(
        f"step 10 second move captured base={second_move_snap['base']!r} "
        f"angle={second_move_snap['rot'][3]:.1f}"
    )

    # Verify unified item ordering. All three snapshots were captured while
    # Tip == BasePad, so they all anchor to the Pad card and the strip reads
    # [BaseSketch, BasePad, baseline, first-move, second-move].
    items = dock.strip.visible_items()
    item_kinds = [item.kind for item in items]
    expected_kinds = ["feature", "feature", "placement", "placement", "placement"]
    if item_kinds != expected_kinds:
        raise AssertionError(
            f"Unified items kinds mismatch: expected {expected_kinds}, got {item_kinds}"
        )
    if items[2].snapshot["label"] != BASELINE_SNAPSHOT_LABEL:
        raise AssertionError(
            f"Items[2] should be the baseline snapshot, got label "
            f"{items[2].snapshot['label']!r}"
        )
    item_names = []
    for item in items:
        if item.is_feature:
            item_names.append(item.feature.Name)
        else:
            item_names.append(f"snap:{item.snapshot['label']}")
    log(f"unified items: {item_names}")

    frames.append(
        screenshot(
            main_window, doc, body, dock, "freecad_tiptrack_placement_frame_02_second_move.png"
        )
    )

    # Steps 11-12: scrub to the baseline card (position 3 in the unified strip).
    # items[:3] == [BaseSketch, BasePad, baseline], so Tip should be BasePad and
    # body.Placement should equal the baseline placement captured at install.
    dock.scrub_to_position(3)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pad:
        raise AssertionError(
            f"At baseline card (pos 3), Tip should be BasePad, got "
            f"{getattr(body.Tip, 'Name', None)!r}"
        )
    assert_placement_close(
        body.Placement,
        (baseline_placement.Base.x, baseline_placement.Base.y, baseline_placement.Base.z),
        (0.0, 0.0, 1.0),
        0.0,
        "baseline scrub",
    )
    log("step 12 baseline placement restored after scrubbing to baseline card")

    frames.append(
        screenshot(
            main_window, doc, body, dock, "freecad_tiptrack_placement_frame_03_scrub_baseline.png"
        )
    )

    # Step 13: scrub to the last placement card (position N) — Pad tip + final placement.
    dock.scrub_to_position(len(items))
    QtWidgets.QApplication.processEvents()
    if body.Tip is not pad:
        raise AssertionError(
            f"At final placement card, Tip should be BasePad, got {getattr(body.Tip, 'Name', None)!r}"
        )
    assert_placement_close(
        body.Placement,
        (20.0, 5.0, 0.0),
        (0.0, 0.0, 1.0),
        45.0,
        "final placement scrub",
    )
    if round(body.Shape.Volume, 3) != initial_volume:
        raise AssertionError(
            f"Volume changed unexpectedly when scrubbing to final placement: "
            f"{round(body.Shape.Volume, 3)} != {initial_volume}"
        )
    log("step 13 final tip+placement restored after forward scrub")

    frames.append(
        screenshot(
            main_window, doc, body, dock, "freecad_tiptrack_placement_frame_04_scrub_final.png"
        )
    )

    # Step 14: scrub to position 0 (pre-history): tip cleared, baseline placement re-applied.
    dock.scrub_to_position(0)
    QtWidgets.QApplication.processEvents()
    if body.Tip is not None:
        raise AssertionError(
            f"At position 0, Tip must be None, got {getattr(body.Tip, 'Name', None)!r}"
        )
    assert_placement_close(
        body.Placement,
        (baseline_placement.Base.x, baseline_placement.Base.y, baseline_placement.Base.z),
        (0.0, 0.0, 1.0),
        0.0,
        "pre-history baseline restore",
    )
    log("step 14 pre-history scrub OK: tip cleared, baseline restored")

    # Verify the scrub-induced placement writes did NOT spawn new snapshots
    # (the suspend_placement_capture guard must hold across recompute).
    if len(get_snapshots(body)) != 3:
        raise AssertionError(
            f"Scrubbing should not produce new snapshots; got {len(get_snapshots(body))}"
        )
    log("step 14 snapshot count stable across scrubbing")

    # Bring the body back to its live (last) placement before saving.
    dock.scrub_to_position(len(items))
    QtWidgets.QApplication.processEvents()

    # Step 15: save and summarize.
    fcstd_path = ARTIFACT_DIR / "tiptrack_placement.FCStd"
    doc.saveAs(str(fcstd_path))
    if not fcstd_path.is_file():
        raise AssertionError("Save failed: FCStd file not written")

    summary = {
        "frames": frames,
        "model": str(fcstd_path),
        "snapshots": get_snapshots(body),
        "item_order": item_names,
        "baseline_anchor": baseline_snap["anchor"],
        "tip_after_full_scrub": getattr(body.Tip, "Name", None),
        "final_volume": round(body.Shape.Volume, 3),
    }
    (ARTIFACT_DIR / "tiptrack_placement_summary.json").write_text(
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
    (ARTIFACT_DIR / "tiptrack_placement_failure.txt").write_text(
        traceback.format_exc(), encoding="utf-8"
    )
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)
