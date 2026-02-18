"""Data models for RF commissioning workflow."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CommissioningPhase(Enum):
    """Phases of cavity commissioning workflow."""

    PRE_CHECKS = "pre_checks"
    COLD_LANDING = "cold_landing"
    SSA_CAL = "ssa_cal"
    COARSE_TUNE = "coarse_tune"
    CHARACTERIZATION = "characterization"
    LOW_POWER_RF = "low_power_rf"
    FINE_TUNE = "fine_tune"
    HIGH_POWER_RAMP = "high_power_ramp"
    OPERATIONAL = "operational"
    COMPLETE = "complete"


class PhaseStatus(Enum):
    """Status of a commissioning phase."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseCheckpoint:
    """Snapshot of data at a phase boundary."""

    timestamp: datetime = field(default_factory=datetime.now)
    operator: str = ""
    notes: str = ""
    measurements: dict = field(default_factory=dict)
    error_message: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "operator": self.operator,
            "notes": self.notes,
            "measurements": self.measurements,
            "error_message": self.error_message,
        }
