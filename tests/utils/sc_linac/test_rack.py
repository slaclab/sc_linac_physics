from unittest.mock import Mock, patch

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.utils.sc_linac.linac import MACHINE
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    FSCANError,
)

_FSCAN_STAT_DONE = 5
_FSCAN_STAT_ABORTED = 6
_FSCAN_STAT_RESTORE_FAIL = 7


@pytest.fixture
def rack():
    # Rack A of CM01 (cavities 1-4).
    return MACHINE.cryomodules["01"].cavities[1].rack


@pytest.mark.parametrize(
    "prop_name, addr_attr",
    [
        ("fscan_freq_start_pv_obj", "fscan_freq_start_pv"),
        ("fscan_freq_stop_pv_obj", "fscan_freq_stop_pv"),
        ("fscan_rms_thresh_pv_obj", "fscan_rms_thresh_pv"),
        ("fscan_mode_overlap_pv_obj", "fscan_mode_overlap_pv"),
        ("fscan_start_pv_obj", "fscan_start_pv"),
        ("fscan_stat_pv_obj", "fscan_stat_pv"),
    ],
)
def test_rack_fscan_pv_obj_lazy_and_cached(rack, prop_name, addr_attr):
    setattr(rack, f"_{prop_name}", None)
    mock_pv = make_mock_pv()
    with patch(
        "sc_linac_physics.utils.sc_linac.rack.PV", return_value=mock_pv
    ) as pv_ctor:
        first = getattr(rack, prop_name)
        second = getattr(rack, prop_name)
    assert first is mock_pv
    assert second is mock_pv
    pv_ctor.assert_called_once_with(getattr(rack, addr_attr))


def _wire_fscan_pvs(rack, stat_sequence):
    """Give the rack mock FSCAN PVs; STAT replays stat_sequence."""
    stat_iter = iter(stat_sequence)
    rack._fscan_freq_start_pv_obj = make_mock_pv()
    rack._fscan_freq_stop_pv_obj = make_mock_pv()
    rack._fscan_rms_thresh_pv_obj = make_mock_pv()
    rack._fscan_mode_overlap_pv_obj = make_mock_pv()
    rack._fscan_start_pv_obj = make_mock_pv()
    stat_pv = make_mock_pv()
    stat_pv.get.side_effect = lambda: next(stat_iter)
    rack._fscan_stat_pv_obj = stat_pv


def _mock_cavity(number):
    cav = Mock()
    cav.number = number
    cav.fscan_sel_pv_obj = make_mock_pv()
    cav.fscan_push_8pi9_pv_obj = make_mock_pv()
    cav.fscan_push_7pi9_pv_obj = make_mock_pv()
    return cav


def _params():
    return dict(
        freq_start=-3_500_000,
        freq_stop=50_000,
        rms_thresh=10.0,
        mode_overlap=1_000,
        poll_interval=0.0,
        timeout_seconds=60.0,
    )


def test_run_fscan_success_selects_and_pushes(rack, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    _wire_fscan_pvs(rack, [3, _FSCAN_STAT_DONE])  # in-progress, then done
    target = _mock_cavity(1)
    other = _mock_cavity(2)
    rack.cavities = {1: target, 2: other}

    rack.run_fscan([target], **_params())

    target.fscan_sel_pv_obj.put.assert_called_once_with(1)
    other.fscan_sel_pv_obj.put.assert_called_once_with(0)
    rack._fscan_start_pv_obj.put.assert_called_once_with(1)
    target.fscan_push_8pi9_pv_obj.put.assert_called_once_with(1)
    target.fscan_push_7pi9_pv_obj.put.assert_called_once_with(1)
    other.fscan_push_8pi9_pv_obj.put.assert_not_called()


def test_run_fscan_multiple_cavities(rack, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    _wire_fscan_pvs(rack, [_FSCAN_STAT_DONE])
    c1, c2, c3 = _mock_cavity(1), _mock_cavity(2), _mock_cavity(3)
    rack.cavities = {1: c1, 2: c2, 3: c3}

    rack.run_fscan([c1, c3], **_params())

    c1.fscan_sel_pv_obj.put.assert_called_once_with(1)
    c3.fscan_sel_pv_obj.put.assert_called_once_with(1)
    c2.fscan_sel_pv_obj.put.assert_called_once_with(0)
    for cav in (c1, c3):
        cav.fscan_push_8pi9_pv_obj.put.assert_called_once_with(1)
        cav.fscan_push_7pi9_pv_obj.put.assert_called_once_with(1)
    c2.fscan_push_8pi9_pv_obj.put.assert_not_called()


@pytest.mark.parametrize(
    "bad_stat", [_FSCAN_STAT_ABORTED, _FSCAN_STAT_RESTORE_FAIL]
)
def test_run_fscan_scan_failure_raises(rack, monkeypatch, bad_stat):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    _wire_fscan_pvs(rack, [bad_stat])
    target = _mock_cavity(1)
    rack.cavities = {1: target}

    with pytest.raises(FSCANError):
        rack.run_fscan([target], **_params())
    target.fscan_push_8pi9_pv_obj.put.assert_not_called()


def test_run_fscan_timeout_raises(rack, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    _wire_fscan_pvs(rack, [3, 3, 3, 3])  # never done
    target = _mock_cavity(1)
    rack.cavities = {1: target}

    params = _params()
    params["timeout_seconds"] = 0.0  # expire immediately
    with pytest.raises(FSCANError):
        rack.run_fscan([target], **params)


def test_run_fscan_abort_raises(rack, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    _wire_fscan_pvs(rack, [3, 3])
    target = _mock_cavity(1)
    rack.cavities = {1: target}

    with pytest.raises(CavityAbortError):
        rack.run_fscan([target], should_abort=lambda: True, **_params())


def test_run_fscan_status_callback_invoked(rack, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    _wire_fscan_pvs(rack, [3, _FSCAN_STAT_DONE])
    target = _mock_cavity(1)
    rack.cavities = {1: target}
    msgs = []

    rack.run_fscan([target], status_callback=msgs.append, **_params())

    assert any("FSCAN" in m for m in msgs)
