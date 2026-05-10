"""Repositories for cryomodule checkout records."""

from __future__ import annotations

import json
from datetime import datetime

from sc_linac_physics.applications.rf_commissioning.models.cryomodule_models import (
    CryomoduleCheckoutRecord,
    CryomodulePhase,
    CryomodulePhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database_helpers import (
    now_iso,
)

from .base import BaseRepository


class CryomoduleRepository(BaseRepository):
    """Persistence for cryomodule-scoped checkout rows."""

    def save_cryomodule_record(
        self,
        record: CryomoduleCheckoutRecord,
        record_id: int | None = None,
        expected_version: int | None = None,
    ) -> int:
        now = now_iso()
        phase_status_json = json.dumps(
            {
                phase.value: status.value
                for phase, status in record.phase_status.items()
            }
        )
        cm_phase_data_json = {
            attr_name: self.serialize_phase_data(getattr(record, attr_name))
            for attr_name in self.cryomodule_phase_data_models
        }

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cm_col_names = list(self.cryomodule_phase_data_models.keys())
            cm_values = [cm_phase_data_json[col] for col in cm_col_names]

            if record_id is None:
                cm_col_list = ", ".join(cm_col_names)
                cm_placeholders = ", ".join("?" * len(cm_col_names))
                cursor.execute(
                    f"""
                    INSERT INTO cryomodule_records (
                        linac, cryomodule, start_time, end_time,
                        {cm_col_list},
                        phase_status,
                        created_at, updated_at, notes
                    ) VALUES (?, ?, ?, ?, {cm_placeholders}, ?, ?, ?, ?)
                    """,
                    (
                        record.linac,
                        record.cryomodule,
                        record.start_time.isoformat(),
                        (
                            record.end_time.isoformat()
                            if record.end_time
                            else None
                        ),
                        *cm_values,
                        phase_status_json,
                        now,
                        now,
                        record.notes,
                    ),
                )
                return int(cursor.lastrowid)

            cm_set_clauses = ", ".join(f"{col} = ?" for col in cm_col_names)
            params = (
                record.linac,
                record.cryomodule,
                record.start_time.isoformat(),
                record.end_time.isoformat() if record.end_time else None,
                *cm_values,
                phase_status_json,
                now,
                record.notes,
                record_id,
            )
            if expected_version is not None:
                cursor.execute(
                    f"""
                    UPDATE cryomodule_records SET
                        linac = ?, cryomodule = ?, start_time = ?, end_time = ?,
                        {cm_set_clauses},
                        phase_status = ?,
                        updated_at = ?, notes = ?,
                        version = version + 1
                    WHERE id = ? AND version = ?
                    """,
                    (*params, expected_version),
                )
                if cursor.rowcount == 0:
                    self.raise_conflict_error(
                        cursor=cursor,
                        table_name="cryomodule_records",
                        row_id=record_id,
                        expected_version=expected_version,
                        missing_message=f"CM record {record_id} not found",
                    )
            else:
                cursor.execute(
                    f"""
                    UPDATE cryomodule_records SET
                        linac = ?, cryomodule = ?, start_time = ?, end_time = ?,
                        {cm_set_clauses},
                        phase_status = ?,
                        updated_at = ?, notes = ?,
                        version = version + 1
                    WHERE id = ?
                    """,
                    params,
                )
                if cursor.rowcount == 0:
                    raise ValueError(f"CM record {record_id} not found")
            return record_id

    def get_cryomodule_record(self, linac: str, cryomodule: str):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cryomodule_records WHERE linac = ? AND cryomodule = ?",
                (linac, cryomodule),
            )
            row = cursor.fetchone()
            return None if row is None else self.cm_row_to_record(row)

    def get_cryomodule_record_with_version(
        self, linac: str, cryomodule: str
    ) -> tuple[CryomoduleCheckoutRecord, int] | None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cryomodule_records WHERE linac = ? AND cryomodule = ?",
                (linac, cryomodule),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self.cm_row_to_record(row), int(row["version"])

    def get_cryomodule_record_id(
        self, linac: str, cryomodule: str
    ) -> int | None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM cryomodule_records
                WHERE linac = ? AND cryomodule = ?
                ORDER BY COALESCE(updated_at, start_time) DESC, id DESC
                LIMIT 1
                """,
                (linac, cryomodule),
            )
            row = cursor.fetchone()
            return None if row is None else int(row["id"])

    def cm_row_to_record(self, row) -> CryomoduleCheckoutRecord:
        phase_status = {
            CryomodulePhase(phase): CryomodulePhaseStatus(status)
            for phase, status in json.loads(row["phase_status"]).items()
        }
        cm_phase_data = {
            attr_name: self.deserialize_phase_data(row[attr_name], model_cls)
            for attr_name, model_cls in self.cryomodule_phase_data_models.items()
        }
        return CryomoduleCheckoutRecord(
            linac=row["linac"],
            cryomodule=row["cryomodule"],
            start_time=datetime.fromisoformat(row["start_time"]),
            **cm_phase_data,
            phase_status=phase_status,
            end_time=(
                datetime.fromisoformat(row["end_time"])
                if row["end_time"]
                else None
            ),
            notes=row["notes"],
        )
