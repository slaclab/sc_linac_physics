"""RF commissioning workflow application.

This module provides data models and workflow management for commissioning
superconducting RF cavities, following LCLS-II operational procedures.

Example Usage
-------------
Create a new commissioning record and track progress through phases::

    from sc_linac_physics.applications.rf_commissioning import (
        CommissioningRecord,
        CommissioningPhase,
        PhaseStatus,
        PiezoPreRFCheck,
        ColdLandingData,
    )

    # Start commissioning a cavity
    record = CommissioningRecord(
        cavity_name="CM01_CAV1",
        cryomodule="CM01",
    )

    # Record piezo pre-RF check
    piezo_check = PiezoPreRFCheck(
        capacitance_a=1.5e-9,
        capacitance_b=1.6e-9,
        channel_a_passed=True,
        channel_b_passed=True,
    )
    record.piezo_pre_rf = piezo_check

    # Complete pre-checks phase
    record.set_phase_status(CommissioningPhase.PRE_CHECKS, PhaseStatus.COMPLETE)
    record.current_phase = CommissioningPhase.COLD_LANDING

    # Record cold landing
    cold_landing = ColdLandingData(
        initial_detune_hz=15000.0,
        steps_to_resonance=50,
        final_detune_hz=500.0,
    )
    record.cold_landing = cold_landing

    # Export to dictionary for storage
    data = record.to_dict()

Data Models
-----------
The module provides these main data structures:

* **CommissioningRecord**: Main container tracking entire commissioning process
* **PiezoPreRFCheck**: Piezo tuner capacitance check results
* **ColdLandingData**: Initial frequency measurement and tuning
* **SSACharacterization**: Solid-state amplifier calibration
* **CavityCharacterization**: Cavity Q and scale factor measurements
* **PiezoWithRFTest**: Piezo tuner performance with RF
* **HighPowerRampData**: Final high-power ramp results
* **PhaseCheckpoint**: Snapshot at phase boundaries

Each data model includes:
- Type-safe fields with defaults
- Computed properties for derived values
- Validation via ``is_complete`` properties
- Serialization via ``to_dict()`` methods
"""

from .data_models import (
    CavityCharacterization,
    ColdLandingData,
    CommissioningPhase,
    CommissioningRecord,
    HighPowerRampData,
    PhaseCheckpoint,
    PhaseStatus,
    PiezoPreRFCheck,
    PiezoWithRFTest,
    SSACharacterization,
)

__all__ = [
    "CavityCharacterization",
    "ColdLandingData",
    "CommissioningPhase",
    "CommissioningRecord",
    "HighPowerRampData",
    "PhaseCheckpoint",
    "PhaseStatus",
    "PiezoPreRFCheck",
    "PiezoWithRFTest",
    "SSACharacterization",
]
