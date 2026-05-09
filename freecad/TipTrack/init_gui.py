# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: GUI entry point for the TipTrack addon.

"""Install the TipTrack timeline dock into the FreeCAD main window."""

import FreeCAD as App
import FreeCADGui as Gui

from freecad.TipTrack.Qt.Gui import QtCore
from freecad.TipTrack.dock import TipTrackDock
from freecad.TipTrack.observer import TipTrackObserver

_DOCK_OBJECT_NAME = "TipTrackTimelineDock"
_observer: TipTrackObserver | None = None


def _view_menu(main_window):
    """Return FreeCAD's View menu when it can be found."""
    menu_bar = main_window.menuBar()
    if menu_bar is not None:
        for action in menu_bar.actions():
            menu = action.menu()
            if menu is not None and action.text().replace("&", "") == "View":
                return menu
    return main_window.findChild(QtCore.QObject, "&View")


def _install() -> None:
    """Install the timeline dock and document/selection observers."""
    global _observer

    main_window = Gui.getMainWindow()
    if main_window is None:
        return

    dock = main_window.findChild(TipTrackDock, _DOCK_OBJECT_NAME)
    if dock is None:
        dock = TipTrackDock(main_window)
        dock.setObjectName(_DOCK_OBJECT_NAME)
        main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)

        action = dock.toggleViewAction()
        action.setText("TipTrack timeline")
        view_menu = _view_menu(main_window)
        if view_menu is not None:
            view_menu.addAction(action)

    if _observer is None:
        _observer = TipTrackObserver(dock)
        App.addDocumentObserver(_observer)
        Gui.Selection.addObserver(_observer)


if App.GuiUp:
    QtCore.QTimer.singleShot(0, _install)
