"""Data models for RF commissioning workflow."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sc_linac_physics.applications.rf_commissioning.models.registry import (
    PhaseRegistration,
    create_phase_registry,
    validate_phase_registry_consistency,
)
from sc_linac_physics.applications.rf_commissioning.models.serialization import (
    phase_display_field,
    serialize_model,
)


class CommissioningPhase(Enum):
    """Phases of cavity commissioning workflow."""

    PIEZO_PRE_RF = "piezo_pre_rf"
    SSA_CHAR = "ssa_char"
    FREQUENCY_TUNING = "frequency_tuning"
    CAVITY_CHAR = "cavity_char"
    PIEZO_WITH_RF = "piezo_with_rf"
    HIGH_POWER_RAMP = "high_power_ramp"
    MP_PROCESSING = "mp_processing"
    ONE_HOUR_RUN = "one_hour_run"
    COMPLETE = "complete"

    @classmethod
    def get_phase_order(cls) -> list["CommissioningPhase"]:
        """Get the required sequential order of phases.

        Returns:
            List of phases in the order they must be executed
        """
        return [
            cls.PIEZO_PRE_RF,
            cls.SSA_CHAR,
            cls.FREQUENCY_TUNING,
            cls.CAVITY_CHAR,
            cls.PIEZO_WITH_RF,
            cls.HIGH_POWER_RAMP,
            cls.MP_PROCESSING,
            cls.ONE_HOUR_RUN,
            cls.COMPLETE,
        ]

    def get_next_phase(self) -> Optional["CommissioningPhase"]:
        """Get the next phase in the sequence.

        Returns:
            Next phase, or None if this is the last phase
        """
        phase_order = self.get_phase_order()
        try:
            current_index = phase_order.index(self)
            if current_index < len(phase_order) - 1:
                return phase_order[current_index + 1]
        except ValueError:
            pass
        return None

    def get_previous_phase(self) -> Optional["CommissioningPhase"]:
        """Get the previous phase in the sequence.

        Returns:
            Previous phase, or None if this is the first phase
        """
        phase_order = self.get_phase_order()
        try:
            current_index = phase_order.index(self)
            if current_index > 0:
                return phase_order[current_index - 1]
        except ValueError:
            pass
        return None


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

    capacitance_a: Optional[float] = phase_display_field(
        default=None,
        label="Ch A Cap",
        widget_name="local_stored_cap_a",
        source_attr="capacitance_a_nf",
        format_spec=".1f",
        unit="nF",
    )  # Farads
    capacitance_b: Optional[float] = phase_display_field(
        default=None,
        label="Ch B Cap",
        widget_name="local_stored_cap_b",
        source_attr="capacitance_b_nf",
        format_spec=".1f",
        unit="nF",
    )  # Farads
    channel_a_passed: bool = False
    channel_b_passed: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def capacitance_a_nf(self) -> Optional[float]:
        """Channel A capacitance in nF."""
        if self.capacitance_a is None:
            return None
        return self.capacitance_a * 1e9

    @property
    def capacitance_b_nf(self) -> Optional[float]:
        """Channel B capacitance in nF."""
        if self.capacitance_b is None:
            return None
        return self.capacitance_b * 1e9

    @property
    def passed(self) -> bool:
        """Check if both channels passed."""
        return self.channel_a_passed and self.channel_b_passed

    @property
    def status_description(self) -> str:
        """Human-readable status."""
        if self.passed:
            return (
                f"PASS: Ch A={self.capacitance_a:.3e}F, "
                f"Ch B={self.capacitance_b:.3e}F"
            )
        else:
            failures = []
            if not self.channel_a_passed:
                failures.append("Ch A")
            if not self.channel_b_passed:
                failures.append("Ch B")
            return f"FAIL: {', '.join(failures)} failed"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return serialize_model(
            self, computed_fields=("passed", "status_description")
        )


@dataclass
class FrequencyTuningData:
    """Frequency tuning phase combining cold landing and π-mode measurements.

    This phase includes:
    1. Cold landing: Initial frequency measurement and tuning to resonance
    2. π-mode measurement: Measurement of 8π/9 and 7π/9 modes
    """

    # Cold landing phase data
    initial_detune_hz: Optional[float] = phase_display_field(
        default=None,
        label="Initial Detune",
        widget_name="freq_tuning_initial_detune",
        format_spec=".3f",
        unit="Hz",
    )
    initial_timestamp: Optional[datetime] = None
    steps_to_resonance: Optional[int] = phase_display_field(
        default=None,
        label="Steps to Resonance",
        widget_name="freq_tuning_steps_to_resonance",
    )
    final_detune_hz: Optional[float] = phase_display_field(
        default=None,
        label="Final Detune",
        widget_name="freq_tuning_final_detune",
        format_spec=".3f",
        unit="Hz",
    )
    final_timestamp: Optional[datetime] = None

    # π-mode measurement phase data
    mode_8pi_9_frequency: Optional[float] = phase_display_field(
        default=None,
        label="8π/9 Frequency",
        widget_name="freq_tuning_8pi_9_freq",
        format_spec=".3f",
        unit="Hz",
    )
    mode_7pi_9_frequency: Optional[float] = phase_display_field(
        default=None,
        label="7π/9 Frequency",
        widget_name="freq_tuning_7pi_9_freq",
        format_spec=".3f",
        unit="Hz",
    )

    timestamp: datetime = field(default_factory=datetime.now)
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
    def cold_landing_complete(self) -> bool:
        """Check if cold landing phase is complete."""
        return (
            self.initial_detune_hz is not None
            and self.steps_to_resonance is not None
            and self.final_detune_hz is not None
        )

    @property
    def pi_mode_complete(self) -> bool:
        """Check if π-mode measurement phase is complete."""
        return (
            self.mode_8pi_9_frequency is not None
            and self.mode_7pi_9_frequency is not None
        )

    @property
    def is_complete(self) -> bool:
        """Check if entire frequency tuning phase is complete."""
        return self.cold_landing_complete and self.pi_mode_complete

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return serialize_model(
            self,
            computed_fields=(
                "initial_detune_khz",
                "final_detune_khz",
                "cold_landing_complete",
                "pi_mode_complete",
                "is_complete",
            ),
        )


@dataclass
class SSACharacterization:
    """SSA calibration results."""

    max_drive: Optional[float] = phase_display_field(
        default=None,
        label="Max Drive",
        widget_name="ssa_max_drive",
        source_attr="max_drive_percent",
        format_spec=".2f",
        unit="%",
    )  # 0.0-1.0
    initial_drive: Optional[float] = phase_display_field(
        default=None,
        label="Initial Drive",
        widget_name="ssa_initial_drive",
        source_attr="initial_drive_percent",
        format_spec=".2f",
        unit="%",
    )
    num_attempts: int = phase_display_field(
        default=0,
        label="Attempts",
        widget_name="ssa_num_attempts",
    )
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
        return serialize_model(
            self,
            computed_fields=(
                "max_drive_percent",
                "initial_drive_percent",
                "drive_reduction",
                "succeeded_first_try",
                "is_complete",
            ),
        )


@dataclass
class CavityCharacterization:
    """Cavity RF characterization results."""

    loaded_q: Optional[float] = phase_display_field(
        default=None,
        label="Loaded Q",
        widget_name="cavity_loaded_q",
        format_spec=".3e",
    )
    probe_q: Optional[float] = phase_display_field(
        default=None,
        label="Probe Q",
        widget_name="cavity_probe_q",
        format_spec=".3e",
    )
    scale_factor: Optional[float] = phase_display_field(
        default=None,
        label="Scale Factor",
        widget_name="cavity_scale_factor",
        format_spec=".6f",
    )
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if characterization is complete."""
        return self.loaded_q is not None and self.scale_factor is not None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return serialize_model(self, computed_fields=("is_complete",))


