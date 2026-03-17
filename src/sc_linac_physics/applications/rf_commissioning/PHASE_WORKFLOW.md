# RF Commissioning Phase Workflow

## Overview

The RF commissioning system enforces **strict sequential phase execution** to ensure proper cavity commissioning. Each phase must complete successfully before the next phase can begin.

## Phase Order

Phases must be executed in this exact order:

1. **PIEZO_PRE_RF** - Piezo tuner validation without RF
2. **COLD_LANDING** - Frequency measurement and tuning
3. **SSA_CHAR** - Solid-state amplifier characterization
4. **CAVITY_CHAR** - RF cavity characterization
5. **PIEZO_WITH_RF** - Piezo tuner testing with RF power
6. **HIGH_POWER** - High power ramp to operational levels
7. **COMPLETE** - Final acceptance and handoff to operations

The **COMPLETE** phase is an administrative step that:
- Marks the cavity as fully commissioned and operational
- Sets the final `end_time` and `overall_status`
- Provides a clear handoff point from commissioning to operations
- Can trigger automated reporting, notifications, or data archival
- Separates technical work (HIGH_POWER) from formal acceptance

## Enforcement Mechanisms

### 1. Automatic Phase Ordering Validation

When starting any phase, the system automatically checks:

```python
# PhaseBase.run() checks ordering BEFORE phase-specific prerequisites
can_start, message = self.context.record.can_start_phase(self.phase_type)
if not can_start:
    # Phase is blocked - previous phase must complete first
    return False
```

### 2. Manual Phase Advancement

Use `advance_to_next_phase()` to safely move between phases:

```python
from sc_linac_physics.applications.rf_commissioning import (
    CommissioningRecord,
    CommissioningPhase,
    PhaseStatus,
)

# Create new commissioning record
record = CommissioningRecord(
    cavity_name="CM02_CAV3",
    cryomodule="CM02"
)

# Complete current phase (PIEZO_PRE_RF is the first phase)
record.set_phase_status(CommissioningPhase.PIEZO_PRE_RF, PhaseStatus.COMPLETE)

# Advance to next phase (with validation)
success, message = record.advance_to_next_phase()
if success:
    print(f"Now at: {record.current_phase.value}")
    # Output: "Now at: cold_landing"
else:
    print(f"Cannot advance: {message}")
```

### 3. Phase Start Validation

Check if a specific phase can be started:

```python
# Check if COLD_LANDING can start
can_start, reason = record.can_start_phase(CommissioningPhase.COLD_LANDING)

if can_start:
    print(f"✓ Can start COLD_LANDING: {reason}")
else:
    print(f"✗ Blocked: {reason}")
    # Example: "✗ Blocked: Previous phase piezo_pre_rf must complete first"
```

## Resume Capability

### Saving State

The database automatically persists all phase progress:

```python
from sc_linac_physics.applications.rf_commissioning import CommissioningDatabase

db = CommissioningDatabase("commissioning.db")
db.initialize()

# Save record (includes current_phase, phase_status, phase_history)
record_id = db.save_record(record)
```

### Resuming Sessions

Load interrupted sessions and continue from where you left off:

```python
# Option 1: Load specific record
record = db.load_record(record_id)
print(f"Resume at: {record.current_phase.value}")

# Option 2: Find all interrupted sessions
active_sessions = db.get_active_records()
for session in active_sessions:
    print(f"Resume {session.cavity_name} at {session.current_phase.value}")

    # Check what phases are complete
    for phase in CommissioningPhase.get_phase_order():
        status = session.get_phase_status(phase)
        print(f"  {phase.value}: {status.value}")
```

### Example: Multi-Session Workflow

```python
# ===== Session 1: Start commissioning =====
record = CommissioningRecord(cavity_name="CM02_CAV3", cryomodule="CM02")

# Run PIEZO_PRE_RF phase
# ... phase completes successfully ...
record.set_phase_status(CommissioningPhase.PIEZO_PRE_RF, PhaseStatus.COMPLETE)

# Save and close
record_id = db.save_record(record)
# Session ends

# ===== Session 2: Resume next day =====
record = db.load_record(record_id)

# Advance to next phase
record.advance_to_next_phase()  # Now at COLD_LANDING

# Run COLD_LANDING phase
# ... phase completes ...
record.set_phase_status(CommissioningPhase.COLD_LANDING, PhaseStatus.COMPLETE)

# Save progress
db.save_record(record, record_id)
# Session ends

# ===== Session 3: Continue =====
record = db.load_record(record_id)
record.advance_to_next_phase()  # Now at SSA_CHAR
# ... continue commissioning ...

# ===== Final session: Complete commissioning =====
# After HIGH_POWER phase completes successfully
record.set_phase_status(CommissioningPhase.HIGH_POWER, PhaseStatus.COMPLETE)
record.advance_to_next_phase()  # Now at COMPLETE

# Complete phase: final acceptance and handoff
record.set_phase_status(CommissioningPhase.COMPLETE, PhaseStatus.COMPLETE)
record.end_time = datetime.now()
record.overall_status = "operational"
db.save_record(record, record_id)

# Cavity is now officially operational
print(f"Commissioning complete! Total time: {record.elapsed_time:.1f} hours")
```

## Phase History & Checkpoints

