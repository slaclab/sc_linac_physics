from unittest.mock import Mock

import pytest

from sc_linac_physics.utils.sc_linac.linac_utils import (
    SSA_TYPE_RATED_POWER_KW,
)
from sc_linac_physics.utils.simulation.ssa_service import SSAPVGroup


@pytest.mark.asyncio
@pytest.mark.parametrize("is_hl, expected_kw", [(False, 3.8), (True, 1.0)])
async def test_ssa_type_matches_cavity_kind(is_hl, expected_kw):
    """SSA.rated_power_kw maps the Type index through this table."""
    ssa = SSAPVGroup("TEST:SSA:", cavityGroup=Mock(is_hl=is_hl))
    await SSAPVGroup.ssa_type.pvspec.startup(ssa, ssa.ssa_type, None)
    assert SSA_TYPE_RATED_POWER_KW[ssa.ssa_type.value] == expected_kw
