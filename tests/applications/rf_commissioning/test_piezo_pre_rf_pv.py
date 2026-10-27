"""Tests for the shared controller helpers in piezo_pre_rf_pv."""

import pytest

from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_pv import (
    cryomodule_key,
    format_pv_update_message,
)


@pytest.mark.parametrize(
    "selection, key",
    [("2", "02"), ("02", "02"), (2, "02"), ("H1", "H1"), ("H2", "H2")],
)
def test_cryomodule_key(selection, key) -> None:
    assert cryomodule_key(selection) == key


@pytest.mark.parametrize("selection", ["...", "", "36", "H3"])
def test_cryomodule_key_rejects_unknown_names(selection) -> None:
    with pytest.raises(ValueError):
        cryomodule_key(selection)


def test_format_pv_update_message_uses_the_key() -> None:
    message = format_pv_update_message("H1", "3", "H1", 3)
    assert message.endswith("(CMH1 Cav3)")
