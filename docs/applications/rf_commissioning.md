# RF Commissioning

`applications/rf_commissioning/` is the acceptance workflow system for newly-installed or returned cavities. It enforces a strictly sequential series of phases with checkpoints, measurement recording, and a persistent audit trail stored in SQLite.

The architecture docs already in the source tree are also worth reading:
- `src/sc_linac_physics/applications/rf_commissioning/ARCHITECTURE.md` — dependency rules, module layout
- `src/sc_linac_physics/applications/rf_commissioning/PHASE_WORKFLOW.md` — phase contract details
- `src/sc_linac_physics/applications/rf_commissioning/COMPLETE_WORKFLOW_EXAMPLE.md` — end-to-end walkthrough

## Commissioning phases (fixed order)

| # | Phase | Description |
|---|-------|-------------|
| 1 | `PIEZO_PRE_RF` | Piezo tuner validation without RF power — always restartable |
| 2 | `SSA_CHAR` | Solid-state amplifier characterization |
| 3 | `FREQUENCY_TUNING` | Frequency measurement and π-mode map |
| 4 | `CAVITY_CHAR` | RF cavity characterization (Q-loaded, scale factor) |
| 5 | `PIEZO_WITH_RF` | Piezo testing under RF load |
| 6 | `HIGH_POWER_RAMP` | Initial high-power RF ramp |
| 7 | `MP_PROCESSING` | Multipactor processing and quench tracking |
| 8 | `ONE_HOUR_RUN` | One-hour RF stability run |
| 9 | `COMPLETE` | Administrative sign-off and handoff to operations |

Phases cannot be skipped, though a phase can be explicitly marked as skipped by an authorized operator (the skip is recorded in the audit trail).

## Key classes

### `CommissioningSession` (`session_manager.py`)

The application-facing facade. Controllers (GUI or CLI) interact only with this class.

```python
session = CommissioningSession(cavity)
session.start_phase(PhaseName.SSA_CHAR, operator="jdoe")
session.record_measurement("Q_loaded", 4.1e7)
session.complete_phase(operator="jdoe")
session.get_current_record()  # → CommissioningRecord
```

Manages: database access, active record state, optimistic locking, phase lifecycle transitions.

### `CommissioningRecord` (`models/data_models.py`)

Dataclass holding:
- Cavity identity (linac, CM, cavity number)
- Current phase and phase status map
- Checkpoint history (immutable, append-only)
- Measurement history (decoupled from phase state, can be written concurrently)
- `version` integer for optimistic locking

### `PhaseBase` (`phases/phase_base.py`)

Abstract base class all phase implementations inherit from. Defines the phase contract:
- `validate()` — pre-execution checks (prerequisite phases complete, hardware in expected state)
- `execute()` — the actual measurement/test steps
- `create_checkpoint(operator, success, measurements, error_msg)` — writes to audit trail
- `retry()` — restart a failed phase from the beginning

### `WorkflowService` (`services/workflow_service.py`)

Pure orchestration layer operating on normalized phase instances (stored in separate database tables from the legacy `CommissioningRecord`). Handles:
- Prerequisite validation
- Phase instance creation (each run of a phase is a discrete record)
- Artifact storage (waveform files, measurement CSVs)
- Phase advancement logic

### `CommissioningDatabase` (`models/persistence/database.py`)

SQLite backend (one file per cryomodule). Schema:
- `commissioning_records` — one row per cavity, versioned
- `phase_history` — append-only; every phase attempt is a row
- `measurements` — append-only; measurement samples keyed by phase and timestamp
- `notes` — operator notes attached to phases
- `operators` — operator registry

## Optimistic locking

Every `CommissioningRecord` has a `version` integer. When `CommissioningSession.complete_phase()` saves the record, it checks that `version` in the database matches the loaded version. If another process modified the record in the meantime, a `RecordConflictError` is raised. The caller must reload the record and retry.

This supports multi-user operation (multiple technicians entering measurements concurrently) without requiring row-level locks.

## Repository pattern

`models/persistence/repositories/` provides typed CRUD classes for each entity:

| Repository | Entity |
|------------|--------|
| `CryomoduleRepository` | Cryomodule commissioning state |
| `MeasurementRepository` | Individual measurements |
| `RecordRepository` | `CommissioningRecord` persistence |
| `NotesRepository` | Operator notes |
| `OperatorRepository` | Operator registry |
| `QueryRepository` | Cross-entity queries |

## Non-obvious design decisions

- **`COMPLETE` is administrative, not technical.** Technical work ends at `ONE_HOUR_RUN`. `COMPLETE` is a separate step for formal supervisor sign-off, allowing different operator roles and triggering handoff notifications.
- **Normalized phase instances.** `WorkflowService` stores discrete phase *attempts* separately from the `CommissioningRecord`. This allows the UI to iterate rapidly without blocking record persistence, and enables full rerun history without overwriting previous results.
- **Measurement decoupling.** Measurements append to a separate table from phase state. Concurrent measurement writes never conflict with phase transitions.
- **Strict import direction.** The package enforces `models → phases → services → session_manager`. An architecture test (`test_session_workflow.py`) guards against circular imports.
- **`PIEZO_PRE_RF` is always restartable.** It has no hardware side effects that would require recovery, so it's the one phase that can be freely rerun without administrative override.
