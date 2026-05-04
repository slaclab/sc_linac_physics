# SC Linac Physics — Documentation

`sc_linac_physics` is the controls, analysis, and display software for the SLAC Superconducting (SC) Linac. It provides operator GUIs, command-line tools, and a Python library for interacting with the 296-cavity RF system via EPICS/Channel Access.

## How the codebase is organized

```
src/sc_linac_physics/
├── utils/          Shared infrastructure: hardware model, EPICS wrappers, Qt utilities
├── applications/   Standalone applications (auto_setup, q0, tuning, …)
├── displays/       PyDM operator displays (cavity_display, srfhome, …)
└── cli/            Unified entry-point launcher (sc-linac) and watcher management
```

Everything in `applications/` and `displays/` is built on top of `utils/`. Start there if you're new.

## Documentation pages

### Infrastructure

| Page | What it covers |
|------|----------------|
| [Linac Hardware Model](utils/linac_model.md) | `Machine → Linac → Cryomodule → Rack → Cavity` class hierarchy, PV naming, cryomodule groupings, all constants |
| [Shared Utilities](utils/shared_utilities.md) | EPICS `PV` wrapper, `PVBatch`, `platform_paths`, `custom_logger`, Qt helpers |

### Applications

| Page | What it covers |
|------|----------------|
| [Auto Setup](applications/auto_setup.md) | Automated cavity turn-on: SSA calibration → auto-tune → characterization → RF ramp |
| [RF Commissioning](applications/rf_commissioning.md) | Phase-gated acceptance workflow for newly-installed cavities |
| [Q0 Measurement](applications/q0.md) | Cavity quality-factor measurement under thermal load |
| [Microphonics](applications/microphonics.md) | Mechanical vibration noise acquisition and analysis |
| [Quench Processing](applications/quench_processing.md) | Automated fake-quench reset and real-quench detection |
| [Tuning](applications/tuning.md) | Cavity frequency control, state polling, and trend persistence |

### Displays

| Page | What it covers |
|------|----------------|
| [Cavity Display](displays/cavity_display.md) | Fault monitoring dashboard for all 296 cavities with heatmap and audio alerts |
| [SRF Home](displays/srf_home.md) | Top-level launcher panel and watcher management |

## Quick orientation

- The physical machine hierarchy is defined once in `utils/sc_linac/` and reused by every application. Read [Linac Hardware Model](utils/linac_model.md) first.
- EPICS PV names follow a strict naming convention derived from linac/cryomodule/cavity numbers. See [Linac Hardware Model § PV naming](utils/linac_model.md#pv-naming-conventions).
- All applications create a module-level `Machine` subclass singleton (e.g., `SETUP_MACHINE`, `Q0_MACHINE`) that eagerly builds the full object tree at import time.
- Background CLI scripts (quench_resetter, tune_status_poll) are managed as "watchers" from SRF Home or via `sc-watcher`.
- See `AGENTS.md` at the repo root for architectural conventions (PV wrappers to use, logging format, platform path standards).
