"""Phase registry definitions for RF commissioning models."""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional


@dataclass(frozen=True)
class PhaseRegistration:
    """Central registration entry for a commissioning phase.

    Holds all metadata needed by the database, UI, and progress indicator.
    Add one entry per phase and every layer auto-discovers the new phase.

    Attributes:
        record_attr:     Attribute name on ``CommissioningRecord``.  Set to
                         ``None`` for terminal phases (e.g. COMPLETE) that
                         have no associated data model or UI tab.
        data_model:      The dataclass type used to store phase results.
                         ``None`` when ``record_attr`` is ``None``.
        display_label:   Full tab title shown in the multi-phase screen.
        progress_label:  Short label shown in the progress indicator
                         (may contain ``\\n`` for line breaks).
    """

    record_attr: Optional[str]
    data_model: Optional[type]
    display_label: str
    progress_label: str


def create_phase_registry() -> dict:
    """Create phase registry entries from the commissioning model classes."""
    from .data_models import (
        CavityCharacterization,
        ColdLandingData,
        CommissioningPhase,
        HighPowerRampData,
        MPProcessingData,
        OneHourRunData,
        PiezoPreRFCheck,
        PiezoWithRFTest,
        PiModeMeasurement,
        SSACharacterization,
    )

    return {
        CommissioningPhase.PIEZO_PRE_RF: PhaseRegistration(
            record_attr="piezo_pre_rf",
            data_model=PiezoPreRFCheck,
            display_label="Piezo Pre-RF",
            progress_label="Piezo\nPre-RF",
        ),
        CommissioningPhase.SSA_CHAR: PhaseRegistration(
            record_attr="ssa_char",
            data_model=SSACharacterization,
            display_label="SSA Characterization",
            progress_label="SSA\nChar",
        ),
        CommissioningPhase.COLD_LANDING: PhaseRegistration(
            record_attr="cold_landing",
            data_model=ColdLandingData,
            display_label="Cold Landing",
            progress_label="Cold\nLanding",
        ),
        CommissioningPhase.PI_MODE: PhaseRegistration(
            record_attr="pi_mode",
            data_model=PiModeMeasurement,
            display_label="π-Mode Measurement",
            progress_label="π-Mode\nMeas",
        ),
        CommissioningPhase.CAVITY_CHAR: PhaseRegistration(
            record_attr="cavity_char",
            data_model=CavityCharacterization,
            display_label="Cavity Characterization",
            progress_label="Cavity\nChar",
        ),
        CommissioningPhase.PIEZO_WITH_RF: PhaseRegistration(
            record_attr="piezo_with_rf",
            data_model=PiezoWithRFTest,
            display_label="Piezo with RF",
            progress_label="Piezo\n@ RF",
        ),
        CommissioningPhase.HIGH_POWER_RAMP: PhaseRegistration(
            record_attr="high_power_ramp",
            data_model=HighPowerRampData,
            display_label="High Power Ramp",
            progress_label="HP\nRamp",
        ),
        CommissioningPhase.MP_PROCESSING: PhaseRegistration(
            record_attr="mp_processing",
            data_model=MPProcessingData,
            display_label="MP Processing",
            progress_label="MP\nProc",
        ),
        CommissioningPhase.ONE_HOUR_RUN: PhaseRegistration(
            record_attr="one_hour_run",
            data_model=OneHourRunData,
            display_label="One Hour Run",
            progress_label="1-Hr\nRun",
        ),
        # Terminal phase – no data model, no UI tab, only a progress node.
        CommissioningPhase.COMPLETE: PhaseRegistration(
            record_attr=None,
            data_model=None,
            display_label="Complete",
            progress_label="Complete",
        ),
    }


def validate_phase_registry_consistency(
    *,
    phase_enum: type[Enum],
    phase_order: list[Enum],
    phase_registry: Mapping[Enum, PhaseRegistration],
) -> None:
    """Ensure phase registry and declared phase order remain in sync."""
    ordered_set = set(phase_order)
    enum_set = set(phase_enum)
    registry_set = set(phase_registry)

    if len(phase_order) != len(ordered_set):
        raise ValueError(
            "CommissioningPhase.get_phase_order() contains duplicates"
        )

    missing_from_order = enum_set - ordered_set
    if missing_from_order:
        missing_names = ", ".join(
            sorted(
                getattr(phase, "value", str(phase))
                for phase in missing_from_order
            )
        )
        raise ValueError(
            "CommissioningPhase.get_phase_order() is missing phases: "
            f"{missing_names}"
        )

    missing_from_registry = enum_set - registry_set
    if missing_from_registry:
        missing_names = ", ".join(
            sorted(
                getattr(phase, "value", str(phase))
                for phase in missing_from_registry
            )
        )
        raise ValueError(
            "PHASE_REGISTRY is missing phase registrations: " f"{missing_names}"
        )

    unknown_in_registry = registry_set - enum_set
    if unknown_in_registry:
        unknown_names = ", ".join(
            sorted(str(phase) for phase in unknown_in_registry)
        )
        raise ValueError(
            "PHASE_REGISTRY contains non-enum phase keys: " f"{unknown_names}"
        )
