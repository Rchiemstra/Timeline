# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: GUI entry point for the TipTrack addon.

"""Install the TipTrack timeline dock into the FreeCAD main window."""

import FreeCAD as App
import FreeCADGui as Gui

from freecad.TipTrack.Qt.Gui import QtCore, QtWidgets
from freecad.TipTrack.dock import TipTrackDock
from freecad.TipTrack.observer import TipTrackObserver
from freecad.TipTrack.preferences import TipTrackPreferences, get_visible_on_startup

_DOCK_OBJECT_NAME = "TipTrackTimelineDock"
_observer: TipTrackObserver | None = None
_preferences_installed = False

# Delays for re-resolving the View menu if the menubar is still wiring up or was rebuilt.
_VIEW_MENU_RETRY_MS = (50, 150, 400, 1000)

# Stripped QAction.text() values for the standard View menu (add locales as needed).
_VIEW_MENU_LABELS = frozenset(
    {
        "View",
        "Ansicht",  # de
        "Vue",  # fr
        "Vista",  # es, it
        "Widok",  # pl
        "Просмотр",  # ru
        "表示",  # ja
        "查看",  # zh_CN
        "檢視",  # zh_TW
    }
)


def _qobject_alive(obj: QtCore.QObject | None) -> bool:
    """True if the binding still wraps a live Qt object (not already destroyed in C++)."""
    if obj is None:
        return False
    try:
        obj.metaObject()
    except RuntimeError:
        return False
    return True


def _view_menu(main_window):
    """Return FreeCAD's View menu when it can be found."""
    menu_bar = main_window.menuBar()
    if not _qobject_alive(menu_bar):
        return None
    for action in menu_bar.actions():
        if not _qobject_alive(action):
            continue
        try:
            label = action.text().replace("&", "").strip()
        except RuntimeError:
            continue
        if label not in _VIEW_MENU_LABELS:
            continue
        menu = action.menu()
        if menu is not None and _qobject_alive(menu) and isinstance(menu, QtWidgets.QMenu):
            return menu
    return None


def _try_attach_view_menu_toggle(main_window, dock: TipTrackDock, retry_index: int = 0) -> None:
    """Add the dock visibility toggle to the View menu; retry if menus are not ready yet."""
    if getattr(dock, "_tiptrack_view_menu_attached", False):
        return

    action = dock.toggleViewAction()
    action.setText("TipTrack timeline")
    view_menu = _view_menu(main_window)

    if view_menu is not None:
        try:
            view_menu.addAction(action)
            dock._tiptrack_view_menu_attached = True
            return
        except RuntimeError as exc:
            last_error = exc
    else:
        last_error = None

    if retry_index >= len(_VIEW_MENU_RETRY_MS):
        detail = last_error if last_error is not None else "View menu not found"
        App.Console.PrintWarning(
            f"TipTrack: failed to add View menu action after retries: {detail}\n"
        )
        return

    delay = _VIEW_MENU_RETRY_MS[retry_index]
    QtCore.QTimer.singleShot(
        delay,
        lambda: _try_attach_view_menu_toggle(main_window, dock, retry_index + 1),
    )


def _install() -> None:
    """Install the timeline dock and document/selection observers."""
    global _observer, _preferences_installed

    main_window = Gui.getMainWindow()
    if main_window is None:
        return

    if not _preferences_installed:
        try:
            Gui.addPreferencePage(TipTrackPreferences, "TipTrack")
            _preferences_installed = True
        except Exception as exc:
            App.Console.PrintWarning(
                f"TipTrack: failed to install preferences page: {exc}\n"
            )

    dock = main_window.findChild(TipTrackDock, _DOCK_OBJECT_NAME)
    if dock is None:
        dock = TipTrackDock(main_window)
        dock.setObjectName(_DOCK_OBJECT_NAME)
        main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)

        _try_attach_view_menu_toggle(main_window, dock)

        dock.setVisible(get_visible_on_startup())

    if _observer is None:
        _observer = TipTrackObserver(dock)
        App.addDocumentObserver(_observer)
        Gui.Selection.addObserver(_observer)


if App.GuiUp:
    QtCore.QTimer.singleShot(0, _install)
