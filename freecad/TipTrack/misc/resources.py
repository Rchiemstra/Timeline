# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Resource helpers for the TipTrack addon.

from importlib.resources import as_file, files

import freecad.TipTrack as module

resources = files(module) / 'Resources'
icons = resources / 'Icons'


def as_icon(name: str) -> str:
    icon = icons / (name + '.svg')
    with as_file(icon) as path:
        return str(path)
