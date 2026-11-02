"""
The Machine every RF commissioning controller builds.

Not exported from models/__init__.py: importing linac.py builds linac.MACHINE
at import time, and the models package stays free of that.
"""

from sc_linac_physics.applications.rf_commissioning.models.commissioning_cavity import (
    CommissioningCavity,
)
from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


def build_commissioning_machine() -> Machine:
    """Return a new Machine with the commissioning cavity and piezo classes.

    Each call builds a new instance. Controllers build one lazily and keep
    it, as they did with Machine().
    """
    return Machine(
        cavity_class=CommissioningCavity, piezo_class=CommissioningPiezo
    )
