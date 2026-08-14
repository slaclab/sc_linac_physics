#DELETE THIS LATER

import pytest
from datetime import datetime

from sc_linac_physics.utils.simulation.fault_service import (
    CavFaultPVGroup,
    PPSPVGroup,
    BSOICPVGroup,
    BeamlineVacuumPVGroup,
    CouplerVacuumPVGroup,
)
from sc_linac_physics.utils.simulation.service import Service


@pytest.fixture
def service():
    return Service()


def test_all_fault_groups_instantiate():
    """Verify all fault service groups can be instantiated."""
    groups = [
        CavFaultPVGroup(prefix="TEST:"),
        PPSPVGroup(prefix="TEST:"),
        BSOICPVGroup(prefix="TEST:"),
        BeamlineVacuumPVGroup(prefix="TEST:"),
        CouplerVacuumPVGroup(prefix="TEST:"),
    ]
    assert all(g is not None for g in groups)


def test_cav_fault_pvgroup_has_required_pvs():
    """Test CavFaultPVGroup contains all expected PVs."""
    group = CavFaultPVGroup(prefix="ACCL:L1B:0110:")
    
    # Some PVs use SeverityProp (creates .SEVR suffix), others use pvproperty (base name)
    expected_pv_patterns = {
        "PRLSUM",        # SeverityProp -> becomes PRLSUM.SEVR
        "CRYO_LTCH",     # pvproperty -> direct base name
        "RESLINK_LTCH",  # pvproperty -> direct base name
        "PLL_LTCH",      # pvproperty -> direct base name
    }

    pvdb_keys = set(group.pvdb.keys())

    for pattern in expected_pv_patterns:
        # Check if the pattern appears in any pvdb key
        matches = [key for key in pvdb_keys if pattern in key]
        assert len(matches) > 0, f"No PV found matching pattern '{pattern}' in {pvdb_keys}"


def test_pvgroup_with_service_registration(service):
    """Test PVGroups register correctly with Service."""
    group = CavFaultPVGroup(prefix="TEST:")
    service.add_pvs(group)
    
    assert "TEST:PRLSUM.SEVR" in service
    assert "TEST:CRYO_LTCH" in service


def test_enum_values_are_correct():
    """Test that enum strings are sensible."""
    group = CavFaultPVGroup(prefix="TEST:")
    
    # Most fault latches should have "Ok" and "Fault"
    assert "Fault" in group.cryo_summary.enum_strings
    assert "Ok" in group.cryo_summary.enum_strings