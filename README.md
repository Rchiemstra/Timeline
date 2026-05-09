<!-- SPDX-License-Identifier: CC0-1.0 -->
<!-- SPDX-FileNotice: Project README for TipTrack. -->

# TipTrack

TipTrack is a FreeCAD addon that shows the active `PartDesign::Body` feature
history as a horizontal docked timeline. The goal is a compact strip where users
can inspect the feature sequence, select items, set the Body tip, and eventually
reorder features within dependency constraints.

![TipTrack timeline placeholder](Resources/Media/Header.webp)

## Install

TipTrack targets FreeCAD 1.0 or newer.

### Windows copy install

Copy this repository folder to FreeCAD's user `Mod` directory as `TipTrack`:

```text
%APPDATA%\FreeCAD\Mod\TipTrack
```

The resulting layout should look like this:

```text
%APPDATA%\FreeCAD\Mod\TipTrack\
├── freecad\
│   └── TipTrack\
├── Resources\
├── package.xml
└── README.md
```

Restart FreeCAD. The dock should appear at the bottom as `TipTrack - Timeline`.

### Windows development install

For development, a junction is easier than copying because FreeCAD loads the
repo directly:

```powershell
$mod = Join-Path $env:APPDATA "FreeCAD\Mod"
New-Item -ItemType Directory -Force -Path $mod
New-Item -ItemType Junction -Path (Join-Path $mod "TipTrack") -Target "C:\Users\Rchie\Music\Timeline"
```

Remove the junction with:

```powershell
Remove-Item "$env:APPDATA\FreeCAD\Mod\TipTrack"
```

### Addon Manager

Once published, TipTrack should be installable through FreeCAD's Addon Manager
from the repository URL.

## Test

### Python checks in Docker

Run the normal test and static-check suite from the repo root:

```powershell
docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim sh -lc "python -m pip install --quiet pytest ruff && pytest -q && python -m compileall -q freecad tests && python - <<'PY'
import xml.etree.ElementTree as ET
ET.parse('package.xml')
print('package.xml parsed')
PY
ruff check freecad tests"
```

Expected result: all pytest tests pass, `package.xml parsed`, and Ruff reports
`All checks passed!`.

### FreeCAD GUI smoke test in Docker

This test starts FreeCAD 1.0.2 under Xvfb, creates a PartDesign Body with
features, loads the TipTrack dock, moves the timeline scrubber, verifies
`Body.Tip` rollback behavior, saves screenshots, and writes a test model.

On Windows, run the helper script:

```bat
run-freecad-integration.bat
```

Or run the Docker command directly:

```powershell
docker run --rm -v "${PWD}:/work" -w /work --entrypoint /bin/bash lscr.io/linuxserver/freecad:1.0.2 -lc "rm -rf /work/artifacts/freecad_tiptrack_frame_*.png /work/artifacts/tiptrack_integration.FCStd /work/artifacts/tiptrack_integration_summary.json /work/artifacts/tiptrack_integration_failure.txt; TIPTRACK_REPO_ROOT=/work TIPTRACK_ARTIFACT_DIR=/work/artifacts timeout 120s xvfb-run -a /opt/freecad/usr/bin/freecad /work/tests/integration/freecad_tiptrack_gui_smoke.py"
```

Recommended for reproducible runs (includes **ffmpeg**; writes MP4/GIF automatically):

```powershell
docker compose run --rm tiptrack-integration
```

Artifacts are written to `artifacts/`:

- `freecad-tiptrack-integration.mp4` / `.gif` — encoded from composite PNG frames (3D viewport stacked above the TipTrack dock); produced inside **Compose**, or by `run-freecad-integration.bat` when **ffmpeg** is on `PATH`
- `tiptrack_integration.FCStd`
- `tiptrack_integration_summary.json`

Full project notes live in [Documentation/README.md](Documentation/README.md).

## Known Issues

- The Docker GUI smoke test validates dock loading and timeline behavior, but a
  manual Addon Manager install test is still needed before publishing.
- Drag reorder depends on FreeCAD 1.0+ `PartDesign::Body.insertObject` behavior
  and may still surface FreeCAD recompute warnings for fragile model references.
- Timeline folder metadata helpers exist, but folder UI grouping is not exposed
  yet.

## Release Notes

See [CHANGELOG.md](CHANGELOG.md).
