# Complete RF Commissioning Workflow Example

This example demonstrates a full cavity commissioning workflow from start to finish, including the COMPLETE phase for final acceptance.

## Scenario

Commissioning cavity **CM02_CAV5** in cryomodule **CM02** with phase-by-phase execution and proper handoff to operations.

## Full Workflow

```python
from datetime import datetime
from sc_linac_physics.applications.rf_commissioning import (
    CommissioningRecord,
    CommissioningPhase,
    PhaseStatus,
    CommissioningDatabase,
    PhaseCheckpoint,
)

# ============================================================================
# SETUP: Initialize database and create record
# ============================================================================

db = CommissioningDatabase("commissioning.db")
db.initialize()

record = CommissioningRecord(
    linac=1,
    cryomodule="02",
    cavity_number=5,
)

# Save initial record
record_id = db.save_record(record)
print(f"Started commissioning: {record.full_cavity_name}")
print(f"Record ID: {record_id}")
print(f"Initial phase: {record.current_phase.value}")

# ============================================================================
# PHASE 1: PIEZO_PRE_RF - Piezo tuner checkout without RF
# ============================================================================

print("\n--- Phase 1: PIEZO_PRE_RF ---")

# Run automated test (in actual code, this would call PiezoPreRFPhase.run())
# ... test executes ...

# Record results
from sc_linac_physics.applications.rf_commissioning import PiezoPreRFCheck

record.piezo_pre_rf = PiezoPreRFCheck(
    capacitance_a=2.3e-9,
    capacitance_b=2.4e-9,
    channel_a_passed=True,
    channel_b_passed=True,
    timestamp=datetime.now(),
    notes="Both channels passed within specs"
)

# Add checkpoint
checkpoint = PhaseCheckpoint(
    phase=CommissioningPhase.PIEZO_PRE_RF,
    timestamp=datetime.now(),
    operator="tech_user",
    step_name="final_validation",
    success=True,
    notes="Piezo test completed successfully",
    measurements={
        "cap_a": 2.3e-9,
        "cap_b": 2.4e-9
    }
)
record.add_checkpoint(checkpoint)

# Mark phase complete and advance
record.set_phase_status(CommissioningPhase.PIEZO_PRE_RF, PhaseStatus.COMPLETE)
success, message = record.advance_to_next_phase()
print(f"Advanced to: {record.current_phase.value}")

# Save progress
db.save_record(record, record_id)

# ============================================================================
# PHASE 2-9: Continue through remaining technical phases
# ============================================================================

# For brevity, showing abbreviated workflow for middle phases

phases_workflow = [
    (CommissioningPhase.SSA_CHAR, "SSA characterized, max drive = 0.85"),
    (CommissioningPhase.FREQUENCY_TUNING, "Frequency tuning completed with 8π/9 and 7π/9 modes measured"),
    (CommissioningPhase.CAVITY_CHAR, "Cavity Q measured, QL = 2.8e7"),
    (CommissioningPhase.PIEZO_WITH_RF, "Piezo with RF tested, gains within spec"),
    (CommissioningPhase.HIGH_POWER_RAMP, "High power initial ramp complete"),
    (CommissioningPhase.MP_PROCESSING, "MP processing complete with acceptable quench spacing"),
    (CommissioningPhase.ONE_HOUR_RUN, "1-hour run complete at target amplitude"),
]

for phase, notes in phases_workflow:
    print(f"\n--- Phase: {phase.value.upper()} ---")

    # ... actual phase execution would happen here ...

    # Record completion
    checkpoint = PhaseCheckpoint(
        phase=phase,
        timestamp=datetime.now(),
        operator="tech_user",
        step_name="phase_completion",
        success=True,
        notes=notes
    )
    record.add_checkpoint(checkpoint)

    record.set_phase_status(phase, PhaseStatus.COMPLETE)

    # Advance to next phase
    success, message = record.advance_to_next_phase()
    if success:
        print(f"✓ {phase.value} complete, advanced to: {record.current_phase.value}")
    else:
        print(f"✗ Cannot advance: {message}")
        break

    # Save progress after each phase
    db.save_record(record, record_id)

# ============================================================================
# PHASE 10: COMPLETE - Final acceptance and handoff
# ============================================================================

print("\n--- Phase 10: COMPLETE (Final Acceptance) ---")

# Verify we're at COMPLETE phase
if record.current_phase == CommissioningPhase.COMPLETE:

    # Perform final acceptance activities
    print("Performing final acceptance checks...")

    # 1. Set end time
    record.end_time = datetime.now()

    # 2. Update overall status
    record.overall_status = "operational"

    # 3. Add final checkpoint
    final_checkpoint = PhaseCheckpoint(
        phase=CommissioningPhase.COMPLETE,
        timestamp=datetime.now(),
        operator="supervisor_user",  # Note: different operator for approval
        step_name="final_acceptance",
        success=True,
        notes="Cavity accepted for operations. All tests passed.",
        measurements={
            "total_duration_hours": record.elapsed_time,
            "final_status": "operational"
        }
    )
    record.add_checkpoint(final_checkpoint)

    # 4. Mark COMPLETE phase as done
    record.set_phase_status(CommissioningPhase.COMPLETE, PhaseStatus.COMPLETE)

    # 5. Save final state
    db.save_record(record, record_id)

    # 6. Generate summary
    print("\n" + "="*60)
    print("✓ COMMISSIONING COMPLETE")
    print("="*60)
    print(f"Cavity:          {record.full_cavity_name}")
    print(f"Cryomodule:      {record.cryomodule}")
    print(f"Started:         {record.start_time}")
    print(f"Completed:       {record.end_time}")
    print(f"Duration:        {record.elapsed_time:.1f} hours")
    print(f"Status:          {record.overall_status}")
    print(f"Total phases:    {len([p for p in CommissioningPhase if record.get_phase_status(p) == PhaseStatus.COMPLETE])}")
    print(f"Record complete: {record.is_complete}")

    # 7. Optional: Send notifications, update EPICS, etc.
    # send_commissioning_notification(record)
    # update_cavity_epics_status(record.full_cavity_name, "operational")
    # generate_final_report(record_id)

    print("\n✓ Cavity handed off to operations team")

# ============================================================================
# VERIFICATION: Check completion status
# ============================================================================

print("\n--- Verification ---")

# Reload from database to verify persistence
verified_record = db.load_record(record_id)

print(f"Record is complete: {verified_record.is_complete}")
print(f"Current phase: {verified_record.current_phase.value}")
print(f"Overall status: {verified_record.overall_status}")

# Show phase history
print(f"\nTotal checkpoints: {len(verified_record.phase_history)}")
for i, cp in enumerate(verified_record.get_checkpoints(), 1):
    status = "✓" if cp.success else "✗"
    print(f"  {i}. [{cp.phase.value}] {cp.step_name}: {status} - {cp.notes}")

# Verify cannot advance past COMPLETE
success, message = verified_record.advance_to_next_phase()
print(f"\nCan advance further: {success} ({message})")

print("\n" + "="*60)
print("Workflow demonstration complete!")
print("="*60)
```

