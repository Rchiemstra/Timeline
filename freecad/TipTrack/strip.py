# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline strip widget for TipTrack.

"""Scrollable horizontal timeline with thumbnail scrubber."""

import FreeCAD as App
import FreeCADGui as Gui

from freecad.TipTrack.feature_item import MIME_FEATURE
from freecad.TipTrack.i18n import translate
from freecad.TipTrack.Qt.Gui import QtCore, QtWidgets
from freecad.TipTrack.reorder import can_move, move_feature
from freecad.TipTrack.timeline_scrubber import THUMB_W, TimelineScrubber


class TimelineStrip(QtWidgets.QWidget):
    """Scrollable horizontal list of features in a PartDesign Body."""

    featureSelected = QtCore.Signal(object)
    featureEditRequested = QtCore.Signal(object)
    featureSetTipRequested = QtCore.Signal(object)
    featureToggleSuppressRequested = QtCore.Signal(object)
    featureRenameCommitted = QtCore.Signal(object, str)
    featureDeleteRequested = QtCore.Signal(object)
    featureMoved = QtCore.Signal(object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._body = None
        self._drop_indicator = QtWidgets.QFrame(self)
        self._drop_indicator.setObjectName("TipTrackDropIndicator")
        self._drop_indicator.setFixedWidth(2)
        self._drop_indicator.setStyleSheet(
            "#TipTrackDropIndicator { background: #28a6f0; }"
        )
        self._drop_indicator.hide()

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QtWidgets.QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self._timeline_scrubber = TimelineScrubber(self._scroll_area)
        self._scroll_area.setWidget(self._timeline_scrubber)

        root_layout.addWidget(self._scroll_area)

        self._timeline_scrubber.featureChanged.connect(self._on_playhead_feature_changed)
        self._timeline_scrubber.featureDoubleClicked.connect(
            self._on_playhead_double_clicked
        )

        for target in (self, self._timeline_scrubber, self._scroll_area.viewport()):
            target.setAcceptDrops(True)
            target.installEventFilter(self)

    @property
    def body(self):
        """Return the Body currently displayed by the strip."""
        return self._body

    def set_body(self, body, *, scrub_position: int | None = None) -> None:
        """Rebuild the strip from body.Group.

        If *scrub_position* is given (``0..len(Group)``), place the playhead there.
        Otherwise the playhead is inferred from ``body.Tip`` (``Tip is None`` → position ``0``).
        """
        self._body = body

        if body is None:
            self._timeline_scrubber.clear()
            self._timeline_scrubber.set_placeholder(
                translate("No active Body - create one in Part Design.")
            )
            return

        features = list(getattr(body, "Group", []) or [])
        if not features:
            self._timeline_scrubber.clear()
            self._timeline_scrubber.set_placeholder(
                translate("Active Body has no features.")
            )
            return

        self._timeline_scrubber.set_placeholder(None)
        self._timeline_scrubber.set_features(features)

        n = len(features)
        if scrub_position is not None:
            pos = max(0, min(int(scrub_position), n))
            self._timeline_scrubber.set_playhead_position(pos, emit_signal=False)
        else:
            tip = getattr(body, "Tip", None)
            if tip is not None:
                try:
                    tip_i = features.index(tip)
                except ValueError:
                    tip_i = 0
                self._timeline_scrubber.set_playhead_position(
                    tip_i + 1, emit_signal=False
                )
            else:
                self._timeline_scrubber.set_playhead_position(0, emit_signal=False)

    def apply_scrub_mute(self, scrub_position: int) -> None:
        """Dim thumbnails with index >= *scrub_position* (``0`` dims the whole row)."""
        self._timeline_scrubber.set_dim_after(scrub_position)

    def set_selected_feature(self, feature) -> None:
        """Move the playhead to the selected feature without emitting signals."""
        feats = self.visible_features()
        if feature is None:
            self._timeline_scrubber.set_playhead_position(0, emit_signal=False)
            return
        selected_name = getattr(feature, "Name", None)
        for i, feat in enumerate(feats):
            if getattr(feat, "Name", None) == selected_name:
                self._timeline_scrubber.set_playhead_index(i, emit_signal=False)
                break

    def select_feature(self, feature) -> None:
        """Select feature in FreeCAD and highlight it in the strip."""
        self._select_feature(feature)

    def visible_features(self) -> list:
        """Return the features currently represented in the strip."""
        return list(getattr(self._body, "Group", []) or [])

    def eventFilter(self, watched, event) -> bool:
        """Drag/drop and optional horizontal wheel pan on the viewport."""
        event_type = event.type()
        if (
            watched is self._scroll_area.viewport()
            and event_type == QtCore.QEvent.Wheel
            and preferences_get_scroll_wheel_pan()
        ):
            angle_delta = event.angleDelta()
            delta = angle_delta.y() or angle_delta.x()
            if delta != 0:
                bar = self._scroll_area.horizontalScrollBar()
                bar.setValue(bar.value() - delta)
                event.accept()
                return True

        if event_type == QtCore.QEvent.DragEnter:
            self._drag_enter(event)
            return True
        if event_type == QtCore.QEvent.DragMove:
            self._drag_move(event, watched)
            return True
        if event_type == QtCore.QEvent.Drop:
            self._drop(event, watched)
            return True
        if event_type == QtCore.QEvent.DragLeave:
            self._hide_drop_indicator()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _on_playhead_feature_changed(self, position: int) -> None:
        feats = self.visible_features()
        if position <= 0:
            try:
                Gui.Selection.clearSelection()
            except Exception:
                pass
            return
        card_index = position - 1
        if 0 <= card_index < len(feats):
            self._select_feature(feats[card_index])

    def _on_playhead_double_clicked(self, index: int) -> None:
        feats = self.visible_features()
        if 0 <= index < len(feats):
            self.featureEditRequested.emit(feats[index])

    def _select_feature(self, feature) -> None:
        if not _feature_is_live(feature):
            return
        _select_in_freecad(feature)
        self.set_selected_feature(feature)
        self.featureSelected.emit(feature)

    def _drag_enter(self, event) -> None:
        if event.mimeData().hasFormat(MIME_FEATURE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drag_move(self, event, watched) -> None:
        feature = self._feature_from_event(event)
        if feature is None or self._body is None:
            self._hide_drop_indicator()
            event.ignore()
            return

        gap_index = self._gap_index_for_event(event, watched)
        final_index = self._final_index_for_gap(feature, gap_index)
        ok, reason = can_move(self._body, feature, final_index)
        if not ok:
            self._hide_drop_indicator()
            QtWidgets.QToolTip.showText(_event_global_pos(event), reason, self)
            event.ignore()
            return

        self._show_drop_indicator(gap_index)
        event.acceptProposedAction()

    def _drop(self, event, watched) -> None:
        feature = self._feature_from_event(event)
        if feature is None or self._body is None:
            self._hide_drop_indicator()
            event.ignore()
            return

        gap_index = self._gap_index_for_event(event, watched)
        final_index = self._final_index_for_gap(feature, gap_index)
        try:
            move_feature(self._body, feature, final_index)
        except Exception as exc:
            self._hide_drop_indicator()
            App.Console.PrintError(f"TipTrack: failed to reorder feature: {exc}\n")
            QtWidgets.QToolTip.showText(_event_global_pos(event), str(exc), self)
            event.ignore()
            return

        self._hide_drop_indicator()
        self.set_body(self._body)
        self.set_selected_feature(feature)
        self.featureMoved.emit(feature, final_index)
        event.acceptProposedAction()

    def _feature_from_event(self, event):
        data = event.mimeData().data(MIME_FEATURE)
        name = bytes(data).decode("utf-8")
        return self._feature_by_name(name)

    def _feature_by_name(self, name: str):
        for feature in list(getattr(self._body, "Group", []) or []):
            if getattr(feature, "Name", None) == name:
                return feature
        return None

    def _map_pos_to_scrubber(self, watched, pos: QtCore.QPoint) -> QtCore.QPoint:
        if watched is self._timeline_scrubber:
            return pos
        return self._timeline_scrubber.mapFrom(watched, pos)

    def _gap_index_for_event(self, event, watched) -> int:
        pos = self._map_pos_to_scrubber(watched, _event_pos(event))
        return self._timeline_scrubber.gap_index_at_x(pos.x())

    def _final_index_for_gap(self, feature, gap_index: int) -> int:
        features = list(getattr(self._body, "Group", []) or [])
        old_index = next(
            index for index, item in enumerate(features) if item is feature
        )
        final_index = gap_index - 1 if gap_index > old_index else gap_index
        return max(0, min(final_index, len(features) - 1))

    def _show_drop_indicator(self, gap_index: int) -> None:
        features = list(getattr(self._body, "Group", []) or [])
        scrub = self._timeline_scrubber
        if not features:
            return

        if 0 <= gap_index < len(features):
            x_position = scrub.cell_left_x(gap_index) - 3
        else:
            x_position = scrub.cell_left_x(len(features) - 1) + THUMB_W + 3

        self._drop_indicator.setParent(scrub)
        self._drop_indicator.setGeometry(
            max(0, x_position), 6, 2, max(16, scrub.height() - 12)
        )
        self._drop_indicator.raise_()
        self._drop_indicator.show()

    def _hide_drop_indicator(self) -> None:
        self._drop_indicator.hide()


def preferences_get_scroll_wheel_pan() -> bool:
    from freecad.TipTrack import preferences

    return preferences.get_scroll_wheel_pan()


def _feature_is_live(feature) -> bool:
    return getattr(feature, "Document", None) is not None


def _select_in_freecad(feature) -> None:
    try:
        Gui.Selection.clearSelection()
        try:
            Gui.Selection.addSelection(feature)
        except Exception:
            document = getattr(feature, "Document", None)
            Gui.Selection.addSelection(document.Name, feature.Name)
    except Exception as exc:
        App.Console.PrintWarning(f"TipTrack: failed to select feature: {exc}\n")


def _event_pos(event):
    position = getattr(event, "position", None)
    if position is not None:
        return position().toPoint()
    return event.pos()


def _event_global_pos(event):
    global_position = getattr(event, "globalPosition", None)
    if global_position is not None:
        return global_position().toPoint()
    return event.globalPos()
