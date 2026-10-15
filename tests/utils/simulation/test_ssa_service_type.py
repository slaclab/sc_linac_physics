from unittest.mock import Mock

import pytest

from sc_linac_physics.utils.sc_linac.linac_utils import (
    SSA_TYPE_RATED_POWER_KW,
)
from sc_linac_physics.utils.simulation.ssa_service import SSAPVGroup


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_hl, is_he, expected_kw",
    [(False, False, 3.8), (True, False, 1.0), (False, True, 7.0)],
)
async def test_ssa_type_matches_cavity_kind(is_hl, is_he, expected_kw):
    """SSA.rated_power_kw maps the Type index through this table."""
    ssa = SSAPVGroup(
        "TEST:SSA:", cavityGroup=Mock(is_hl=is_hl), is_high_energy=is_he
    )
    await SSAPVGroup.ssa_type.pvspec.startup(ssa, ssa.ssa_type, None)
    # An untouched enum holds its int; a written one holds its label.
    value = ssa.ssa_type.value
    index = (
        value
        if isinstance(value, int)
        else ssa.ssa_type.enum_strings.index(value)
    )
    assert SSA_TYPE_RATED_POWER_KW[index] == expected_kw


def test_service_marks_l4b_ssas_high_energy():
    from sc_linac_physics.utils.sc_linac.linac_utils import L4B
    from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
        SCLinacPhysicsService,
    )

    service = SCLinacPhysicsService()
    he = service[f"ACCL:L4B:{L4B[0]}10:SSA:Type"].group
    std = service["ACCL:L1B:0210:SSA:Type"].group
    assert he.is_high_energy and not std.is_high_energy
