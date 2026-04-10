"""Session-level tests for normalized workflow v2 APIs."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)


def _new_session(tmp_path) -> CommissioningSession:
    return CommissioningSession(db_path=str(tmp_path / "session_workflow.db"))


def test_session_starts_active_phase_instance(tmp_path):
    session = _new_session(tmp_path)

    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    record_id = session.db.save_record(record)
    session.load_record(record_id)

    started = session.start_active_phase_instance(
        CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )

    assert started is not None
    assert started.run_id > 0
    assert started.phase_instance_id > 0
    assert started.attempt_number == 1


def test_session_complete_and_fail_phase_instance(tmp_path):
    session = _new_session(tmp_path)

    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    record_id = session.db.save_record(record)
    session.load_record(record_id)

    started = session.start_active_phase_instance(
        CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )
    assert started is not None

    completed = session.complete_active_phase_instance(
        phase_instance_id=started.phase_instance_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        artifact_payload={"result": "ok"},
    )
    assert completed is True

    run = session.get_active_workflow_run_v2()
    assert run is not None
    assert run["status"] == "in_progress"
    assert run["current_phase"] == CommissioningPhase.SSA_CHAR.value

    # Start second attempt and fail it to verify failure path from session API.
    started2 = session.start_active_phase_instance(
        CommissioningPhase.SSA_CHAR,
        operator="tester",
    )
    assert started2 is not None

    failed = session.fail_active_phase_instance(
        phase_instance_id=started2.phase_instance_id,
        phase=CommissioningPhase.SSA_CHAR,
        error_message="failed phase",
        artifact_payload={"partial": True},
    )
    assert failed is True

    run2 = session.get_active_workflow_run_v2()
    assert run2 is not None
    assert run2["status"] == "failed"
    assert run2["current_phase"] == CommissioningPhase.SSA_CHAR.value

    instances = session.get_active_phase_instances_v2()
    assert len(instances) == 2
    assert instances[-1]["status"] == "failed"


def test_session_phase_command_helper(tmp_path):
    session = _new_session(tmp_path)

    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    record_id = session.db.save_record(record)
    session.load_record(record_id)

    phase_instance_id = session.begin_phase_command(
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )
    assert phase_instance_id is not None

    completed = session.complete_phase_command(
        phase=CommissioningPhase.PIEZO_PRE_RF,
        phase_instance_id=phase_instance_id,
        artifact_payload={"result": "ok"},
    )
    assert completed is True

    run = session.get_active_workflow_run_v2()
    assert run is not None
    assert run["current_phase"] == CommissioningPhase.SSA_CHAR.value
