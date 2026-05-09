# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline dock widget for TipTrack.

"""Dock widget that hosts the TipTrack timeline UI."""

import FreeCAD as App
import FreeCADGui as Gui

from freecad.TipTrack.body_resolver import get_active_body
from freecad.TipTrack.Qt.Gui import QtCore, QtGui, QtWidgets
from freecad.TipTrack.strip import TimelineStrip
from freecad.TipTrack.tip_controller import set_tip, toggle_suppression


class TipTrackDock(QtWidgets.QDockWidget):
    """Dock widget installed globally in the FreeCAD main window."""

    def __init__(self, parent=None):
        super().__init__("TipTrack - Timeline", parent)
        self._body = None
        self._selected_feature = None

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

        self._body_label = QtWidgets.QLabel("No active Body", toolbar)
        self._body_label.setMinimumWidth(120)
        self._body_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._refresh_button = QtWidgets.QPushButton("Refresh", toolbar)
        self._refresh_button.clicked.connect(self.refresh)

        toolbar_layout.addWidget(self._body_label)
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
        shortcut = shortcut_class(QtGui.QKeySequence(QtCore.Qt.Key_Space), self)
        shortcut.activated.connect(self.toggle_selected_visibility)

        self.refresh()

    @property
    def body(self):
        """Return the Body currently displayed by the dock."""
        return self._body

    def refresh(self) -> None:
        """Refresh the displayed Body and feature strip."""
        self._body = get_active_body()
        self.strip.set_body(self._body)

        if self._body is None:
            self._body_label.setText("No active Body")
            self._selected_feature = None
            return

        label = getattr(self._body, "Label", getattr(self._body, "Name", "Body"))
        self._body_label.setText(str(label))
        self._selected_feature = getattr(self._body, "Tip", None)
        self.strip.set_selected_feature(self._selected_feature)

    def set_selected_feature(self, feature) -> None:
        """Synchronize strip highlighting from an external selection."""
        self._set_selected_feature(feature)

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
            "Delete feature",
            f"Delete {label}?",
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

    def _show_error(self, title: str, exc: Exception) -> None:
        message = f"TipTrack: {title} failed: {exc}"
        App.Console.PrintError(f"{message}\n")
        QtWidgets.QMessageBox.critical(self, title, str(exc))
