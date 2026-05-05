"""Tests for rf_commissioning package root exports used in docs."""

import sc_linac_physics.applications.rf_commissioning as rf_commissioning


def test_package_root_reexports_documented_symbols():
    expected_symbols = [
        "CommissioningRecord",
        "CommissioningPhase",
        "PhaseStatus",
        "CommissioningDatabase",
        "PhaseCheckpoint",
        "PiezoPreRFCheck",
        "WorkflowService",
    ]

    for symbol_name in expected_symbols:
        assert hasattr(rf_commissioning, symbol_name)
