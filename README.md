<!-- SPDX-License-Identifier: CC0-1.0 -->
<!-- SPDX-FileNotice: Project README for TipTrack. -->

# TipTrack

TipTrack is a FreeCAD addon that shows the active `PartDesign::Body` feature
history as a horizontal docked timeline. The goal is a compact strip where users
can inspect the feature sequence, select items, set the Body tip, and eventually
reorder features within dependency constraints.

![TipTrack timeline placeholder](Resources/Media/Header.webp)

## Installation

TipTrack targets FreeCAD 1.0 or newer.

For development, clone this repository into FreeCAD's `Mod` directory and
restart FreeCAD:

```bash
git clone https://github.com/Rchiemstra/Timeline.git TipTrack
```

Once published, TipTrack should be installable through FreeCAD's Addon Manager.

Full project notes live in [Documentation/README.md](Documentation/README.md).
