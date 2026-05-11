# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Timeline playhead scrubber with feature thumbnails.

"""Horizontal timeline scrubber: thumbnails + draggable playhead."""

from __future__ import annotations

from freecad.TipTrack.feature_item import icon_for, placement_icon
from freecad.TipTrack.i18n import translate
from freecad.TipTrack.placement_history import KIND_FEATURE, KIND_PLACEMENT, TimelineItem
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
    itemContextRequested = QtCore.Signal(int, QtCore.QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[TimelineItem] = []
        self._pixmaps: list[QtGui.QPixmap] = []
        self._labels: list[str] = []
        self._kinds: list[str] = []
        self._thumb_cache: dict[tuple[str, str], QtGui.QPixmap] = {}
        # Slider position 0 = pre-history; 1..N align with item cards 0..N-1.
        self._playhead_position = 0
        self._dim_from_position: int | None = None
        self._dragging_playhead = False
        self._placeholder: str | None = None
        self._placement_icon_cache: QtGui.QPixmap | None = None

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.Fixed,
        )

    def cell_stride(self) -> int:
        return THUMB_W + CELL_GAP

    def content_width(self) -> int:
        if self._placeholder and not self._items:
            return max(200, self.fontMetrics().horizontalAdvance(self._placeholder) + 24)
        n = len(self._items)
        if n == 0:
            return 120
        return MARGIN_H * 2 + n * self.cell_stride() - CELL_GAP

    def minimumSizeHint(self) -> QtCore.QSize:
        h = TRI_H + THUMB_H + LABEL_H + MARGIN_V * 2
        if self._placeholder and not self._items:
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
        self._items = []
        self._pixmaps = []
        self._labels = []
        self._kinds = []
        self._playhead_position = 0
        self._dim_from_position = None
        self.updateGeometry()
        self.update()

    def set_items(self, items: list) -> None:
        """Load items (features and placement snapshots) and cache thumbnails.

        Accepts either a list of ``TimelineItem`` or (for back-compat) a plain
        feature list, which is wrapped in feature ``TimelineItem`` objects.
        """
        items = [self._coerce_item(entry) for entry in items]
        self._items = items
        self._pixmaps = []
        self._labels = []
        self._kinds = [item.kind for item in items]
        fm = self.fontMetrics()
        for item in items:
            self._pixmaps.append(self._pixmap_for(item))
            self._labels.append(
                fm.elidedText(item.label, QtCore.Qt.ElideRight, THUMB_W),
            )
        if items:
            n = len(items)
            self._playhead_position = max(0, min(self._playhead_position, n))
        else:
            self._playhead_position = 0
        self.updateGeometry()
        self.update()

    # Back-compat alias: callers that previously passed a feature list keep working.
    set_features = set_items

    def _coerce_item(self, entry) -> TimelineItem:
        if isinstance(entry, TimelineItem):
            return entry
        return TimelineItem.for_feature(entry)

    def _pixmap_for(self, item: TimelineItem) -> QtGui.QPixmap:
        if item.is_feature:
            key = self._cache_key(item.feature)
            pm = self._thumb_cache.get(key)
            if pm is None:
                pm = icon_for(item.feature).pixmap(QtCore.QSize(ICON_SIZE, ICON_SIZE))
                self._thumb_cache[key] = pm
            return pm
        if self._placement_icon_cache is None:
            self._placement_icon_cache = placement_icon().pixmap(
                QtCore.QSize(ICON_SIZE, ICON_SIZE)
            )
        return self._placement_icon_cache

    def _cache_key(self, feat) -> tuple[str, str]:
        vo = getattr(feat, "ViewObject", None)
        icon_blob = str(getattr(vo, "Icon", "") if vo else "")
        return (str(getattr(feat, "Name", "")), icon_blob[:160])

    def playhead_center_for_position(self, position: int) -> int:
        """X center of the playhead for timeline *position* (``0`` = pre-history)."""
        n = len(self._items)
        pos = max(0, min(int(position), n))
        if pos == 0:
            return max(TRI_H // 2 + 1, self.cell_left_x(0) - CELL_GAP // 2 - 2)
        return self.cell_left_x(pos - 1) + THUMB_W + CELL_GAP // 2

    def set_playhead_position(self, position: int, *, emit_signal: bool = False) -> None:
        """Move the playhead to slider position ``0`` (pre-history) through ``N`` (full history)."""
        if not self._items:
            return
        n = len(self._items)
        idx = max(0, min(int(position), n))
        old_cx = self.playhead_center_x()
        changed = idx != self._playhead_position
        self._playhead_position = idx
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

    def set_playhead_index(self, item_index: int, *, emit_signal: bool = False) -> None:
        """Move playhead to the right edge of card *item_index* (slider = index + 1)."""
        if not self._items:
            return
        self.set_playhead_position(int(item_index) + 1, emit_signal=emit_signal)

    def set_dim_after(self, scrub_position: int | None) -> None:
        """Dim feature cards with index >= *scrub_position* (0 dims every thumbnail)."""
        self._dim_from_position = scrub_position
        self.update()

    def playhead_position(self) -> int:
        return self._playhead_position

    def playhead_index(self) -> int:
        """Legacy: feature index under the playhead, or ``0`` at pre-history."""
        if self._playhead_position <= 0:
            return 0
        return self._playhead_position - 1

    def position_at_x(self, x: int) -> int:
        """Map pixel *x* to slider position ``0..N``."""
        if not self._items:
            return 0
        n = len(self._items)
        centers = [self.playhead_center_for_position(p) for p in range(n + 1)]
        return min(range(n + 1), key=lambda p: abs(centers[p] - x))

    def index_at_x(self, x: int) -> int:
        """Item card index ``0..N-1`` for hit-testing (e.g. double-click on a card)."""
        if not self._items:
            return 0
        stride = self.cell_stride()
        i = int(round((x - MARGIN_H - THUMB_W / 2) / stride))
        return max(0, min(i, len(self._items) - 1))

    def gap_index_at_x(self, x: int) -> int:
        """Insertion gap index for drag-drop (item-space; strip translates to features)."""
        if not self._items:
            return 0
        stride = self.cell_stride()
        inner_x = x - MARGIN_H + stride / 2
        idx = int(inner_x // stride)
        return max(0, min(idx, len(self._items)))

    def cell_left_x(self, index: int) -> int:
        return MARGIN_H + index * self.cell_stride()

    def playhead_center_x(self) -> int:
        return self.playhead_center_for_position(self._playhead_position)

    def feature_at_index(self, index: int):
        """Return the FreeCAD feature at index, or None if the card is a placement."""
        if 0 <= index < len(self._items):
            item = self._items[index]
            if item.is_feature:
                return item.feature
        return None

    def item_at_index(self, index: int) -> TimelineItem | None:
        """Return the timeline item at index, or None when out of range."""
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def items(self) -> list[TimelineItem]:
        """Return a shallow copy of the currently displayed timeline items."""
        return list(self._items)

    def kind_at_index(self, index: int) -> str | None:
        """Return ``"feature"`` or ``"placement"`` for index, or None if out of range."""
        if 0 <= index < len(self._kinds):
            return self._kinds[index]
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

        if self._placeholder and not self._items:
            painter.setPen(palette.mid().color())
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, self._placeholder)
            _ = event
            return

        if not self._items:
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

        for i, (pm, lbl, kind) in enumerate(zip(self._pixmaps, self._labels, self._kinds)):
            x = self.cell_left_x(i)
            thumb_rect = QtCore.QRect(x, thumb_y, THUMB_W, THUMB_H)
            if kind == KIND_PLACEMENT:
                bg = palette.alternateBase().color()
                painter.fillRect(thumb_rect.adjusted(-1, -1, 1, 1), bg)
                pen_color = palette.highlight().color()
                pen = QtGui.QPen(pen_color, 1, QtCore.Qt.DashLine)
            else:
                painter.fillRect(
                    thumb_rect.adjusted(-1, -1, 1, 1), palette.base().color()
                )
                pen = QtGui.QPen(palette.mid().color(), 1)
            painter.setPen(pen)
            painter.drawRoundedRect(thumb_rect.adjusted(0, 0, -1, -1), 3, 3)

            icon_rect = QtCore.QRect(0, 0, ICON_SIZE, ICON_SIZE)
            icon_rect.moveCenter(thumb_rect.center())
            muted = self._dim_from_position is not None and i >= self._dim_from_position
            if muted:
                painter.setOpacity(0.38)
            painter.drawPixmap(icon_rect.topLeft(), pm)
            painter.setOpacity(1.0)

            painter.setPen(
                palette.mid().color() if muted else palette.buttonText().color()
            )
            label_rect = QtCore.QRect(x, label_y, THUMB_W, LABEL_H)
            painter.drawText(label_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, lbl)
            _ = KIND_FEATURE  # imported for clarity / API surface

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
            and self._items
            and not self._placeholder
        ):
            self._dragging_playhead = True
            pos = self.position_at_x(event.pos().x())
            self.set_playhead_position(pos, emit_signal=False)
            self.featureChanged.emit(self._playhead_position)
            event.accept()
            return
        if (
            event.button() == QtCore.Qt.RightButton
            and self._items
            and not self._placeholder
        ):
            idx = self.index_at_x(event.pos().x())
            global_pos_fn = getattr(event, "globalPosition", None)
            if global_pos_fn is not None:
                global_point = global_pos_fn().toPoint()
            else:
                global_point = event.globalPos()
            self.itemContextRequested.emit(idx, global_point)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if (
            self._dragging_playhead
            and event.buttons() & QtCore.Qt.LeftButton
            and self._items
        ):
            pos = self.position_at_x(event.pos().x())
            self.set_playhead_position(pos, emit_signal=True)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._dragging_playhead = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._items and event.button() == QtCore.Qt.LeftButton:
            idx = self.index_at_x(event.pos().x())
            self.featureDoubleClicked.emit(idx)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if not self._items or self._placeholder:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta == 0:
            super().wheelEvent(event)
            return
        step = 1 if delta < 0 else -1
        self.set_playhead_position(self._playhead_position + step, emit_signal=True)
        event.accept()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if not self._items:
            super().keyPressEvent(event)
            return
        key = event.key()
        last = len(self._items)
        if key == QtCore.Qt.Key_Left:
            self.set_playhead_position(self._playhead_position - 1, emit_signal=True)
            event.accept()
            return
        if key == QtCore.Qt.Key_Right:
            self.set_playhead_position(self._playhead_position + 1, emit_signal=True)
            event.accept()
            return
        if key == QtCore.Qt.Key_Home:
            self.set_playhead_position(0, emit_signal=True)
            event.accept()
            return
        if key == QtCore.Qt.Key_End:
            self.set_playhead_position(last, emit_signal=True)
            event.accept()
            return
        super().keyPressEvent(event)
