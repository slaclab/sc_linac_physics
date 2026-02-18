"""Data models for RF commissioning workflow."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


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


@dataclass
class PiezoPreRFCheck:
    """Piezo tuner pre-RF checkout results."""

    capacitance_a: Optional[float] = None  # Farads
    capacitance_b: Optional[float] = None  # Farads
    channel_a_passed: bool = False
    channel_b_passed: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def passed(self) -> bool:
        """Check if both channels passed."""
        return self.channel_a_passed and self.channel_b_passed

    @property
    def status_description(self) -> str:
        """Human-readable status."""
        if self.passed:
            return f"PASS: Ch A={self.capacitance_a:.3e}F, Ch B={self.capacitance_b:.3e}F"
        else:
            failures = []
            if not self.channel_a_passed:
                failures.append("Ch A")
            if not self.channel_b_passed:
                failures.append("Ch B")
            return f"FAIL: {', '.join(failures)} failed"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "capacitance_a": self.capacitance_a,
            "capacitance_b": self.capacitance_b,
            "channel_a_passed": self.channel_a_passed,
            "channel_b_passed": self.channel_b_passed,
            "passed": self.passed,
            "status_description": self.status_description,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }
