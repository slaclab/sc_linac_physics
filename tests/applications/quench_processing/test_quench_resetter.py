from random import choice
from typing import List
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.applications.quench_processing.quench_cavity import (
    QuenchCavity,
)
from sc_linac_physics.applications.quench_processing.quench_cryomodule import (
    QuenchCryomodule,
)
from sc_linac_physics.applications.quench_processing.quench_resetter import (
    check_cavities,
    CavityResetTracker,
)
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import (
    HW_MODE_ONLINE_VALUE,
    HW_MODE_MAINTENANCE_VALUE,
    HW_MODE_OFFLINE_VALUE,
    HW_MODE_MAIN_DONE_VALUE,
    HW_MODE_READY_VALUE,
)
from tests.mock_utils import mock_func


@pytest.fixture
def cavities(monkeypatch):
    monkeypatch.setattr("os.makedirs", mock_func)
    monkeypatch.setattr(
        "lcls_tools.common.logger.logger.custom_logger", mock_func
    )
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
        cavity.reset_quench = MagicMock(return_value=True)

    yield cavity_lst


@pytest.fixture
def reset_tracker():
    """Provide a CavityResetTracker instance for tests."""
    return CavityResetTracker(cooldown_seconds=3.0)


def test_check_cavities_quenched(cavities, reset_tracker):
    watcher_pv = make_mock_pv(get_val=0)
    quenched_cav = choice(cavities)
    quenched_cav._quench_latch_pv_obj = make_mock_pv(get_val=1)

    counts = check_cavities(cavities, watcher_pv, reset_tracker)

    # Verify counts
    assert counts["reset"] == 1
    assert counts["skipped"] == 0
    assert counts["error"] == 0

    # Verify reset was called only for quenched cavity
    for cavity in cavities:
        if cavity == quenched_cav:
            cavity.reset_quench.assert_called()
        else:
            cavity.reset_quench.assert_not_called()


def test_check_cavities_not_online(cavities, reset_tracker):
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

    counts = check_cavities(cavities, watcher_pv, reset_tracker)

    # Verify that offline cavity was not counted as checked
    num_online = len(cavities) - 1
    assert counts["checked"] == num_online
    assert counts["reset"] == num_online

    # Verify reset behavior
    for cavity in cavities:
        if cavity == not_online_cav:
            cavity.reset_quench.assert_not_called()
        else:
            cavity.reset_quench.assert_called()


def test_check_cavities_not_on(cavities, reset_tracker):
    watcher_pv = make_mock_pv(get_val=0)

    for cavity in cavities:
        cavity._quench_latch_pv_obj = make_mock_pv(get_val=1)

    not_on_cav = choice(cavities)
    not_on_cav._rf_control_pv_obj = make_mock_pv(get_val=0)

    counts = check_cavities(cavities, watcher_pv, reset_tracker)

    # Verify that turned-off cavity was not counted as checked
    num_on = len(cavities) - 1
    assert counts["checked"] == num_on
    assert counts["reset"] == num_on

    # Verify reset behavior
    for cavity in cavities:
        if cavity == not_on_cav:
            cavity.reset_quench.assert_not_called()
        else:
            cavity.reset_quench.assert_called()


def test_check_cavities_cooldown_prevents_reset(cavities, reset_tracker):
    """Test that cooldown period prevents immediate re-reset."""
    watcher_pv = make_mock_pv(get_val=0)
    quenched_cav = choice(cavities)
    quenched_cav._quench_latch_pv_obj = make_mock_pv(get_val=1)

    # First reset
    counts1 = check_cavities(cavities, watcher_pv, reset_tracker)
    assert counts1["reset"] == 1
    assert counts1["skipped"] == 0
    quenched_cav.reset_quench.assert_called_once()

    # Immediate second check - should be skipped due to cooldown
    quenched_cav.reset_quench.reset_mock()
    counts2 = check_cavities(cavities, watcher_pv, reset_tracker)
    assert counts2["reset"] == 0
    assert counts2["skipped"] == 1
    quenched_cav.reset_quench.assert_not_called()


def test_check_cavities_failed_reset(cavities, reset_tracker):
    """Test that failed resets are tracked correctly."""
    watcher_pv = make_mock_pv(get_val=0)
    quenched_cav = choice(cavities)
    quenched_cav._quench_latch_pv_obj = make_mock_pv(get_val=1)
    quenched_cav.reset_quench = MagicMock(return_value=False)

    counts = check_cavities(cavities, watcher_pv, reset_tracker)

    assert counts["reset"] == 0
    assert counts["error"] == 1
    quenched_cav.reset_quench.assert_called_once()


def test_check_cavities_heartbeat_update(cavities, reset_tracker):
    """Test that heartbeat PV is updated."""
    watcher_pv = make_mock_pv(get_val=5)

    check_cavities(cavities, watcher_pv, reset_tracker)

    # Verify heartbeat was incremented
    watcher_pv.put.assert_called_once_with(6)


def test_reset_tracker_stats(cavities, reset_tracker):
    """Test that reset tracker properly records statistics."""
    watcher_pv = make_mock_pv(get_val=0)
    quenched_cav = choice(cavities)
    quenched_cav._quench_latch_pv_obj = make_mock_pv(get_val=1)

    # Perform a reset
    check_cavities(cavities, watcher_pv, reset_tracker)

    # Check summary
    summary = reset_tracker.get_summary()
    cavity_id = str(quenched_cav)

    assert cavity_id in summary
    assert summary[cavity_id]["total_resets"] == 1
    assert summary[cavity_id]["failed_resets"] == 0


def test_reset_tracker_can_reset(reset_tracker, cavities):
    """Test the can_reset method returns proper tuple."""
    test_cavity = cavities[0]

    # Should be able to reset initially
    can_reset, reason = reset_tracker.can_reset(test_cavity)
    assert can_reset is True
    assert reason == "ready"

    # Record a reset
    reset_tracker.record_reset(test_cavity, success=True)

    # Should not be able to reset immediately
    can_reset, reason = reset_tracker.can_reset(test_cavity)
    assert can_reset is False
    assert "cooldown active" in reason


def test_multiple_cavities_quenched(cavities, reset_tracker):
    """Test handling multiple quenched cavities in one cycle."""
    watcher_pv = make_mock_pv(get_val=0)

    # Quench 3 random cavities
    quenched_cavs = [choice(cavities) for _ in range(3)]
    for cav in quenched_cavs:
        cav._quench_latch_pv_obj = make_mock_pv(get_val=1)

    counts = check_cavities(cavities, watcher_pv, reset_tracker)

    # All quenched cavities should be reset
    assert counts["reset"] == len(quenched_cavs)

    for cav in quenched_cavs:
        cav.reset_quench.assert_called()