@dataclass
class PiezoWithRFTest:
    """Piezo tuner with-RF test results."""

    amplifier_gain_a: Optional[float] = phase_display_field(
        default=None,
        label="Amplifier Gain A",
        widget_name="piezo_rf_gain_a",
        format_spec=".6f",
    )
    amplifier_gain_b: Optional[float] = phase_display_field(
        default=None,
        label="Amplifier Gain B",
        widget_name="piezo_rf_gain_b",
        format_spec=".6f",
    )
    detune_gain: Optional[float] = phase_display_field(
        default=None,
        label="Detune Gain",
        widget_name="piezo_rf_detune_gain",
        format_spec=".6f",
    )
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
        return serialize_model(self, computed_fields=("is_complete",))


@dataclass
class HighPowerRampData:
    """High power initial ramp results."""

    had_multipactor_event: bool = phase_display_field(
        default=False,
        label="Multipactor Event",
        widget_name="hp_initial_had_multipactor_event",
        true_text="Yes",
        false_text="No",
    )
    field_emission_onset: Optional[float] = phase_display_field(
        default=None,
        label="Field Emission Onset",
        widget_name="hp_initial_field_emission_onset",
        format_spec=".3f",
        unit="MV",
    )  # MV, if observed
    max_amplitude_reached: Optional[float] = phase_display_field(
        default=None,
        label="Max Amplitude Reached",
        widget_name="hp_initial_max_amplitude_reached",
        format_spec=".3f",
        unit="MV",
    )  # MV
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if initial ramp captured required data."""
        return self.max_amplitude_reached is not None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return serialize_model(self, computed_fields=("is_complete",))


@dataclass
class MPProcessingQuenchEvent:
    """Single quench event observed during MP processing."""

    timestamp: datetime
    session_id: str = ""
    amplitude: float = phase_display_field(
        default=0.0,
        label="Quench Amplitude",
        widget_name="hp_mp_quench_amplitude",
        format_spec=".3f",
        unit="MV",
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return serialize_model(self)


@dataclass
class MPProcessingData:
    """High power MP processing session data and quench timing."""

    session_id: str = field(
        default_factory=lambda: datetime.now().strftime("mp_%Y%m%dT%H%M%S%f")
    )
    quench_events: list[MPProcessingQuenchEvent] = field(default_factory=list)
    notes: str = ""
    decarad: Optional[int] = None

    @property
    def quench_count(self) -> int:
        """Total quenches recorded in this MP processing session."""
        return len(self.quench_events)

    @property
    def quench_intervals_seconds(self) -> list[float]:
        """Elapsed seconds between consecutive quench events."""
        if len(self.quench_events) < 2:
            return []
        return [
            (
                self.quench_events[idx].timestamp
                - self.quench_events[idx - 1].timestamp
            ).total_seconds()
            for idx in range(1, len(self.quench_events))
        ]

    @property
    def is_complete(self) -> bool:
        """Check if session identifier exists."""
        return bool(self.session_id)

    def add_quench(
        self, *, amplitude: float, timestamp: Optional[datetime] = None
    ) -> None:
        """Append a quench event to the current session."""
        self.quench_events.append(
            MPProcessingQuenchEvent(
                session_id=self.session_id,
                timestamp=timestamp or datetime.now(),
                amplitude=amplitude,
            )
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return serialize_model(
            self,
            computed_fields=(
                "quench_count",
                "quench_intervals_seconds",
                "is_complete",
            ),
        )


@dataclass
class OneHourRunData:
    """High power one-hour run results."""

    final_amplitude: Optional[float] = phase_display_field(
        default=None,
        label="Final Amplitude",
        widget_name="hp_one_hour_final_amplitude",
        format_spec=".3f",
        unit="MV",
    )  # MV
    one_hour_complete: bool = phase_display_field(
        default=False,
        label="One Hour Complete",
        widget_name="hp_one_hour_complete",
        true_text="Yes",
        false_text="No",
    )
    amplitude_limitation_reason: str = phase_display_field(
        default="",
        label="Amplitude Limitation Reason",
        widget_name="hp_one_hour_amplitude_limitation_reason",
    )
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if one-hour run is complete."""
        return self.final_amplitude is not None and self.one_hour_complete

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return serialize_model(self, computed_fields=("is_complete",))


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

    phase: CommissioningPhase
    timestamp: datetime
    operator: str
    step_name: str
    success: bool
    notes: str = ""
    measurements: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return serialize_model(self)


