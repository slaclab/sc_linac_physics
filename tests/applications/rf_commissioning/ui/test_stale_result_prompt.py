"""Tests for the shared Rerun/Skip prompt for stale setup_rf results."""

from datetime import datetime
from unittest.mock import Mock

from sc_linac_physics.applications.rf_commissioning.ui.stale_result_prompt import (  # noqa: E501
    age_text,
    ask_about_stale_results,
)

OLD = datetime(2026, 10, 20, 11, 52)
STALE = {
    "ssa_calibration_time": OLD,
    "ssa_calibration_good": True,
    "ssa_calibration_recent": False,
    "characterization_time": None,
    "characterization_complete": False,
    "characterization_recent": False,
}


def test_age_text():
    now = datetime(2026, 10, 20, 14, 57)
    assert age_text(OLD, now) == "3 h 05 min"
    assert age_text(None) == "unknown"


def test_recent_results_are_not_asked_about():
    ask, params = Mock(), {}
    data = {"ssa_calibration_recent": True, "characterization_recent": True}
    assert ask_about_stale_results(ask, params, data, Mock())
    ask.assert_not_called()
    assert params == {}


def test_each_answer_goes_in_the_parameter_setup_rf_reads():
    ask, params, log = Mock(side_effect=[True, False]), {}, Mock()
    assert ask_about_stale_results(ask, params, STALE, log)
    assert params == {
        "rerun_ssa_calibration": True,
        "rerun_characterization": False,
    }
    assert [c.args for c in ask.call_args_list] == [
        ("SSA calibration", "CALTS", OLD, True),
        ("characterization", "PROBECALTS", None, False),
    ]
    assert log.call_count == 2


def test_closing_a_prompt_cancels_and_asks_nothing_more():
    ask, params = Mock(return_value=None), {}
    assert not ask_about_stale_results(ask, params, STALE, Mock())
    ask.assert_called_once()
    assert params == {}
