"""Repositories for measurement history and measurement notes."""

from __future__ import annotations

import json

from sc_linac_physics.applications.rf_commissioning.models.persistence.database_helpers import (
    append_note,
    dumps_json,
    now_iso,
    parse_json_list,
    serialize_measurement_data,
    update_note,
)

from .base import BaseRepository


class MeasurementRepository(BaseRepository):
    """Persistence for measurement history rows."""

    def add_measurement_history(
        self,
        record_id: int,
        phase,
        measurement_data,
        operator: str | None = None,
        notes: str | None = None,
        phase_instance_id: int | None = None,
    ) -> int:
        now = now_iso()
        data_json = serialize_measurement_data(measurement_data)
        notes_payload = (
            append_note([], operator=operator, note=notes, timestamp=now)
            if notes
            else []
        )
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO measurement_history (
                    record_id, phase_instance_id, phase, timestamp, operator, measurement_data, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    phase_instance_id,
                    phase.value,
                    now,
                    operator,
                    data_json,
                    dumps_json(notes_payload),
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def get_measurement_history(
        self,
        record_id: int,
        phase=None,
    ) -> list[dict]:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            if phase:
                cursor.execute(
                    """
                    SELECT * FROM measurement_history
                    WHERE record_id = ? AND phase = ?
                    ORDER BY timestamp DESC
                    """,
                    (record_id, phase.value),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM measurement_history
                    WHERE record_id = ?
                    ORDER BY timestamp DESC
                    """,
                    (record_id,),
                )

            history = []
            for row in cursor.fetchall():
                history.append(
                    {
                        "id": row["id"],
                        "phase_instance_id": row["phase_instance_id"],
                        "phase": row["phase"],
                        "timestamp": row["timestamp"],
                        "operator": row["operator"],
                        "notes": parse_json_list(row["notes"]),
                        "measurement_data": json.loads(row["measurement_data"]),
                    }
                )
            return history

    def get_measurement_notes(self, record_id: int, phase=None) -> list[dict]:
        history = self.get_measurement_history(record_id, phase)
        notes = []
        for entry in history:
            for index, note_item in enumerate(entry.get("notes") or []):
                notes.append(
                    {
                        "entry_id": entry["id"],
                        "note_index": index,
                        "phase": entry["phase"],
                        "measurement_timestamp": entry.get("timestamp"),
                        "timestamp": note_item.get("timestamp"),
                        "operator": note_item.get("operator"),
                        "note": note_item.get("note", ""),
                    }
                )

        return sorted(
            notes,
            key=lambda item: item.get("timestamp")
            or item.get("measurement_timestamp")
            or "",
            reverse=True,
        )

    def append_measurement_note(
        self,
        entry_id: int,
        operator: str | None,
        note: str,
    ) -> bool:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT notes FROM measurement_history WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return False

            notes_list = append_note(
                parse_json_list(row[0]),
                operator=operator,
                note=note,
            )
            cursor.execute(
                "UPDATE measurement_history SET notes = ? WHERE id = ?",
                (dumps_json(notes_list), entry_id),
            )
            return cursor.rowcount > 0

    def update_measurement_note(
        self,
        entry_id: int,
        note_index: int,
        operator: str | None,
        note: str,
    ) -> bool:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT notes FROM measurement_history WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return False

            notes_list = update_note(
                parse_json_list(row[0]),
                note_index=note_index,
                operator=operator,
                note=note,
            )
            if notes_list is None:
                return False

            cursor.execute(
                "UPDATE measurement_history SET notes = ? WHERE id = ?",
                (dumps_json(notes_list), entry_id),
            )
            return cursor.rowcount > 0
