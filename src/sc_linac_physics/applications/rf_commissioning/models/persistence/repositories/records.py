"""Repositories for commissioning cavity records."""

from __future__ import annotations

from datetime import datetime

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database_helpers import (
    build_workflow_state,
    now_iso,
)

from .base import BaseRepository


class RecordRepository(BaseRepository):
    """Persistence for cavity commissioning session rows."""

    def save_record(
        self,
        record: CommissioningRecord,
        record_id: int | None = None,
        expected_version: int | None = None,
    ) -> int:
        now = now_iso()
        phase_data_json = {
            attr_name: self.serialize_phase_data(getattr(record, attr_name))
            for attr_name in self.phase_data_models
        }

        with self.db.connection() as conn:
            cursor = conn.cursor()
            linac_number = str(record.linac)
            phase_col_names = list(self.phase_data_models.keys())
            phase_values = [phase_data_json[col] for col in phase_col_names]

            if record_id is None:
                phase_col_list = ", ".join(phase_col_names)
                phase_placeholders = ", ".join("?" * len(phase_col_names))
                cursor.execute(
                    f"""
                    INSERT INTO commissioning_records (
                        linac, linac_number, cryomodule, cavity_number, start_time, end_time,
                        {phase_col_list},
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, {phase_placeholders}, ?, ?)
                    """,
                    (
                        str(record.linac),
                        linac_number,
                        record.cryomodule,
                        record.cavity_number,
                        record.start_time.isoformat(),
                        (
                            record.end_time.isoformat()
                            if record.end_time
                            else None
                        ),
                        *phase_values,
                        now,
                        now,
                    ),
                )
                return int(cursor.lastrowid)

            phase_set_clauses = ", ".join(
                f"{col} = ?" for col in phase_col_names
            )
            params = (
                str(record.linac),
                linac_number,
                record.cryomodule,
                record.cavity_number,
                record.start_time.isoformat(),
                record.end_time.isoformat() if record.end_time else None,
                *phase_values,
                now,
                record_id,
            )

            if expected_version is not None:
                cursor.execute(
                    f"""
                    UPDATE commissioning_records SET
                        linac = ?, linac_number = ?, cryomodule = ?, cavity_number = ?, start_time = ?, end_time = ?,
                        {phase_set_clauses},
                        updated_at = ?,
                        version = version + 1
                    WHERE id = ? AND version = ?
                    """,
                    (*params, expected_version),
                )
                if cursor.rowcount == 0:
                    self.raise_conflict_error(
                        cursor=cursor,
                        table_name="commissioning_records",
                        row_id=record_id,
                        expected_version=expected_version,
                        missing_message=f"Record {record_id} not found",
                    )
            else:
                cursor.execute(
                    f"""
                    UPDATE commissioning_records SET
                        linac = ?, linac_number = ?, cryomodule = ?, cavity_number = ?, start_time = ?, end_time = ?,
                        {phase_set_clauses},
                        updated_at = ?,
                        version = version + 1
                    WHERE id = ?
                    """,
                    params,
                )
                if cursor.rowcount == 0:
                    raise ValueError(f"Record {record_id} not found")
            return record_id

    def get_record(self, record_id: int) -> CommissioningRecord | None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM commissioning_records WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self.row_to_record(row, cursor)

    def get_record_with_version(
        self, record_id: int
    ) -> tuple[CommissioningRecord, int] | None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM commissioning_records WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self.row_to_record(row, cursor), int(row["version"])

    def row_to_record(self, row, cursor) -> CommissioningRecord:
        current_phase, overall_status, phase_status = self.load_workflow_state(
            cursor=cursor,
            record_id=int(row["id"]),
        )
        phase_data = {
            attr_name: self.deserialize_phase_data(row[attr_name], model_cls)
            for attr_name, model_cls in self.phase_data_models.items()
        }
        return CommissioningRecord(
            linac=int(row["linac"]),
            cryomodule=row["cryomodule"],
            cavity_number=int(row["cavity_number"]),
            start_time=datetime.fromisoformat(row["start_time"]),
            current_phase=current_phase,
            **phase_data,
            phase_history=[],
            phase_status=phase_status,
            end_time=(
                datetime.fromisoformat(row["end_time"])
                if row["end_time"]
                else None
            ),
            overall_status=overall_status,
        )

    def load_workflow_state(
        self,
        *,
        cursor,
        record_id: int,
    ) -> tuple[CommissioningPhase, str, dict[CommissioningPhase, PhaseStatus]]:
        cursor.execute(
            """
            SELECT id, status, current_phase
            FROM commissioning_runs
            WHERE record_id = ?
            """,
            (record_id,),
        )
        run = cursor.fetchone()
        cursor.execute(
            """
            SELECT phase, attempt_number, status
            FROM commissioning_phase_instances
            WHERE run_id = ?
            ORDER BY attempt_number ASC, id ASC
            """,
            (run["id"],) if run is not None else (-1,),
        )
        return build_workflow_state(run, cursor.fetchall())
