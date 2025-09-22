from random import randint
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.displays.cavity_display import Runner


@pytest.fixture
def runner() -> Runner:
    runner = Runner(lazy_fault_pvs=True)
    runner._watcher_pv_obj = make_mock_pv(get_val=randint(0, 1000000))
    for cavity in runner.backend_cavities:
        cavity.run_through_faults = MagicMock()
    return runner


def test_check_faults(runner):
    runner.check_faults()
    for cavity in runner.backend_cavities:
        cavity.run_through_faults.assert_called()
    runner._watcher_pv_obj.put.assert_called()


def test_watcher_pv_obj(runner):
    assert runner.watcher_pv_obj == runner._watcher_pv_obj
