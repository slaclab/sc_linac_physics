# RF Commissioning Phase Workflow

## Overview

RF commissioning uses a **normalized phase-instance lifecycle**.

- A cavity has one canonical `commissioning_records` row.
- Workflow state lives in `commissioning_runs` and
  `commissioning_phase_instances`.
- Each phase attempt is explicit and append-only.
- Progression happens by completing phase instances, not by mutating
  `CommissioningRecord.current_phase` directly.

## Phase Order

Phases execute in fixed order:

1. `PIEZO_PRE_RF`
2. `SSA_CHAR`
3. `FREQUENCY_TUNING`
4. `CAVITY_CHAR`
5. `PIEZO_WITH_RF`
6. `HIGH_POWER_RAMP`
7. `MP_PROCESSING`
8. `ONE_HOUR_RUN`
9. `COMPLETE`

`COMPLETE` is administrative sign-off after technical work is done.

## Lifecycle API (Session-First)

Use `CommissioningSession` as the primary interface from GUI/CLI layers.

```python
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)

session = CommissioningSession()

# Create or load canonical record for cavity
record, record_id, created = session.start_new_record(
    cryomodule="02",
    cavity_number=3,
)

# Validate prerequisites for target phase
can_run, reason = session.can_run_phase(CommissioningPhase.PIEZO_PRE_RF)
if not can_run:
    raise RuntimeError(reason)

# Start phase attempt
start = session.start_active_phase_instance(
    phase=CommissioningPhase.PIEZO_PRE_RF,
    operator="jdoe",
)
if start is None:
    raise RuntimeError("No active record")

# Persist measurements as append-only history (optional during run)
session.add_measurement_to_history(
    phase=CommissioningPhase.PIEZO_PRE_RF,
    measurement_data={"capacitance_a": 2.3e-9, "capacitance_b": 2.4e-9},
    operator="jdoe",
    phase_instance_id=start.phase_instance_id,
)

# Complete attempt and advance workflow
session.complete_active_phase_instance(
    phase_instance_id=start.phase_instance_id,
    phase=CommissioningPhase.PIEZO_PRE_RF,
    artifact_payload={"summary": "piezo pre-rf pass"},
)

# Save wide record fields (notes, phase payload dataclass fields, etc.)
session.save_active_record()
```

## Enforcement Rules

### Prerequisite enforcement

`WorkflowService` checks the latest attempt of the previous phase.

- Allowed previous statuses: `complete`, `skipped`
- Blocked previous statuses: `not_started`, `in_progress`, `failed`
- `PIEZO_PRE_RF` is always restartable

`CommissioningSession.can_run_phase(...)` currently enforces a stricter
check (`complete` prerequisite) for non-`PIEZO_PRE_RF` phases.

### Advancement model

Advancement is automatic on completion:

- `complete_phase_instance(...)` updates the attempt status
- Workflow run moves to the next phase (`commissioning_runs.current_phase`)
- If current phase is `COMPLETE`, run status becomes `complete`

## Resume Capability

Resume by loading the record into an active session and inspecting projection.

```python
session = CommissioningSession(db_path="commissioning.db")

loaded = session.load_record(record_id)
if loaded is None:
    raise ValueError("Record not found")

projection = session.get_active_phase_projection()
if projection is not None:
    print("Current phase:", projection["current_phase"].value)
    print("Run status:", projection["run"]["status"])
    for phase, status in projection["phase_status"].items():
        print(phase.value, status.value)
```

## Failure and Retry

Retry means starting another attempt for the same phase.

```python
start = session.start_active_phase_instance(
    phase=CommissioningPhase.SSA_CHAR,
    operator="jdoe",
)

if start is None:
    raise RuntimeError("Failed to start phase")

session.fail_active_phase_instance(
    phase_instance_id=start.phase_instance_id,
    phase=CommissioningPhase.SSA_CHAR,
    error_message="Drive limit interlock",
    artifact_payload={"fault": "interlock"},
)

# Later retry creates attempt_number + 1
retry = session.start_active_phase_instance(
    phase=CommissioningPhase.SSA_CHAR,
    operator="jdoe",
)
```

## COMPLETE Phase Pattern

`COMPLETE` is handled like any other phase attempt, but typically by an
approver/operator role distinct from technical execution.

```python
start = session.start_active_phase_instance(
    phase=CommissioningPhase.COMPLETE,
    operator="supervisor",
)

session.complete_active_phase_instance(
    phase_instance_id=start.phase_instance_id,
    phase=CommissioningPhase.COMPLETE,
    artifact_payload={"handoff": "operations", "approved_by": "supervisor"},
)

session.append_general_note("supervisor", "Commissioning accepted")
session.save_active_record()
```

## Best Practices

### Do

- Use `CommissioningSession` for controller/UI interactions.
- Start/complete/fail explicit phase instances for all phase transitions.
- Store technical outputs as `measurement_history` and/or artifacts.
- Save active record after modifying wide-record fields.
- Use `get_active_phase_projection()` for UI state.

### Do Not

- Do not manually force phase progression by editing `current_phase`.
- Do not infer readiness from checkpoint text alone.
- Do not skip prerequisite checks in custom tooling.

## API Quick Reference

```python
# Session lifecycle
session.start_new_record(cryomodule, cavity_number, linac=None)
session.load_record(record_id)
session.save_active_record()

# Phase lifecycle
session.can_run_phase(phase)
session.start_active_phase_instance(phase, operator)
session.complete_active_phase_instance(phase_instance_id=..., phase=...)
session.fail_active_phase_instance(phase_instance_id=..., phase=..., error_message=...)

# Projection / history
session.get_active_phase_projection()
session.get_active_phase_instances()
session.add_measurement_to_history(phase, measurement_data, ...)
session.get_measurement_history(phase=None)
```

## See Also

See `src/sc_linac_physics/applications/rf_commissioning/COMPLETE_WORKFLOW_EXAMPLE.md` for an end-to-end example aligned to this lifecycle.
