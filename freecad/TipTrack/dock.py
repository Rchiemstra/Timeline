# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline dock widget for TipTrack.

"""Dock widget that hosts the TipTrack timeline UI."""

from freecad.TipTrack.Qt.Gui import QtCore, QtWidgets


class TipTrackDock(QtWidgets.QDockWidget):
    """Dock widget installed globally in the FreeCAD main window."""

    def __init__(self, parent=None):
        super().__init__("TipTrack - Timeline", parent)
        self.setAllowedAreas(
            QtCore.Qt.BottomDockWidgetArea | QtCore.Qt.TopDockWidgetArea
        )

        label = QtWidgets.QLabel("TipTrack timeline - Phase 0 stub")
        label.setAlignment(QtCore.Qt.AlignCenter)
        self.setWidget(label)

