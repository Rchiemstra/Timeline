# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline strip widget for TipTrack.

"""Read-only horizontal feature timeline for the active Body."""

import FreeCAD as App
import FreeCADGui as Gui

from freecad.TipTrack.feature_item import FeatureItem
from freecad.TipTrack.Qt.Gui import QtCore, QtWidgets


class TimelineStrip(QtWidgets.QWidget):
    """Scrollable horizontal list of features in a PartDesign Body."""

    featureSelected = QtCore.Signal(object)
    featureEditRequested = QtCore.Signal(object)
    featureSetTipRequested = QtCore.Signal(object)
    featureToggleSuppressRequested = QtCore.Signal(object)
    featureRenameCommitted = QtCore.Signal(object, str)
    featureDeleteRequested = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._body = None
        self._items_by_name: dict[str, FeatureItem] = {}
        self._empty_label: QtWidgets.QLabel | None = None

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

    @property
    def body(self):
        """Return the Body currently displayed by the strip."""
        return self._body

    def set_body(self, body) -> None:
        """Rebuild the strip from body.Group."""
        self._body = body
        self._clear_items()

        if body is None:
            self._show_empty_state("No active Body - create one in Part Design.")
            return

        features = list(getattr(body, "Group", []) or [])
        if not features:
            self._show_empty_state("Active Body has no features.")
            return

        tip = getattr(body, "Tip", None)
        for feature in features:
            name = getattr(feature, "Name", "")
            item = FeatureItem(feature, is_tip=feature is tip, parent=self._content)
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
