<!-- SPDX-License-Identifier: CC0-1.0 -->
<!-- SPDX-FileNotice: Changelog for TipTrack. -->

# Changelog

## Unreleased

- Added pre-history timeline position ``0`` (``Body.Tip`` cleared, viewport
  geometry hidden with visibility restored when leaving), slider range
  ``0..N``, and position-based scrubbing via ``scrub_tip_to_position``. Feature
  index helpers still map as ``position = feature_index + 1``. Playback begins
  at pre-history and advances through full history. Pre-history visibility is
  applied after the tip clear and document recompute so the 3D view stays hidden.
  Sketch-only slider positions (no PartDesign tip yet) hide the Body and show
  only the active timeline feature (e.g. the sketch wireframe).

## 0.1.0 - 2026-05-09

- Adapted the FreeCAD addon template for TipTrack.
- Added a global timeline dock for the active PartDesign Body.
- Added feature selection, edit, rename, delete, suppress, set-tip, and visibility actions.
- Added dependency-aware drag reorder logic with unit tests.
- Added multi-body switching, preferences, keyboard navigation, and translation scaffolding.