Every step of every phase is recorded in an append-only audit log:

```python
from sc_linac_physics.applications.rf_commissioning import PhaseCheckpoint
from datetime import datetime

# Phases automatically create checkpoints
checkpoint = PhaseCheckpoint(
    phase=CommissioningPhase.PIEZO_PRE_RF,
    timestamp=datetime.now(),
    operator="operator_name",
    step_name="trigger_test",
    success=True,
    measurements={"capacitance_a": 2.3e-9, "capacitance_b": 2.4e-9}
)
record.add_checkpoint(checkpoint)

# Query checkpoints later
piezo_checkpoints = record.get_checkpoints(CommissioningPhase.PIEZO_PRE_RF)
for cp in piezo_checkpoints:
    print(f"{cp.step_name}: {'✓' if cp.success else '✗'} - {cp.notes}")

# Get latest checkpoint for debugging
latest = record.get_latest_checkpoint(CommissioningPhase.PIEZO_PRE_RF)
if not latest.success:
    print(f"Last failure: {latest.error_message}")
```

## Error Recovery

### Failed Phase

If a phase fails, it must be retried before advancing:

```python
# Phase fails
record.set_phase_status(CommissioningPhase.SSA_CHAR, PhaseStatus.FAILED)

# Cannot advance past failed phase
success, message = record.advance_to_next_phase()
# success = False
# message = "Cannot advance: ssa_char is not complete (status: failed)"

# Fix issue and retry the same phase
record.set_phase_status(CommissioningPhase.SSA_CHAR, PhaseStatus.IN_PROGRESS)
# ... re-run phase ...
record.set_phase_status(CommissioningPhase.SSA_CHAR, PhaseStatus.COMPLETE)

# Now can advance
record.advance_to_next_phase()  # ✓ Success
```

### Skipped Phase

Phases can be marked as skipped (counts as complete for ordering):

```python
# Skip a phase (still allows advancement to next phase)
record.set_phase_status(CommissioningPhase.CAVITY_CHAR, PhaseStatus.SKIPPED)

# Can still advance (SKIPPED is treated as complete for ordering)
record.advance_to_next_phase()  # Can advance to PIEZO_WITH_RF
```

## Integration with PhaseBase

The `PhaseBase` class automatically enforces ordering:

```python
from sc_linac_physics.applications.rf_commissioning.phases import (
    PhaseBase,
    PhaseContext,
    PiezoPreRFPhase
)

# Create context
context = PhaseContext(
    record=record,
    operator="operator_name",
    parameters={"cavity": cavity_obj}
)

# Create phase instance
phase = PiezoPreRFPhase(context)

# Run phase (automatically checks ordering + prerequisites)
success = phase.run()

# If previous phase not complete:
# - Creates checkpoint: "phase_ordering_check" with success=False
# - Returns False
# - Record unchanged
```

## COMPLETE Phase Workflow

The COMPLETE phase is typically handled manually as the final administrative step:

```python
# After all technical phases finish
if record.current_phase == CommissioningPhase.HIGH_POWER:
    if record.get_phase_status(CommissioningPhase.HIGH_POWER) == PhaseStatus.COMPLETE:
        # Advance to COMPLETE phase
        success, message = record.advance_to_next_phase()

        if success:
            # Perform final acceptance activities
            record.end_time = datetime.now()
            record.overall_status = "operational"

            # Optional: Generate final report
            # Optional: Update cavity EPICS status
            # Optional: Send notification to operations team

            # Mark as complete
            record.set_phase_status(CommissioningPhase.COMPLETE, PhaseStatus.COMPLETE)
            db.save_record(record, record_id)

            print(f"✓ Cavity {record.cavity_name} commissioned successfully!")
            print(f"  Duration: {record.elapsed_time:.1f} hours")
```

## Best Practices

### ✅ DO:
- Always use `advance_to_next_phase()` to move between phases
- Check `can_start_phase()` before allowing user to start a phase
- Save record to database after each phase completes
- Use `get_active_records()` to find interrupted sessions
- Create checkpoints with detailed measurements and notes

### ❌ DON'T:
- Manually set `record.current_phase` without validation
- Skip phase ordering checks
- Forget to mark phases complete before advancing
- Lose the database file (contains all history)

## API Quick Reference

```python
# Phase navigation
CommissioningPhase.get_phase_order() -> List[CommissioningPhase]
phase.get_next_phase() -> Optional[CommissioningPhase]
phase.get_previous_phase() -> Optional[CommissioningPhase]

# Phase validation
record.can_start_phase(phase) -> (bool, str)
record.advance_to_next_phase() -> (bool, str)

# Phase status
record.get_phase_status(phase) -> PhaseStatus
record.set_phase_status(phase, status) -> None

# Checkpoints
record.add_checkpoint(checkpoint) -> None
record.get_checkpoints(phase=None) -> List[PhaseCheckpoint]
record.get_latest_checkpoint(phase=None) -> Optional[PhaseCheckpoint]

# Database
db.save_record(record, record_id=None) -> int
db.load_record(record_id) -> Optional[CommissioningRecord]
db.get_active_records() -> List[CommissioningRecord]
```

## Example: Complete Workflow

See `examples/rf_commissioning_workflow.py` for a complete working example of commissioning a cavity with proper phase ordering and error handling.
