# RF Commissioning

`applications/rf_commissioning/` implements the acceptance workflow for newly-installed or returned cavities. It enforces an ordered, phase-gated process with persistent records, phase-attempt history, artifacts, and operator audit data in SQLite.

Related in-source architecture docs:
- `src/sc_linac_physics/applications/rf_commissioning/ARCHITECTURE.md`
- `src/sc_linac_physics/applications/rf_commissioning/PHASE_WORKFLOW.md`
- `src/sc_linac_physics/applications/rf_commissioning/COMPLETE_WORKFLOW_EXAMPLE.md`

## How to launch

- Direct launcher: `sc-rf-comm`
- Unified launcher: `sc-linac rf-commissioning`
- Python entry point: `sc_linac_physics.cli.launchers:launch_rf_commissioning`

For UI-only development without live EPICS, set `PYDM_DEFAULT_PROTOCOL=fake`.

## Commissioning phases (fixed order)

| # | Enum member | Stored value | Description |
|---|-------------|--------------|-------------|
| 1 | `PIEZO_PRE_RF` | `piezo_pre_rf` | Piezo tuner validation without RF power (always restartable) |
| 2 | `SSA_CHAR` | `ssa_char` | Solid-state amplifier characterization |
| 3 | `FREQUENCY_TUNING` | `frequency_tuning` | Frequency measurement and pi-mode map |
| 4 | `CAVITY_CHAR` | `cavity_char` | RF cavity characterization (loaded Q, scale factor) |
| 5 | `PIEZO_WITH_RF` | `piezo_with_rf` | Piezo testing under RF load |
| 6 | `HIGH_POWER_RAMP` | `high_power_ramp` | Initial high-power RF ramp |
| 7 | `MP_PROCESSING` | `mp_processing` | Multipactor processing and quench tracking |
| 8 | `ONE_HOUR_RUN` | `one_hour_run` | One-hour RF stability run |
| 9 | `COMPLETE` | `complete` | Administrative sign-off and handoff |

Phases are sequential. In normalized workflow validation, the previous phase must be `complete` (or explicitly `skipped`) before the next phase can start. In the current session helper (`CommissioningSession.can_run_phase`), the previous phase must be `complete`. `PIEZO_PRE_RF` is the only phase intentionally restartable at any time.

## Session API (current usage)

`CommissioningSession` (`session_manager.py`) is the facade used by GUI/CLI controllers.

```python
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
	CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
	CommissioningSession,
)

session = CommissioningSession()

# Load or create the cavity record and make it active
record, record_id, created_new = session.start_new_record(
	cryomodule="02",
	cavity_number=3,
)

# Start a normalized phase-attempt instance
result = session.start_active_phase_instance(
	phase=CommissioningPhase.SSA_CHAR,
	operator="jdoe",
)

if result is not None:
	session.add_measurement_to_history(
		phase=CommissioningPhase.SSA_CHAR,
		measurement_data={"max_drive": 0.82},
		operator="jdoe",
		phase_instance_id=result.phase_instance_id,
	)

	session.complete_active_phase_instance(
		phase_instance_id=result.phase_instance_id,
		phase=CommissioningPhase.SSA_CHAR,
		artifact_payload={"summary": "SSA characterization completed"},
	)
```

## Core components

### `CommissioningSession` (`session_manager.py`)

Owns:
- `CommissioningDatabase` connection and initialization
- Active `CommissioningRecord` and optimistic-lock version tracking
- Normalized phase-instance lifecycle methods (`start/complete/fail`)
- Measurement history and notes helpers

### `CommissioningRecord` (`models/data_models.py`)

Legacy wide-record model containing:
- Cavity identity (`linac`, `cryomodule`, `cavity_number`)
- `current_phase` and per-phase `PhaseStatus`
- Phase payload fields (`ssa_char`, `frequency_tuning`, etc.)
- Append-only checkpoint history (`phase_history`)

The normalized run/phase-instance tables are the source of truth for progression.
`CommissioningRecord.current_phase` is retained for compatibility and reporting.

### `WorkflowService` (`services/workflow_service.py`)

Normalized orchestration layer for discrete phase attempts. Handles:
- Prerequisite validation from phase-instance state
- Attempt-numbered phase starts
- Completion/failure transitions
- Artifact and workflow-event writes

## Database model (important tables)

`CommissioningDatabase` (`models/persistence/database.py`) initializes schema from `models/persistence/database_schema.py`.

- `commissioning_records`: one wide record per cavity (versioned)
- `measurement_history`: append-only measurement log, optional `phase_instance_id` link
- `commissioning_runs`: one normalized run per record
- `commissioning_phase_instances`: one row per phase attempt
- `commissioning_phase_artifacts`: structured payloads per phase attempt
- `commissioning_workflow_events`: append-only workflow event stream
- `operators`: approved operator registry

## Optimistic locking

`commissioning_records.version` is used to prevent lost updates across users/processes.

- `CommissioningSession.save_active_record()` writes with `expected_version`
- Note updates (`append_general_note`, `update_general_note`) also check version
- On mismatch, a `RecordConflictError` is raised and caller should reload before retrying

Because measurements are appended in `measurement_history`, concurrent measurement writes do not require record-level conflict resolution.

## Repository layer

`models/persistence/repositories/` provides typed accessors:

| Repository | Entity |
|------------|--------|
| `CryomoduleRepository` | Cryomodule commissioning state |
| `MeasurementRepository` | Measurement history records |
| `RecordRepository` | `CommissioningRecord` persistence |
| `NotesRepository` | Operator notes |
| `OperatorRepository` | Operator registry |
| `QueryRepository` | Cross-entity queries |

## Design notes

- `COMPLETE` is administrative, not a technical measurement phase.
- Normalized phase attempts preserve full rerun history and support artifact/event trails.
- Import direction is enforced: `models -> phases -> services -> session_manager`.
- `PIEZO_PRE_RF` is intentionally restartable because it has no high-power RF side effects.
- UI defaults currently show the `PIEZO_PRE_RF` tab only; placeholder tabs for later
  phases can be enabled in phase spec configuration.