## Expected Output

```
Started commissioning: L1B_CM02_CAV5
Record ID: 1
Initial phase: piezo_pre_rf

--- Phase 1: PIEZO_PRE_RF ---
Advanced to: ssa_char

--- Phase: SSA_CHAR ---
✓ ssa_char complete, advanced to: frequency_tuning

--- Phase: FREQUENCY_TUNING ---
✓ frequency_tuning complete, advanced to: cavity_char

--- Phase: CAVITY_CHAR ---
✓ cavity_char complete, advanced to: piezo_with_rf

--- Phase: PIEZO_WITH_RF ---
✓ piezo_with_rf complete, advanced to: high_power_ramp

--- Phase: HIGH_POWER_RAMP ---
✓ high_power_ramp complete, advanced to: mp_processing

--- Phase: MP_PROCESSING ---
✓ mp_processing complete, advanced to: one_hour_run

--- Phase: ONE_HOUR_RUN ---
✓ one_hour_run complete, advanced to: complete

--- Phase 10: COMPLETE (Final Acceptance) ---
Performing final acceptance checks...

============================================================
✓ COMMISSIONING COMPLETE
============================================================
Cavity:          L1B_CM02_CAV5
Cryomodule:      02
Started:         2026-02-25 10:00:00
Completed:       2026-02-25 16:30:00
Duration:        6.5 hours
Status:          operational
Total phases:    10
Record complete: True

✓ Cavity handed off to operations team

--- Verification ---
Record is complete: True
Current phase: complete
Overall status: operational

Total checkpoints: 10
  1. [piezo_pre_rf] final_validation: ✓ - Piezo test completed successfully
    2. [ssa_char] phase_completion: ✓ - SSA characterized, max drive = 0.85
    3. [frequency_tuning] phase_completion: ✓ - Frequency tuning completed with cold landing detune = 5 Hz and 8π/9 and 7π/9 modes measured
    4. [cavity_char] phase_completion: ✓ - Cavity Q measured, QL = 2.8e7
    5. [piezo_with_rf] phase_completion: ✓ - Piezo with RF tested, gains within spec
    6. [high_power_ramp] phase_completion: ✓ - High power initial ramp complete
    7. [mp_processing] phase_completion: ✓ - MP processing complete with acceptable quench spacing
    8. [one_hour_run] phase_completion: ✓ - 1-hour run complete at target amplitude
    9. [complete] final_acceptance: ✓ - Cavity accepted for operations. All tests passed.

Can advance further: False (complete is the final phase)

============================================================
Workflow demonstration complete!
============================================================
```

## Key Takeaways

1. **COMPLETE phase separates technical work from administrative acceptance**
    - Technical work ends at ONE_HOUR_RUN
   - COMPLETE is for formal sign-off and handoff

2. **Different operators for work vs. approval**
    - Technician runs tests through ONE_HOUR_RUN
   - Supervisor/physicist approves in COMPLETE phase

3. **Final checkpoint records acceptance**
   - Who approved it
   - When it was accepted
   - Final measurements/summary

4. **Clean status checking**
   - `record.is_complete` is unambiguous
   - `record.current_phase == COMPLETE` means fully done
   - `record.overall_status = "operational"` set during COMPLETE

5. **Audit trail preserved**
   - All phases tracked in `phase_history`
   - Can review who did what and when
   - Supports compliance/quality assurance

6. **Cannot accidentally re-run**
   - Once at COMPLETE, cannot advance further
   - Clear terminal state for the workflow
