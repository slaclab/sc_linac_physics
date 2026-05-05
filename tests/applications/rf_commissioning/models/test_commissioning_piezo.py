"""Tests for commissioning-specific piezo PV bindings."""

from __future__ import annotations

import pytest

import sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo as commissioning_piezo_module
from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)


class _DummyCavity:
    def pv_addr(self, suffix: str) -> str:
        return f"TEST:{suffix}"

    def __str__(self) -> str:
        return "TEST_CAVITY"


class _FakePV:
    created: list[str] = []

    def __init__(self, pvname: str):
        self.pvname = pvname
        _FakePV.created.append(pvname)


@pytest.fixture
def piezo(monkeypatch: pytest.MonkeyPatch) -> CommissioningPiezo:
    _FakePV.created.clear()
    monkeypatch.setattr(commissioning_piezo_module, "PV", _FakePV)
    return CommissioningPiezo(_DummyCavity())


@pytest.mark.parametrize(
    ("pv_attr", "pv_obj_prop"),
    [
        ("prerf_test_start_pv", "prerf_test_start_pv_obj"),
        ("prerf_test_status_pv", "prerf_test_status_pv_obj"),
        ("prerf_cha_status_pv", "prerf_cha_status_pv_obj"),
        ("prerf_chb_status_pv", "prerf_chb_status_pv_obj"),
        ("prerf_cha_testmsg_pv", "prerf_cha_testmsg_pv_obj"),
        ("prerf_chb_testmsg_pv", "prerf_chb_testmsg_pv_obj"),
        ("capacitance_a_pv", "capacitance_a_pv_obj"),
        ("capacitance_b_pv", "capacitance_b_pv_obj"),
        ("withrf_run_check_pv", "withrf_run_check_pv_obj"),
        ("withrf_check_status_pv", "withrf_check_status_pv_obj"),
        ("withrf_status_pv", "withrf_status_pv_obj"),
        ("amplifiergain_a_pv", "amplifiergain_a_pv_obj"),
        ("amplifiergain_b_pv", "amplifiergain_b_pv_obj"),
        ("withrf_push_dfgain_pv", "withrf_push_dfgain_pv_obj"),
        ("withrf_save_dfgain_pv", "withrf_save_dfgain_pv_obj"),
        ("detunegain_new_pv", "detunegain_new_pv_obj"),
    ],
)
def test_pv_object_properties_lazy_create_and_cache(
    piezo: CommissioningPiezo,
    pv_attr: str,
    pv_obj_prop: str,
) -> None:
    expected_pv = getattr(piezo, pv_attr)

    pv_obj_1 = getattr(piezo, pv_obj_prop)
    pv_obj_2 = getattr(piezo, pv_obj_prop)

    assert pv_obj_1 is pv_obj_2
    assert pv_obj_1.pvname == expected_pv
    assert _FakePV.created.count(expected_pv) == 1


def test_pre_rf_pv_names_use_expected_suffixes(
    piezo: CommissioningPiezo,
) -> None:
    assert piezo.prerf_test_start_pv.endswith("TESTSTRT")
    assert piezo.prerf_test_status_pv.endswith("TESTSTS")
    assert piezo.prerf_cha_status_pv.endswith("CHA_TESTSTAT")
    assert piezo.prerf_chb_status_pv.endswith("CHB_TESTSTAT")
    assert piezo.capacitance_a_pv.endswith("CHA_C")
    assert piezo.capacitance_b_pv.endswith("CHB_C")


def test_with_rf_pv_names_use_expected_suffixes(
    piezo: CommissioningPiezo,
) -> None:
    assert piezo.withrf_run_check_pv.endswith("RFTESTSTRT")
    assert piezo.withrf_check_status_pv.endswith("RFTESTSTS")
    assert piezo.withrf_status_pv.endswith("RFSTESTSTAT")
    assert piezo.amplifiergain_a_pv.endswith("CHA_AMPGAIN")
    assert piezo.amplifiergain_b_pv.endswith("CHB_AMPGAIN")
    assert piezo.withrf_push_dfgain_pv.endswith("PUSH_DFGAIN.PROC")
    assert piezo.withrf_save_dfgain_pv.endswith("SAVE_DFGAIN.PROC")
    assert piezo.detunegain_new_pv.endswith("DFGAIN_NEW")
