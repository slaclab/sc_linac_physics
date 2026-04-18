"""Targeted tests for Piezo Pre-RF controller helpers."""

from types import SimpleNamespace
from unittest.mock import Mock

import sc_linac_physics.applications.rf_commissioning.controllers.piezo_pre_rf_controller as controller_module
from sc_linac_physics.applications.rf_commissioning.controllers.piezo_pre_rf_controller import (
    PiezoPreRFController,
)
from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    PiezoPreRFCheck,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
)


class _ViewStub:
    def get_current_operator(self) -> str:
        return "Test Operator"


def test_append_measurement_history_uses_active_phase_instance_id() -> None:
    session = Mock()
    controller = PiezoPreRFController(_ViewStub(), session)

    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    record.piezo_pre_rf = PiezoPreRFCheck(
        capacitance_a=25.3e-9,
        capacitance_b=24.8e-9,
        channel_a_passed=True,
        channel_b_passed=True,
    )
    controller.context = PhaseContext(record=record, operator="Test Operator")
    controller._active_phase_instance_id = 42

    controller._append_measurement_history()

    session.add_measurement_to_history.assert_called_once()
    args, kwargs = session.add_measurement_to_history.call_args
    assert kwargs["phase_instance_id"] == 42
    assert kwargs["operator"] == "Test Operator"
    assert args[1] is record.piezo_pre_rf


def test_get_machine_cavity_builds_machine_with_commissioning_piezo(
    monkeypatch,
) -> None:
    class _MachineStub:
        def __init__(self, *, piezo_class):
            self.piezo_class = piezo_class
            self.cryomodules = {
                "02": SimpleNamespace(cavities={1: "cavity-object"})
            }

    monkeypatch.setattr(controller_module, "Machine", _MachineStub)

    controller = PiezoPreRFController(_ViewStub(), Mock())

    cavity = controller._get_machine_cavity(2, 1)

    assert cavity == "cavity-object"
    assert isinstance(controller.machine, _MachineStub)
    assert controller.machine.piezo_class is CommissioningPiezo
