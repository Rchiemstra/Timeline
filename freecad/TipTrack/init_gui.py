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


def _view_menu_entry(main_window):
    """Return (View QAction, QMenu) when both wrappers are still alive."""
    menu_bar = main_window.menuBar()
    if not _qobject_alive(menu_bar):
        return None, None
    for menu_action in menu_bar.actions():
        if not _qobject_alive(menu_action):
            continue
        try:
            label = menu_action.text().replace("&", "").strip()
        except RuntimeError:
            continue
        if label not in _VIEW_MENU_LABELS:
            continue
        menu = menu_action.menu()
        if menu is not None and _qobject_alive(menu) and isinstance(menu, QtWidgets.QMenu):
            return menu_action, menu
    return None, None


def _schedule_view_menu_retry(dock: TipTrackDock, retry_index: int) -> None:
    """Queue another attachment attempt after a short delay."""
    if retry_index >= len(_VIEW_MENU_RETRY_MS):
        return
    delay = _VIEW_MENU_RETRY_MS[retry_index]
    QtCore.QTimer.singleShot(
        delay,
        lambda d=dock, ri=retry_index + 1: _try_attach_view_menu_toggle(d, ri),
    )


def _schedule_view_menu_reattach(dock: TipTrackDock) -> None:
    """Defer reattach so a workbench switch can finish rebuilding menus first."""
    delay = _VIEW_MENU_RETRY_MS[0]
    QtCore.QTimer.singleShot(delay, lambda d=dock: _try_attach_view_menu_toggle(d, 0))


def _install_workbench_reattach_hook(main_window, dock: TipTrackDock) -> None:
    """Re-run View menu attachment after workbench changes may rebuild menus."""
    if getattr(dock, "_tiptrack_wb_hook_installed", False):
        return
    wb_sig = getattr(main_window, "workbenchActivated", None)
    if wb_sig is None:
        return
    try:
        wb_sig.connect(lambda *_: _schedule_view_menu_reattach(dock))
        dock._tiptrack_wb_hook_installed = True
    except (TypeError, RuntimeError):
        pass


def _try_attach_view_menu_toggle(dock: TipTrackDock, retry_index: int = 0) -> None:
    """Add the dock visibility toggle to the View menu; retry if menus are not ready yet."""
    if not _qobject_alive(dock):
        return

    main_window = Gui.getMainWindow()
    if main_window is None or not _qobject_alive(main_window):
        _schedule_view_menu_retry(dock, retry_index)
        return

    menu_bar = main_window.menuBar()
    if menu_bar is None or not _qobject_alive(menu_bar):
        _schedule_view_menu_retry(dock, retry_index)
        return

    try:
        action = dock.toggleViewAction()
    except RuntimeError:
        action = None
    if action is None or not _qobject_alive(action):
        _schedule_view_menu_retry(dock, retry_index)
        return

    action.setText("TipTrack timeline")

    view_menu_action, view_menu = _view_menu_entry(main_window)
    if (
        view_menu_action is None
        or view_menu is None
        or not _qobject_alive(view_menu_action)
        or not _qobject_alive(view_menu)
    ):
        _schedule_view_menu_retry(dock, retry_index)
        return

    try:
        if action in view_menu.actions():
            dock._tiptrack_view_menu_attached = True
            return
        view_menu.addAction(action)
        dock._tiptrack_view_menu_attached = True
    except RuntimeError:
        _schedule_view_menu_retry(dock, retry_index)


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

        _install_workbench_reattach_hook(main_window, dock)
        _try_attach_view_menu_toggle(dock)

        dock.setVisible(get_visible_on_startup())

    if _observer is None:
        _observer = TipTrackObserver(dock)
        App.addDocumentObserver(_observer)
        Gui.Selection.addObserver(_observer)


if App.GuiUp:
    QtCore.QTimer.singleShot(0, _install)
