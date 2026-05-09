# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline feature item widget for TipTrack.

"""Feature buttons used by the TipTrack timeline strip."""

from pathlib import Path

import FreeCADGui as Gui

from freecad.TipTrack import preferences
from freecad.TipTrack.Qt.Gui import QtCore, QtGui, QtWidgets

ITEM_WIDTH = 56
ITEM_HEIGHT = 72
LABEL_HORIZONTAL_PADDING = 8
MIME_FEATURE = "application/x-tiptrack-feature"


def _event_pos(event):
    position = getattr(event, "position", None)
    if position is not None:
        return position().toPoint()
    return event.pos()


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

    def __init__(
        self,
        feature,
        *,
        is_tip: bool = False,
        item_size: int | None = None,
        show_label: bool | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.feature = feature
        self._is_tip = is_tip
        self._is_selected = False
        self._editor = None
        self._drag_start_pos = None
        self._item_size = item_size or preferences.DEFAULT_ITEM_SIZE
        self._border_color = QtGui.QColor()
        self._background_color = QtGui.QColor(0, 0, 0, 0)
        self._show_label = (
            preferences.DEFAULT_SHOW_LABELS if show_label is None else show_label
        )

        label = str(getattr(feature, "Label", getattr(feature, "Name", "")))
        type_id = str(getattr(feature, "TypeId", "Unknown"))

        self.setIcon(icon_for(feature))
        icon_size = max(22, min(34, self._item_size - 28))
        self.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.setToolTip(f"{label}\n{type_id}")
        item_height = ITEM_HEIGHT if self._show_label else self._item_size
        self.setFixedSize(self._item_size, item_height)
        if self._show_label:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        else:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.clicked.connect(self._emit_selected)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._set_label(label)
        self._apply_style()

    def paintEvent(self, event) -> None:
        """Paint icon and label into fixed regions to avoid text overlap."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window().color())

        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        background = QtGui.QColor(self._background_color)
        if self.underMouse() and background.alpha() == 0:
            background = self.palette().mid().color()
            background.setAlpha(35)
        if background.alpha() > 0:
            painter.setBrush(QtGui.QBrush(background))
        else:
            painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(self._border_color, 1))
        painter.drawRoundedRect(rect, 4, 4)

        content_rect = self.rect().adjusted(4, 4, -4, -4)
        icon_size = self.iconSize()
        if self._show_label:
            label_height = self.fontMetrics().height() + 2
            label_rect = QtCore.QRect(
                content_rect.left(),
                content_rect.bottom() - label_height + 1,
                content_rect.width(),
                label_height,
            )
            icon_area = QtCore.QRect(
                content_rect.left(),
                content_rect.top(),
                content_rect.width(),
                max(1, content_rect.height() - label_height - 3),
            )
        else:
            label_rect = QtCore.QRect()
            icon_area = content_rect

        icon_rect = QtCore.QRect(0, 0, icon_size.width(), icon_size.height())
        icon_rect.moveCenter(icon_area.center())
        self.icon().paint(painter, icon_rect, QtCore.Qt.AlignCenter)

        if self._show_label:
            painter.setPen(self.palette().buttonText().color())
            painter.drawText(label_rect, QtCore.Qt.AlignCenter, self.text())

        _ = event

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
        if not self._show_label:
            self.setText("")
            return

        max_width = max(12, self._item_size - LABEL_HORIZONTAL_PADDING)
        self.setText(
            self.fontMetrics().elidedText(label, QtCore.Qt.ElideRight, max_width)
        )

    def _apply_style(self) -> None:
        palette = self.palette()
        neutral = palette.mid().color().name()
        highlight = palette.highlight().color().name()
        selected = palette.link().color().name()

        border = neutral
        background = QtGui.QColor(0, 0, 0, 0)
        if self._is_tip:
            border = highlight
            background = palette.highlight().color()
            background.setAlpha(35)
        if self._is_selected:
            border = selected
            background = palette.link().color()
            background.setAlpha(35)

        self._border_color = QtGui.QColor(border)
        self._background_color = background
        self.setStyleSheet("QToolButton { border: none; padding: 0; font-size: 10px; }")
        self.update()
