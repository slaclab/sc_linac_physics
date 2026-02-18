"""Data models for RF commissioning workflow."""

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
