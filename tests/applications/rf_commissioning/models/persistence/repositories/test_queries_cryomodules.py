"""Tests for query and cryomodule persistence behavior."""

from __future__ import annotations

import json

import pytest

from sc_linac_physics.applications.rf_commissioning.models.cryomodule_models import (
    CryomoduleCheckoutRecord,
    CryomodulePhase,
    CryomodulePhaseStatus,
    MagnetCheckoutData,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PhaseStatus,
    PiezoPreRFCheck,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    CommissioningDatabase,
    RecordConflictError,
    RecordDeletionDisabledError,
)
from sc_linac_physics.applications.rf_commissioning.services.workflow_service import (
    WorkflowService,
)


def _new_db(tmp_path) -> CommissioningDatabase:
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    return db


def _new_record(cavity_number: int = 1) -> CommissioningRecord:
    record = CommissioningRecord(
        linac=1, cryomodule="02", cavity_number=cavity_number
    )
    record.piezo_pre_rf = PiezoPreRFCheck(
        capacitance_a=2.1e-9,
        capacitance_b=2.2e-9,
        channel_a_passed=True,
        channel_b_passed=True,
    )
    record.phase_status[CommissioningPhase.PIEZO_PRE_RF] = PhaseStatus.COMPLETE
    return record


def _new_cryomodule_record() -> CryomoduleCheckoutRecord:
    record = CryomoduleCheckoutRecord(linac="L1B", cryomodule="02")
    record.magnet_checkout = MagnetCheckoutData(
        passed=True,
        operator="tester",
        notes="all good",
    )
    record.phase_status[CryomodulePhase.MAGNET_CHECKOUT] = (
        CryomodulePhaseStatus.COMPLETE
    )
    record.notes = "initial notes"
    return record


def test_query_repository_filters_active_records_and_exposes_workflow_metadata(
    tmp_path,
):
    db = _new_db(tmp_path)
    svc = WorkflowService(db)

    inactive_record_id = db.save_record(_new_record(1))
    active_record_id = db.save_record(_new_record(2))

    started = svc.start_phase_for_record(
        record_id=active_record_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )
    svc.complete_phase_instance(
        record_id=active_record_id,
        phase_instance_id=started.phase_instance_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        artifact_payload={"result": "ok"},
    )

    records = db.get_records_by_cryomodule("02")
    assert [record.cavity_number for record in records] == [2, 1]

    active_records = db.get_records_by_cryomodule("02", active_only=True)
    assert [record.cavity_number for record in active_records] == [2]

    summary = db.find_records_for_cavity(1, "02", "2")
    assert len(summary) == 1
    assert summary[0]["current_phase"] == CommissioningPhase.SSA_CHAR.value
    assert summary[0]["piezo_pre_rf"] == {
        "channel_a_passed": True,
        "channel_b_passed": True,
        "capacitance_a": 2.1e-9,
        "capacitance_b": 2.2e-9,
    }
    assert db.get_record_id_for_cavity(1, "02", "2") == active_record_id
    assert db.get_active_record_id_for_cavity(1, "02", "2") == active_record_id
    assert db.get_active_record_id_for_cavity(1, "02", "1") is None

    workflow_run = db.get_workflow_run(active_record_id)
    assert workflow_run is not None
    assert workflow_run["status"] == "in_progress"
    assert workflow_run["current_phase"] == CommissioningPhase.SSA_CHAR.value

    phase_instances = db.get_phase_instances(active_record_id)
    assert len(phase_instances) == 1
    assert phase_instances[0]["phase"] == CommissioningPhase.PIEZO_PRE_RF.value
    assert phase_instances[0]["status"] == "complete"

    with pytest.raises(RecordDeletionDisabledError):
        db.delete_record(inactive_record_id)
    assert db.get_record(inactive_record_id) is not None


def test_cryomodule_repository_round_trips_records_and_detects_conflicts(
    tmp_path,
):
    db = _new_db(tmp_path)

    record = _new_cryomodule_record()
    record_id = db.save_cryomodule_record(record)
    assert db.get_cryomodule_record_id("L1B", "02") == record_id

    loaded = db.get_cryomodule_record_with_version("L1B", "02")
    assert loaded is not None
    loaded_record, version = loaded
    assert loaded_record.magnet_checkout is not None
    assert loaded_record.magnet_checkout.operator == "tester"
    assert (
        loaded_record.phase_status[CryomodulePhase.MAGNET_CHECKOUT]
        is CryomodulePhaseStatus.COMPLETE
    )
    assert loaded_record.notes == "initial notes"

    loaded_record.notes = "updated notes"
    loaded_record.phase_status[CryomodulePhase.MAGNET_CHECKOUT] = (
        CryomodulePhaseStatus.FAILED
    )
    assert (
        db.save_cryomodule_record(
            loaded_record,
            record_id=record_id,
            expected_version=version,
        )
        == record_id
    )

    refreshed = db.get_cryomodule_record("L1B", "02")
    assert refreshed is not None
    assert refreshed.notes == "updated notes"
    assert (
        refreshed.phase_status[CryomodulePhase.MAGNET_CHECKOUT]
        is CryomodulePhaseStatus.FAILED
    )

    try:
        db.save_cryomodule_record(
            loaded_record,
            record_id=record_id,
            expected_version=version,
        )
    except RecordConflictError as exc:
        assert exc.record_id == record_id
    else:
        raise AssertionError("Expected stale cryomodule save to raise conflict")


@pytest.mark.parametrize("legacy_payload", [["legacy"], "legacy", 123])
def test_get_record_summaries_ignores_non_object_piezo_payloads(
    tmp_path,
    legacy_payload,
):
    db = _new_db(tmp_path)
    record_id = db.save_record(_new_record(1))

    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE commissioning_records
            SET piezo_pre_rf = ?
            WHERE id = ?
            """,
            (json.dumps(legacy_payload), record_id),
        )

    summaries = db.find_records_for_cavity(1, "02", "1")
    assert len(summaries) == 1
    assert "piezo_pre_rf" not in summaries[0]
