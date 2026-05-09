# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Preferences for TipTrack.

"""Preference storage and preferences page for TipTrack."""

import FreeCAD as App

from freecad.TipTrack.i18n import translate
from freecad.TipTrack.Qt.Gui import QtWidgets

PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/TipTrack"

DEFAULT_ITEM_SIZE = 56
DEFAULT_SHOW_LABELS = True
DEFAULT_VISIBLE_ON_STARTUP = True
DEFAULT_SCROLL_WHEEL_PAN = True


def _params():
    param_get = getattr(App, "ParamGet", None)
    if param_get is None:
        return None
    return param_get(PARAM_PATH)


def get_item_size() -> int:
    """Return the configured timeline item width in pixels."""
    params = _params()
    if params is None:
        return DEFAULT_ITEM_SIZE
    return int(params.GetInt("ItemSize", DEFAULT_ITEM_SIZE))


def set_item_size(value: int) -> None:
    """Persist the configured timeline item width in pixels."""
    params = _params()
    if params is not None:
        params.SetInt("ItemSize", int(value))


def get_show_labels() -> bool:
    """Return whether feature labels should be shown under icons."""
    params = _params()
    if params is None:
        return DEFAULT_SHOW_LABELS
    return bool(params.GetBool("ShowLabels", DEFAULT_SHOW_LABELS))


def set_show_labels(value: bool) -> None:
    """Persist whether feature labels should be shown under icons."""
    params = _params()
    if params is not None:
        params.SetBool("ShowLabels", bool(value))


def get_visible_on_startup() -> bool:
    """Return whether the dock should be visible when FreeCAD starts."""
    params = _params()
    if params is None:
        return DEFAULT_VISIBLE_ON_STARTUP
    return bool(params.GetBool("VisibleOnStartup", DEFAULT_VISIBLE_ON_STARTUP))


def set_visible_on_startup(value: bool) -> None:
    """Persist whether the dock should be visible when FreeCAD starts."""
    params = _params()
    if params is not None:
        params.SetBool("VisibleOnStartup", bool(value))


def get_scroll_wheel_pan() -> bool:
    """Return whether mouse wheel events pan the timeline horizontally."""
    params = _params()
    if params is None:
        return DEFAULT_SCROLL_WHEEL_PAN
    return bool(params.GetBool("ScrollWheelPan", DEFAULT_SCROLL_WHEEL_PAN))


def set_scroll_wheel_pan(value: bool) -> None:
    """Persist whether mouse wheel events pan the timeline horizontally."""
    params = _params()
    if params is not None:
        params.SetBool("ScrollWheelPan", bool(value))


class TipTrackPreferences:
    """FreeCAD preference page for TipTrack."""

    def __init__(self):
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(self.form)

        self.item_size = QtWidgets.QSpinBox(self.form)
        self.item_size.setRange(40, 96)
        self.item_size.setSingleStep(4)
        self.item_size.setSuffix(" px")

        self.show_labels = QtWidgets.QCheckBox(self.form)
        self.visible_on_startup = QtWidgets.QCheckBox(self.form)
        self.scroll_wheel_pan = QtWidgets.QCheckBox(self.form)

        layout.addRow(translate("Item size"), self.item_size)
        layout.addRow(translate("Show labels"), self.show_labels)
        layout.addRow(translate("Visible on startup"), self.visible_on_startup)
        layout.addRow(translate("Mouse wheel pans strip"), self.scroll_wheel_pan)

        self.loadSettings()

    def saveSettings(self) -> None:
        """Persist current form values to FreeCAD preferences."""
        set_item_size(self.item_size.value())
        set_show_labels(self.show_labels.isChecked())
        set_visible_on_startup(self.visible_on_startup.isChecked())
        set_scroll_wheel_pan(self.scroll_wheel_pan.isChecked())

    def loadSettings(self) -> None:
        """Load FreeCAD preferences into the form."""
        self.item_size.setValue(get_item_size())
        self.show_labels.setChecked(get_show_labels())
        self.visible_on_startup.setChecked(get_visible_on_startup())
        self.scroll_wheel_pan.setChecked(get_scroll_wheel_pan())

