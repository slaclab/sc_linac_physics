from unittest.mock import patch

from sc_linac_physics.displays.cavity_display.backend import (
    backend_cavity,
    backend_machine,
)
from sc_linac_physics.displays.cavity_display.backend.backend_machine import (
    BackendMachine,
)


def test_logs_one_summary_line_not_one_per_cavity():
    with (
        patch.object(backend_machine, "cavity_fault_logger") as machine_logger,
        patch.object(backend_cavity, "cavity_fault_logger") as cavity_logger,
    ):
        machine = BackendMachine(lazy_fault_pvs=True)
    num_cavities = sum(len(cm.cavities) for cm in machine.cryomodules.values())

    machine_logger.info.assert_called_once()
    data = machine_logger.info.call_args.kwargs["extra"]["extra_data"]
    assert data["cavity_count"] == num_cavities
    assert data["lazy_mode"] is True
    for method in ("debug", "info"):
        getattr(cavity_logger, method).assert_not_called()
