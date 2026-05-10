# Cavity Display

`displays/cavity_display/` is the primary real-time fault monitoring dashboard for the SC Linac. It shows fault status across all 296 cavities organized in a hierarchical tree, with optional heatmap visualization and audio alerts for unacknowledged alarms.

## Architecture overview

```
cavity_display/
├── backend/
│   ├── backend_cavity.py   — per-cavity fault collection and PV monitoring
│   ├── backend_machine.py  — builds the BackendCavity hierarchy
│   ├── fault.py            — individual fault condition (PV + threshold + description)
│   └── runner.py           — continuous polling service
├── frontend/
│   ├── cavity_widget.py    — individual cavity tile (color-coded by severity)
│   ├── gui_cavity.py       — cavity row in tree view
│   ├── gui_cryomodule.py   — cryomodule section in tree view
│   ├── gui_machine.py      — top-level display
│   ├── alarm_sidebar.py    — persistent unacknowledged alarm list
│   ├── audio_manager.py    — escalating audio alerts
│   └── heatmap/            — alternative 2D grid visualization
│       ├── color_mapper.py
│       ├── heatmap_cavity_widget.py
│       └── heatmap_cm_widget.py
├── cavity_display.py       — PyDM Display entry point
└── utils/
    ├── faults.csv          — fault definitions (PV suffix, threshold, description)
    └── utils.py
```

## Backend

### `BackendCavity` (`backend/backend_cavity.py`)

Extends `Cavity` with fault monitoring. Key methods:

- `create_faults()` — parses `faults.csv` and instantiates `Fault` objects keyed by hash. Each fault knows its PV name, threshold, and human-readable description.
- `_batch_pv_init()` — connects status output PVs using `PV.batch_create()`. Input fault PVs are read-only and fetched via `caget_many()` (no persistent PV objects).
- `get_faults()` — returns current fault status by batch-reading fault input PVs.
- `check_archives()` — queries the EPICS archiver for historical fault frequency over a configurable time window.

### `Fault` (`backend/fault.py`)

Represents one fault condition. Computes:
- Current status (OK / WARNING / ALARM / INVALID) by comparing PV value to threshold
- Severity (maps to PyDM alarm color conventions)
- Description string for display

### `runner.py`

Continuous service loop:
1. Calls `check_cavities()` on all `BackendCavity` objects
2. Publishes fault summary to output PVs (for archiver and other displays)
3. Sleeps `BACKEND_SLEEP_TIME` between iterations
4. Handles Ctrl+C gracefully during initialization

## Frontend

### Tree view hierarchy

```
gui_machine.py (GUIMachine)
└── gui_cryomodule.py (GUICryomodule)  ×60
    └── gui_cavity.py (GUICavity)       ×8
        └── cavity_widget.py (CavityWidget)
```

`CavityWidget` shows a colored tile — green (no alarm), yellow (warning), red (alarm), gray (invalid) — that reflects the worst current fault severity for that cavity. Clicking a tile expands a fault detail panel.

### `AlarmSidebar` (`frontend/alarm_sidebar.py`)

Persistent list of unacknowledged alarms across all cavities. Items remain until an operator explicitly acknowledges them. Provides a scrollable view separate from the main tree.

### `AudioAlertManager` (`frontend/audio_manager.py`)

Escalating audio alerts:
- **ALARM** severity → sound immediately
- **WARNING** severity → sound after 2-minute grace period
- Per-cavity rate limiting: no more than one sound per cavity per 5 minutes, preventing alert storms
- Logs alert events separately from the main application log

### Heatmap (`frontend/heatmap/`)

Alternative visualization showing all cavities as a 2D color grid:

- `ColorMapper` — maps numeric fault count (0 to `vmax`) to a Blue → White → Red gradient using a non-linear normalized scale (0.5 = white = neutral)
- `HeatmapCavityWidget` — single cavity cell
- `HeatmapCMWidget` — one cryomodule row with 8 cavity cells
- `SeverityFilter` — filters which fault severities are shown

## Key design choices

- **Fault PVs read via `caget_many()`** — fault *input* PVs are never stored as `PV` objects. Batch reads minimize connection overhead for 296 cavities × N faults.
- **Only output PVs are `PV` objects** — needed for `put()` calls (publishing fault summaries); everything else is read-only via batch CA.
- **Archive-based trend alerts** — historical fault frequency (e.g., "faulted 10 times today") supplements instantaneous severity for context-aware alerting.
- **`faults.csv` drives fault definitions** — adding a new fault condition requires only a CSV row, no code change. The CSV is packaged in the wheel and verified in CI.

## Entry points

```bash
sc-cavity           # cavity display
sc-faults           # fault decoder sub-display
sc-fcount           # fault count sub-display
```
