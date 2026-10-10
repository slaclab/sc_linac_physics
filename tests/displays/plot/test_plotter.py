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


def make_machine():
    from unittest.mock import Mock

    linacs = []
    for linac_name, cms in (("L0B", ["01"]), ("L1B", ["02", "03", "H1", "H2"])):
        linac = Mock()
        linac.name = linac_name
        linac.cryomodules = {}
        for name in cms:
            cm = Mock()
            cm.name = name
            cm.jt_valve_readback_pv = f"fake://CM{name}:JT"
            cm.ds_level_pv = f"fake://CM{name}:DS"
            cm.us_level_pv = f"fake://CM{name}:US"
            cm.aact_mean_sum_pv = f"fake://CM{name}:AACT"
            linac.cryomodules[name] = cm
        linacs.append(linac)
    machine = Mock()
    machine.linacs = linacs
    return machine


@pytest.fixture
def cryo_display(qtbot):
    with (
        patch.object(plotter, "Machine", return_value=make_machine()),
        patch.object(
            plotter, "get_pvs_all_groupings", return_value=make_groups(2)
        ),
    ):
        widget = plotter.CryoSignalsDisplay()
    qtbot.addWidget(widget)
    yield widget
    for plot in widget.cryo_plots + [widget.plot]:
        plot.clear()


def test_cryo_view_opens_one_plot_per_cm(cryo_display):
    assert cryo_display.view_combo.currentText() == plotter.CRYO_VIEW
    titles = [p.curve_set.title for p in cryo_display.cryo_plots]
    assert titles == ["CM 01"]
    assert cryo_display.plots == cryo_display.cryo_plots


def test_cryo_view_default_ranges(cryo_display):
    (plot,) = cryo_display.cryo_plots
    assert plot.curve_set.y_ranges == {
        "Jt Valve Readback": (0, 80),
        "Ds Level": (80, 100),
        "Us Level": (60, 80),
        "Aact Mean Sum": (0, 144),
    }


def test_switching_linac_rebuilds_grid(cryo_display):
    cryo_display.linac_combo.setCurrentIndex(1)
    titles = [p.curve_set.title for p in cryo_display.cryo_plots]
    assert titles == ["CM 02", "CM 03", "CM H1", "CM H2"]
    positions = [
        cryo_display.cryo_grid.getItemPosition(
            cryo_display.cryo_grid.indexOf(p)
        )[:2]
        for p in cryo_display.cryo_plots
    ]
    assert positions == [(0, 0), (0, 1), (1, 0), (1, 1)]


def test_cryo_range_change_applies_to_all_and_survives_switch(cryo_display):
    cryo_display.linac_combo.setCurrentIndex(1)
    with (
        patch.object(
            plotter.AxisRangeDialog, "exec_", return_value=QDialog.Accepted
        ),
        patch.object(
            plotter.AxisRangeDialog,
            "get_settings",
            return_value={
                "Ds Level": {"auto_scale": False, "range": (20.0, 80.0)},
                "Us Level": {"auto_scale": True, "range": None},
            },
        ),
    ):
        cryo_display.open_axis_ranges()
    for plot in cryo_display.cryo_plots:
        assert plot.curve_set.y_ranges["Ds Level"] == (20.0, 80.0)
        assert "Us Level" not in plot.curve_set.y_ranges

    cryo_display.linac_combo.setCurrentIndex(0)
    (plot,) = cryo_display.cryo_plots
    assert plot.curve_set.y_ranges["Ds Level"] == (20.0, 80.0)
    assert "Us Level" not in plot.curve_set.y_ranges


def test_view_switch_shows_matching_controls(cryo_display):
    cryo_display.show()
    assert cryo_display.cryo_box.isVisible()
    assert not any(b.isVisible() for b in cryo_display.custom_boxes)
    cryo_display.view_combo.setCurrentText(plotter.CUSTOM_VIEW)
    assert not cryo_display.cryo_box.isVisible()
    assert all(b.isVisible() for b in cryo_display.custom_boxes)
    assert cryo_display.plots == [cryo_display.plot]


def test_time_span_reaches_every_cryo_plot(cryo_display):
    cryo_display.linac_combo.setCurrentIndex(1)
    with patch.object(plotter.ArchiverPlot, "set_time_span") as set_span:
        cryo_display.time_span_combo.setCurrentText("6 hours")
    assert set_span.call_count == 4


def test_curve_sets_without_ranges_use_defaults():
    from sc_linac_physics.displays.plot.cryo_signals import (
        cryo_signals_curve_sets,
    )

    (curve_set,) = cryo_signals_curve_sets(make_machine().linacs[0])
    assert [c.pv for c in curve_set.curves] == [
        "fake://CM01:JT",
        "fake://CM01:DS",
        "fake://CM01:US",
        "fake://CM01:AACT",
    ]
    assert curve_set.y_ranges["Aact Mean Sum"] == (0, 144)
