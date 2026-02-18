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


@dataclass
class ColdLandingData:
    """Cold landing frequency measurement and tuning data."""

    initial_detune_hz: Optional[float] = None
    initial_timestamp: Optional[datetime] = None
    steps_to_resonance: Optional[int] = None
    final_detune_hz: Optional[float] = None
    final_timestamp: Optional[datetime] = None
    notes: str = ""

    @property
    def initial_detune_khz(self) -> Optional[float]:
        """Initial detune in kHz."""
        if self.initial_detune_hz is None:
            return None
        return self.initial_detune_hz / 1000

    @property
    def final_detune_khz(self) -> Optional[float]:
        """Final detune in kHz."""
        if self.final_detune_hz is None:
            return None
        return self.final_detune_hz / 1000

    @property
    def is_complete(self) -> bool:
        """Check if tuning is complete."""
        return (
            self.initial_detune_hz is not None
            and self.steps_to_resonance is not None
            and self.final_detune_hz is not None
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "initial_detune_hz": self.initial_detune_hz,
            "initial_detune_khz": self.initial_detune_khz,
            "initial_timestamp": (
                self.initial_timestamp.isoformat()
                if self.initial_timestamp
                else None
            ),
            "steps_to_resonance": self.steps_to_resonance,
            "final_detune_hz": self.final_detune_hz,
            "final_detune_khz": self.final_detune_khz,
            "final_timestamp": (
                self.final_timestamp.isoformat()
                if self.final_timestamp
                else None
            ),
            "is_complete": self.is_complete,
            "notes": self.notes,
        }


@dataclass
class SSACharacterization:
    """SSA calibration results."""

    max_drive: Optional[float] = None  # 0.0-1.0
    initial_drive: Optional[float] = None
    num_attempts: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def max_drive_percent(self) -> Optional[float]:
        """Maximum drive as percentage (0-100)."""
        if self.max_drive is None:
            return None
        return self.max_drive * 100

    @property
    def initial_drive_percent(self) -> Optional[float]:
        """Initial drive as percentage (0-100)."""
        if self.initial_drive is None:
            return None
        return self.initial_drive * 100

    @property
    def drive_reduction(self) -> Optional[float]:
        """Total reduction in drive level."""
        if self.initial_drive is None or self.max_drive is None:
            return None
        return self.initial_drive - self.max_drive

    @property
    def succeeded_first_try(self) -> bool:
        """Check if calibration succeeded on first attempt."""
        return self.num_attempts == 1

    @property
    def is_complete(self) -> bool:
        """Check if calibration completed successfully."""
        return self.max_drive is not None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "max_drive": self.max_drive,
            "max_drive_percent": self.max_drive_percent,
            "initial_drive": self.initial_drive,
            "initial_drive_percent": self.initial_drive_percent,
            "num_attempts": self.num_attempts,
            "drive_reduction": self.drive_reduction,
            "succeeded_first_try": self.succeeded_first_try,
            "is_complete": self.is_complete,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }
