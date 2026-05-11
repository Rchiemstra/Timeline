# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Unit tests for TipTrack init_gui View menu attachment.

"""Tests for View menu toggle attachment without a running FreeCAD GUI."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QMenu


class _FakeSignal:
    """Minimal stand-in for MainWindow.workbenchActivated."""

    def __init__(self) -> None:
        self._slots: list = []

    def connect(self, slot) -> None:
        self._slots.append(slot)

    def emit(self, *args) -> None:
        for slot in self._slots:
            slot(*args)


class _MainWindowWithWorkbench(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.workbenchActivated = _FakeSignal()


class _BrokenViewMenu(QMenu):
    """QMenu that simulates a deleted or invalid wrapper on addAction."""

    def addAction(self, action):  # noqa: ANN001
        raise RuntimeError("QMenu wrapper is no longer valid")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def init_gui(mock_freecad, qapp):
    """init_gui imports FreeCAD; qapp must exist before Qt widget types load reliably."""
    from freecad.TipTrack import init_gui as m

    return m


@pytest.fixture
def sync_timers(init_gui, monkeypatch):
    """Run QTimer.singleShot callbacks immediately (no event loop)."""

    def _run_immediately(_delay_ms, callback):
        callback()

    monkeypatch.setattr(init_gui.QtCore.QTimer, "singleShot", staticmethod(_run_immediately))


@pytest.fixture
def capture_warnings(mock_freecad):
    app, _gui = mock_freecad
    messages: list[str] = []

    class _Console:
        @staticmethod
        def PrintWarning(msg: str) -> None:
            messages.append(msg)

    app.Console = _Console()
    return messages


def _main_window_with_view(qapp, broken_menu: bool = False) -> tuple[QMainWindow, QMenu]:
    mw = QMainWindow()
    menu_cls = _BrokenViewMenu if broken_menu else QMenu
    view_menu = menu_cls("View", mw)
    mw.menuBar().addMenu(view_menu)
    return mw, view_menu


def test_attach_view_toggle_when_view_menu_alive(
    mock_freecad, qapp, init_gui, sync_timers
):
    """Toggle action is added when the View menu exists and is valid."""
    _app, gui = mock_freecad
    mw, view_menu = _main_window_with_view(qapp)
    dock = QDockWidget(mw)
    mw.addDockWidget(Qt.BottomDockWidgetArea, dock)
    gui.getMainWindow = lambda: mw

    init_gui._try_attach_view_menu_toggle(dock)

    toggle = dock.toggleViewAction()
    assert toggle in view_menu.actions()
    assert toggle.text() == "TipTrack timeline"


def test_retries_exit_cleanly_when_add_action_raises(
    mock_freecad, qapp, init_gui, sync_timers, capture_warnings
):
    """RuntimeError from addAction exhausts retries without crashing or warning."""
    _app, gui = mock_freecad
    mw, _view_menu = _main_window_with_view(qapp, broken_menu=True)
    dock = QDockWidget(mw)
    mw.addDockWidget(Qt.BottomDockWidgetArea, dock)
    gui.getMainWindow = lambda: mw

    init_gui._try_attach_view_menu_toggle(dock)

    assert not any(
        "failed to add View menu action after retries" in m for m in capture_warnings
    )


def test_no_warning_when_view_menu_missing(
    mock_freecad, qapp, init_gui, sync_timers, capture_warnings
):
    """Missing View menu: retries stop quietly (no startup warning)."""
    _app, gui = mock_freecad
    mw = QMainWindow()
    dock = QDockWidget(mw)
    mw.addDockWidget(Qt.BottomDockWidgetArea, dock)
    gui.getMainWindow = lambda: mw

    init_gui._try_attach_view_menu_toggle(dock)

    assert not any(
        "failed to add View menu action after retries" in m for m in capture_warnings
    )


def test_re_resolves_main_window_on_retry(mock_freecad, qapp, init_gui, sync_timers):
    """Each attempt calls Gui.getMainWindow() again (stale closure is not used)."""
    _app, gui = mock_freecad
    mw = QMainWindow()
    view_menu = QMenu("View", mw)
    mw.menuBar().addMenu(view_menu)
    dock = QDockWidget(mw)
    mw.addDockWidget(Qt.BottomDockWidgetArea, dock)

    calls = {"n": 0}

    def get_mw():
        calls["n"] += 1
        if calls["n"] < 3:
            return None
        return mw

    gui.getMainWindow = get_mw

    init_gui._try_attach_view_menu_toggle(dock)

    assert calls["n"] >= 3
    assert dock.toggleViewAction() in view_menu.actions()


def test_workbench_activated_reattach_no_duplicate(
    mock_freecad, qapp, init_gui, sync_timers
):
    """After workbenchActivated, reattach runs once without duplicate actions."""
    _app, gui = mock_freecad
    mw = _MainWindowWithWorkbench()
    view_menu = QMenu("View", mw)
    mw.menuBar().addMenu(view_menu)

    dock = QDockWidget(mw)
    mw.addDockWidget(Qt.BottomDockWidgetArea, dock)
    gui.getMainWindow = lambda: mw

    init_gui._install_workbench_reattach_hook(mw, dock)
    init_gui._try_attach_view_menu_toggle(dock)

    toggle = dock.toggleViewAction()
    assert list(view_menu.actions()).count(toggle) == 1

    mw.workbenchActivated.emit("PartDesignWorkbench")

    assert list(view_menu.actions()).count(toggle) == 1
