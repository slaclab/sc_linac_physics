"""Tests for CommissioningCavity and build_commissioning_machine."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.commissioning_cavity import (
    CommissioningCavity,
)
from sc_linac_physics.applications.rf_commissioning.models.commissioning_machine import (
    build_commissioning_machine,
)
from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)


@pytest.fixture
def cavity() -> CommissioningCavity:
    return build_commissioning_machine().cryomodules["02"].cavities[1]


def test_machine_uses_commissioning_cavity_and_piezo(cavity):
    assert isinstance(cavity, CommissioningCavity)
    assert isinstance(cavity.piezo, CommissioningPiezo)


def test_machine_is_new_each_call():
    assert build_commissioning_machine() is not build_commissioning_machine()


def test_tune_to_resonance_chirp_passes_args_to_auto_tune(cavity):
    cavity._auto_tune = Mock()
    callback = Mock()

    cavity.tune_to_resonance_chirp(
        tolerance_hz=50.0, iteration_callback=callback, max_stepper_temp=70.0
    )

    cavity._auto_tune.assert_called_once()
    kwargs = cavity._auto_tune.call_args.kwargs
    assert kwargs["tolerance"] == 50.0
    assert kwargs["iteration_callback"] is callback
    assert kwargs["max_stepper_temp"] == 70.0
    # The signed step count is left as it is.
    assert "reset_signed_steps" not in kwargs


def test_tune_to_resonance_chirp_reads_chirp_detune(cavity, monkeypatch):
    monkeypatch.setattr(
        CommissioningCavity, "detune_chirp", property(lambda self: 1234.0)
    )
    cavity._auto_tune = Mock()

    cavity.tune_to_resonance_chirp(tolerance_hz=50.0)

    delta_hz_func = cavity._auto_tune.call_args.kwargs["delta_hz_func"]
    assert delta_hz_func() == 1234.0


def test_tune_to_resonance_chirp_does_not_set_up_or_finish(cavity):
    cavity._auto_tune = Mock()
    cavity.setup_tuning = Mock()
    cavity._tune_config_pv_obj = Mock()

    cavity.tune_to_resonance_chirp(tolerance_hz=50.0)

    cavity.setup_tuning.assert_not_called()
    cavity._tune_config_pv_obj.put.assert_not_called()


def test_models_package_does_not_import_linac():
    """Importing linac.py builds linac.MACHINE, so models must not."""
    code = (
        "import sys\n"
        "import sc_linac_physics.applications.rf_commissioning.models\n"
        "assert 'sc_linac_physics.utils.sc_linac.linac' not in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
