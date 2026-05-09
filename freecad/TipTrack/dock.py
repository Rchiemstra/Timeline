# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline dock widget for TipTrack.

"""Dock widget that hosts the TipTrack timeline UI."""

import FreeCAD as App
import FreeCADGui as Gui

from freecad.TipTrack.body_resolver import get_active_body, get_bodies
from freecad.TipTrack.i18n import translate
from freecad.TipTrack.Qt.Gui import QtCore, QtGui, QtWidgets
from freecad.TipTrack.strip import TimelineStrip
from freecad.TipTrack.tip_controller import set_tip, toggle_suppression


class TipTrackDock(QtWidgets.QDockWidget):
    """Dock widget installed globally in the FreeCAD main window."""

    def __init__(self, parent=None):
        super().__init__(translate("TipTrack - Timeline"), parent)
        self._body = None
        self._selected_feature = None
        self._body_by_name = {}
        self._selected_body_by_document = {}
        self._refreshing_selector = False

        self.setAllowedAreas(
            QtCore.Qt.BottomDockWidgetArea | QtCore.Qt.TopDockWidgetArea
        )

        container = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        toolbar = QtWidgets.QWidget(container)
        toolbar_layout = QtWidgets.QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)

        self._body_selector = QtWidgets.QComboBox(toolbar)
        self._body_selector.setMinimumWidth(140)
        self._body_selector.currentIndexChanged.connect(self._body_selector_changed)

        self._refresh_button = QtWidgets.QPushButton(translate("Refresh"), toolbar)
        self._refresh_button.clicked.connect(self.refresh)

        toolbar_layout.addWidget(self._body_selector)
        toolbar_layout.addWidget(self._refresh_button)
        toolbar_layout.addStretch(1)

        self.strip = TimelineStrip(container)
        self.strip.featureSelected.connect(self._set_selected_feature)
        self.strip.featureEditRequested.connect(self.edit_feature)
        self.strip.featureSetTipRequested.connect(self.set_tip_to_feature)
        self.strip.featureToggleSuppressRequested.connect(self.toggle_suppression)
        self.strip.featureRenameCommitted.connect(self.rename_feature)
        self.strip.featureDeleteRequested.connect(self.delete_feature)
        self.strip.featureMoved.connect(self._feature_moved)

        layout.addWidget(toolbar)
        layout.addWidget(self.strip, 1)
        self.setWidget(container)

        shortcut_class = getattr(QtGui, "QShortcut", None) or QtWidgets.QShortcut
        visibility_shortcut = shortcut_class(
            QtGui.QKeySequence(QtCore.Qt.Key_Space), self
        )
        visibility_shortcut.activated.connect(self.toggle_selected_visibility)

        left_shortcut = shortcut_class(QtGui.QKeySequence(QtCore.Qt.Key_Left), self)
        left_shortcut.activated.connect(lambda: self.select_adjacent_feature(-1))

        right_shortcut = shortcut_class(QtGui.QKeySequence(QtCore.Qt.Key_Right), self)
        right_shortcut.activated.connect(lambda: self.select_adjacent_feature(1))

        enter_shortcut = shortcut_class(QtGui.QKeySequence(QtCore.Qt.Key_Return), self)
        enter_shortcut.activated.connect(self.set_selected_as_tip)

        delete_shortcut = shortcut_class(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self)
        delete_shortcut.activated.connect(self.delete_selected_feature)

        self.refresh()

    @property
    def body(self):
        """Return the Body currently displayed by the dock."""
        return self._body

    def refresh(self) -> None:
        """Refresh the displayed Body and feature strip."""
        self._body = self._resolve_selected_body()
        self.strip.set_body(self._body)

        if self._body is None:
            self._selected_feature = None
            return

        self._selected_feature = getattr(self._body, "Tip", None)
        self.strip.set_selected_feature(self._selected_feature)

    def set_selected_feature(self, feature) -> None:
        """Synchronize strip highlighting from an external selection."""
        self._set_selected_feature(feature)

    def select_adjacent_feature(self, step: int) -> None:
        """Move keyboard selection left or right in the strip."""
        features = self.strip.visible_features()
        if not features:
            return

        current_index = next(
            (
                index
                for index, feature in enumerate(features)
                if feature is self._selected_feature
            ),
            0,
        )

        next_index = max(0, min(current_index + step, len(features) - 1))
        self.strip.select_feature(features[next_index])

    def set_selected_as_tip(self) -> None:
        """Set the selected feature as the Body tip."""
        if self._selected_feature is not None:
            self.set_tip_to_feature(self._selected_feature)

    def delete_selected_feature(self) -> None:
        """Delete the selected feature after confirmation."""
        if self._selected_feature is not None:
            self.delete_feature(self._selected_feature)

    def edit_feature(self, feature) -> None:
        """Open FreeCAD's native edit task panel for feature."""
        if feature is None or getattr(feature, "Document", None) is None:
            return

        try:
            Gui.ActiveDocument.setEdit(feature.Name)
        except Exception as exc:
            self._show_error("Edit feature", exc)

    def set_tip_to_feature(self, feature) -> None:
        """Set the current Body tip to feature."""
        try:
            set_tip(self._body, feature)
            self.refresh()
        except Exception as exc:
            self._show_error("Set as tip", exc)

    def toggle_suppression(self, feature) -> None:
        """Toggle feature suppression when FreeCAD exposes that property."""
        try:
            toggle_suppression(feature)
            self.refresh()
        except Exception as exc:
            self._show_error("Toggle suppress", exc)

    def rename_feature(self, feature, new_label: str) -> None:
        """Rename feature without recomputing geometry."""
        if feature is None or getattr(feature, "Document", None) is None:
            return

        try:
            feature.Label = new_label
            self.refresh()
        except Exception as exc:
            self._show_error("Rename feature", exc)

    def delete_feature(self, feature) -> None:
        """Delete feature after user confirmation."""
        if feature is None or getattr(feature, "Document", None) is None:
            return

        label = str(getattr(feature, "Label", getattr(feature, "Name", "feature")))
        result = QtWidgets.QMessageBox.question(
            self,
            translate("Delete feature"),
            translate("Delete {label}?").format(label=label),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if result != QtWidgets.QMessageBox.Yes:
            return

        try:
            document = getattr(feature, "Document", None) or App.ActiveDocument
            document.removeObject(feature.Name)
            document.recompute()
            self.refresh()
        except Exception as exc:
            self._show_error("Delete feature", exc)

    def toggle_selected_visibility(self) -> None:
        """Run FreeCAD's visibility toggle command for the selected feature."""
        feature = self._selected_feature
        if feature is None or getattr(feature, "Document", None) is None:
            return

        try:
            Gui.Selection.clearSelection()
            try:
                Gui.Selection.addSelection(feature)
            except Exception:
                Gui.Selection.addSelection(feature.Document.Name, feature.Name)
            Gui.runCommand("Std_ToggleVisibility")
        except Exception as exc:
            App.Console.PrintWarning(f"TipTrack: failed to toggle visibility: {exc}\n")

    def _set_selected_feature(self, feature) -> None:
        self._selected_feature = feature
        self.strip.set_selected_feature(feature)

    def _feature_moved(self, feature, index: int) -> None:
        _ = index
        self._selected_feature = feature
        self.refresh()

    def _resolve_selected_body(self):
        bodies = get_bodies()
        self._rebuild_body_selector(bodies)
        if not bodies:
            return None

        document_key = self._document_key()
        selected_name = self._selected_body_by_document.get(document_key)
        if selected_name in self._body_by_name:
            return self._body_by_name[selected_name]

        active_body = get_active_body()
        if any(body is active_body for body in bodies):
            self._remember_body(active_body)
            self._set_selector_body(active_body)
            return active_body

        body = bodies[0]
        self._remember_body(body)
        self._set_selector_body(body)
        return body

    def _rebuild_body_selector(self, bodies: list) -> None:
        current_name = getattr(self._body, "Name", None)
        self._body_by_name = {getattr(body, "Name", ""): body for body in bodies}

        self._refreshing_selector = True
        try:
            self._body_selector.clear()
            if not bodies:
                self._body_selector.addItem(translate("No active Body"), "")
                self._body_selector.setEnabled(False)
                return

            self._body_selector.setEnabled(True)
            for body in bodies:
                label = getattr(body, "Label", getattr(body, "Name", "Body"))
                name = getattr(body, "Name", "")
                self._body_selector.addItem(str(label), name)

            if current_name in self._body_by_name:
                self._set_selector_name(current_name)
        finally:
            self._refreshing_selector = False

    def _body_selector_changed(self, index: int) -> None:
        if self._refreshing_selector or index < 0:
            return
        body_name = self._body_selector.itemData(index)
        body = self._body_by_name.get(body_name)
        if body is None:
            return
        self._remember_body(body)
        self._body = body
        self.strip.set_body(body)
        self._selected_feature = getattr(body, "Tip", None)
        self.strip.set_selected_feature(self._selected_feature)

    def _set_selector_body(self, body) -> None:
        self._set_selector_name(getattr(body, "Name", ""))

    def _set_selector_name(self, body_name: str) -> None:
        index = self._body_selector.findData(body_name)
        if index >= 0:
            self._body_selector.setCurrentIndex(index)

    def _remember_body(self, body) -> None:
        self._selected_body_by_document[self._document_key()] = getattr(
            body, "Name", ""
        )

    def _document_key(self) -> str:
        document = getattr(self._body, "Document", None) or getattr(
            App, "ActiveDocument", None
        )
        return str(getattr(document, "Name", ""))

    def _show_error(self, title: str, exc: Exception) -> None:
        message = f"TipTrack: {title} failed: {exc}"
        App.Console.PrintError(f"{message}\n")
        QtWidgets.QMessageBox.critical(self, title, str(exc))
