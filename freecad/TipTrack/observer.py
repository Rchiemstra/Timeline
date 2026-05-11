# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: FreeCAD observer stubs for TipTrack.

"""Document and selection observer for TipTrack."""

try:
    import FreeCAD as App
except ImportError:
    App = None

from freecad.TipTrack.body_resolver import body_contains, get_active_body, is_body

_DocumentObserver = getattr(App, "DocumentObserver", object) if App else object

_REFRESH_PROPERTIES = {"Group", "Tip", "Label", "Visibility"}
_PLACEMENT_PROPERTY = "Placement"


class TipTrackObserver(_DocumentObserver):
    """Observer that will keep the timeline dock synchronized with FreeCAD."""

    def __init__(self, dock):
        super().__init__()
        self.dock = dock

    def slotChangedObject(self, obj, prop) -> None:
        """Handle changes to document objects."""
        if prop == _PLACEMENT_PROPERTY and is_body(obj):
            self._handle_body_placement_change(obj)
            return
        if prop in _REFRESH_PROPERTIES and self._affects_current_body(obj):
            self._refresh()

    def slotCreatedObject(self, obj) -> None:
        """Handle object creation."""
        if is_body(obj):
            self._handle_body_created(obj)
        if is_body(obj) or self._affects_current_body(obj):
            self._refresh()

    def slotDeletedObject(self, obj) -> None:
        """Handle object deletion."""
        self._refresh()

    def slotActivateDocument(self, doc) -> None:
        """Handle active document changes."""
        self._refresh()

    def slotDeletedDocument(self, doc) -> None:
        """Handle document deletion."""
        self._refresh()

    def addSelection(self, doc, obj, sub, point) -> None:
        """Handle FreeCAD selection additions."""
        feature = self._resolve_selection(doc, obj)
        if feature is not None and self._affects_current_body(feature):
            self.dock.set_selected_feature(feature)

    def removeSelection(self, doc, obj, sub) -> None:
        """Handle FreeCAD selection removals."""

    def setSelection(self, doc) -> None:
        """Handle FreeCAD selection replacement."""

    def clearSelection(self, doc) -> None:
        """Handle FreeCAD selection clearing."""

    def _refresh(self) -> None:
        refresh = getattr(self.dock, "refresh", None)
        if refresh is not None:
            refresh()

    def _handle_body_placement_change(self, body) -> None:
        """Forward a body.Placement change to the dock for snapshot capture."""
        handler = getattr(self.dock, "handle_body_placement_change", None)
        if handler is None:
            return
        try:
            handler(body)
        except Exception:
            return

    def _handle_body_created(self, body) -> None:
        """Forward a new-body event so the dock can record its baseline placement."""
        handler = getattr(self.dock, "handle_body_created", None)
        if handler is None:
            return
        try:
            handler(body)
        except Exception:
            return

    def _affects_current_body(self, obj) -> bool:
        body = getattr(self.dock, "body", None) or get_active_body()
        if body is None:
            return is_body(obj)
        return is_body(obj) or body_contains(body, obj)

    def _resolve_selection(self, doc, obj):
        if obj is None:
            return None
        if not isinstance(obj, str):
            return obj
        if App is None:
            return None

        try:
            document = App.getDocument(doc) if isinstance(doc, str) else doc
            return document.getObject(obj)
        except Exception:
            return None
