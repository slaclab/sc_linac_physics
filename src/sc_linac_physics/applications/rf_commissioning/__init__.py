"""
RF Commissioning Application

Manual commissioning workflow for superconducting cavities with emphasis on
careful operator-guided procedures and comprehensive data recording.

Key Features:
- Phase-based commissioning workflow
- Cold landing frequency measurement
- SQLite database for local data persistence
- Complete audit trail with operator tracking
- Resume capability from any phase

Usage:
    from sc_linac_physics.applications.rf_commissioning import (
        CommissioningPhase,
        PhaseStatus,
        ColdLandingData,
        CommissioningRecord,
        CommissioningDatabase,
    )

    # Create a commissioning record
    record = CommissioningRecord(
        cavity_name="L1B_CM02_CAV3",
        cryomodule="02",
    )

    # Record cold landing measurement
    cold_landing = ColdLandingData(
        initial_detune_hz=-143766,
        steps_to_resonance=14376,
        final_detune_hz=-234,
    )

    record.cold_landing = cold_landing

    # Save to database
    db = CommissioningDatabase("commissioning.db")
    db.initialize()
    record_id = db.save_record(record)

    # Resume later
    active_sessions = db.get_active_records()
"""

__version__ = "0.1.0"

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
from .database import CommissioningDatabase

__all__ = [
    # Enums
    "CommissioningPhase",
    "PhaseStatus",
    # Phase tracking
    "PhaseCheckpoint",
    # Phase-specific data
    "PiezoPreRFCheck",
    "ColdLandingData",
    "SSACharacterization",
    "CavityCharacterization",
    "PiezoWithRFTest",
    "HighPowerRampData",
    # Main record
    "CommissioningRecord",
    # Database
    "CommissioningDatabase",
]
