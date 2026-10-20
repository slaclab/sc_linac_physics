from unittest.mock import Mock

import pytest

from sc_linac_physics.utils.simulation.ssa_service import SSAPVGroup


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_hl, is_he, expected_kw",
    [(False, False, 3.8), (True, False, 1.0), (False, True, 7.0)],
)
async def test_pwr_rating_matches_cavity_kind(is_hl, is_he, expected_kw):
    """The sim serves 1 kW on HL, 7 kW on L4B, 3.8 kW elsewhere."""
    ssa = SSAPVGroup(
        "TEST:SSA:", cavityGroup=Mock(is_hl=is_hl), is_high_energy=is_he
    )
    await SSAPVGroup.pwr_rating.pvspec.startup(ssa, ssa.pwr_rating, None)
    assert ssa.pwr_rating.value == pytest.approx(expected_kw)


def test_service_marks_l4b_ssas_high_energy():
    from sc_linac_physics.utils.sc_linac.linac_utils import L4B
    from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
        SCLinacPhysicsService,
    )

    service = SCLinacPhysicsService()
    he = service[f"ACCL:L4B:{L4B[0]}10:SSA:PwrRating"].group
    std = service["ACCL:L1B:0210:SSA:PwrRating"].group
    assert he.is_high_energy and not std.is_high_energy
