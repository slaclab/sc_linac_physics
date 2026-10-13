"""New plotter, with a small fake hierarchy and fake:// PVs."""

from unittest.mock import patch

import pytest
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from sc_linac_physics.displays.plot import plotter
from sc_linac_physics.displays.plot.cryo_signals_display import (
    CryoSignalsDisplay,
)
from sc_linac_physics.displays.plot.plotter import PlotterDisplay
from sc_linac_physics.displays.plot.utils import (
    CavityPVs,
    CryomodulePVs,
    HierarchicalPVs,
    LinacPVs,
    PVGroup,
    RackPVs,
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
    groups = HierarchicalPVs(
        linacs={"L1B": LinacPVs(name="L1B", pvs=cm.pvs)},
        cryomodules={"02": cm},
        racks={
            ("02", "A"): RackPVs(
                rack_name="A",
                cryomodule_name="02",
                linac_name="L1B",
                pvs=cm.pvs,
            )
        },
        cavities=cavities,
    )
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


def find(tree, path):
    """The tree item at `path`, e.g. ["L1B", "CM02", "Rack A", "Cavity 1"]."""
    items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    for name in path:
        (item,) = [i for i in items if i.text(0) == name]
        items = [item.child(i) for i in range(item.childCount())]
    return item


def pick(display, path, *names):
    """Choose a tree node, then plot the attributes named `names`."""
    picker = display.picker
    picker.tree.setCurrentItem(find(picker.tree, path))
    attrs = picker.attributes
    rows = [attrs.topLevelItem(i) for i in range(attrs.topLevelItemCount())]
    picker._request([row for row in rows if row.text(0) in names])


CAV = ["L1B", "CM02", "Rack A"]
CM = ["L1B", "CM02"]


def plotted_rows(display):
    tree = display.plotted.tree
    return [
        tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())
    ]


def test_starts_at_machine_with_tree_collapsed(display):
    tree = display.picker.tree
    assert tree.currentItem().text(0) == "Machine"
    tops = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    assert [t.text(0) for t in tops] == ["Machine", "L1B", "Decarads"]
    assert not any(t.isExpanded() for t in tops)


def test_pick_one_cavity_attribute(display):
    pick(display, CAV + ["Cavity 3"], "aact")
    assert plotted_pvs(display) == ["fake://CM02:CAV3:AACT"]
    assert plotted_rows(display) == ["CM02 Cavity 3 aact"]
    assert display.plotted.count_label.text() == "1 curve"


def test_adding_again_skips_plotted_pvs(display):
    pick(display, CAV + ["Cavity 1"], "ades")
    pick(display, CAV + ["Cavity 1"], "ades")
    assert plotted_pvs(display) == ["fake://CM02:CAV1:ADES"]
    assert len(plotted_rows(display)) == 1


def test_typed_pv_gets_its_own_axis(display):
    display.picker.pv_edit.setText("  fake://ANY:PV  ")
    display.picker.add_typed_pv()
    (curve,) = display.plot.curve_set.curves
    assert (curve.pv, curve.label, curve.axis) == ("fake://ANY:PV",) * 3
    assert display.picker.pv_edit.text() == ""


def test_blank_typed_pv_does_nothing(display):
    display.picker.pv_edit.setText("   ")
    display.picker.add_typed_pv()
    assert plotted_pvs(display) == []


def test_over_confirm_threshold_asks_first(display):
    with patch.object(
        QMessageBox, "question", return_value=QMessageBox.No
    ) as ask:
        pick(display, CM, "ades")
    ask.assert_called_once()
    assert "60 curves" in ask.call_args.args[2]
    assert plotted_pvs(display) == []

    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        pick(display, CM, "ades")
    assert len(plotted_pvs(display)) == 60


def test_over_max_is_refused(display, monkeypatch):
    monkeypatch.setattr(plotter, "MAX_CURVES", 10)
    with (
        patch.object(QMessageBox, "warning") as warn,
        patch.object(QMessageBox, "question") as ask,
    ):
        pick(display, CM, "ades")
    warn.assert_called_once()
    ask.assert_not_called()
    assert plotted_pvs(display) == []


def test_remove_button_and_clear(display):
    for n in (1, 2):
        pick(display, CAV + [f"Cavity {n}"], "ades")
    tree = display.plotted.tree
    tree.itemWidget(tree.topLevelItem(0), 2).click()
    assert plotted_pvs(display) == ["fake://CM02:CAV2:ADES"]
    assert plotted_rows(display) == ["CM02 Cavity 2 ades"]

    display.plotted.clear_requested.emit()
    assert plotted_pvs(display) == []
    assert display.plotted.count_label.text() == "0 curves"


def test_unchecking_hides_curve_and_keeps_it(display):
    pick(display, CAV + ["Cavity 1"], "ades")
    item = display.plotted.tree.topLevelItem(0)
    item.setCheckState(0, plotter.Qt.Unchecked)
    assert not display.plot._items["fake://CM02:CAV1:ADES"].isVisible()
    assert plotted_pvs(display) == ["fake://CM02:CAV1:ADES"]


def test_plotted_row_shows_curve_color(display):
    pick(display, CAV + ["Cavity 1"], "ades")
    (curve,) = display.plot.curve_set.curves
    icon = display.plotted.tree.topLevelItem(0).icon(0)
    color = icon.pixmap(12, 12).toImage().pixelColor(6, 6)
    assert color.getRgb()[:3] == curve.color


