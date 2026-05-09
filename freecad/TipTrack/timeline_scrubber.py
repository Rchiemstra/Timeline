# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline playhead scrubber with feature thumbnails.

"""Horizontal timeline scrubber: thumbnails + draggable playhead."""

from __future__ import annotations

from freecad.TipTrack.feature_item import icon_for
from freecad.TipTrack.i18n import translate
from freecad.TipTrack.Qt.Gui import QtCore, QtGui, QtWidgets

THUMB_W = 56
THUMB_H = 40
CELL_GAP = 6
TRI_H = 10
LABEL_H = 16
MARGIN_H = 8
MARGIN_V = 6
ICON_SIZE = 32


class TimelineScrubber(QtWidgets.QWidget):
    """Thumbnail strip with a draggable playhead and triangular handle."""

    featureChanged = QtCore.Signal(int)
    featureDoubleClicked = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._features: list = []
        self._pixmaps: list[QtGui.QPixmap] = []
        self._labels: list[str] = []
        self._thumb_cache: dict[tuple[str, str], QtGui.QPixmap] = {}
        self._playhead_index = 0
        self._dim_after: int | None = None
        self._dragging_playhead = False
        self._placeholder: str | None = None

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.Fixed,
        )

    def cell_stride(self) -> int:
        return THUMB_W + CELL_GAP

    def content_width(self) -> int:
        if self._placeholder and not self._features:
            return max(200, self.fontMetrics().horizontalAdvance(self._placeholder) + 24)
        n = len(self._features)
        if n == 0:
            return 120
        return MARGIN_H * 2 + n * self.cell_stride() - CELL_GAP

    def minimumSizeHint(self) -> QtCore.QSize:
        h = TRI_H + THUMB_H + LABEL_H + MARGIN_V * 2
        if self._placeholder and not self._features:
            h = max(h, 48)
        return QtCore.QSize(self.content_width(), h)

    def sizeHint(self) -> QtCore.QSize:
        return self.minimumSizeHint()

    def set_placeholder(self, text: str | None) -> None:
        """Show centered status text when there is no feature row."""
        self._placeholder = text
        self.updateGeometry()
        self.update()

    def clear(self) -> None:
        self._features = []
        self._pixmaps = []
        self._labels = []
        self._playhead_index = 0
        self._dim_after = None
        self.updateGeometry()
        self.update()

    def set_features(self, features: list) -> None:
        """Load features and rebuild cached thumbnails (not repainted from icons each frame)."""
        self._features = list(features)
        self._pixmaps = []
        self._labels = []
        fm = self.fontMetrics()
        for feat in self._features:
            key = self._cache_key(feat)
            pm = self._thumb_cache.get(key)
            if pm is None:
                pm = icon_for(feat).pixmap(QtCore.QSize(ICON_SIZE, ICON_SIZE))
                self._thumb_cache[key] = pm
            self._pixmaps.append(pm)
            label = str(getattr(feat, "Label", getattr(feat, "Name", "")))
            self._labels.append(
                fm.elidedText(label, QtCore.Qt.ElideRight, THUMB_W),
            )
        if self._features:
            self._playhead_index = max(
                0, min(self._playhead_index, len(self._features) - 1)
            )
        else:
            self._playhead_index = 0
        self.updateGeometry()
        self.update()

    def _cache_key(self, feat) -> tuple[str, str]:
        vo = getattr(feat, "ViewObject", None)
        icon_blob = str(getattr(vo, "Icon", "") if vo else "")
        return (str(getattr(feat, "Name", "")), icon_blob[:160])

    def set_playhead_index(self, index: int, *, emit_signal: bool = False) -> None:
        if not self._features:
            return
        idx = max(0, min(int(index), len(self._features) - 1))
        old_cx = self.playhead_center_x()
        changed = idx != self._playhead_index
        self._playhead_index = idx
        new_cx = self.playhead_center_x()
        dirty = QtCore.QRect(
            min(old_cx, new_cx) - TRI_H,
            0,
            abs(new_cx - old_cx) + TRI_H * 2,
            self.height(),
        )
        self.update(dirty.normalized())
        self._scroll_playhead_visible()
        if emit_signal and changed:
            self.featureChanged.emit(idx)

    def set_dim_after(self, scrub_index: int | None) -> None:
        """Visually mute thumbnails with index strictly greater than scrub_index."""
        self._dim_after = scrub_index
        self.update()

    def playhead_index(self) -> int:
        return self._playhead_index

    def index_at_x(self, x: int) -> int:
        if not self._features:
            return 0
        stride = self.cell_stride()
        i = int(round((x - MARGIN_H - THUMB_W / 2) / stride))
        return max(0, min(i, len(self._features) - 1))

    def gap_index_at_x(self, x: int) -> int:
        """Insertion gap index for drag-drop (same midpoint convention as old strip)."""
        if not self._features:
            return 0
        stride = self.cell_stride()
        inner_x = x - MARGIN_H + stride / 2
        idx = int(inner_x // stride)
        return max(0, min(idx, len(self._features)))

    def cell_left_x(self, index: int) -> int:
        return MARGIN_H + index * self.cell_stride()

    def playhead_center_x(self) -> int:
        return self.cell_left_x(self._playhead_index) + THUMB_W + CELL_GAP // 2

    def feature_at_index(self, index: int):
        if 0 <= index < len(self._features):
            return self._features[index]
        return None

    def _scroll_playhead_visible(self) -> None:
        scroll = self.parentWidget()
        while scroll is not None and not isinstance(scroll, QtWidgets.QScrollArea):
            scroll = scroll.parentWidget()
        if scroll is None:
            return
        bar = scroll.horizontalScrollBar()
        cx = self.playhead_center_x()
        margin = THUMB_W * 2
        vw = scroll.viewport().width()
        if cx < bar.value() + margin:
            bar.setValue(max(0, cx - margin))
        elif cx > bar.value() + vw - margin:
            bar.setValue(min(bar.maximum(), cx - vw + margin))

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.window().color())

        if self._placeholder and not self._features:
            painter.setPen(palette.mid().color())
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, self._placeholder)
            _ = event
            return

        if not self._features:
            painter.setPen(palette.mid().color())
            painter.drawText(
                self.rect(),
                QtCore.Qt.AlignCenter,
                translate("Active Body has no features."),
            )
            _ = event
            return

        track_top = TRI_H + MARGIN_V // 2
        thumb_y = track_top
        label_y = thumb_y + THUMB_H + 2

        for i, (pm, lbl) in enumerate(zip(self._pixmaps, self._labels)):
            x = self.cell_left_x(i)
            thumb_rect = QtCore.QRect(x, thumb_y, THUMB_W, THUMB_H)
            painter.fillRect(thumb_rect.adjusted(-1, -1, 1, 1), palette.base().color())
            painter.setPen(QtGui.QPen(palette.mid().color(), 1))
            painter.drawRoundedRect(thumb_rect.adjusted(0, 0, -1, -1), 3, 3)

            icon_rect = QtCore.QRect(0, 0, ICON_SIZE, ICON_SIZE)
            icon_rect.moveCenter(thumb_rect.center())
            muted = self._dim_after is not None and i > self._dim_after
            if muted:
                painter.setOpacity(0.38)
            painter.drawPixmap(icon_rect.topLeft(), pm)
            painter.setOpacity(1.0)

            painter.setPen(
                palette.mid().color() if muted else palette.buttonText().color()
            )
            label_rect = QtCore.QRect(x, label_y, THUMB_W, LABEL_H)
            painter.drawText(label_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, lbl)

        cx = self.playhead_center_x()
        tri_top = MARGIN_V // 2
        tri = QtGui.QPolygon(
            [
                QtCore.QPoint(cx, tri_top + TRI_H),
                QtCore.QPoint(cx - TRI_H // 2, tri_top),
                QtCore.QPoint(cx + TRI_H // 2, tri_top),
            ]
        )
        hl = palette.highlight().color()
        painter.setPen(QtGui.QPen(hl, 1))
        painter.setBrush(hl)
        painter.drawPolygon(tri)
        painter.drawLine(cx, tri_top + TRI_H, cx, thumb_y + THUMB_H + LABEL_H)

        _ = event

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if (
            event.button() == QtCore.Qt.LeftButton
            and self._features
            and not self._placeholder
        ):
            self._dragging_playhead = True
            idx = self.index_at_x(event.pos().x())
            self.set_playhead_index(idx, emit_signal=False)
            self.featureChanged.emit(self._playhead_index)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if (
            self._dragging_playhead
            and event.buttons() & QtCore.Qt.LeftButton
            and self._features
        ):
            idx = self.index_at_x(event.pos().x())
            self.set_playhead_index(idx, emit_signal=True)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._dragging_playhead = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._features and event.button() == QtCore.Qt.LeftButton:
            idx = self.index_at_x(event.pos().x())
            self.featureDoubleClicked.emit(idx)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if not self._features or self._placeholder:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta == 0:
            super().wheelEvent(event)
            return
        step = 1 if delta < 0 else -1
        self.set_playhead_index(self._playhead_index + step, emit_signal=True)
        event.accept()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if not self._features:
            super().keyPressEvent(event)
            return
        key = event.key()
        last = len(self._features) - 1
        if key == QtCore.Qt.Key_Left:
            self.set_playhead_index(self._playhead_index - 1, emit_signal=True)
            event.accept()
            return
        if key == QtCore.Qt.Key_Right:
            self.set_playhead_index(self._playhead_index + 1, emit_signal=True)
            event.accept()
            return
        if key == QtCore.Qt.Key_Home:
            self.set_playhead_index(0, emit_signal=True)
            event.accept()
            return
        if key == QtCore.Qt.Key_End:
            self.set_playhead_index(last, emit_signal=True)
            event.accept()
            return
        super().keyPressEvent(event)
