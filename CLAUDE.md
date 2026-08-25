# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_cli.py -v

# Run with coverage report (80% minimum enforced in CI)
pytest --cov=sc_linac_physics --cov-report=term-missing

# Lint
flake8 . --count --max-complexity=10 --max-line-length=120 --show-source --statistics
black --check .

# Format
black .

# Install for development
pip install -e ".[dev,test]"
```

Set `PYDM_DEFAULT_PROTOCOL=fake` to run UI code without live EPICS hardware.

## Documentation

Full documentation lives in [`docs/`](docs/index.md):
- [`docs/utils/linac_model.md`](docs/utils/linac_model.md) — hardware model, PV naming, all constants
- [`docs/utils/shared_utilities.md`](docs/utils/shared_utilities.md) — EPICS `PV`/`PVBatch`, logger, Qt helpers
- [`docs/applications/auto_setup.md`](docs/applications/auto_setup.md) — automated cavity turn-on
- [`docs/applications/rf_commissioning.md`](docs/applications/rf_commissioning.md) — phase-gated acceptance workflow
- [`docs/applications/q0.md`](docs/applications/q0.md), [`microphonics.md`](docs/applications/microphonics.md), [`quench_processing.md`](docs/applications/quench_processing.md), [`tuning.md`](docs/applications/tuning.md)
- [`docs/displays/cavity_display.md`](docs/displays/cavity_display.md), [`srf_home.md`](docs/displays/srf_home.md)

See also `AGENTS.md` at the repo root for architectural conventions enforced across the codebase.

## Architecture

This package provides controls, displays, and analysis tools for the SLAC SC Linac (superconducting RF linac). It is built on PyDM/PyQt5 and uses EPICS (via caproto/pyepics) for hardware communication.

```
src/sc_linac_physics/
├── applications/       # Major standalone applications
├── displays/           # PyDM-based operator displays
├── cli/                # Unified launcher CLI (sc-linac entry point)
└── utils/              # Shared infrastructure (EPICS, Qt, logging, linac model)
```

### Linac Hardware Model (`utils/sc_linac/`)

The full hierarchy is `Machine → Linac → Cryomodule → Rack → Cavity` (+ `SSA`, `StepperTuner`, `Piezo` per cavity). `linac_utils.py` defines cryomodule groupings (L0B–L4B), all EPICS PV naming conventions, and hardware constants. All applications build a module-level `Machine` subclass singleton (e.g., `SETUP_MACHINE`) at import time.

### EPICS Integration (`utils/epics/`)

Use `PV` (never raw `pyepics.PV`) — it adds retry/backoff, typed exceptions, and never returns `None`. For bulk reads across many cavities, use `PVBatch.get_values()`. PV objects are always lazily instantiated on first property access to avoid connecting to hardware at import time.

Platform-aware paths (log dirs, database dirs) live in `utils/platform_paths.py`.

### Displays (`displays/`)

All displays inherit from `pydm.Display`. They are launched either from `.ui` files or as Python classes. The `@display` decorator in `cli/launchers.py` registers them for the unified CLI and handles standalone vs. embedded modes.

### Applications (`applications/`)

Each major application follows a three-layer pattern:
- `backend/` — business logic and EPICS communication, no Qt dependency
- `frontend/` — PyQt5 widgets
- `launcher/` — CLI entry point(s)

### Hierarchical Setup (`applications/auto_setup/`)

`SetupMachine` → `SetupLinac` → `SetupCryomodule` → `SetupCavity` mirrors the physical hierarchy. CLI commands at each level (`sc-setup-all`, `sc-setup-linac`, `sc-setup-cm`, `sc-setup-cav`) map to corresponding backend classes. Request flags (SSA cal, auto-tune, characterization, RF ramp) are EPICS PVs set by GUI/CLI before triggering start.

### RF Commissioning (`applications/rf_commissioning/`)

Nine-phase gated acceptance workflow (PIEZO_PRE_RF → SSA_CHAR → … → ONE_HOUR_RUN → COMPLETE). `CommissioningSession` is the application facade; `PhaseBase` is the abstract base for all phases; `WorkflowService` orchestrates normalized phase instances; `CommissioningDatabase` (SQLite) stores records with optimistic locking. See the three `.md` files inside `applications/rf_commissioning/` for detailed architecture docs.

### Threading

Long-running operations use `Worker(QThread)` from `utils/qt.py`, which emits `finished`, `progress`, `error`, and `status` signals. Never run blocking EPICS calls on the main Qt thread.

### Logging

`utils/logger.py` provides `custom_logger()` with rotating file handlers. Use `utils/platform_paths.py` to get the correct base log directory (`/home/physics/srf/logfiles` on Linux, `~/` on macOS).

## Testing Notes

- Headless Qt tests require `QT_QPA_PLATFORM=offscreen` (set automatically by `conftest.py` — no need to set it manually).
- `conftest.py` redirects `/home/physics` to a temp directory so tests never write to real paths.
- EPICS PVs are mocked via `unittest.mock`; no hardware connection is required.
- `pytest-asyncio` is configured with `asyncio_mode = auto`.
- The 80% coverage threshold is enforced by CI — check coverage before opening a PR.

## Scope and shipping

These rules exist because AI-assisted development makes it easy to produce more
change per PR than a reviewer can absorb. They are about reviewability, not
about slowing down.

### Split at planning time, not review time

Before starting a piece of work, state how it will be split into PRs. Splitting
is a planning decision — once the code is written, splitting becomes a chore and
gets skipped. If a task can't be described as a sequence of independently
mergeable changes, say so and explain why before starting.

### Target PR size

Aim for **under 400 changed lines** excluding tests and generated files. Past
~800, split it. Large mechanical changes (renames, formatting, generated code)
are exempt but should be their own PR, never mixed with logic changes.

When a change is growing past the target mid-work, stop and propose a split
rather than continuing.

### Flag operator-visible changes

If a change alters what a user sees or how an application behaves by default —
new or reordered UI, changed defaults, renamed commands, altered PV usage,
different launch behavior — say so explicitly in the PR description under the
`## Operator-visible` heading, in one or two sentences of plain language.

