<!-- SPDX-License-Identifier: CC0-1.0 -->
<!-- SPDX-FileNotice: Changelog for TipTrack. -->

# Changelog

## Unreleased

- Added Body Placement capture: when the active Body's ``Placement`` changes,
  TipTrack records a snapshot and renders it as a dedicated card on the
  timeline, interleaved chronologically with feature cards. Scrubbing onto a
  placement card re-applies that stored placement and rolls the tip back to
  the anchor feature; position ``0`` restores the original baseline placement.
  A baseline snapshot is recorded automatically the first time TipTrack sees a
  Body (controlled by the new ``Capture Body moves on timeline`` preference,
  default on). Snapshots persist on the Body as a hidden
  ``Group_TipTrackPlacements`` JSON property. Right-clicking a placement card
  offers Restore-as-current / Rename / Delete; placement cards are not
  drag-reorderable.
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
