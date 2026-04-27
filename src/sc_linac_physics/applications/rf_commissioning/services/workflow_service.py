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
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
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

    def _validate_phase_prerequisites(
        self,
        *,
        cursor,
        run_id: int,
        phase: CommissioningPhase,
    ) -> tuple[bool, str]:
        """Validate phase can start from normalized phase instances.

        Args:
            cursor: Database cursor
            run_id: The workflow run ID
            phase: Phase to validate

        Returns:
            Tuple of (can_start, reason)
        """
        # PIEZO_PRE_RF is the first phase and can always be started/restarted
        if phase == CommissioningPhase.PIEZO_PRE_RF:
            return True, "Piezo Pre-RF can be run at any time"

        # Check if previous phase is complete
        previous_phase = phase.get_previous_phase()
        if previous_phase is None:
            return True, "No previous phase required"

        cursor.execute(
            """
            SELECT status FROM commissioning_phase_instances
            WHERE run_id = ? AND phase = ?
            ORDER BY attempt_number DESC
            LIMIT 1
            """,
            (run_id, previous_phase.value),
        )
        result = cursor.fetchone()
        previous_status = result[0] if result else None

        if previous_status not in {"complete", "skipped"}:
            status_str = previous_status or "not_started"
            return (
                False,
                f"Previous phase {previous_phase.value} must be complete or skipped first "
                f"(status: {status_str})",
            )

        return True, f"Prerequisites met for {phase.value} (reruns allowed)"

    def start_phase_for_record(
        self,
        *,
        record_id: int,
        phase: CommissioningPhase,
        operator: str,
        workflow_name: str = "rf_commissioning",
    ) -> PhaseStartResult:
        """Create or resume a run and start a new phase instance attempt."""
        now = datetime.now().isoformat()
        with self.db.connection() as conn:
            cursor = conn.cursor()

            run_id = self._get_or_create_run(
                cursor=cursor,
                record_id=record_id,
                phase=phase,
                operator=operator,
                workflow_name=workflow_name,
                now=now,
            )

            # Validate prerequisites from normalized phase-instance state.
            can_start, message = self._validate_phase_prerequisites(
                cursor=cursor,
                run_id=run_id,
                phase=phase,
            )
            if not can_start:
                raise ValueError(message)

            cursor.execute(
                """
                SELECT COALESCE(MAX(attempt_number), 0)
                FROM commissioning_phase_instances
                WHERE run_id = ? AND phase = ?
                """,
                (run_id, phase.value),
            )
            attempt_number = int(cursor.fetchone()[0]) + 1

            cursor.execute(
                """
                INSERT INTO commissioning_phase_instances (
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
                UPDATE commissioning_runs
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
        with self.db.connection() as conn:
            cursor = conn.cursor()
            run_id = self._get_run_id_for_record(cursor, record_id)

            self._validate_phase_instance_for_run(
                cursor=cursor,
                run_id=run_id,
                phase_instance_id=phase_instance_id,
                phase=phase,
            )

            cursor.execute(
                """
                UPDATE commissioning_phase_instances
                SET status = ?, ended_at = ?, error_message = NULL, updated_at = ?
                WHERE id = ? AND run_id = ?
                """,
                ("complete", now, now, phase_instance_id, run_id),
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
                UPDATE commissioning_runs
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
        with self.db.connection() as conn:
            cursor = conn.cursor()
            run_id = self._get_run_id_for_record(cursor, record_id)

            self._validate_phase_instance_for_run(
                cursor=cursor,
                run_id=run_id,
                phase_instance_id=phase_instance_id,
                phase=phase,
            )

            cursor.execute(
                """
                UPDATE commissioning_phase_instances
                SET status = ?, ended_at = ?, error_message = ?, updated_at = ?
                WHERE id = ? AND run_id = ?
                """,
                ("failed", now, error_message, now, phase_instance_id, run_id),
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
                UPDATE commissioning_runs
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
        phase: CommissioningPhase,
        operator: str,
        workflow_name: str,
        now: str,
    ) -> int:
        cursor.execute(
            "SELECT id FROM commissioning_runs WHERE record_id = ?",
            (record_id,),
        )
        row = cursor.fetchone()
        if row is not None:
            return int(row["id"])

        linac, cryomodule, cavity_number = self._get_record_coordinates(
            cursor, record_id
        )

        cursor.execute(
            """
            INSERT INTO commissioning_runs (
                record_id, workflow_name, linac, cryomodule, cavity_number,
                operator, status, current_phase, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                workflow_name,
                linac,
                cryomodule,
                cavity_number,
                operator,
                "in_progress",
                phase.value,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _get_record_coordinates(cursor, record_id: int) -> tuple[str, str, str]:
        cursor.execute(
            """
            SELECT linac, cryomodule, cavity_number
            FROM commissioning_records
            WHERE id = ?
            """,
            (record_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(
                f"No commissioning record exists for id={record_id}"
            )
        return (
            str(row["linac"]),
            str(row["cryomodule"]),
            str(row["cavity_number"]),
        )

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
            INSERT INTO commissioning_phase_artifacts (
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
            INSERT INTO commissioning_workflow_events (
                run_id, phase_instance_id, event_type, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, phase_instance_id, event_type, json.dumps(payload), now),
        )

    @staticmethod
    def _get_run_id_for_record(cursor, record_id: int) -> int:
        cursor.execute(
            "SELECT id FROM commissioning_runs WHERE record_id = ?",
            (record_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(
                f"No workflow run exists for record_id={record_id}"
            )
        return int(row["id"])

    @staticmethod
    def _validate_phase_instance_for_run(
        *,
        cursor,
        run_id: int,
        phase_instance_id: int,
        phase: CommissioningPhase,
    ) -> None:
        cursor.execute(
            """
            SELECT phase
            FROM commissioning_phase_instances
            WHERE id = ? AND run_id = ?
            """,
            (phase_instance_id, run_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(
                "Phase instance does not belong to the target workflow run: "
                f"run_id={run_id}, phase_instance_id={phase_instance_id}"
            )

        if row["phase"] != phase.value:
            raise ValueError(
                "Phase instance/phase mismatch: "
                f"expected {phase.value}, found {row['phase']}"
            )
