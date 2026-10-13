"""Every PV name the hardware model holds should be served by sc-sim.

The model names its PVs as ``*_pv`` string attributes, and ``*_pvs`` lists
of them (Linac.beamline_vacuum_pvs, ...), on each object. That's the same
rule PVExtractor uses in displays/plot/utils.py. This walks the whole MACHINE tree, collects those
names, and checks each one is a key of SCLinacPhysicsService.

A PV the model uses and the sim doesn't serve fails in sim only when that
code path runs, and then as a connection timeout. This test fails at once,
and names the attribute.

KNOWN_GAPS lists the attributes not served yet. The test fails if a gap is
missing from the list, and also if a listed gap has been closed, so the
list can't go stale.
"""

from collections import defaultdict

import pytest

from sc_linac_physics.utils.sc_linac.linac import MACHINE
from sc_linac_physics.utils.sc_linac.linac_utils import SCLinacObject

# (class name, attribute) -> why it isn't served yet.
KNOWN_GAPS = {
    ("Cryomodule", "ds_pressure_pv"): "cryo: no CPT:...:DS:PRESS group",
    ("Cryomodule", "jt_valve_readback_pv"): "cryo: HL JT valve readback",
    ("Cryomodule", "heater_readback_pv"): "cryo: HL heater readback",
    ("Machine", "global_heater_feedback_pv"): "cryo: CHTR:CM00 total",
    # The sim serves vacuum as ACCL:...:00:/10: groups, not these VGXX gauge
    # names. The plot display picks them up through PVExtractor.
    ("Cryomodule", "vacuum_pvs"): "vacuum: no VGXX:...:COMBO_P gauges",
    ("Cryomodule", "coupler_vacuum_pvs"): "vacuum: no VGXX:...:COMBO_P",
    ("Linac", "beamline_vacuum_pvs"): "vacuum: no VGXX:...:COMBO_P gauges",
    ("Linac", "insulating_vacuum_pvs"): "vacuum: no VGXX:...:COMBO_P",
}


def _is_model_node(value) -> bool:
    return isinstance(value, SCLinacObject) or type(value).__name__ in (
        "Machine",
        "Linac",
    )


def _model_pv_names(root) -> list:
    """(class name, attribute, PV name) for every *_pv / *_pvs name."""
    found, seen, stack = [], set(), [root]
    while stack:
        obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        for attr, value in vars(obj).items():
            if isinstance(value, str):
                if attr.endswith("_pv") and ":" in value:
                    found.append((type(obj).__name__, attr, value))
            elif _is_model_node(value):
                stack.append(value)
            elif isinstance(value, dict):
                stack.extend(v for v in value.values() if _is_model_node(v))
            elif isinstance(value, (list, tuple)):
                if attr.endswith("_pvs"):
                    found.extend(
                        (type(obj).__name__, attr, v)
                        for v in value
                        if isinstance(v, str) and ":" in v
                    )
                stack.extend(v for v in value if _is_model_node(v))
    return found


@pytest.fixture(scope="module")
def unserved():
    from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
        SCLinacPhysicsService,
    )

    served = set(SCLinacPhysicsService().keys())
    by_attr = defaultdict(list)
    for cls, attr, pv in _model_pv_names(MACHINE):
        if pv not in served:
            by_attr[(cls, attr)].append(pv)
    return by_attr


def test_walk_finds_the_model_pvs():
    """Guard against the walk silently finding nothing."""
    names = _model_pv_names(MACHINE)
    attrs = {(cls, attr) for cls, attr, _ in names}
    assert ("Cavity", "ades_pv") in attrs
    assert ("Linac", "beamline_vacuum_pvs") in attrs  # a *_pvs list
    assert ("SSA", "status_pv") in attrs
    assert ("StepperTuner", "motor_moving_pv") in attrs
    assert len(names) > 40000


def test_every_model_pv_is_served(unserved):
    new_gaps = {
        key: pvs[:3] for key, pvs in unserved.items() if key not in KNOWN_GAPS
    }
    assert not new_gaps, (
        "The model uses PVs sc-sim doesn't serve (first 3 of each shown). "
        f"Add them to the sim: {new_gaps}"
    )


def test_known_gaps_are_still_gaps(unserved):
    closed = sorted(key for key in KNOWN_GAPS if key not in unserved)
    assert (
        not closed
    ), f"These are served now; remove them from KNOWN_GAPS: {closed}"