@dataclass
class CommissioningRecord:
    """Complete commissioning record for a cavity."""

    linac: int
    cryomodule: str
    cavity_number: int
    start_time: datetime = field(default_factory=datetime.now)
    current_phase: CommissioningPhase = CommissioningPhase.PIEZO_PRE_RF

    # Phase-specific data
    piezo_pre_rf: Optional[PiezoPreRFCheck] = None
    frequency_tuning: Optional[FrequencyTuningData] = None
    ssa_char: Optional[SSACharacterization] = None
    cavity_char: Optional[CavityCharacterization] = None
    piezo_with_rf: Optional[PiezoWithRFTest] = None
    high_power_ramp: Optional[HighPowerRampData] = None
    mp_processing: Optional[MPProcessingData] = None
    one_hour_run: Optional[OneHourRunData] = None

    # Phase tracking
    phase_history: list[PhaseCheckpoint] = field(default_factory=list)
    phase_status: dict[CommissioningPhase, PhaseStatus] = field(
        default_factory=dict
    )

    end_time: datetime | None = None
    overall_status: str = "in_progress"

    def __post_init__(self):
        """Initialize phase status tracking."""
        if not 0 <= self.linac <= 4:
            raise ValueError(
                f"Invalid linac index {self.linac}. Expected integer in range 0..4"
            )

        if not self.phase_status:
            for phase in CommissioningPhase:
                self.phase_status[phase] = PhaseStatus.NOT_STARTED
            self.phase_status[self.current_phase] = PhaseStatus.IN_PROGRESS

    @property
    def is_complete(self) -> bool:
        """Check if all commissioning is complete."""
        return self.current_phase == CommissioningPhase.COMPLETE

    @property
    def full_cavity_name(self) -> str:
        """Get the full formatted cavity name for display (e.g., L1B_CM02_CAV3)."""
        return f"L{self.linac}B_CM{self.cryomodule}_CAV{self.cavity_number}"

    @property
    def short_cavity_name(self) -> str:
        """Get the short formatted cavity name (e.g., 02_CAV3)."""
        return f"{self.cryomodule}_CAV{self.cavity_number}"

    @property
    def elapsed_time(self) -> float | None:
        """Total elapsed time in hours."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 3600
        return (datetime.now() - self.start_time).total_seconds() / 3600

    def get_phase_status(self, phase: CommissioningPhase) -> PhaseStatus:
        """Get status of a specific phase."""
        return self.phase_status.get(phase, PhaseStatus.NOT_STARTED)

    def set_phase_status(
        self, phase: CommissioningPhase, status: PhaseStatus
    ) -> None:
        """Set status of a specific phase."""
        self.phase_status[phase] = status

    def can_start_phase(self, phase: CommissioningPhase) -> tuple[bool, str]:
        """Check if a phase can be started based on prerequisites.

        Args:
            phase: The phase to check

        Returns:
            Tuple of (can_start, reason)
            - can_start: True if the phase can be started
            - reason: Explanation of why or why not
        """
        # PIEZO_PRE_RF is the first phase and can always be started/restarted
        if phase == CommissioningPhase.PIEZO_PRE_RF:
            return True, "Piezo Pre-RF can be run at any time"

        # Check if previous phase is complete
        previous_phase = phase.get_previous_phase()
        if previous_phase is None:
            return True, "No previous phase required"

        previous_status = self.get_phase_status(previous_phase)
        if previous_status != PhaseStatus.COMPLETE:
            return (
                False,
                f"Previous phase {previous_phase.value} must complete first (status: {previous_status.value})",
            )

        return True, f"Prerequisites met for {phase.value} (reruns allowed)"

    def advance_to_next_phase(self) -> tuple[bool, str]:
        """Advance to the next phase in the sequence.

        Returns:
            Tuple of (success, message)
            - success: True if phase was advanced
            - message: Explanation of outcome
        """
        # Check if current phase is complete
        current_status = self.get_phase_status(self.current_phase)
        if current_status != PhaseStatus.COMPLETE:
            return (
                False,
                f"Cannot advance: {self.current_phase.value} is not complete (status: {current_status.value})",
            )

        # Get next phase
        next_phase = self.current_phase.get_next_phase()
        if next_phase is None:
            return False, f"{self.current_phase.value} is the final phase"

        # Validate can start next phase
        can_start, reason = self.can_start_phase(next_phase)
        if not can_start:
            return False, f"Cannot start {next_phase.value}: {reason}"

        # Update current phase
        self.current_phase = next_phase
        self.phase_status[next_phase] = PhaseStatus.IN_PROGRESS

        return True, f"Advanced to {next_phase.value}"

    def add_checkpoint(self, checkpoint: PhaseCheckpoint) -> None:
        """Add a checkpoint to the history.

        Args:
            checkpoint: The checkpoint to add
        """
        self.phase_history.append(checkpoint)

    def get_checkpoints(
        self, phase: CommissioningPhase | None = None
    ) -> list[PhaseCheckpoint]:
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
        self, phase: CommissioningPhase | None = None
    ) -> PhaseCheckpoint | None:
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
            "linac": self.linac,
            "cryomodule": self.cryomodule,
            "cavity_number": self.cavity_number,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "current_phase": self.current_phase.value,
            "overall_status": self.overall_status,
            "elapsed_time_hours": self.elapsed_time,
            "is_complete": self.is_complete,
            "piezo_pre_rf": (
                self.piezo_pre_rf.to_dict() if self.piezo_pre_rf else None
            ),
            "frequency_tuning": (
                self.frequency_tuning.to_dict()
                if self.frequency_tuning
                else None
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
                self.high_power_ramp.to_dict() if self.high_power_ramp else None
            ),
            "mp_processing": (
                self.mp_processing.to_dict() if self.mp_processing else None
            ),
            "one_hour_run": (
                self.one_hour_run.to_dict() if self.one_hour_run else None
            ),
            "phase_status": {
                phase.value: status.value
                for phase, status in self.phase_status.items()
            },
            "phase_history": [cp.to_dict() for cp in self.phase_history],
        }


# ---------------------------------------------------------------------------
# Central phase registry
# ---------------------------------------------------------------------------
# This is the *single source of truth* for every layer of the application.
#
# To add a new phase:
#   1. Add a new ``CommissioningPhase`` enum value above.
#   2. Create a dataclass for the phase results (e.g. ``MyPhaseData``).
#   3. Add a ``PhaseRegistration`` entry below.
#   4. Add the corresponding optional field to ``CommissioningRecord``
#      (e.g. ``my_phase: Optional[MyPhaseData] = None``).
#   5. Optionally register a custom display class in
#      ``ui/phase_displays.py::PHASE_DISPLAY_MAP`` – if omitted, a
#      generic placeholder screen is generated automatically.
#
# Everything else (DB schema migration, INSERT/UPDATE SQL, UI tabs, and
# the progress indicator) is derived from this registry automatically.

PHASE_REGISTRY: dict[CommissioningPhase, PhaseRegistration] = (
    create_phase_registry()
)

validate_phase_registry_consistency(
    phase_enum=CommissioningPhase,
    phase_order=CommissioningPhase.get_phase_order(),
    phase_registry=PHASE_REGISTRY,
)
