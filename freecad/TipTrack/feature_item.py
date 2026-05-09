# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline feature item widget for TipTrack.

"""Feature buttons used by the TipTrack timeline strip."""

from pathlib import Path

import FreeCADGui as Gui

from freecad.TipTrack.Qt.Gui import QtCore, QtGui, QtWidgets

ITEM_WIDTH = 56
ITEM_HEIGHT = 72
LABEL_LIMIT = 12
MIME_FEATURE = "application/x-tiptrack-feature"


def _event_pos(event):
    position = getattr(event, "position", None)
    if position is not None:
        return position().toPoint()
    return event.pos()


def _short_label(label: str, limit: int = LABEL_LIMIT) -> str:
    if len(label) <= limit:
        return label
    return f"{label[: limit - 3]}..."


def _fallback_icon() -> QtGui.QIcon:
    style = QtWidgets.QApplication.style()
    return style.standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView)


def _icon_from_freecad(value: str) -> QtGui.QIcon | None:
    get_icon = getattr(Gui, "getIcon", None)
    if get_icon is None:
        return None

    try:
        icon = get_icon(value)
    except Exception:
        return None

    if isinstance(icon, QtGui.QIcon):
        return icon
    if isinstance(icon, QtGui.QPixmap):
        return QtGui.QIcon(icon)
    if isinstance(icon, str) and icon:
        return QtGui.QIcon(icon)
    return None


def _icon_from_xpm(value: str) -> QtGui.QIcon | None:
    pixmap = QtGui.QPixmap()
    if pixmap.loadFromData(value.encode("utf-8"), "XPM"):
        return QtGui.QIcon(pixmap)
    return None


def icon_for(feature) -> QtGui.QIcon:
    """Return the best available icon for a FreeCAD feature."""
    view_object = getattr(feature, "ViewObject", None)
    icon_value = getattr(view_object, "Icon", None)

    if isinstance(icon_value, QtGui.QIcon):
        return icon_value
    if isinstance(icon_value, QtGui.QPixmap):
        return QtGui.QIcon(icon_value)
    if isinstance(icon_value, str) and icon_value:
        stripped = icon_value.lstrip()
        if stripped.startswith("/* XPM */"):
            icon = _icon_from_xpm(icon_value)
            if icon is not None:
                return icon
        if icon_value.startswith(":/") or Path(icon_value).exists():
            return QtGui.QIcon(icon_value)
        icon = _icon_from_freecad(icon_value)
        if icon is not None:
            return icon

    icon = _icon_from_freecad(getattr(feature, "TypeId", ""))
    return icon if icon is not None else _fallback_icon()


class FeatureItem(QtWidgets.QToolButton):
    """Compact button representing one feature in a Body history."""

    featureSelected = QtCore.Signal(object)
    editRequested = QtCore.Signal(object)
    setTipRequested = QtCore.Signal(object)
    toggleSuppressRequested = QtCore.Signal(object)
    renameCommitted = QtCore.Signal(object, str)
    deleteRequested = QtCore.Signal(object)

    def __init__(self, feature, *, is_tip: bool = False, parent=None):
        super().__init__(parent)
        self.feature = feature
        self._is_tip = is_tip
        self._is_selected = False
        self._editor = None
        self._drag_start_pos = None

        label = str(getattr(feature, "Label", getattr(feature, "Name", "")))
        type_id = str(getattr(feature, "TypeId", "Unknown"))

        self._set_label(label)
        self.setIcon(icon_for(feature))
        self.setIconSize(QtCore.QSize(28, 28))
        self.setToolTip(f"{label}\n{type_id}")
        self.setFixedSize(ITEM_WIDTH, ITEM_HEIGHT)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.clicked.connect(self._emit_selected)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._apply_style()

    def mousePressEvent(self, event) -> None:
        """Remember the initial press point for drag detection."""
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_start_pos = _event_pos(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Start a feature drag once the cursor passes Qt's drag threshold."""
        if not (event.buttons() & QtCore.Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return

        distance = (_event_pos(event) - self._drag_start_pos).manhattanLength()
        if distance < QtWidgets.QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()
        mime_data.setData(
            MIME_FEATURE, str(getattr(self.feature, "Name", "")).encode("utf-8")
        )
        drag.setMimeData(mime_data)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self._drag_start_pos)

        exec_drag = getattr(drag, "exec", None) or drag.exec_
        exec_drag(QtCore.Qt.MoveAction)

    def mouseDoubleClickEvent(self, event) -> None:
        """Request FreeCAD's native edit task for this feature."""
        self.editRequested.emit(self.feature)
        super().mouseDoubleClickEvent(event)

    def set_tip_active(self, active: bool) -> None:
        """Update whether this item represents the Body tip."""
        self._is_tip = active
        self._apply_style()

    def set_selected_active(self, active: bool) -> None:
        """Update whether this item represents the current selection."""
        self._is_selected = active
        self._apply_style()

    def _emit_selected(self, checked: bool = False) -> None:
        _ = checked
        self.featureSelected.emit(self.feature)

    def _show_context_menu(self, position) -> None:
        menu = QtWidgets.QMenu(self)
        edit_action = menu.addAction("Edit")
        set_tip_action = menu.addAction("Set as tip")
        suppress_action = menu.addAction("Toggle suppress")
        suppress_action.setEnabled(hasattr(self.feature, "Suppressed"))
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")

        exec_menu = getattr(menu, "exec", None) or menu.exec_
        action = exec_menu(self.mapToGlobal(position))
        if action is edit_action:
            self.editRequested.emit(self.feature)
        elif action is set_tip_action:
            self.setTipRequested.emit(self.feature)
        elif action is suppress_action:
            self.toggleSuppressRequested.emit(self.feature)
        elif action is rename_action:
            self._start_rename()
        elif action is delete_action:
            self.deleteRequested.emit(self.feature)

    def _start_rename(self) -> None:
        if self._editor is not None:
            self._editor.setFocus()
            return

        label = str(getattr(self.feature, "Label", getattr(self.feature, "Name", "")))
        editor = QtWidgets.QLineEdit(label, self)
        editor.setGeometry(3, self.height() - 26, self.width() - 6, 22)
        editor.selectAll()
        editor.setFocus(QtCore.Qt.PopupFocusReason)
        editor.editingFinished.connect(self._commit_rename)
        editor.show()
        self._editor = editor

    def _commit_rename(self) -> None:
        editor = self._editor
        if editor is None:
            return

        new_label = editor.text().strip()
        editor.deleteLater()
        self._editor = None

        if not new_label:
            return

        self._set_label(new_label)
        self.renameCommitted.emit(self.feature, new_label)

    def _set_label(self, label: str) -> None:
        self.setText(_short_label(label))

    def _apply_style(self) -> None:
        border = "#5b6772"
        background = "transparent"
        if self._is_tip:
            border = "#28a6f0"
            background = "rgba(40, 166, 240, 35)"
        if self._is_selected:
            border = "#f0a928"
            background = "rgba(240, 169, 40, 35)"

        self.setStyleSheet(
            "QToolButton {"
            f"border: 1px solid {border};"
            "border-radius: 4px;"
            f"background: {background};"
            "padding: 2px;"
            "}"
            "QToolButton:hover {"
            "background: rgba(128, 128, 128, 35);"
            "}"
        )
