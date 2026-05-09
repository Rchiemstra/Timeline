# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline feature item widget for TipTrack.

"""Feature buttons used by the TipTrack timeline strip."""

from pathlib import Path

import FreeCADGui as Gui

from freecad.TipTrack.Qt.Gui import QtCore, QtGui, QtWidgets

ITEM_WIDTH = 56
ITEM_HEIGHT = 72
LABEL_LIMIT = 12


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

    def __init__(self, feature, *, is_tip: bool = False, parent=None):
        super().__init__(parent)
        self.feature = feature
        self._is_tip = is_tip
        self._is_selected = False

        label = str(getattr(feature, "Label", getattr(feature, "Name", "")))
        type_id = str(getattr(feature, "TypeId", "Unknown"))

        self.setText(_short_label(label))
        self.setIcon(icon_for(feature))
        self.setIconSize(QtCore.QSize(28, 28))
        self.setToolTip(f"{label}\n{type_id}")
        self.setFixedSize(ITEM_WIDTH, ITEM_HEIGHT)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.clicked.connect(self._emit_selected)
        self._apply_style()

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
