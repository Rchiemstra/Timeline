# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Translation helpers for TipTrack.

"""Translation helper for TipTrack user-facing strings."""

from freecad.TipTrack.Qt.Gui import QtCore

CONTEXT = "TipTrack"


def translate(text: str) -> str:
    """Translate text in the TipTrack context."""
    return QtCore.QCoreApplication.translate(CONTEXT, text)

