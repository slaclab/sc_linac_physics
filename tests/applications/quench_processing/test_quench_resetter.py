from random import choice
from typing import List
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.applications.quench_processing.quench_cavity import QuenchCavity
from sc_linac_physics.applications.quench_processing.quench_cryomodule import (
    QuenchCryomodule,
)
from sc_linac_physics.applications.quench_processing.quench_resetter import (
    check_cavities,
)
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import (
    HW_MODE_ONLINE_VALUE,
    HW_MODE_MAINTENANCE_VALUE,
    HW_MODE_OFFLINE_VALUE,
    HW_MODE_MAIN_DONE_VALUE,
    HW_MODE_READY_VALUE,
)
from tests.utils.mock_utils import mock_func


@pytest.fixture
def cavities(monkeypatch):
    monkeypatch.setattr("os.makedirs", mock_func)
    monkeypatch.setattr("lcls_tools.common.logger.logger.custom_logger", mock_func)
    monkeypatch.setattr("logging.FileHandler", mock_func)
    cavity_lst: List[QuenchCavity] = list(
        Machine(
            cavity_class=QuenchCavity, cryomodule_class=QuenchCryomodule
        ).all_iterator
    )

    for cavity in cavity_lst:
        cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
        cavity._rf_control_pv_obj = make_mock_pv(get_val=1)
        cavity._quench_latch_pv_obj = make_mock_pv(get_val=0)
        cavity.reset_quench = MagicMock(return_value=False)

    yield cavity_lst


def test_check_cavities_quenched(cavities):
    watcher_pv = make_mock_pv(get_val=0)
    quenched_cav = choice(cavities)
    quenched_cav._quench_latch_pv_obj = make_mock_pv(get_val=1)

    check_cavities(cavities, watcher_pv)
    for cavity in cavities:
        if cavity == quenched_cav:
            cavity.reset_quench.assert_called()
        else:
            cavity.reset_quench.assert_not_called()


def test_check_cavities_not_online(cavities):
    watcher_pv = make_mock_pv(get_val=0)

    for cavity in cavities:
        cavity._quench_latch_pv_obj = make_mock_pv(get_val=1)

    not_online_cav = choice(cavities)
    not_online_cav._hw_mode_pv_obj = make_mock_pv(
        get_val=choice(
            [
                HW_MODE_MAINTENANCE_VALUE,
                HW_MODE_OFFLINE_VALUE,
                HW_MODE_MAIN_DONE_VALUE,
                HW_MODE_READY_VALUE,
            ]
        )
    )

    check_cavities(cavities, watcher_pv)
    for cavity in cavities:
        if cavity == not_online_cav:
            cavity.reset_quench.assert_not_called()
        else:
            cavity.reset_quench.assert_called()


def test_check_cavities_not_on(cavities):
    watcher_pv = make_mock_pv(get_val=0)

    for cavity in cavities:
        cavity._quench_latch_pv_obj = make_mock_pv(get_val=1)

    not_on_cav = choice(cavities)
    not_on_cav._rf_control_pv_obj = make_mock_pv(get_val=0)

    check_cavities(cavities, watcher_pv)
    for cavity in cavities:
        if cavity == not_on_cav:
            cavity.reset_quench.assert_not_called()
        else:
            cavity.reset_quench.assert_called()