These need a short note to `#srf-software` when released. Changes that hide
inside a large commit and surprise people at launch are the specific failure
mode this prevents.

The PR template (`.github/pull_request_template.md`) has sections for this, for
split rationale, for decisions worth recording, and for tagging a learning
reviewer. Fill them in rather than deleting them.

### Record decisions with reasoning

When choosing between real alternatives — reusing production code vs.
reimplementing, staging a rollout, deferring a migration — write down the
reasoning, not just the outcome. A comment at the decision point is enough for
small calls; anything architectural goes in `docs/`.

The reasoning is what nobody can reconstruct later. The code shows what was
chosen; it never shows what was rejected or why.

### Write for the physicist reading it

Two reviewers are auto-requested by `.github/CODEOWNERS`, and they read for
different things. Sebastian reads software design — framework structure, phase
sequencing, threading, persistence. Ryan reads machine behavior, and as area
physicist he needs to know exactly what the code commands the hardware to do and
how it derives the numbers people act on.

That second audience shapes how hardware-facing code should be written:

- **Make PV writes obvious.** Any code path that puts a value to the machine
  should be readable without tracing three layers of indirection. Name the PV,
  state the units, and say what physically happens.
- **State hardware assumptions where they're relied on.** The code encodes
  expectations about tuner behavior, limit switches, piezo state, and cavity
  frequency response that are obvious to whoever wrote the phase and invisible
  to everyone else.
- **Show the physics in analysis code.** In `q0/`, `quench_processing/`,
  `microphonics/`, and anywhere else a fit or threshold produces a number: cite
  the relationship being used and where the constants came from. A silent change
  to a fit is a silent change to a physics conclusion.
- **Flag anything that changes what the machine does**, even when the code
  change looks cosmetic. Reordered writes, changed defaults, adjusted timeouts.

`applications/rf_commissioning/` remains single-maintainer. Non-trivial changes
there should be readable by someone who did not write them — favor explicit
naming and docstrings on phase logic over compact code.

## Conventions

- Black 80-character line length; Flake8 allows up to 120 (the two tools have different limits — this is intentional).
- Releases use conventional commits (`feat`, `fix`, `perf`, `refactor`) and are published to GitHub Releases (not PyPI) via `python-semantic-release`.
- Packaged data (`.ui` files, `faults.csv`, Q0 calibration/example data) must be listed in `pyproject.toml` under `[tool.setuptools.package-data]` — CI verifies the built wheel contains them.
