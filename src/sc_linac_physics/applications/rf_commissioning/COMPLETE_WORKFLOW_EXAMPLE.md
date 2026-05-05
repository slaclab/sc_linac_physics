# Complete RF Commissioning Workflow Example

This example demonstrates the current session-first lifecycle:

- create/load the canonical record for one cavity,
- start explicit phase attempts,
- complete/fail attempts with artifacts,
- and finish with the `COMPLETE` approval phase.

## Scenario

Commission cavity `02_CAV5` in cryomodule `02` and hand it off to operations.

## End-to-End Example

```python
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)


def run_phase(
    session: CommissioningSession,
    phase: CommissioningPhase,
    operator: str,
    measurement_data: dict,
    artifact_payload: dict,
) -> None:
    can_run, reason = session.can_run_phase(phase)
    if not can_run:
        raise RuntimeError(f"Cannot run {phase.value}: {reason}")

    started = session.start_active_phase_instance(phase=phase, operator=operator)
    if started is None:
        raise RuntimeError(f"Failed to start {phase.value}")

    # Optional: append measurement history while the phase is in progress.
    session.add_measurement_to_history(
        phase=phase,
        measurement_data=measurement_data,
        operator=operator,
        phase_instance_id=started.phase_instance_id,
    )

    ok = session.complete_active_phase_instance(
        phase_instance_id=started.phase_instance_id,
        phase=phase,
        artifact_payload=artifact_payload,
    )
    if not ok:
        raise RuntimeError(f"Failed to complete {phase.value}")


session = CommissioningSession(db_path="commissioning.db")

record, record_id, created_new = session.start_new_record(
    cryomodule="02",
    cavity_number=5,
)

print(f"Record ID: {record_id} (created_new={created_new})")
print(f"Cavity: {record.full_cavity_name}")

# Phase 1: PIEZO_PRE_RF
run_phase(
    session=session,
    phase=CommissioningPhase.PIEZO_PRE_RF,
    operator="tech_user",
    measurement_data={"capacitance_a": 2.3e-9, "capacitance_b": 2.4e-9},
    artifact_payload={"summary": "piezo pre-rf pass"},
)

# Phase 2: SSA_CHAR (show one failure + retry)
ssa_start = session.start_active_phase_instance(
    phase=CommissioningPhase.SSA_CHAR,
    operator="tech_user",
)
if ssa_start is None:
    raise RuntimeError("Failed to start ssa_char")

failed = session.fail_active_phase_instance(
    phase_instance_id=ssa_start.phase_instance_id,
    phase=CommissioningPhase.SSA_CHAR,
    error_message="Drive limit interlock",
    artifact_payload={"fault": "interlock"},
)
if not failed:
    raise RuntimeError("Failed to mark ssa_char failed")

# Retry creates the next attempt_number for the same phase.
run_phase(
    session=session,
    phase=CommissioningPhase.SSA_CHAR,
    operator="tech_user",
    measurement_data={"max_drive": 0.85, "attempt": "retry"},
    artifact_payload={"summary": "ssa characterization pass"},
)

# Continue technical phases.
for phase, measurement in [
    (CommissioningPhase.FREQUENCY_TUNING, {"final_detune_hz": 5.0}),
    (CommissioningPhase.CAVITY_CHAR, {"loaded_q": 2.8e7}),
    (CommissioningPhase.PIEZO_WITH_RF, {"detune_gain": 0.10}),
    (CommissioningPhase.HIGH_POWER_RAMP, {"max_amplitude_reached": 17.5}),
    (CommissioningPhase.MP_PROCESSING, {"quench_count": 3}),
    (CommissioningPhase.ONE_HOUR_RUN, {"one_hour_complete": True}),
]:
    run_phase(
        session=session,
        phase=phase,
        operator="tech_user",
        measurement_data=measurement,
        artifact_payload={"summary": f"{phase.value} pass"},
    )

# Phase 9: COMPLETE (typically approver/supervisor role)
run_phase(
    session=session,
    phase=CommissioningPhase.COMPLETE,
    operator="supervisor_user",
    measurement_data={"handoff": "operations"},
    artifact_payload={"approved_by": "supervisor_user"},
)

session.append_general_note("supervisor_user", "Commissioning accepted")
session.save_active_record()

projection = session.get_active_phase_projection()
if projection is None:
    raise RuntimeError("Expected active projection")

print(f"Run status: {projection['run']['status']}")
print(f"Current phase: {projection['current_phase'].value}")

for phase, status in projection["phase_status"].items():
    print(f"  {phase.value}: {status.value}")
```

## What to Verify

1. `session.start_new_record(...)` reuses the same canonical record for the same cavity.
2. Every phase transition is represented by explicit rows in `commissioning_phase_instances`.
3. Fail/retry creates a new attempt number for that phase.
4. Completing `COMPLETE` sets run status to `complete` in `commissioning_runs`.
5. Measurement data is append-only in `measurement_history`.

## Notes

- Use cryomodule identifiers like `02` / `H1` (not `CM02`) in API calls.
- Progression happens through phase-instance completion, not by directly editing
  `CommissioningRecord.current_phase`.
- Use `session.get_active_phase_projection()` for UI/state display.
