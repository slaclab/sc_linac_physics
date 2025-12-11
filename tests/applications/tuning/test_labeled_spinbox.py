# tests/test_tuning_gui/test_labeled_spinbox.py
"""Tests for LabeledSpinbox component."""


class TestLabeledSpinbox:
    """Tests for LabeledSpinbox class."""

    def test_initialization(self, qapp_global, pydm_patches):
        """Test LabeledSpinbox creates correct components."""
        from sc_linac_physics.applications.tuning.tuning_gui import (
            LabeledSpinbox,
        )

        spinbox = LabeledSpinbox("TEST:CHANNEL:PV")
        assert spinbox.label.text() == "PV"
        assert spinbox.layout.count() == 2

    def test_label_extraction(self, qapp_global, pydm_patches):
        """Test label extracts last part of PV name."""
        from sc_linac_physics.applications.tuning.tuning_gui import (
            LabeledSpinbox,
        )

        spinbox = LabeledSpinbox("LONG:PATH:TO:VARIABLE")
        assert spinbox.label.text() == "VARIABLE"
