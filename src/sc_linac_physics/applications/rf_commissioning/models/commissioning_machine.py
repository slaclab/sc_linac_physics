"""
The Machine RF commissioning runs on.

Not exported from models/__init__.py: importing linac.py builds linac.MACHINE
at import time, and the models package stays free of that.
"""

import threading

from sc_linac_physics.applications.rf_commissioning.models.commissioning_cavity import (
    CommissioningCavity,
)
from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.utils.sc_linac.linac import Machine

_shared_machine: Machine | None = None
_shared_machine_lock = threading.Lock()


def build_commissioning_machine() -> Machine:
    """Return a new Machine with the commissioning cavity and piezo classes."""
    return Machine(
        cavity_class=CommissioningCavity, piezo_class=CommissioningPiezo
    )


def get_commissioning_machine() -> Machine:
    """Return the one Machine every commissioning tab uses.

    Built on the first call. Sharing it means every tab holds the same
    CommissioningCavity objects, so CommissioningCavity.claim can stop two
    tabs from running one cavity. It also shares Cavity.abort_flag: an abort
    pressed in one tab reaches whatever is running that cavity, which the
    claim makes the same tab.
    """
    global _shared_machine
    with _shared_machine_lock:
        if _shared_machine is None:
            _shared_machine = build_commissioning_machine()
        return _shared_machine
