# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Qt GUI shim for TipTrack.

"""Expose QtCore, QtGui, and QtWidgets through one import path."""

from freecad.TipTrack.Qt.Core import QtCore, QtGui, QtWidgets

__all__ = ("QtCore", "QtGui", "QtWidgets")

