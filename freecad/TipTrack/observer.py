# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: FreeCAD observer stubs for TipTrack.

"""Document and selection observer stubs for TipTrack."""

try:
    import FreeCAD as App
except ImportError:
    App = None

_DocumentObserver = getattr(App, "DocumentObserver", object) if App else object


class TipTrackObserver(_DocumentObserver):
    """Observer that will keep the timeline dock synchronized with FreeCAD."""

    def __init__(self, dock):
        super().__init__()
        self.dock = dock

    def slotChangedObject(self, obj, prop) -> None:
        """Handle changes to document objects."""

    def slotCreatedObject(self, obj) -> None:
        """Handle object creation."""

    def slotDeletedObject(self, obj) -> None:
        """Handle object deletion."""

    def slotActivateDocument(self, doc) -> None:
        """Handle active document changes."""

    def slotDeletedDocument(self, doc) -> None:
        """Handle document deletion."""

    def addSelection(self, doc, obj, sub, point) -> None:
        """Handle FreeCAD selection additions."""

    def removeSelection(self, doc, obj, sub) -> None:
        """Handle FreeCAD selection removals."""

    def setSelection(self, doc) -> None:
        """Handle FreeCAD selection replacement."""

    def clearSelection(self, doc) -> None:
        """Handle FreeCAD selection clearing."""