def test_filter_hides_attributes(display):
    display.picker.tree.setCurrentItem(
        find(display.picker.tree, CAV + ["Cavity 1"])
    )
    display.picker.filter_edit.setText("aact")
    attrs = display.picker.attributes
    hidden = {
        attrs.topLevelItem(i).text(0): attrs.topLevelItem(i).isHidden()
        for i in range(attrs.topLevelItemCount())
    }
    assert hidden == {"aact": False, "ades": True}


def test_search_matches_word_starts(display):
    picker = display.picker
    picker.search_edit.setText("cm02 cav 1")
    cavities = find(picker.tree, CAV)
    shown = [
        cavities.child(i).text(0)
        for i in range(cavities.childCount())
        if not cavities.child(i).isHidden()
    ]
    # "1" must start a word: "Cavity 10" matches, "Cavity 21" doesn't.
    assert "Cavity 1" in shown and "Cavity 10" in shown
    assert "Cavity 21" not in shown and "Cavity 2" not in shown


def test_empty_plot_shows_hint(display):
    assert display.plot._pages.currentIndex() == 1
    pick(display, CAV + ["Cavity 1"], "ades")
    assert display.plot._pages.currentIndex() == 0
    display.clear()
    assert display.plot._pages.currentIndex() == 1


def test_axis_range_dialog_sets_ranges(display):
    pick(display, CAV + ["Cavity 1"], "ades")
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
        widget = CryoSignalsDisplay()
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
    assert cryo_display.linac_combo.isVisible()
    assert not cryo_display.selection_panel.isVisible()
    cryo_display.view_combo.setCurrentText(plotter.CUSTOM_VIEW)
    assert not cryo_display.linac_combo.isVisible()
    assert cryo_display.selection_panel.isVisible()
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


def test_cryo_grid_has_one_shared_legend(cryo_display):
    cryo_display.show()
    (plot,) = cryo_display.cryo_plots
    assert not plot.plot.showLegend
    text = cryo_display.cryo_legend.text()
    for label in ("Jt Valve Readback", "Ds Level", "Us Level", "Aact Mean Sum"):
        assert label in text
    for curve in plot.curve_set.curves:
        assert f"rgb{curve.color}" in text

    cryo_display.legend_check.setChecked(False)
    assert not cryo_display.cryo_legend.isVisible()


def test_cryo_plots_have_no_axis_titles(cryo_display):
    (plot,) = cryo_display.cryo_plots
    axis = plot.plot.plotItem.axes["Ds Level"]["item"]
    assert not axis.label.isVisible()


@pytest.mark.parametrize(
    "module,expected",
    [
        ("sc_linac_physics.displays.plot.plotter", "PlotterDisplay"),
        (
            "sc_linac_physics.displays.plot.cryo_signals_display",
            "CryoSignalsDisplay",
        ),
    ],
)
def test_each_display_file_has_one_display_class(module, expected):
    """PyDM opens a display by file and takes the first Display it finds."""
    import importlib
    import inspect

    from pydm import Display

    found = [
        name
        for name, obj in inspect.getmembers(importlib.import_module(module))
        if inspect.isclass(obj)
        and issubclass(obj, Display)
        and obj is not Display
    ]
    assert found == [expected]


def test_open_file_limit_is_raised_within_hard_limit(monkeypatch):
    calls = []
    monkeypatch.setattr(plotter.resource, "getrlimit", lambda _: (256, 1024))
    monkeypatch.setattr(
        plotter.resource, "setrlimit", lambda _, limits: calls.append(limits)
    )
    plotter.raise_open_file_limit(4096)
    assert calls == [(1024, 1024)]


def test_open_file_limit_never_lowered(monkeypatch):
    calls = []
    monkeypatch.setattr(plotter.resource, "getrlimit", lambda _: (10000, 20000))
    monkeypatch.setattr(
        plotter.resource, "setrlimit", lambda _, limits: calls.append(limits)
    )
    plotter.raise_open_file_limit(4096)
    assert calls == []


def test_add_decarad_head_curves(display):
    pick(display, ["Decarads", "Decarad 1", "Head 3"], "avg dose rate")
    (curve,) = display.plot.curve_set.curves
    assert curve.pv == "RADM:SYS0:100:03:GAMMAAVE"
    assert curve.label == "Decarad 1 head 3 avg"
    assert curve.axis == "avg dose rate"


def test_whole_decarad_offers_all_ten_heads(display):
    pick(display, ["Decarads", "Decarad 2"], "raw dose rate")
    curves = display.plot.curve_set.curves
    assert len(curves) == 10
    assert curves[-1].label == "Decarad 2 head 10 raw"


def test_many_pv_pick_gets_per_cavity_labels(display):
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        pick(display, CM, "ades")  # 60 PVs
    labels = [c.label for c in display.plot.curve_set.curves[:2]]
    assert labels == ["CM02 Cavity 1 ades", "CM02 Cavity 2 ades"]


def test_axis_names_are_readable(display):
    pick(display, ["Decarads", "Decarad 1", "Head 1"], "avg dose rate")
    assert display.plot.curve_set.axis_names == ["avg dose rate"]
