# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Qt binding loader for TipTrack.

"""Load whichever PySide binding is available in the host FreeCAD."""

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide import QtCore, QtGui, QtWidgets

__all__ = ("QtCore", "QtGui", "QtWidgets")

