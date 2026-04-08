"""Normalized workflow orchestration service.

This service introduces a phase-instance model independent from the legacy
wide commissioning record schema. It is intentionally write-focused so the UI
can adopt it incrementally while prototype workflows evolve rapidly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.models.database import (
    CommissioningDatabase,
)


@dataclass(frozen=True)
class PhaseStartResult:
    """Result for starting a phase instance."""

    run_id: int
    phase_instance_id: int
    attempt_number: int


class WorkflowService:
    """Orchestrate normalized phase lifecycle for commissioning runs."""

    def __init__(self, db: CommissioningDatabase):
        self.db = db

    def start_phase_for_record(
        self,
        *,
        record_id: int,
        record: CommissioningRecord,
        phase: CommissioningPhase,
        operator: str,
        workflow_name: str = "rf_commissioning_v2",
    ) -> PhaseStartResult:
        """Create or resume a run and start a new phase instance attempt."""
        can_start, message = record.can_start_phase(phase)
        if not can_start:
            raise ValueError(message)

        now = datetime.now().isoformat()
        with self.db._get_connection() as conn:  # noqa: SLF001
            cursor = conn.cursor()

            run_id = self._get_or_create_run(
                cursor=cursor,
                record_id=record_id,
                record=record,
                operator=operator,
                workflow_name=workflow_name,
                now=now,
            )

            cursor.execute(
                """
                SELECT COALESCE(MAX(attempt_number), 0)
                FROM commissioning_phase_instances_v2
                WHERE run_id = ? AND phase = ?
                """,
                (run_id, phase.value),
            )
            attempt_number = int(cursor.fetchone()[0]) + 1

            cursor.execute(
                """
                INSERT INTO commissioning_phase_instances_v2 (
                    run_id, phase, attempt_number, status, operator,
                    started_at, ended_at, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    phase.value,
                    attempt_number,
                    "in_progress",
                    operator,
                    now,
                    None,
                    None,
                    now,
                    now,
                ),
            )
            phase_instance_id = int(cursor.lastrowid)

            self._insert_event(
                cursor=cursor,
                run_id=run_id,
                phase_instance_id=phase_instance_id,
                event_type="phase_started",
                payload={
                    "phase": phase.value,
                    "attempt": attempt_number,
                    "operator": operator,
                },
                now=now,
            )

            cursor.execute(
                """
                UPDATE commissioning_runs_v2
                SET current_phase = ?, status = ?, operator = ?, updated_at = ?
                WHERE id = ?
                """,
                (phase.value, "in_progress", operator, now, run_id),
            )

        return PhaseStartResult(
            run_id=run_id,
            phase_instance_id=phase_instance_id,
            attempt_number=attempt_number,
        )

    def complete_phase_instance(
        self,
        *,
        record_id: int,
        phase_instance_id: int,
        phase: CommissioningPhase,
        artifact_payload: dict | None = None,
        artifact_type: str = "phase_result",
    ) -> None:
        """Mark a phase instance complete and persist structured artifact."""
        now = datetime.now().isoformat()
        with self.db._get_connection() as conn:  # noqa: SLF001
            cursor = conn.cursor()
            run_id = self._get_run_id_for_record(cursor, record_id)

            cursor.execute(
                """
                UPDATE commissioning_phase_instances_v2
                SET status = ?, ended_at = ?, error_message = NULL, updated_at = ?
                WHERE id = ?
                """,
                ("complete", now, now, phase_instance_id),
            )

            if artifact_payload is not None:
                self._insert_artifact(
                    cursor=cursor,
                    phase_instance_id=phase_instance_id,
                    artifact_type=artifact_type,
                    payload=artifact_payload,
                    now=now,
                )

            next_phase = phase.get_next_phase()
            run_status = "complete" if next_phase is None else "in_progress"
            current_phase = (
                phase.value if next_phase is None else next_phase.value
            )

            cursor.execute(
                """
                UPDATE commissioning_runs_v2
                SET current_phase = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (current_phase, run_status, now, run_id),
            )

            self._insert_event(
                cursor=cursor,
                run_id=run_id,
                phase_instance_id=phase_instance_id,
                event_type="phase_completed",
                payload={
                    "phase": phase.value,
                    "next_phase": next_phase.value if next_phase else None,
                    "run_status": run_status,
                },
                now=now,
            )

    def fail_phase_instance(
        self,
        *,
        record_id: int,
        phase_instance_id: int,
        phase: CommissioningPhase,
        error_message: str,
        artifact_payload: dict | None = None,
        artifact_type: str = "phase_failure_snapshot",
    ) -> None:
        """Mark a phase instance failed, optionally with failure artifact."""
        now = datetime.now().isoformat()
        with self.db._get_connection() as conn:  # noqa: SLF001
            cursor = conn.cursor()
            run_id = self._get_run_id_for_record(cursor, record_id)

            cursor.execute(
                """
                UPDATE commissioning_phase_instances_v2
                SET status = ?, ended_at = ?, error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                ("failed", now, error_message, now, phase_instance_id),
            )

            if artifact_payload is not None:
                self._insert_artifact(
                    cursor=cursor,
                    phase_instance_id=phase_instance_id,
                    artifact_type=artifact_type,
                    payload=artifact_payload,
                    now=now,
                )

            cursor.execute(
                """
                UPDATE commissioning_runs_v2
                SET current_phase = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (phase.value, "failed", now, run_id),
            )

            self._insert_event(
                cursor=cursor,
                run_id=run_id,
                phase_instance_id=phase_instance_id,
                event_type="phase_failed",
                payload={"phase": phase.value, "error": error_message},
                now=now,
            )

    def _get_or_create_run(
        self,
        *,
        cursor,
        record_id: int,
        record: CommissioningRecord,
        operator: str,
        workflow_name: str,
        now: str,
    ) -> int:
        cursor.execute(
            "SELECT id FROM commissioning_runs_v2 WHERE record_id = ?",
            (record_id,),
        )
        row = cursor.fetchone()
        if row is not None:
            return int(row["id"])

        cursor.execute(
            """
            INSERT INTO commissioning_runs_v2 (
                record_id, workflow_name, linac, cryomodule, cavity_number,
                operator, status, current_phase, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                workflow_name,
                str(record.linac),
                record.cryomodule,
                str(record.cavity_number),
                operator,
                "in_progress",
                record.current_phase.value,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _insert_artifact(
        *,
        cursor,
        phase_instance_id: int,
        artifact_type: str,
        payload: dict,
        now: str,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO commissioning_phase_artifacts_v2 (
                phase_instance_id, artifact_type, payload_json, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (phase_instance_id, artifact_type, json.dumps(payload), now),
        )

    @staticmethod
    def _insert_event(
        *,
        cursor,
        run_id: int,
        phase_instance_id: int,
        event_type: str,
        payload: dict,
        now: str,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO commissioning_workflow_events_v2 (
                run_id, phase_instance_id, event_type, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, phase_instance_id, event_type, json.dumps(payload), now),
        )

    @staticmethod
    def _get_run_id_for_record(cursor, record_id: int) -> int:
        cursor.execute(
            "SELECT id FROM commissioning_runs_v2 WHERE record_id = ?",
            (record_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(
                f"No workflow run exists for record_id={record_id}"
            )
        return int(row["id"])
