import pytest
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem

from sc_linac_physics.displays.plot.pv_picker import (
    axis_for,
    shared_attributes,
    curves_for,
    decarad_pvs,
    readable,
    short_path,
)
from sc_linac_physics.displays.plot.utils import PVGroup
from sc_linac_physics.utils.sc_linac.decarad import Decarad


@pytest.mark.parametrize(
    "attribute,axis",
    [("ades_pv", "ades"), ("detune_pvs", "detune"), ("odd", "odd")],
)
def test_axis_for(attribute, axis):
    assert axis_for(attribute) == axis


def test_readable():
    assert readable("detune_best_pv") == "detune best"


def test_curves_for_puts_one_attribute_on_one_axis():
    group = PVGroup({("Cavity", "ades_pv"): ["A:1", "A:2"]})
    curves = curves_for(group, [("Cavity", "ades_pv")], {"A:2": "two"})
    assert [(c.pv, c.label, c.axis) for c in curves] == [
        ("A:1", "A:1", "ades"),
        ("A:2", "two", "ades"),
    ]


def test_decarad_pvs_for_a_whole_unit():
    decarad = Decarad(2)
    node = decarad_pvs(list(decarad.heads.values()))
    avg = node.pvs[("DecaradHead", "avg_dose_rate_pv")]
    assert avg[0] == "RADM:SYS0:200:01:GAMMAAVE"
    assert len(avg) == 10
    assert node.labels["RADM:SYS0:200:10:GAMMA_DOSE_RATE"] == (
        "Decarad 2 head 10 raw"
    )


@pytest.mark.parametrize(
    "path,expected",
    [
        (["L1B", "CM02", "Rack A", "Cavity 1"], "CM02 Cavity 1"),
        (["L1B", "CM02", "Rack A"], "CM02 Rack A"),
        (["L1B", "CM02"], "CM02"),
        (["L1B"], "L1B"),
        (["Decarads", "Decarad 1", "Head 3"], "Decarad 1 Head 3"),
    ],
)
def test_short_path(qtbot, path, expected):
    tree = QTreeWidget()
    qtbot.addWidget(tree)
    item = QTreeWidgetItem(tree, [path[0]])
    for name in path[1:]:
        item = QTreeWidgetItem(item, [name])
    assert short_path(item) == expected


def test_cm_pv_in_a_cavity_group_is_labeled_by_the_cm(qtbot):
    """Cavity groups also hold their CM's PVs; the label must say CM."""
    from sc_linac_physics.displays.plot.pv_picker import PVPicker
    from sc_linac_physics.displays.plot.utils import (
        CavityPVs,
        CryomodulePVs,
        HierarchicalPVs,
        LinacPVs,
        RackPVs,
    )

    cm_key = ("Cryomodule", "aact_mean_sum_pv")
    cavity = CavityPVs(
        number=1,
        rack_name="A",
        cryomodule_name="02",
        linac_name="L1B",
        pvs=PVGroup({cm_key: ["CM02:SUM"], ("Cavity", "ades_pv"): ["C1:ADES"]}),
    )
    cm = CryomodulePVs(
        name="02", linac_name="L1B", pvs=PVGroup({cm_key: ["CM02:SUM"]})
    )
    groups = HierarchicalPVs(
        linacs={"L1B": LinacPVs(name="L1B")},
        cryomodules={"02": cm},
        racks={
            ("02", "A"): RackPVs(
                rack_name="A", cryomodule_name="02", linac_name="L1B"
            )
        },
        cavities={("02", 1): cavity},
    )
    picker = PVPicker(groups)
    qtbot.addWidget(picker)
    assert picker.labels["CM02:SUM"] == "CM02 aact mean sum"
    assert picker.labels["C1:ADES"] == "CM02 Cavity 1 ades"


def test_attribute_from_two_sources_gets_two_axes():
    group = PVGroup(
        {
            ("Linac", "aact_mean_sum_pv"): ["L:SUM"],
            ("Cryomodule", "aact_mean_sum_pv"): ["CM:SUM"],
            ("Cavity", "ades_pv"): ["C:ADES"],
        }
    )
    shared = shared_attributes(group)
    assert shared == {"aact_mean_sum_pv"}
    curves = curves_for(group, list(group.pvs), shared=shared)
    assert {c.pv: c.axis for c in curves} == {
        "L:SUM": "aact mean sum (Linac)",
        "CM:SUM": "aact mean sum (Cryomodule)",
        "C:ADES": "ades",
    }
