"""New plotter, with a small fake hierarchy and fake:// PVs."""

from unittest.mock import patch

import pytest
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from sc_linac_physics.displays.plot import plotter
from sc_linac_physics.displays.plot.plotter import (
    PlotterDisplay,
    axis_for,
    curves_for,
)
from sc_linac_physics.displays.plot.utils import (
    CavityPVs,
    CryomodulePVs,
    HierarchicalPVs,
    PVGroup,
)


def make_groups(n_cavities=2):
    cavities = {
        ("02", n): CavityPVs(
            number=n,
            rack_name="A",
            cryomodule_name="02",
            linac_name="L1B",
            pvs=PVGroup(
                {
                    ("Cavity", "ades_pv"): [f"fake://CM02:CAV{n}:ADES"],
                    ("Cavity", "aact_pv"): [f"fake://CM02:CAV{n}:AACT"],
                }
            ),
        )
        for n in range(1, n_cavities + 1)
    }
    cm = CryomodulePVs(
        name="02",
        linac_name="L1B",
        pvs=PVGroup(
            {
                ("Cavity", "ades_pv"): [
                    pv
                    for c in cavities.values()
                    for pv in c.pvs[("Cavity", "ades_pv")]
                ]
            }
        ),
    )
    groups = HierarchicalPVs(cryomodules={"02": cm}, cavities=cavities)
    groups.machine.pvs = cm.pvs
    return groups


@pytest.fixture(autouse=True)
def flush_deferred_deletes():
    yield
    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.fixture
def display(qtbot):
    with (
        patch.object(plotter, "Machine"),
        patch.object(
            plotter, "get_pvs_all_groupings", return_value=make_groups(60)
        ),
    ):
        widget = PlotterDisplay()
    qtbot.addWidget(widget)
    yield widget
    widget.plot.clear()


def plotted_pvs(display):
    return [c.pv for c in display.plot.curve_set.curves]


def select(display, level, obj, attribute):
    display.level_combo.setCurrentText(level)
    display.object_combo.setCurrentText(obj)
    for i in range(display.attribute_list.count()):
        item = display.attribute_list.item(i)
        item.setSelected(item.data(0x0100)[1] == attribute)


@pytest.mark.parametrize(
    "attribute,axis",
    [("ades_pv", "ades"), ("detune_pvs", "detune"), ("odd", "odd")],
)
def test_axis_for(attribute, axis):
    assert axis_for(attribute) == axis


def test_curves_for_puts_one_attribute_on_one_axis():
    group = make_groups(2).cryomodules["02"].pvs
    curves = curves_for(group, [("Cavity", "ades_pv")])
    assert [c.pv for c in curves] == [
        "fake://CM02:CAV1:ADES",
        "fake://CM02:CAV2:ADES",
    ]
    assert {c.axis for c in curves} == {"ades"}


def test_object_combo_carries_groups_not_strings(display):
    display.level_combo.setCurrentText("Cavity")
    assert display.object_combo.currentText() == "CM02 cavity 1"
    assert display.object_combo.currentData().number == 1


def test_add_selected(display):
    select(display, "Cavity", "CM02 cavity 3", "aact_pv")
    display.add_selected()
    assert plotted_pvs(display) == ["fake://CM02:CAV3:AACT"]
    assert display.plotted_list.count() == 1
    assert display.count_label.text() == "1 PV plotted"


def test_adding_again_skips_plotted_pvs(display):
    select(display, "Cavity", "CM02 cavity 1", "ades_pv")
    display.add_selected()
    display.add_selected()
    assert plotted_pvs(display) == ["fake://CM02:CAV1:ADES"]
    assert display.plotted_list.count() == 1


def test_typed_pv_gets_its_own_axis(display):
    display.pv_edit.setText("  fake://ANY:PV  ")
    display.add_typed_pv()
    (curve,) = display.plot.curve_set.curves
    assert (curve.pv, curve.label, curve.axis) == ("fake://ANY:PV",) * 3
    assert display.pv_edit.text() == ""


def test_blank_typed_pv_does_nothing(display):
    display.pv_edit.setText("   ")
    display.add_typed_pv()
    assert plotted_pvs(display) == []


def test_over_confirm_threshold_asks_first(display):
    select(display, "Cryomodule", "CM02", "ades_pv")
    with patch.object(
        QMessageBox, "question", return_value=QMessageBox.No
    ) as ask:
        display.add_selected()
    ask.assert_called_once()
    assert "60 curves" in ask.call_args.args[2]
    assert plotted_pvs(display) == []

    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        display.add_selected()
    assert len(plotted_pvs(display)) == 60


def test_over_max_is_refused(display, monkeypatch):
    monkeypatch.setattr(plotter, "MAX_CURVES", 10)
    select(display, "Cryomodule", "CM02", "ades_pv")
    with (
        patch.object(QMessageBox, "warning") as warn,
        patch.object(QMessageBox, "question") as ask,
    ):
        display.add_selected()
    warn.assert_called_once()
    ask.assert_not_called()
    assert plotted_pvs(display) == []


def test_remove_selected_and_clear(display):
    for n in (1, 2):
        select(display, "Cavity", f"CM02 cavity {n}", "ades_pv")
        display.add_selected()
    display.plotted_list.item(0).setSelected(True)
    display.remove_selected()
    assert plotted_pvs(display) == ["fake://CM02:CAV2:ADES"]
    assert display.plotted_list.count() == 1

    display.clear()
    assert plotted_pvs(display) == []
    assert display.count_label.text() == "0 PVs plotted"


def test_filter_hides_attributes(display):
    display.level_combo.setCurrentText("Cavity")
    display.filter_edit.setText("aact")
    hidden = {
        display.attribute_list.item(i).data(0x0100)[1]: (
            display.attribute_list.item(i).isHidden()
        )
        for i in range(display.attribute_list.count())
    }
    assert hidden == {"aact_pv": False, "ades_pv": True}


def test_axis_range_dialog_sets_ranges(display):
    select(display, "Cavity", "CM02 cavity 1", "ades_pv")
    display.add_selected()
    with (
        patch.object(
            plotter.AxisRangeDialog, "exec_", return_value=QDialog.Accepted
        ),
        patch.object(
            plotter.AxisRangeDialog,
            "get_settings",
            return_value={"ades": {"auto_scale": False, "range": (0.0, 20.0)}},
        ),
    ):
        display.open_axis_ranges()
    assert display.plot.curve_set.y_ranges == {"ades": (0.0, 20.0)}


def test_axis_range_dialog_needs_curves(display):
    with patch.object(QMessageBox, "information") as info:
        display.open_axis_ranges()
    info.assert_called_once()


def test_time_span_combo(display):
    with patch.object(display.plot, "set_time_span") as set_span:
        display.time_span_combo.setCurrentText("6 hours")
    set_span.assert_called_once_with(6 * 3600)
