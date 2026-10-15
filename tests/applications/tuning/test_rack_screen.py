# tests/applications/tuning/test_rack_screen.py
"""Tests for RackScreen component."""

import pytest


class TestRackScreen:
    """Tests for RackScreen class."""

    def test_initialization(self, qapp_global, mock_rack, rack_screen_patches):
        """Test RackScreen initialization."""
        from sc_linac_physics.applications.tuning.tuning_gui import RackScreen

        screen = RackScreen(mock_rack)
        assert screen.rack == mock_rack
        assert screen.groupbox.title() == "Rack A"

    def test_detune_plot_populated(
        self, qapp_global, mock_rack, rack_screen_patches
    ):
        """Test detune plot receives cavity data."""
        from sc_linac_physics.applications.tuning.tuning_gui import RackScreen

        screen = RackScreen(mock_rack)
        curves = screen.detune_plot.curve_set.curves

        # 2 cavities * 2 PVs each (detune + cold)
        assert len(curves) == 4

    @pytest.mark.parametrize("use_rf,expected", [(True, 1), (False, 0)])
    def test_rack_cold_button(
        self,
        qapp_global,
        mock_rack,
        mock_parent,
        rack_screen_patches,
        use_rf,
        expected,
    ):
        """Test rack cold button with different RF states."""
        from sc_linac_physics.applications.tuning.tuning_gui import RackScreen

        mock_parent.get_use_rf_state.return_value = use_rf
        screen = RackScreen(mock_rack, parent=mock_parent)
        screen.on_rack_cold_button_clicked()

        assert mock_rack.use_rf == expected
        mock_rack.trigger_start.assert_called_once()

    def test_rack_abort_button(
        self, qapp_global, mock_rack, rack_screen_patches
    ):
        """Test rack abort button."""
        from sc_linac_physics.applications.tuning.tuning_gui import RackScreen

        screen = RackScreen(mock_rack)
        screen.abort_button.click()
        mock_rack.trigger_abort.assert_called_once()


def test_rack_detune_curve_set(mock_rack):
    """Detune solid, cold landing dashed, one shared color per cavity."""
    from sc_linac_physics.applications.tuning.tuning_gui import (
        rack_detune_curve_set,
    )

    curve_set = rack_detune_curve_set(mock_rack)
    pvs = [c.pv for c in curve_set.curves]
    assert pvs == [
        "TEST:DETUNE",
        "TEST:DF_COLD",
        "TEST:CAV2:DETUNE",
        "TEST:CAV2:DF_COLD",
    ]
    detune, cold, detune_2, _ = curve_set.curves
    assert [c.dashed for c in curve_set.curves] == [False, True, False, True]
    assert detune.color == cold.color != detune_2.color
    assert curve_set.axis_names == ["Detune (Hz)"]
