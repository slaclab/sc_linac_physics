"""Data models for RF commissioning workflow."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


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


@dataclass
class CavityCharacterization:
    """Cavity RF characterization results."""

    loaded_q: Optional[float] = None
    probe_q: Optional[float] = None
    scale_factor: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if characterization is complete."""
        return self.loaded_q is not None and self.scale_factor is not None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "loaded_q": self.loaded_q,
            "probe_q": self.probe_q,
            "scale_factor": self.scale_factor,
            "is_complete": self.is_complete,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }


@dataclass
class PiezoWithRFTest:
    """Piezo tuner with-RF test results."""

    amplifier_gain_a: Optional[float] = None
    amplifier_gain_b: Optional[float] = None
    detune_gain: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if all measurements were taken."""
        return (
            self.amplifier_gain_a is not None
            and self.amplifier_gain_b is not None
            and self.detune_gain is not None
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "amplifier_gain_a": self.amplifier_gain_a,
            "amplifier_gain_b": self.amplifier_gain_b,
            "detune_gain": self.detune_gain,
            "is_complete": self.is_complete,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }


@dataclass
class HighPowerRampData:
    """High power ramp and one-hour run results."""

    final_amplitude: Optional[float] = None  # MV
    one_hour_complete: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if ramp is complete."""
        return self.final_amplitude is not None and self.one_hour_complete

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "final_amplitude": self.final_amplitude,
            "one_hour_complete": self.one_hour_complete,
            "is_complete": self.is_complete,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }


@dataclass
class PhaseCheckpoint:
    """Checkpoint recording a specific event during a commissioning phase.

    Attributes:
        phase: The commissioning phase this checkpoint belongs to
        timestamp: When the checkpoint was created
        operator: Name of the operator
        step_name: Name of the step being executed
        success: Whether the step was successful
        notes: Human-readable notes about the step
        measurements: Optional measurement data from the step
        error_message: Optional error message if step failed
    """

    phase: CommissioningPhase  # ADD THIS LINE
    timestamp: datetime
    operator: str
    step_name: str
    success: bool
    notes: str = ""
    measurements: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "phase": self.phase.value,  # ADD THIS LINE
            "timestamp": self.timestamp.isoformat(),
            "operator": self.operator,
            "step_name": self.step_name,
            "success": self.success,
            "notes": self.notes,
            "measurements": self.measurements,
            "error_message": self.error_message,
        }


@dataclass
class CommissioningRecord:
    """Complete commissioning record for a cavity."""

    cavity_name: str
    cryomodule: str
    start_time: datetime = field(default_factory=datetime.now)
    current_phase: CommissioningPhase = CommissioningPhase.PRE_CHECKS

    # Phase-specific data
    piezo_pre_rf: Optional[PiezoPreRFCheck] = None
    cold_landing: Optional[ColdLandingData] = None
    ssa_char: Optional[SSACharacterization] = None
    cavity_char: Optional[CavityCharacterization] = None
    piezo_with_rf: Optional[PiezoWithRFTest] = None
    high_power: Optional[HighPowerRampData] = None

    # Phase tracking
    phase_history: List[PhaseCheckpoint] = field(
        default_factory=list
    )  # CHANGED: was dict[CommissioningPhase, PhaseCheckpoint]
    phase_status: dict[CommissioningPhase, PhaseStatus] = field(
        default_factory=dict
    )

    end_time: Optional[datetime] = None
    overall_status: str = "in_progress"

    def __post_init__(self):
        """Initialize phase status tracking."""
        if not self.phase_status:
            for phase in CommissioningPhase:
                self.phase_status[phase] = PhaseStatus.NOT_STARTED
            self.phase_status[CommissioningPhase.PRE_CHECKS] = (
                PhaseStatus.IN_PROGRESS
            )

    @property
    def is_complete(self) -> bool:
        """Check if all commissioning is complete."""
        return self.current_phase == CommissioningPhase.COMPLETE

    @property
    def elapsed_time(self) -> Optional[float]:
        """Total elapsed time in hours."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 3600
        return (datetime.now() - self.start_time).total_seconds() / 3600

    def get_phase_status(self, phase: CommissioningPhase) -> PhaseStatus:
        """Get status of a specific phase."""
        return self.phase_status.get(phase, PhaseStatus.NOT_STARTED)

    def set_phase_status(self, phase: CommissioningPhase, status: PhaseStatus):
        """Set status of a specific phase."""
        self.phase_status[phase] = status

    # UPDATED METHODS:
    def add_checkpoint(self, checkpoint: PhaseCheckpoint):
        """Add a checkpoint to the history.

        Args:
            checkpoint: The checkpoint to add
        """
        self.phase_history.append(checkpoint)

    def get_checkpoints(
        self, phase: Optional[CommissioningPhase] = None
    ) -> List[PhaseCheckpoint]:
        """Get checkpoints, optionally filtered by phase.

        Args:
            phase: If provided, only return checkpoints for this phase

        Returns:
            List of checkpoints (all or filtered by phase)
        """
        if phase is None:
            return self.phase_history
        return [cp for cp in self.phase_history if cp.phase == phase]

    def get_latest_checkpoint(
        self, phase: Optional[CommissioningPhase] = None
    ) -> Optional[PhaseCheckpoint]:
        """Get the most recent checkpoint, optionally for a specific phase.

        Args:
            phase: If provided, get latest checkpoint for this phase only

        Returns:
            Most recent checkpoint, or None if no checkpoints exist
        """
        checkpoints = self.get_checkpoints(phase)
        return checkpoints[-1] if checkpoints else None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "cavity_name": self.cavity_name,
            "cryomodule": self.cryomodule,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "current_phase": self.current_phase.value,
            "overall_status": self.overall_status,
            "elapsed_time_hours": self.elapsed_time,
            "is_complete": self.is_complete,
            "piezo_pre_rf": (
                self.piezo_pre_rf.to_dict() if self.piezo_pre_rf else None
            ),
            "cold_landing": (
                self.cold_landing.to_dict() if self.cold_landing else None
            ),
            "ssa_characterization": (
                self.ssa_char.to_dict() if self.ssa_char else None
            ),
            "cavity_characterization": (
                self.cavity_char.to_dict() if self.cavity_char else None
            ),
            "piezo_with_rf": (
                self.piezo_with_rf.to_dict() if self.piezo_with_rf else None
            ),
            "high_power_ramp": (
                self.high_power.to_dict() if self.high_power else None
            ),
            "phase_status": {
                phase.value: status.value
                for phase, status in self.phase_status.items()
            },
            "phase_history": [
                cp.to_dict() for cp in self.phase_history
            ],  # CHANGED: was dict comprehension
        }
