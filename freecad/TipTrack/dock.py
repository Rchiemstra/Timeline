# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline dock widget for TipTrack.

"""Dock widget that hosts the TipTrack timeline UI."""

import FreeCAD as App
import FreeCADGui as Gui

from freecad.TipTrack.body_resolver import (
    get_active_body,
    get_bodies,
    is_live_object,
    safe_getattr,
    safe_object_name,
)
from freecad.TipTrack.i18n import translate
from freecad.TipTrack.Qt.Gui import QtCore, QtGui, QtWidgets
from freecad.TipTrack.strip import TimelineStrip
from freecad.TipTrack.tip_controller import (
    capture_body_group_visibility,
    hide_captured_viewobjects,
    restore_captured_visibility,
    scrub_tip_to_position,
    set_tip,
    set_viewobject_visibility,
    toggle_suppression,
)


class TipTrackDock(QtWidgets.QDockWidget):
    """Dock widget installed globally in the FreeCAD main window."""

    def __init__(self, parent=None):
        super().__init__(translate("TipTrack - Timeline"), parent)
        self._body = None
        self._selected_feature = None
        self._body_by_name = {}
        self._selected_body_by_document = {}
        self._refreshing_selector = False
        self._updating_navigation = False
        self._refresh_depth = 0
        self._scrub_visibility_capture: list = []
        self._scrub_visibility_capture_body = None

        self.setAllowedAreas(
            QtCore.Qt.BottomDockWidgetArea | QtCore.Qt.TopDockWidgetArea
        )

        container = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        toolbar = QtWidgets.QWidget(container)
        toolbar_layout = QtWidgets.QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)

        self._body_selector = QtWidgets.QComboBox(toolbar)
        self._body_selector.setMinimumWidth(140)
        self._body_selector.currentIndexChanged.connect(self._body_selector_changed)

        nav_controls = QtWidgets.QWidget(toolbar)
        nav_layout = QtWidgets.QHBoxLayout(nav_controls)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(1)

        self._first_button = self._make_nav_button(
            "SP_MediaSkipBackward",
            translate("Start"),
            lambda: self.scrub_to_position(0),
        )
        self._previous_button = self._make_nav_button(
            "SP_MediaSeekBackward",
            translate("Previous feature"),
            lambda: self.select_adjacent_feature(-1),
        )
        self._play_button = self._make_nav_button(
            "SP_MediaPlay",
            translate("Play timeline selection"),
            self._toggle_playback,
        )
        self._play_button.setCheckable(True)
        self._next_button = self._make_nav_button(
            "SP_MediaSeekForward",
            translate("Next feature"),
            lambda: self.select_adjacent_feature(1),
        )
        self._last_button = self._make_nav_button(
            "SP_MediaSkipForward",
            translate("Last feature"),
            self.select_last_feature,
        )
        for button in (
            self._first_button,
            self._previous_button,
            self._play_button,
            self._next_button,
            self._last_button,
        ):
            nav_layout.addWidget(button)
        nav_layout.addStretch(1)

        self._refresh_button = QtWidgets.QPushButton(translate("Refresh"), toolbar)
        self._refresh_button.clicked.connect(self.refresh)

        toolbar_layout.addWidget(self._body_selector)
        toolbar_layout.addWidget(nav_controls)
        toolbar_layout.addWidget(self._refresh_button)
        toolbar_layout.addStretch(1)

        self.strip = TimelineStrip(container)
        self.strip.featureSelected.connect(self._set_selected_feature)
        self.strip.featureEditRequested.connect(self.edit_feature)
        self.strip.featureSetTipRequested.connect(self.set_tip_to_feature)
        self.strip.featureToggleSuppressRequested.connect(self.toggle_suppression)
        self.strip.featureRenameCommitted.connect(self.rename_feature)
        self.strip.featureDeleteRequested.connect(self.delete_feature)
        self.strip.featureMoved.connect(self._feature_moved)
        self.strip._timeline_scrubber.featureChanged.connect(
            self._on_timeline_playhead_position_changed
        )

        timeline_panel = QtWidgets.QWidget(container)
        timeline_layout = QtWidgets.QVBoxLayout(timeline_panel)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(0)

        timeline_row = QtWidgets.QWidget(timeline_panel)
        row_layout = QtWidgets.QHBoxLayout(timeline_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self._scrubber = QtWidgets.QSlider(QtCore.Qt.Horizontal, timeline_row)
        self._scrubber.setRange(0, 0)
        self._scrubber.setSingleStep(1)
        self._scrubber.setPageStep(1)
        self._scrubber.setTickPosition(QtWidgets.QSlider.NoTicks)
        self._scrubber.setMinimumWidth(160)
        self._scrubber.setMaximumWidth(220)
        self._scrubber.setToolTip(translate("Timeline scrubber"))
        self._scrubber.valueChanged.connect(self._scrubber_changed)

        row_layout.addWidget(self.strip, 1)
        row_layout.addWidget(
            self._scrubber,
            0,
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
        )

        timeline_layout.addWidget(timeline_row, 1)

        layout.addWidget(toolbar)
        layout.addWidget(timeline_panel, 1)
        self.setWidget(container)

        shortcut_class = getattr(QtGui, "QShortcut", None) or QtWidgets.QShortcut
        visibility_shortcut = shortcut_class(
            QtGui.QKeySequence(QtCore.Qt.Key_Space), self
        )
        visibility_shortcut.activated.connect(self.toggle_selected_visibility)

        left_shortcut = shortcut_class(QtGui.QKeySequence(QtCore.Qt.Key_Left), self)
        left_shortcut.activated.connect(lambda: self.select_adjacent_feature(-1))

        right_shortcut = shortcut_class(QtGui.QKeySequence(QtCore.Qt.Key_Right), self)
        right_shortcut.activated.connect(lambda: self.select_adjacent_feature(1))

        enter_shortcut = shortcut_class(QtGui.QKeySequence(QtCore.Qt.Key_Return), self)
        enter_shortcut.activated.connect(self.set_selected_as_tip)

        delete_shortcut = shortcut_class(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self)
        delete_shortcut.activated.connect(self.delete_selected_feature)

        self._play_timer = QtCore.QTimer(self)
        self._play_timer.setInterval(600)
        self._play_timer.timeout.connect(self._play_next_feature)

        self.refresh()

    @property
    def body(self):
        """Return the Body currently displayed by the dock."""
        if self._body is not None and not is_live_object(self._body):
            return None
        return self._body

    def refresh(self) -> None:
        """Refresh the displayed Body and feature strip."""
        if self._refresh_depth:
            return
        self._refresh_depth += 1
        try:
            if self._body is not None and not is_live_object(self._body):
                self._body = None
            self._body = self._resolve_selected_body()
            self.strip.set_body(self._body)

            if self._body is None:
                self._restore_scrub_visibility_if_needed()
                self._selected_feature = None
                self._update_navigation_controls()
                return

            tip = safe_getattr(self._body, "Tip", None)
            self._selected_feature = tip
            if tip is not None:
                self._restore_scrub_visibility_if_needed()
            self.strip.set_selected_feature(self._selected_feature)
            self._sync_scrubber_to_tip()
            self._update_navigation_controls()
        finally:
            self._refresh_depth -= 1

    def set_selected_feature(self, feature) -> None:
        """Synchronize strip highlighting from an external selection."""
        self._set_selected_feature(feature)

    def select_adjacent_feature(self, step: int) -> None:
        """Move keyboard selection left or right in the strip."""
        features = self.strip.visible_features()
        if not features:
            return

        current_pos = self._scrubber.value()
        next_pos = max(0, min(current_pos + step, len(features)))
        self.scrub_to_position(next_pos)

    def select_feature_at(self, index: int) -> None:
        """Select the feature at index in the current strip."""
        features = self.strip.visible_features()
        if not features:
            self._update_navigation_controls()
            return

        safe_index = max(0, min(index, len(features) - 1))
        self.strip.select_feature(features[safe_index])
        self._update_navigation_controls()

    def scrub_to_position(self, position: int) -> None:
        """Move the scrubber to timeline position ``0`` (pre-history) through ``N`` (full tip)."""
        features = self.strip.visible_features()
        if self._body is None or not features:
            self._update_navigation_controls()
            return

        n = len(features)
        pos = max(0, min(int(position), n))

        try:
            tip_target = scrub_tip_to_position(self._body, pos)
            head = features[pos - 1] if pos > 0 else None
            non_solid = pos == 0 or tip_target is None

            if non_solid:
                self._ensure_scrub_visibility_capture()
                self._apply_non_solid_scrub_visibility(pos, head)
            else:
                self._restore_scrub_visibility_if_needed()

            self.strip.set_body(self._body, scrub_position=pos)
            if pos == 0:
                self._selected_feature = None
                self.strip.set_selected_feature(None)
                try:
                    Gui.Selection.clearSelection()
                except Exception:
                    pass
            elif tip_target is None:
                self._selected_feature = head
                if head is not None:
                    self.strip.select_feature(head)
            else:
                self._selected_feature = head
                if head is not None:
                    self.strip.select_feature(head)

            self._set_scrubber_value(pos)
            self._update_navigation_controls()
        except Exception as exc:
            self._restore_scrub_visibility_if_needed()
            self._show_error("Timeline scrubber", exc)

    def scrub_to_index(self, index: int) -> None:
        """Move the scrubber to feature ``Group[index]`` (slider position ``index + 1``)."""
        features = self.strip.visible_features()
        if self._body is None or not features:
            self._update_navigation_controls()
            return

        safe_index = max(0, min(index, len(features) - 1))
        self.scrub_to_position(safe_index + 1)

    def select_last_feature(self) -> None:
        """Select the last feature in the current strip."""
        features = self.strip.visible_features()
        if features:
            self.scrub_to_position(len(features))

    def set_selected_as_tip(self) -> None:
        """Set the selected feature as the Body tip."""
        if self._selected_feature is not None:
            self.set_tip_to_feature(self._selected_feature)

    def delete_selected_feature(self) -> None:
        """Delete the selected feature after confirmation."""
        if self._selected_feature is not None:
            self.delete_feature(self._selected_feature)

    def edit_feature(self, feature) -> None:
        """Open FreeCAD's native edit task panel for feature."""
        if feature is None or getattr(feature, "Document", None) is None:
            return

        try:
            Gui.ActiveDocument.setEdit(feature.Name)
        except Exception as exc:
            self._show_error("Edit feature", exc)

    def set_tip_to_feature(self, feature) -> None:
        """Set the current Body tip to feature."""
        try:
            set_tip(self._body, feature)
            self.refresh()
        except Exception as exc:
            self._show_error("Set as tip", exc)

    def toggle_suppression(self, feature) -> None:
        """Toggle feature suppression when FreeCAD exposes that property."""
        try:
            toggle_suppression(feature)
            self.refresh()
        except Exception as exc:
            self._show_error("Toggle suppress", exc)

    def rename_feature(self, feature, new_label: str) -> None:
        """Rename feature without recomputing geometry."""
        if feature is None or getattr(feature, "Document", None) is None:
            return

        try:
            feature.Label = new_label
            self.refresh()
        except Exception as exc:
            self._show_error("Rename feature", exc)

    def delete_feature(self, feature) -> None:
        """Delete feature after user confirmation."""
        if feature is None or getattr(feature, "Document", None) is None:
            return

        label = str(getattr(feature, "Label", getattr(feature, "Name", "feature")))
        result = QtWidgets.QMessageBox.question(
            self,
            translate("Delete feature"),
            translate("Delete {label}?").format(label=label),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if result != QtWidgets.QMessageBox.Yes:
            return

        try:
            document = getattr(feature, "Document", None) or App.ActiveDocument
            document.removeObject(feature.Name)
            document.recompute()
            self.refresh()
        except Exception as exc:
            self._show_error("Delete feature", exc)

    def toggle_selected_visibility(self) -> None:
        """Run FreeCAD's visibility toggle command for the selected feature."""
        feature = self._selected_feature
        if feature is None or getattr(feature, "Document", None) is None:
            return

        try:
            Gui.Selection.clearSelection()
            try:
                Gui.Selection.addSelection(feature)
            except Exception:
                Gui.Selection.addSelection(feature.Document.Name, feature.Name)
            Gui.runCommand("Std_ToggleVisibility")
        except Exception as exc:
            App.Console.PrintWarning(f"TipTrack: failed to toggle visibility: {exc}\n")

    def _on_timeline_playhead_position_changed(self, position: int) -> None:
        if self._updating_navigation:
            return
        self.scrub_to_position(int(position))

    def _restore_scrub_visibility_if_needed(self) -> None:
        if self._scrub_visibility_capture:
            restore_captured_visibility(self._scrub_visibility_capture)
        self._scrub_visibility_capture = []
        self._scrub_visibility_capture_body = None

    def _ensure_scrub_visibility_capture(self) -> None:
        body = self._body
        if body is None:
            return
        if self._scrub_visibility_capture_body is body and self._scrub_visibility_capture:
            return
        self._restore_scrub_visibility_if_needed()
        self._scrub_visibility_capture = capture_body_group_visibility(body)
        self._scrub_visibility_capture_body = body

    def _apply_non_solid_scrub_visibility(self, pos: int, head_feature) -> None:
        """Hide Body and all Group objects; at sketch-only positions show *head_feature* only."""
        if not self._scrub_visibility_capture:
            return
        hide_captured_viewobjects(self._scrub_visibility_capture)
        if pos > 0 and head_feature is not None:
            set_viewobject_visibility(head_feature, True)

    def _set_selected_feature(self, feature) -> None:
        self._selected_feature = feature
        self.strip.set_selected_feature(feature)
        self._update_navigation_controls()

    def _feature_moved(self, feature, index: int) -> None:
        _ = index
        self._selected_feature = feature
        self.refresh()

    def _resolve_selected_body(self):
        bodies = get_bodies()
        self._rebuild_body_selector(bodies)
        if not bodies:
            return None

        document_key = self._document_key()
        selected_name = self._selected_body_by_document.get(document_key)
        if selected_name in self._body_by_name:
            return self._body_by_name[selected_name]

        active_body = get_active_body()
        if any(body is active_body for body in bodies):
            self._remember_body(active_body)
            self._set_selector_body(active_body)
            return active_body

        body = bodies[0]
        self._remember_body(body)
        self._set_selector_body(body)
        return body

    def _rebuild_body_selector(self, bodies: list) -> None:
        current_name = safe_object_name(self._body)
        if self._body is not None and current_name is None:
            self._body = None
        self._body_by_name = {
            safe_object_name(body) or "": body for body in bodies
        }

        self._refreshing_selector = True
        try:
            self._body_selector.clear()
            if not bodies:
                self._body_selector.addItem(translate("No active Body"), "")
                self._body_selector.setEnabled(False)
                return

            self._body_selector.setEnabled(True)
            for body in bodies:
                name = safe_object_name(body) or ""
                label = safe_getattr(body, "Label", None) or name or "Body"
                self._body_selector.addItem(str(label), name)

            if current_name in self._body_by_name:
                self._set_selector_name(current_name)
        finally:
            self._refreshing_selector = False

    def _body_selector_changed(self, index: int) -> None:
        if self._refreshing_selector or index < 0:
            return
        self._restore_scrub_visibility_if_needed()
        body_name = self._body_selector.itemData(index)
        body = self._body_by_name.get(body_name)
        if body is None:
            return
        self._remember_body(body)
        self._body = body
        self.strip.set_body(body)
        self._selected_feature = safe_getattr(body, "Tip", None)
        self.strip.set_selected_feature(self._selected_feature)
        self._sync_scrubber_to_tip()
        self._update_navigation_controls()

    def _set_selector_body(self, body) -> None:
        self._set_selector_name(safe_object_name(body) or "")

    def _set_selector_name(self, body_name: str) -> None:
        index = self._body_selector.findData(body_name)
        if index >= 0:
            self._body_selector.setCurrentIndex(index)

    def _remember_body(self, body) -> None:
        self._selected_body_by_document[self._document_key()] = (
            safe_object_name(body) or ""
        )

    def _document_key(self) -> str:
        document = safe_getattr(self._body, "Document", None)
        if document is None:
            document = getattr(App, "ActiveDocument", None)
        return str(getattr(document, "Name", ""))

    def _show_error(self, title: str, exc: Exception) -> None:
        message = f"TipTrack: {title} failed: {exc}"
        App.Console.PrintError(f"{message}\n")
        QtWidgets.QMessageBox.critical(self, title, str(exc))

    def _make_nav_button(self, icon_name: str, tooltip: str, callback):
        button = QtWidgets.QToolButton(self)
        button.setAutoRaise(True)
        button.setFixedSize(24, 22)
        button.setIcon(self.style().standardIcon(_standard_pixmap(icon_name)))
        button.setToolTip(tooltip)
        button.clicked.connect(lambda checked=False: callback())
        return button

    def _scrubber_changed(self, value: int) -> None:
        if self._updating_navigation:
            return
        self.scrub_to_position(value)

    def _toggle_playback(self) -> None:
        if self._play_button.isChecked():
            if not self.strip.visible_features():
                self._play_button.setChecked(False)
                return
            self.scrub_to_position(0)
            self._play_timer.start()
        else:
            self._play_timer.stop()

    def _play_next_feature(self) -> None:
        features = self.strip.visible_features()
        if not features:
            self._stop_playback()
            return

        current_pos = self._current_scrub_position(features)
        n = len(features)
        if current_pos >= n:
            self._stop_playback()
            return

        self.scrub_to_position(current_pos + 1)

    def _stop_playback(self) -> None:
        self._play_timer.stop()
        self._play_button.setChecked(False)

    def _current_feature_index(self, features: list | None = None) -> int:
        features = features if features is not None else self.strip.visible_features()
        return next(
            (
                index
                for index, feature in enumerate(features)
                if feature is self._selected_feature
            ),
            0,
        )

    def _current_scrub_position(self, features: list | None = None) -> int:
        features = features if features is not None else self.strip.visible_features()
        if not features:
            return 0
        n = len(features)
        return max(0, min(self._scrubber.value(), n))

    def _sync_scrubber_to_tip(self) -> None:
        features = self.strip.visible_features()
        tip = safe_getattr(self._body, "Tip", None)
        n = len(features)
        if tip is not None:
            try:
                tip_position = features.index(tip) + 1
            except ValueError:
                tip_position = 0
            if tip_position > 0:
                self._restore_scrub_visibility_if_needed()
        else:
            tip_position = max(0, min(self._scrubber.value(), n)) if n else 0
        self._set_scrubber_value(tip_position)

    def _set_scrubber_value(self, value: int) -> None:
        self._updating_navigation = True
        try:
            self._scrubber.setValue(value)
        finally:
            self._updating_navigation = False

    def _update_navigation_controls(self) -> None:
        features = self.strip.visible_features()
        has_features = bool(features)
        max_pos = len(features)
        current_pos = self._current_scrub_position(features) if has_features else 0

        self._updating_navigation = True
        try:
            self._scrubber.setEnabled(has_features)
            self._scrubber.setRange(0, max(0, max_pos))
            self._scrubber.setValue(current_pos)
        finally:
            self._updating_navigation = False

        at_first = current_pos <= 0
        at_last = current_pos >= max_pos
        self._first_button.setEnabled(has_features and not at_first)
        self._previous_button.setEnabled(has_features and not at_first)
        self._next_button.setEnabled(has_features and not at_last)
        self._last_button.setEnabled(has_features and not at_last)
        self._play_button.setEnabled(has_features)
        if not has_features or at_last:
            self._stop_playback()

        self._sync_strip_scrub_visual()

    def _sync_strip_scrub_visual(self) -> None:
        if self._body is None:
            return
        self.strip.apply_scrub_mute(self._scrubber.value())


def _standard_pixmap(name: str):
    return getattr(QtWidgets.QStyle, name, QtWidgets.QStyle.SP_ArrowRight)
