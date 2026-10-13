import pytest
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem

from sc_linac_physics.displays.plot.pv_picker import (
    axis_for,
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
