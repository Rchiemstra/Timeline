# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Placeholder widget exports for TipTrack.

"""Placeholder module kept for compatibility with the addon template layout."""

from freecad.TipTrack.Qt.Gui import QtCore, QtWidgets


class PhaseZeroWidget(QtWidgets.QWidget):
    """Small placeholder widget used before the timeline strip is implemented."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel("TipTrack timeline - Phase 0 stub")
        label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(label)

