# Fault Heatmap Display

A single-screen visualization of fault activity across all 480 cavities in the LCLS superconducting linac. Each cavity is color-coded by fault count over a user-selected time range. Navy/purple means low activity, yellow means the worst offenders.

## Why This Exists

Before the heatmap, figuring out which parts of the linac were having problems meant opening cavity displays one at a time. That works when you already know where to look but it doesn't help when you need the big picture. This tool lets you see every cryomodule and cavity at once so patterns jump out immediately.

## Architecture

Three layers, loosely coupled through Qt signals:

```
Frontend (what you see)
  FaultHeatmapDisplay, HeatmapCMWidget, HeatmapCavityWidget
  ColorBarWidget, SeverityFilter

Data Fetching
  FaultDataFetcher (QThread + ThreadPoolExecutor)
  CavityFaultResult

Backend (pre-existing)
  BackendMachine, BackendCavity.get_fault_counts()
  FaultCounter, EPICS archiver queries
```

The frontend never talks to the archiver directly. `FaultDataFetcher` calls `BackendCavity.get_fault_counts()`, which queries the CUDSTATUS and CUDSEVR PVs from the EPICS archiver. Results are emitted back via Qt signals, keeping the UI responsive.

## File Breakdown

| File | What It Does |
|------|-------------|
| `fault_heatmap_display.py` | Main display window. Controls, grid layout, data flow coordination. |
| `heatmap_cm_widget.py` | One cryomodule column. Label, status bar, and 8 cavity widgets stacked vertically. |
| `heatmap_cavity_widget.py` | Single colored rectangle. Custom `paintEvent`, auto text contrast, selection/highlight borders. |
| `color_mapper.py` | Maps fault count to RGB color via a 6-stop gradient. Supports log scale. |
| `color_bar_widget.py` | Vertical legend on the right. Gradient bar with tick marks, synced with `ColorMapper`. |
| `severity_filter.py` | Toggles which severity levels (alarm/warning/invalid) count toward the total. |
| `fault_data_fetcher.py` | `QThread` that fetches all cavity fault data in parallel. Emits progress and results. |

## How the Data Flows

1. User picks a time range and clicks **Load All Faults**
2. `FaultDataFetcher` spins up a thread pool (8 workers), queries the archiver for each cavity
3. As results come back, the display gets `cavity_result` signals and widgets show a pending state
4. When all queries finish, the display calculates the global max, updates `ColorMapper`'s range, and colors every cavity
5. Severity checkboxes and the TLC dropdown filter counts on the fly without re-fetching

## Color Scale

The default gradient runs through 6 stops:

| Position | Color | Meaning |
|----------|-------|---------|
| 0.0 | Dark purple | No/few faults |
| 0.2 | Blue-purple | Low |
| 0.4 | Teal | Below average |
| 0.6 | Green-teal | Above average |
| 0.8 | Green-yellow | High |
| 1.0 | Bright yellow | Worst |

Log scale is on by default. It spreads out the low end of the range so you can still distinguish cavities with 2 vs 10 faults even when one cavity has 500.

## Selection and Partial Fetch

- **Click** a cavity to select/deselect it (cyan border)
- **Click** a CM label to toggle all 8 cavities in that cryomodule
- **Click** the select button on a linac section header to toggle the whole section
- With cavities selected, **Fetch Selected** re-queries only those cavities, useful for refreshing a trouble spot without waiting for the full linac

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `F5` | Reload all faults |
| `Esc` | Clear selection |

## Running Standalone

```bash
# With a real machine connection
python -m sc_linac_physics.displays.cavity_display.frontend.heatmap.fault_heatmap_display

# For development without EPICS
PYDM_DEFAULT_PROTOCOL=fake python -m sc_linac_physics.displays.cavity_display.frontend.heatmap.fault_heatmap_display
```

The display needs a `BackendMachine` instance. When run as `__main__`, it creates one with `lazy_fault_pvs=True` and sets the archiver timeout to 30 seconds.

## Linac Layout

The grid mirrors the physical linac layout:

```
Row 1:  L0B (1 CM)  |  L1B (2 CMs + H1, H2)  |  L2B (12 CMs)
Row 2:  L3B (20 CMs)
Row 3:  L4B (23 CMs)
```

Each section has its own color theme in the UI so you can tell at a glance which part of the linac you're looking at.

## Testing

```bash
QT_QPA_PLATFORM=offscreen pytest tests/displays/cavity_display/frontend/heatmap/ -v
```

Every module has a corresponding test file in `tests/displays/cavity_display/frontend/heatmap/`.
