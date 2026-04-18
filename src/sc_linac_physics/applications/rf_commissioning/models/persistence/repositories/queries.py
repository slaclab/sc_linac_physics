"""Query helpers for commissioning database browsing and workflow metadata."""

from __future__ import annotations

import json
import logging

from sc_linac_physics.applications.rf_commissioning.models.persistence.database_errors import (
    RecordDeletionDisabledError,
)

from .base import BaseRepository

logger = logging.getLogger(__name__)


class QueryRepository(BaseRepository):
    """Read/query operations for cavity commissioning sessions."""

    def get_record_by_cavity(
        self,
        linac: int,
        cryomodule: str,
        cavity_number: str,
        active_only: bool = True,
    ):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT r.*
                FROM commissioning_records r
                LEFT JOIN commissioning_runs w ON w.record_id = r.id
                WHERE r.linac = ? AND r.cryomodule = ? AND r.cavity_number = ?
            """
            params = [str(linac), cryomodule, cavity_number]
            if active_only:
                query += " AND w.status = 'in_progress'"
            query += (
                " ORDER BY COALESCE(w.updated_at, r.updated_at, r.start_time) DESC, "
                "r.id DESC LIMIT 1"
            )
            cursor.execute(query, params)
            row = cursor.fetchone()
            if row is None:
                return None
            return self.db._records.row_to_record(row, cursor)

    def get_records_by_cryomodule(
        self, cryomodule: str, active_only: bool = False
    ) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT r.*
                FROM commissioning_records r
                LEFT JOIN commissioning_runs w ON w.record_id = r.id
                WHERE r.cryomodule = ?
            """
            params = [cryomodule]
            if active_only:
                query += " AND w.status = 'in_progress'"
            query += (
                " ORDER BY COALESCE(w.updated_at, r.updated_at, r.start_time) DESC, "
                "r.id DESC"
            )
            cursor.execute(query, params)
            return [
                self.db._records.row_to_record(row, cursor)
                for row in cursor.fetchall()
            ]

    def find_records_for_cavity(
        self, linac: int, cryomodule: str, cavity_number: str
    ) -> list[dict]:
        return self.get_record_summaries(
            where_clause="r.linac = ? AND r.cryomodule = ? AND r.cavity_number = ?",
            params=[str(linac), cryomodule, cavity_number],
        )

    def get_record_id_for_cavity(
        self, linac: int, cryomodule: str, cavity_number: str
    ) -> int | None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM commissioning_records
                WHERE linac = ? AND cryomodule = ? AND cavity_number = ?
                ORDER BY COALESCE(updated_at, start_time) DESC, id DESC
                LIMIT 1
                """,
                (str(linac), cryomodule, cavity_number),
            )
            row = cursor.fetchone()
            return None if row is None else int(row["id"])

    def get_active_record_id_for_cavity(
        self, linac: int, cryomodule: str, cavity_number: str
    ) -> int | None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM commissioning_records
                WHERE linac = ? AND cryomodule = ? AND cavity_number = ?
                  AND id IN (
                    SELECT record_id FROM commissioning_runs
                    WHERE status = 'in_progress'
                  )
                ORDER BY COALESCE(updated_at, start_time) DESC, id DESC
                LIMIT 1
                """,
                (str(linac), cryomodule, cavity_number),
            )
            row = cursor.fetchone()
            return None if row is None else int(row["id"])

    def get_record_summaries(
        self, where_clause: str = "", params: list | None = None
    ) -> list[dict]:
        params = params or []
        query = """
            SELECT r.id,
                   r.linac,
                   r.linac_number,
                   r.cryomodule,
                   r.cavity_number,
                   r.start_time,
                   r.end_time,
                   COALESCE(w.current_phase, 'piezo_pre_rf') AS current_phase,
                   COALESCE(w.status, 'not_started') AS overall_status,
                   COALESCE(w.updated_at, r.updated_at) AS updated_at,
                   r.piezo_pre_rf
            FROM commissioning_records r
            LEFT JOIN commissioning_runs w
                ON w.record_id = r.id
        """
        if where_clause:
            query += " WHERE " + where_clause
        query += " ORDER BY start_time DESC"

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        records: list[dict] = []
        for row in rows:
            record = {
                "id": row["id"],
                "linac": row["linac"] or "?",
                "linac_number": row["linac_number"],
                "cryomodule": row["cryomodule"] or "?",
                "cavity_number": row["cavity_number"] or "?",
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "current_phase": row["current_phase"],
                "overall_status": row["overall_status"],
                "updated_at": row["updated_at"],
            }
            if row["piezo_pre_rf"]:
                try:
                    data = json.loads(row["piezo_pre_rf"])
                    record["piezo_pre_rf"] = {
                        "channel_a_passed": data.get("channel_a_passed"),
                        "channel_b_passed": data.get("channel_b_passed"),
                        "capacitance_a": data.get("capacitance_a"),
                        "capacitance_b": data.get("capacitance_b"),
                    }
                except json.JSONDecodeError:
                    pass
            records.append(record)
        return records

    def get_all_records(self) -> list[dict]:
        try:
            return self.get_record_summaries()
        except Exception as exc:
            logger.exception("Error getting all records: %s", exc)
            return []

    def get_active_records(self) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*
                FROM commissioning_records r
                JOIN commissioning_runs w ON w.record_id = r.id
                WHERE w.status = 'in_progress'
                ORDER BY COALESCE(w.updated_at, r.updated_at, r.start_time) DESC, r.id DESC
                """)
            return [
                self.db._records.row_to_record(row, cursor)
                for row in cursor.fetchall()
            ]

    def delete_record(self, record_id: int) -> bool:
        raise RecordDeletionDisabledError(record_id)

    def get_database_stats(self) -> dict:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM commissioning_records")
            total = cursor.fetchone()[0]

            cursor.execute("""
                SELECT status, COUNT(*)
                FROM commissioning_runs
                GROUP BY status
                """)
            by_status = dict(cursor.fetchall())

            cursor.execute("""
                SELECT current_phase, COUNT(*)
                FROM commissioning_runs
                GROUP BY current_phase
                """)
            by_phase = dict(cursor.fetchall())

            cursor.execute("""
                SELECT cryomodule, COUNT(*)
                FROM commissioning_records
                GROUP BY cryomodule
                """)
            by_cryomodule = dict(cursor.fetchall())

        return {
            "total_records": total,
            "by_status": by_status,
            "by_phase": by_phase,
            "by_cryomodule": by_cryomodule,
        }

    def get_workflow_run(self, record_id: int) -> dict | None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, record_id, workflow_name, linac, cryomodule,
                       cavity_number, operator, status, current_phase,
                       created_at, updated_at
                FROM commissioning_runs
                WHERE record_id = ?
                """,
                (record_id,),
            )
            row = cursor.fetchone()
            return None if row is None else dict(row)

    def get_phase_instances(self, record_id: int) -> list[dict]:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT pi.id, pi.run_id, pi.phase, pi.attempt_number,
                       pi.status, pi.operator, pi.started_at, pi.ended_at,
                       pi.error_message, pi.created_at, pi.updated_at
                FROM commissioning_phase_instances pi
                JOIN commissioning_runs r ON r.id = pi.run_id
                WHERE r.record_id = ?
                ORDER BY pi.created_at ASC, pi.id ASC
                """,
                (record_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
