from unittest.mock import patch

from sc_linac_physics.displays.cavity_display.backend import backend_machine
from sc_linac_physics.displays.cavity_display.backend.backend_machine import (
    BackendMachine,
)


def test_logs_one_summary_line_not_one_per_cavity():
    with patch.object(backend_machine, "cavity_fault_logger") as logger:
        machine = BackendMachine(lazy_fault_pvs=True)
    num_cavities = sum(len(cm.cavities) for cm in machine.cryomodules.values())
    logger.info.assert_called_once()
    msg, count, mode, _seconds = logger.info.call_args.args
    assert (count, mode) == (num_cavities, "lazy")
    assert "cavities initialized" in msg
