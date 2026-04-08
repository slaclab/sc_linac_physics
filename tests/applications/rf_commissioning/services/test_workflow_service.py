"""Tests for normalized WorkflowService lifecycle."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.models.database import (
    CommissioningDatabase,
)
from sc_linac_physics.applications.rf_commissioning.services import (
    WorkflowService,
)


def _new_record() -> CommissioningRecord:
    return CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)


def test_start_phase_creates_run_and_instance(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "workflow.db"))
    db.initialize()
    svc = WorkflowService(db)

    record = _new_record()
    record_id = db.save_record(record)

    start = svc.start_phase_for_record(
        record_id=record_id,
        record=record,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )

    assert start.run_id > 0
    assert start.phase_instance_id > 0
    assert start.attempt_number == 1


def test_complete_phase_writes_artifact_and_advances(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "workflow.db"))
    db.initialize()
    svc = WorkflowService(db)

    record = _new_record()
    record_id = db.save_record(record)

    start = svc.start_phase_for_record(
        record_id=record_id,
        record=record,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )

    record.set_phase_status(
        CommissioningPhase.PIEZO_PRE_RF, PhaseStatus.COMPLETE
    )

    svc.complete_phase_instance(
        record_id=record_id,
        phase_instance_id=start.phase_instance_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        artifact_payload={"result": "ok", "capacitance_a_nf": 2.4},
    )

    with db._get_connection() as conn:  # noqa: SLF001
        cursor = conn.cursor()

        cursor.execute(
            "SELECT status, current_phase FROM commissioning_runs_v2 WHERE id = ?",
            (start.run_id,),
        )
        row = cursor.fetchone()
        assert row["status"] == "in_progress"
        assert row["current_phase"] == CommissioningPhase.SSA_CHAR.value

        cursor.execute(
            "SELECT status FROM commissioning_phase_instances_v2 WHERE id = ?",
            (start.phase_instance_id,),
        )
        row = cursor.fetchone()
        assert row["status"] == "complete"

        cursor.execute(
            "SELECT COUNT(*) AS count FROM commissioning_phase_artifacts_v2 WHERE phase_instance_id = ?",
            (start.phase_instance_id,),
        )
        row = cursor.fetchone()
        assert row["count"] == 1


def test_fail_phase_marks_run_failed(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "workflow.db"))
    db.initialize()
    svc = WorkflowService(db)

    record = _new_record()
    record_id = db.save_record(record)

    start = svc.start_phase_for_record(
        record_id=record_id,
        record=record,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )

    svc.fail_phase_instance(
        record_id=record_id,
        phase_instance_id=start.phase_instance_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        error_message="test failure",
        artifact_payload={"partial": True},
    )

    with db._get_connection() as conn:  # noqa: SLF001
        cursor = conn.cursor()

        cursor.execute(
            "SELECT status, current_phase FROM commissioning_runs_v2 WHERE id = ?",
            (start.run_id,),
        )
        row = cursor.fetchone()
        assert row["status"] == "failed"
        assert row["current_phase"] == CommissioningPhase.PIEZO_PRE_RF.value

        cursor.execute(
            "SELECT status, error_message FROM commissioning_phase_instances_v2 WHERE id = ?",
            (start.phase_instance_id,),
        )
        row = cursor.fetchone()
        assert row["status"] == "failed"
        assert row["error_message"] == "test failure"
