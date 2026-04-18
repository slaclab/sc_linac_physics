# AGENTS.md

## Big-picture architecture
- Core domain model is hierarchical and EPICS-first: `Machine -> Linac -> Cryomodule -> Rack -> Cavity` in `src/sc_linac_physics/utils/sc_linac/`.
- `Machine()` eagerly builds the full accelerator object graph at import time (`utils/sc_linac/linac.py`, global `MACHINE`), so avoid heavy side effects in constructors.
- PV naming and topology are centralized in `utils/sc_linac/linac_utils.py` (`LINAC_TUPLES`, `LINAC_CM_MAP`, `build_cavity_pv*`); reuse these instead of hand-building PV strings.
- Auto-setup launchers mirror physical hierarchy (global/linac/cm/cavity) and propagate request flags downward via AUTO PVs (`applications/auto_setup/backend/setup_utils.py`).
- GUI launching is centralized in `cli/launchers.py`; `sc-linac` discovers `launch_*` functions dynamically and classifies them via decorators (`@display`, `@application`).
- Simulation (`utils/simulation/sc_linac_physics_service.py`) reproduces the same hierarchy with caproto PVGroups and launcher groups (`setup/off/cold/park`) for offline development.

## Developer workflows that matter here
- Use Python 3.12+; install editable with extras:
  - `pip install -e ".[dev,test]"`
- Main quality gate is pytest with coverage settings from `pyproject.toml` (`--cov=sc_linac_physics`, html in `htmlcov/`):
  - `pytest`
- GUI/headless tests assume Qt offscreen and disabled PyDM telemetry/plugins; see `tests/conftest.py` (`QT_QPA_PLATFORM=offscreen`, `PYDM_DATA_PLUGINS_DISABLED=1`).
- CLI health checks are mostly `--help` smoke tests (`tests/test_integration.py`, `tests/test_setup_commands.py`).
- When adding/changing console commands, update `[project.scripts]` in `pyproject.toml` and verify entry points in `tests/test_cli_entrypoints.py`.

## Project conventions (non-generic)
- Prefer `sc_linac_physics.utils.epics.PV` over raw `epics.PV`; this wrapper enforces retry/reconnect/exception semantics (`utils/epics/core.py`).
- For one-shot large PV reads, prefer `PVBatch.get_values` (used by tuning poller) instead of creating hundreds of PV objects (`utils/epics/batch.py`, `applications/tuning/state/tune_status_poll.py`).
- Logging convention is structured: `custom_logger(..., extra={"extra_data": {...}})` for both text and JSONL outputs (`utils/logger.py`).
- Platform-aware filesystem paths are deliberate (`utils/platform_paths.py`): Linux defaults to `/home/physics/srf/...`, macOS to `~/...`.
- Setup commands expect cryomodule identifiers like `01`, `H1` (not `CM01`), and cavity as `1..8` (`srf_*_setup_launcher.py`).

## Integration points and cross-component communication
- External control system integration is EPICS/Channel Access (`pyepics`) and caproto IOC simulation (`sc-sim`).
- UI stack is PyDM + Qt + PyQtGraph; launchers instantiate `PyDMApplication` and open Python displays by class file path (`cli/launchers.py`).
- Watcher orchestration is operationally coupled to `tmux_launcher` and `xterm` (`cli/watcher_commands.py`), including hardcoded SSH env vars.
- Tuning state polling persists operational snapshots to SQLite + JSON (`applications/tuning/state/tune_status_poll.py`), with change history tables.
- RF commissioning is a separate SQLite-backed workflow subsystem with optimistic locking/versioning and normalized phase instances (`applications/rf_commissioning/session_manager.py`).

## High-signal file map for new agents
- Entrypoints: `pyproject.toml`, `src/sc_linac_physics/cli/cli.py`, `src/sc_linac_physics/cli/launchers.py`
- Domain model + constants: `src/sc_linac_physics/utils/sc_linac/linac.py`, `src/sc_linac_physics/utils/sc_linac/linac_utils.py`
- EPICS abstraction: `src/sc_linac_physics/utils/epics/core.py`, `src/sc_linac_physics/utils/epics/batch.py`
- Auto-setup flow: `src/sc_linac_physics/applications/auto_setup/backend/setup_machine.py`, `src/sc_linac_physics/applications/auto_setup/launcher/`
- Simulation IOC: `src/sc_linac_physics/utils/simulation/sc_linac_physics_service.py`
- Test harness assumptions: `tests/conftest.py`
