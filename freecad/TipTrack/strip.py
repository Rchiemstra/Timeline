# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline strip widget for TipTrack.

"""Read-only horizontal feature timeline for the active Body."""

import FreeCAD as App
import FreeCADGui as Gui

from freecad.TipTrack import preferences
from freecad.TipTrack.feature_item import FeatureItem, MIME_FEATURE
from freecad.TipTrack.i18n import translate
from freecad.TipTrack.Qt.Gui import QtCore, QtWidgets
from freecad.TipTrack.reorder import can_move, move_feature


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
        self._items_by_name: dict[str, FeatureItem] = {}
        self._empty_label: QtWidgets.QLabel | None = None
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

        self._content = QtWidgets.QWidget()
        self._layout = QtWidgets.QHBoxLayout(self._content)
        self._layout.setContentsMargins(6, 4, 6, 4)
        self._layout.setSpacing(4)
        self._layout.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self._scroll_area.setWidget(self._content)
        root_layout.addWidget(self._scroll_area)

        for target in (self, self._content, self._scroll_area.viewport()):
            target.setAcceptDrops(True)
            target.installEventFilter(self)

    @property
    def body(self):
        """Return the Body currently displayed by the strip."""
        return self._body

    def set_body(self, body) -> None:
        """Rebuild the strip from body.Group."""
        self._body = body
        self._clear_items()

        if body is None:
            self._show_empty_state(
                translate("No active Body - create one in Part Design.")
            )
            return

        features = list(getattr(body, "Group", []) or [])
        if not features:
            self._show_empty_state(translate("Active Body has no features."))
            return

        tip = getattr(body, "Tip", None)
        item_size = preferences.get_item_size()
        show_labels = preferences.get_show_labels()
        for feature in features:
            name = getattr(feature, "Name", "")
            item = FeatureItem(
                feature,
                is_tip=feature is tip,
                item_size=item_size,
                show_label=show_labels,
                parent=self._content,
            )
            item.featureSelected.connect(self._select_feature)
            item.editRequested.connect(self.featureEditRequested.emit)
            item.setTipRequested.connect(self.featureSetTipRequested.emit)
            item.toggleSuppressRequested.connect(
                self.featureToggleSuppressRequested.emit
            )
            item.renameCommitted.connect(self.featureRenameCommitted.emit)
            item.deleteRequested.connect(self.featureDeleteRequested.emit)
            self._items_by_name[name] = item
            self._layout.addWidget(item)

        self._layout.addStretch(1)

    def set_selected_feature(self, feature) -> None:
        """Highlight feature as selected in the strip."""
        selected_name = getattr(feature, "Name", None)
        for name, item in self._items_by_name.items():
            item.set_selected_active(name == selected_name)

    def select_feature(self, feature) -> None:
        """Select feature in FreeCAD and highlight it in the strip."""
        self._select_feature(feature)

    def visible_features(self) -> list:
        """Return the features currently represented in the strip."""
        return list(getattr(self._body, "Group", []) or [])

    def wheelEvent(self, event) -> None:
        """Pan the horizontal strip with the mouse wheel when enabled."""
        if not preferences.get_scroll_wheel_pan():
            super().wheelEvent(event)
            return

        angle_delta = event.angleDelta()
        delta = angle_delta.y() or angle_delta.x()
        if delta == 0:
            super().wheelEvent(event)
            return

        bar = self._scroll_area.horizontalScrollBar()
        bar.setValue(bar.value() - delta)
        event.accept()

    def eventFilter(self, watched, event) -> bool:
        """Handle drag/drop on child widgets that receive viewport events."""
        event_type = event.type()
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

    def _clear_items(self) -> None:
        self._items_by_name.clear()
        while self._layout.count():
            layout_item = self._layout.takeAt(0)
            widget = layout_item.widget()
            if widget is not None:
                widget.deleteLater()
        self._empty_label = None

    def _show_empty_state(self, text: str) -> None:
        label = QtWidgets.QLabel(text, self._content)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("color: palette(mid); padding: 8px;")
        self._empty_label = label
        self._layout.addWidget(label)
        self._layout.addStretch(1)

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

    def _gap_index_for_event(self, event, watched) -> int:
        pos = _event_pos(event)
        if watched is not self._content:
            pos = self._content.mapFrom(watched, pos)
        return self._gap_index_from_x(pos.x())

    def _gap_index_from_x(self, x_position: int) -> int:
        features = list(getattr(self._body, "Group", []) or [])
        items = [
            self._items_by_name.get(getattr(feature, "Name", "")) for feature in features
        ]
        visible_items = [item for item in items if item is not None]
        for index, item in enumerate(visible_items):
            if x_position < item.x() + item.width() / 2:
                return index
        return len(visible_items)

    def _final_index_for_gap(self, feature, gap_index: int) -> int:
        features = list(getattr(self._body, "Group", []) or [])
        old_index = next(
            index for index, item in enumerate(features) if item is feature
        )
        final_index = gap_index - 1 if gap_index > old_index else gap_index
        return max(0, min(final_index, len(features) - 1))

    def _show_drop_indicator(self, gap_index: int) -> None:
        features = list(getattr(self._body, "Group", []) or [])
        item = None
        if 0 <= gap_index < len(features):
            item = self._items_by_name.get(getattr(features[gap_index], "Name", ""))

        if item is not None:
            x_position = item.x() - 3
        else:
            last_item = None
            if features:
                last_item = self._items_by_name.get(getattr(features[-1], "Name", ""))
            x_position = (last_item.x() + last_item.width() + 3) if last_item else 4

        self._drop_indicator.setParent(self._content)
        self._drop_indicator.setGeometry(
            max(0, x_position), 6, 2, max(16, self._content.height() - 12)
        )
        self._drop_indicator.raise_()
        self._drop_indicator.show()

    def _hide_drop_indicator(self) -> None:
        self._drop_indicator.hide()


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
