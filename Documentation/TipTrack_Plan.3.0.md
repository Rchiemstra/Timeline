# TipTrack — FreeCAD Horizontal Timeline Addon

**Project goal:** Build a FreeCAD addon that displays the active `PartDesign::Body`'s feature history as a horizontal strip docked at the bottom of the main window, similar in feel to Autodesk Fusion 360's timeline. The strip lets users click to roll the model back to any feature, double-click to edit, drag to reorder (within dependency constraints), and stays in sync with the rest of the FreeCAD UI.

**Working name:** TipTrack (named after FreeCAD's `Body.Tip` property — feel free to rename in `package.xml`, the workbench class, and the docs in one pass at the end).

**Target FreeCAD version:** 1.0 or newer. FreeCAD 1.0 introduced the new toponaming code, which is what makes feature reordering safe enough to expose in a UI. Do **not** support 0.21 or earlier.

**Starting point:** The repository was bootstrapped from the official [FreeCAD/Addon-Template](https://github.com/FreeCAD/Addon-Template). Most files described below already exist; the agent's job in Phase 0 is to rename and customize them, not to author them from scratch. Reference the template's [Structure wiki page](https://github.com/FreeCAD/Addon-Template/wiki/Structure) when in doubt about where something belongs.

---

## Tech stack and conventions

- **Language:** Python 3.10+ (whatever ships with the target FreeCAD).
- **GUI:** Qt via PySide. The template provides a binding shim under `freecad/TipTrack/Qt/`. Import through it:

  ```python
  from freecad.TipTrack.Qt.Gui import QtCore, QtGui, QtWidgets
  ```

  This works regardless of whether the host FreeCAD ships PySide2 or PySide6. Don't `import PySide` directly outside the shim itself.

- **FreeCAD APIs:** `import FreeCAD as App` and `import FreeCADGui as Gui`. Treat these as available only when `App.GuiUp` is true.
- **No external Python dependencies** beyond what FreeCAD ships with. The addon must install via the Addon Manager with no extra `pip install` step.
- **License:** LGPL-3.0-or-later for code (`LICENSE-CODE`), CC-BY-SA-4.0 for icons and media (`LICENSE-ICON`). These are the licenses the template ships with — keep both files unchanged; just verify the copyright holder line.
- **Style:** PEP 8, type hints where they help, docstrings on every public class and function. No frameworks like Pydantic.
- **Logging:** Use `FreeCAD.Console.PrintMessage` / `PrintWarning` / `PrintError`, not `print()` or `logging`.

---

## Repository layout

This follows the FreeCAD/Addon-Template structure exactly. Files marked **(template)** already exist and just need editing; files marked **(new)** must be added by the agent.

```
TipTrack/
├── .github/
│   ├── CONTRIBUTING.md          # (template) edit to describe TipTrack
│   └── FUNDING.yml              # (template) optional, can delete or fill in
├── .vscode/
│   └── extensions.json          # (template) keep as-is
├── Documentation/
│   ├── README.md                # (template) entrypoint for full docs
│   └── Usage/
│       ├── Howto-Install.md     # (template, rename) install instructions
│       └── Howto-Reorder.md     # (new) explains drag-reorder rules in Phase 3
├── Resources/
│   ├── Documents/
│   │   └── Overview.md          # (template) shown in the Addon Manager — keep short
│   ├── Icons/
│   │   └── Logo.svg             # (template, replace) TipTrack logo
│   └── Media/
│       └── Header.webp          # (template, replace) screenshot of the strip in action
├── freecad/
│   └── TipTrack/                # renamed from `Minimal/` in the template
│       ├── __init__.py          # (template) loaded headless + GUI; keep almost empty
│       ├── init_gui.py          # (template) GUI-only entry point; we expand this
│       ├── Qt/
│       │   ├── Core.py          # (template) PySide Qt-binding shim — keep as-is
│       │   ├── Gui.py           # (template) Qt widgets shim — keep as-is
│       │   └── Widget.py        # (template) sample widget — replace with our dock
│       ├── Resources/
│       │   └── Icons/
│       │       └── Logo.svg     # (template) bundled icon used at runtime
│       ├── dock.py              # (new) TipTrackDock(QDockWidget)
│       ├── strip.py             # (new) TimelineStrip(QWidget)
│       ├── feature_item.py      # (new) FeatureItem(QToolButton)
│       ├── observer.py          # (new) DocumentObserver + Selection observer
│       ├── body_resolver.py     # (new) get_active_body() and helpers
│       ├── tip_controller.py    # (new) wraps Body.Tip mutations + recompute
│       └── reorder.py           # (new) Phase 3: dependency analysis
├── tests/                       # (new) pytest, runs without FreeCAD
│   ├── conftest.py
│   └── test_reorder.py
├── .editorconfig                # (template) keep as-is
├── .gitignore                   # (template) keep as-is
├── CHANGELOG.md                 # (template) edit
├── LICENSE-CODE                 # (template) keep as-is (LGPL-3.0)
├── LICENSE-ICON                 # (template) keep as-is (CC-BY-SA-4.0)
├── README.md                    # (template) edit — repo front page
├── package.xml                  # (template) edit every field
└── pyproject.toml               # (template) edit name + dev deps
```

**Important conventions from the template:**

- The Python code lives under `freecad/TipTrack/` as a [namespace package](https://wiki.freecad.org/PEP420). FreeCAD discovers it because `freecad/` is a namespace package shared across all modern addons. Do **not** add an `__init__.py` to the `freecad/` directory itself.
- Entry points are `__init__.py` (loaded for both CLI and GUI) and `init_gui.py` (loaded only when the GUI is up). These are lowercase with underscores, *not* the legacy `Init.py` / `InitGui.py` you'll see in older addons.
- The template provides a Qt binding shim under `freecad/TipTrack/Qt/` so the addon code can do `from freecad.TipTrack.Qt.Gui import QtWidgets` and not care whether the host is using PySide2 or PySide6. Use this shim everywhere instead of importing PySide directly.
- `pyproject.toml` is for *development* tools only (linters, formatters, pytest). The addon is not pip-installed by users — they get it through the FreeCAD Addon Manager, which clones the repo into FreeCAD's `Mod/` directory.
- `Resources/Documents/Overview.md` is rendered inside FreeCAD's Addon Manager dialog, which uses Qt's limited Markdown renderer. Keep it short, plain, and don't rely on advanced Markdown features there. The full README on GitHub can be richer.

---

## Phase 0 — Adapt the template (target: 1 session)

The repo was cloned from FreeCAD/Addon-Template, so most scaffolding exists. This phase is a search-and-replace exercise plus enough wiring to confirm the addon loads.

### Tasks

1. **Rename the namespace package**: `freecad/Minimal/` → `freecad/TipTrack/`. Update every import that referenced `freecad.Minimal` accordingly. There won't be many — the template is intentionally small.

2. **Update `package.xml`**: every field. Specifically:
   - `<name>TipTrack</name>`
   - `<description>` — one sentence, English. This is what shows in the Addon Manager grid.
   - `<version>0.0.1</version>` — start here, not 0.1.0; reserve 0.1.0 for the first user-facing release.
   - `<maintainer>` with the user's name + email (the human, not the agent — leave a `TODO(maintainer)` comment if the agent doesn't have it).
   - `<license>` — keep `LGPL-3.0-or-later` for code; the template's setup is correct.
   - `<url type="repository">` and `<url type="readme">` and `<url type="bugtracker">` — point to the GitHub repo.
   - `<dependencies>` — add `<freecad>` with `min="1.0"`.
   - `<content>` — declare a `<preferencepack>` only if needed (no, for us); declare the addon as a `<workbench>` only if we end up making it one. Per the architecture decision below, we won't, so use `<content type="other">` instead. Verify the exact tag against the [Package Metadata wiki](https://wiki.freecad.org/Package_Metadata) since this part of the spec evolves.

3. **Update `pyproject.toml`**: change the project name to `tiptrack`, update the description, add dev dependencies (`pytest`, `ruff`). Do not add runtime dependencies — there are none.

4. **Replace `Resources/Icons/Logo.svg`** with a simple TipTrack logo. A placeholder is fine for now (e.g., a small SVG with a horizontal row of three rectangles, the middle one highlighted). Keep dimensions square, around 64×64 viewBox. Do the same for `freecad/TipTrack/Resources/Icons/Logo.svg`.

5. **Edit `README.md`** at the repo root: TipTrack title, one-paragraph description, GIF/screenshot placeholder, install instructions (via Addon Manager once published, or by cloning into `Mod/` for development), link to `Documentation/README.md`.

6. **Edit `Resources/Documents/Overview.md`** — this is the Addon Manager's view of the project. Keep it under ~200 words, no images that aren't bundled, no nested HTML.

7. **Edit `CHANGELOG.md`**: clear template content, add an `## Unreleased` section at the top.

8. **Architecture decision in `init_gui.py`**: do **not** register a workbench. Instead, install a global dock widget. Replace the template's workbench-registration code with:

   ```python
   import FreeCAD as App
   import FreeCADGui as Gui
   from freecad.TipTrack.Qt.Gui import QtCore
   from freecad.TipTrack.dock import TipTrackDock
   from freecad.TipTrack.observer import TipTrackObserver

   def _install():
       main_window = Gui.getMainWindow()
       dock = TipTrackDock(main_window)
       main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)
       observer = TipTrackObserver(dock)
       App.addDocumentObserver(observer)
       Gui.Selection.addObserver(observer)
       # Add toggle action under the View menu
       view_menu = main_window.findChild(QtCore.QObject, "&View")
       if view_menu is not None:
           view_menu.addAction(dock.toggleViewAction())

   if App.GuiUp:
       # Defer until the main window is fully constructed
       QtCore.QTimer.singleShot(0, _install)
   ```

   The `singleShot(0, ...)` trick is important: `init_gui.py` runs before the main window's menus are fully built, so synchronous installation often fails silently.

9. **Stub `dock.py`**: minimal `TipTrackDock(QDockWidget)` whose central widget is just a `QLabel("TipTrack timeline — Phase 0 stub")`. Phase 1 fills it in.

10. **Stub `observer.py`**: a class with all the observer methods present but doing nothing. Phase 1 wires them up.

11. **Verify the template's Qt shim works**: import `QtCore`, `QtGui`, `QtWidgets` from `freecad.TipTrack.Qt.Gui` (or whichever module the shim exposes — read `Qt/Gui.py` to confirm) and use those everywhere. Don't `import PySide` directly outside that shim.

12. **Set up `tests/`**: `conftest.py` should make the `freecad` namespace importable for tests by mocking `App` and `Gui` imports. A pytest fixture `mock_freecad` that patches `sys.modules["FreeCAD"]` and `sys.modules["FreeCADGui"]` is the standard approach. The agent will use this fixture for `reorder.py` tests in Phase 3.

### Acceptance criteria

- Symlink (or copy) the repo into FreeCAD's `Mod/` directory, restart FreeCAD, and the View menu has a "TipTrack timeline" toggle.
- Toggling it shows a dock at the bottom with the placeholder label.
- No errors in the Report View at startup, and no errors when opening, switching, or closing documents.
- `pytest` runs (even if zero tests yet) without import errors.
- `package.xml` validates — load it via the Addon Manager from a local Git URL and confirm metadata renders.

---

## Phase 1 — Read-only timeline (MVP)

This is the phase that delivers the core "it looks like Fusion's timeline" experience.

### Tasks

1. **`body_resolver.py`** — function `get_active_body()`:
   - If `Gui.ActiveDocument` is None or has no objects → return None.
   - Prefer the body containing the currently selected object (`Gui.Selection.getSelection()`).
   - Otherwise, prefer the body marked as active via `Gui.ActiveDocument.ActiveView.getActiveObject("pdbody")`.
   - Otherwise, the first object with `TypeId == "PartDesign::Body"`.
   - Return None if no Body exists in the document. The strip should render an empty/help state in that case.

2. **`strip.py`** — `TimelineStrip(QWidget)`:
   - Horizontal `QHBoxLayout`, left-aligned, with a `QScrollArea` wrapper for long histories.
   - Method `set_body(body)` rebuilds the strip from `body.Group`.
   - Each feature becomes a `FeatureItem` widget (next file).
   - The widget corresponding to `body.Tip` gets a highlight (different border color or background).
   - Empty state: single muted label "No active Body — create one in Part Design."

3. **`feature_item.py`** — `FeatureItem(QToolButton)`:
   - Icon comes from `feature.ViewObject.Icon` if available, else a generic gear.
   - Convert FreeCAD's `XPM`/`SVG` icon string to a `QIcon`. FreeCAD provides a helper: `Gui.getIcon(name)` for built-ins, but for `ViewObject.Icon` you typically build a `QPixmap` from the XPM string. Write a small `icon_for(feature)` helper in `feature_item.py` that handles both cases.
   - Tooltip: feature `Label` (user-facing name) and `TypeId`.
   - Below the icon, show the feature's `Label` truncated to ~12 chars.
   - Fixed size: 56×72 pixels. The strip should feel dense but readable.

4. **`dock.py`** — `TipTrackDock(QDockWidget)`:
   - Title: "TipTrack — Timeline".
   - Allowed areas: bottom and top only.
   - Content widget hosts the `TimelineStrip` plus a thin toolbar on the left with: a body-selector `QComboBox` (Phase 4 will populate it; for MVP just show the active body name as a label) and a "Refresh" button.

5. **`observer.py`** — `TipTrackObserver(App.DocumentObserver)`:
   - Subclass `App.DocumentObserver` and override:
     - `slotChangedObject(obj, prop)` — refresh if `obj` is a Body or any feature inside the active Body, and `prop` is one of `Group`, `Tip`, `Label`, `Visibility`.
     - `slotCreatedObject(obj)` / `slotDeletedObject(obj)` — refresh if affects active body.
     - `slotActivateDocument(doc)` / `slotDeletedDocument(doc)` — full rebuild.
   - Register via `App.addDocumentObserver(self)` in `init_gui.py` after the dock is created. Unregister on app shutdown.
   - Also add a `Gui.Selection` observer (`Gui.Selection.addObserver(...)`) so that selecting a feature elsewhere highlights it in the strip.

6. **Click-to-rollback** (read-only "rollback view," no destructive change):
   - Single click on a `FeatureItem`: select that feature in the tree (`Gui.Selection.clearSelection(); Gui.Selection.addSelection(feature)`).
   - Spacebar in the strip simulates the FreeCAD "show this state" toggle. Easiest implementation: install a `QShortcut` on the dock that calls `Gui.runCommand("Std_ToggleVisibility")` after ensuring the right feature is selected.

### Acceptance criteria

- Open `chain_link.FCStd` (the user's example file). The bottom dock shows: Origin, Sketch, Pad, Pad001, Pad002, Sketch002, Hole, Sketch003 — in that order, with icons.
- The current Tip (Hole, in that file) is visually highlighted.
- Adding a new Pad in Part Design causes the strip to gain a new button without manual refresh.
- Renaming a feature in the tree updates its label in the strip.
- Closing the document clears the strip.

### Out of scope for Phase 1

- Editing features.
- Reordering.
- Multi-body support (just show the resolved active body).
- Group folders.
- Dark/light theme adjustments beyond what Qt does automatically.

---

## Phase 2 — Interactivity

### Tasks

1. **Double-click to edit**: `FeatureItem` emits `editRequested(feature)`. The dock connects this to `Gui.ActiveDocument.setEdit(feature.Name)`. This opens FreeCAD's normal task panel for the feature, identical to what double-clicking the tree does.

2. **Set Tip from the strip** (this is the real "drag the Fusion timeline marker" equivalent):
   - Right-click context menu on a `FeatureItem` includes "Set as tip."
   - Clicking it calls `tip_controller.set_tip(body, feature)`, which wraps:

     ```python
     body.Tip = feature
     App.ActiveDocument.recompute()
     ```

   - The strip refreshes its highlight.

3. **Suppress / unsuppress**: context menu adds "Toggle suppress." Implementation: features in PartDesign have a `Suppressed` boolean property on some types and not others. Check `hasattr(feature, "Suppressed")` first; if absent, gray out the menu item. Recompute after toggling.

4. **Rename**: context menu "Rename" opens a small inline `QLineEdit` over the label. On commit, set `feature.Label = new_name`.

5. **Delete**: context menu "Delete" asks for confirmation, then `App.ActiveDocument.removeObject(feature.Name)`. Be defensive — if the deletion would orphan dependents, FreeCAD will complain; catch the exception and show a message box.

6. **Selection sync, both directions**:
   - Strip click → tree selection (already done in Phase 1).
   - Tree click → strip highlight. Implement via the `Gui.Selection` observer's `addSelection` callback.

### Acceptance criteria

- Double-clicking the Pad button opens the Pad's edit task panel.
- Right-click → "Set as tip" on Pad001 makes the model render only up to Pad001 and updates the highlight.
- Right-click → "Delete" on Sketch003 removes it from both the strip and the tree.
- Selecting Hole in the tree highlights Hole in the strip.

---

## Phase 3 — Reorder with dependency awareness

This is the hardest phase and where most "Fusion-clone for FreeCAD" attempts have stopped. Budget more time for it.

### Tasks

1. **`reorder.py`** — pure-logic module, no Qt:

   - `def can_move(body, feature, new_index) -> tuple[bool, str]`: returns `(True, "")` if the move is dependency-legal, else `(False, "reason for user")`.
   - The check: build the dependency graph from each feature's `OutList` (what it depends on). A feature cannot end up before any of its `OutList` members. A feature cannot end up after any feature in its `InList` (things that depend on it).
   - Write unit tests for this in `tests/test_reorder.py` against synthetic mock objects. This module should be testable without launching FreeCAD.

2. **Drag-and-drop in `TimelineStrip`**:
   - Enable drag on `FeatureItem` via `mousePressEvent` + `QDrag` with a custom MIME type `application/x-tiptrack-feature` carrying the feature's `Name`.
   - The strip accepts drops and computes a target index from the drop x-coordinate.
   - Before accepting, call `reorder.can_move(...)`. If illegal, show a tooltip with the reason and refuse the drop (visual: red ghost while dragging).
   - On legal drop:
     - Reassign `body.Group` to the new ordered list. Note: `body.Group` is read-only in some FreeCAD versions; the supported way to reorder is via `body.removeObject(feature)` then `body.insertObject(feature, before_target)`. Verify which API works in 1.0+ and use that.
     - Recompute and refresh the strip.

3. **Visual feedback during drag**: insertion indicator (a 2px vertical line at the drop position), legal/illegal cursor, snap to gaps between items.

### Acceptance criteria

- Dragging Pad001 to before Pad in `chain_link.FCStd` is rejected (Pad001 may depend on Pad).
- Dragging Hole to before Sketch003 succeeds if Hole doesn't reference Sketch003.
- Reorders are persisted on save and survive a reload.
- The `reorder.can_move` tests pass without FreeCAD running.

---

## Phase 4 — Polish

### Tasks

1. **Multi-body switcher**: the body-selector `QComboBox` (placeholder from Phase 1) now lists every Body in the active document. Switching it changes which body's history is shown. Active selection persists per document.

2. **Group folders**: Fusion lets users group timeline operations into collapsible folders. FreeCAD doesn't have a native equivalent in `Body.Group`. Implement this as TipTrack-only metadata stored in `body.Group_TipTrackFolders` (a serialized JSON property on the body, added by us). Out of scope to make this round-trip with other tools — it's a TipTrack convenience.

3. **Dark/light theme awareness**: read FreeCAD's stylesheet preference and adjust highlight color, separator color, and item background accordingly. Don't hardcode colors.

4. **Preferences page**: add a TipTrack pane under Edit → Preferences via `Gui.addPreferencePage(...)`. Settings: item size, show labels yes/no, default visibility on startup, scroll-wheel-to-pan-strip.

5. **Keyboard navigation**: left/right arrows move highlight along the strip; Enter sets tip; Delete removes feature.

6. **Localization**: wrap user-facing strings in `QtCore.QCoreApplication.translate("TipTrack", "…")` or use `FreeCAD.Qt.translate`. Ship an English `.ts` file; others can be PR'd later.

### Acceptance criteria

- Documents with two Bodies show a working selector.
- The strip looks correct in both FreeCAD's default light theme and a common dark theme (e.g. "Dark Modern").
- Preferences persist across restarts.

---

## Phase 5 — Distribution

### Tasks

1. Verify the addon installs cleanly via the Addon Manager from a local Git URL. The template's `package.xml` and namespace-package layout should make this straightforward.
2. Confirm the `Resources/Documents/Overview.md` page renders correctly inside the Addon Manager dialog (it uses Qt's limited Markdown — re-check after any edits).
3. Tag `v0.1.0` on the repo.
4. Open a PR to https://github.com/FreeCAD/FreeCAD-addons adding TipTrack to the index, per their contribution guidelines. The template's `package.xml` is already in the format the index scrapes.
5. Write a release entry in `CHANGELOG.md` and link it from `README.md`.
6. Optional: announce on the FreeCAD forum's "Open discussion" subforum with a link to the repo and a screenshot. The forum reaction will be a useful early bug-finder.

---

## Cross-cutting concerns the agent should keep in mind

- **Don't fight FreeCAD's recompute model.** After any mutation that affects geometry (`body.Tip = ...`, `body.removeObject(...)`, `feature.Suppressed = True`), call `App.ActiveDocument.recompute()`. After mutations that are display-only (`Label` rename, our internal folder metadata), do **not** recompute — it's expensive.
- **Guard every callback against stale references.** If a document is closed while a Qt event is in flight, `feature` references can dangle. Check `feature.Document is not None` before touching anything.
- **Never assume a single document.** Use `Gui.ActiveDocument` and `App.ActiveDocument` consistently and refresh on document-switch.
- **Don't add a workbench just to have one.** TipTrack is a global dock, not a workbench. Adding it as a workbench would force users to switch workbenches to use it, defeating the point.
- **Topological naming**: in FreeCAD 1.0+, reordering a feature can still occasionally break references. The addon should not try to fix this — surface FreeCAD's own warnings to the user via a status label in the dock when a recompute fails.

---

## Reference materials

- FreeCAD scripting basics: https://wiki.freecad.org/Power_users_hub
- Document observers: https://wiki.freecad.org/PySide_Beginner_Examples (has a section on observers) and the source of `App.DocumentObserver`.
- PartDesign Body internals: https://wiki.freecad.org/PartDesign_Body and the C++ source at `src/Mod/PartDesign/App/Body.cpp` for the canonical behavior of `Tip`, `Group`, `insertObject`.
- Addon Manager `package.xml` spec: https://wiki.freecad.org/Package_Metadata
- Existing related addon for inspiration on dock-widget patterns: the `Ribbon` addon (https://github.com/APEbbers/FreeCAD-Ribbon) — it adds top-of-window UI and is a good reference for how to inject UI into the main window without being a workbench.
- Fusion's own `VerticalTimeline` addon (going the opposite direction, Fusion-side): https://github.com/thomasa88/VerticalTimeline — useful only as a UX reference for what users expect.

---

## Definition of done for v0.1.0

- Phase 0, 1, 2 complete and acceptance criteria met.
- Phase 3 may be partial (drag UI working, dependency check working, but folder grouping / multi-body deferred).
- Installs cleanly via Addon Manager from a Git URL.
- README has install instructions, a screenshot, and a known-issues section.
- At least 5 unit tests in `tests/` covering `reorder.can_move` edge cases.
- No exceptions in FreeCAD's Report View during normal use on `chain_link.FCStd` and one multi-body test file.

Anything beyond this is v0.2 territory.
