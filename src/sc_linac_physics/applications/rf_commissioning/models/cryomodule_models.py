"""Cryomodule-scoped checkout models for RF commissioning."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from sc_linac_physics.applications.rf_commissioning.models.registry import (
    PhaseRegistration,
    validate_phase_registry_consistency,
)
from sc_linac_physics.applications.rf_commissioning.models.serialization import (
    phase_display_field,
    serialize_model,
)


class CryomodulePhase(Enum):
    """Independent cryomodule-level checkout phases."""

    MAGNET_CHECKOUT = "magnet_checkout"

    @classmethod
    def get_phase_order(cls) -> list["CryomodulePhase"]:
        """Get display/execution order for cryomodule-level phases."""
        return [cls.MAGNET_CHECKOUT]


class CryomodulePhaseStatus(Enum):
    """Status of a cryomodule-level phase."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class MagnetCheckoutData:
    """Magnet checkout results for a cryomodule (QUAD, XCOR, YCOR)."""

    passed: bool = phase_display_field(
        default=False,
        label="Magnet Checkout Status",
        widget_name="cm_magnet_passed",
        true_text="PASS",
        false_text="FAIL",
    )
    operator: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if magnet checkout has been performed (pass or fail)."""
        # Checkout is complete once it's been attempted (passed or failed)
        return True

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return serialize_model(self, computed_fields=("is_complete",))


@dataclass
class CryomoduleCheckoutRecord:
    """Cryomodule-scoped checkout record independent of cavity workflow."""

    linac: str
    cryomodule: str
    start_time: datetime = field(default_factory=datetime.now)

    magnet_checkout: Optional[MagnetCheckoutData] = None

    phase_status: dict[CryomodulePhase, CryomodulePhaseStatus] = field(
        default_factory=dict
    )
    end_time: datetime | None = None
    overall_status: str = "in_progress"
    notes: str = ""

    def __post_init__(self):
        """Initialize status map for all cryomodule phases."""
        if not self.phase_status:
            for phase in CryomodulePhase:
                self.phase_status[phase] = CryomodulePhaseStatus.NOT_STARTED

    @property
    def full_cryomodule_name(self) -> str:
        """Get full formatted cryomodule name for display."""
        return f"{self.linac}_CM{self.cryomodule}"

    @property
    def elapsed_time(self) -> float:
        """Total elapsed time in hours."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 3600
        return (datetime.now() - self.start_time).total_seconds() / 3600

    def get_phase_status(self, phase: CryomodulePhase) -> CryomodulePhaseStatus:
        """Get status of a cryomodule phase."""
        return self.phase_status.get(phase, CryomodulePhaseStatus.NOT_STARTED)

    def set_phase_status(
        self, phase: CryomodulePhase, status: CryomodulePhaseStatus
    ) -> None:
        """Set status of a cryomodule phase."""
        self.phase_status[phase] = status

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "linac": self.linac,
            "cryomodule": self.cryomodule,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "overall_status": self.overall_status,
            "elapsed_time_hours": self.elapsed_time,
            "magnet_checkout": (
                self.magnet_checkout.to_dict() if self.magnet_checkout else None
            ),
            "phase_status": {
                phase.value: status.value
                for phase, status in self.phase_status.items()
            },
        }


def create_cryomodule_phase_registry() -> (
    dict[CryomodulePhase, PhaseRegistration]
):
    """Create central cryomodule phase registry entries."""
    return {
        CryomodulePhase.MAGNET_CHECKOUT: PhaseRegistration(
            record_attr="magnet_checkout",
            data_model=MagnetCheckoutData,
            display_label="Magnet Checkout",
            progress_label="Magnet\nCheck",
        ),
    }


CRYOMODULE_PHASE_REGISTRY: dict[CryomodulePhase, PhaseRegistration] = (
    create_cryomodule_phase_registry()
)

validate_phase_registry_consistency(
    phase_enum=CryomodulePhase,
    phase_order=CryomodulePhase.get_phase_order(),
    phase_registry=CRYOMODULE_PHASE_REGISTRY,
)
