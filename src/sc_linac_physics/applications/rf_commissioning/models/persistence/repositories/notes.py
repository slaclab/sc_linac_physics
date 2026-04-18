"""Repositories for commissioning general notes."""

from __future__ import annotations

from sc_linac_physics.applications.rf_commissioning.models.persistence.database_errors import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database_helpers import (
    append_note,
    now_iso,
    parse_json_list,
    update_note,
)

from .base import BaseRepository


class NotesRepository(BaseRepository):
    """Persistence for record-level general notes."""

    def get_general_notes(self, record_id: int) -> list[dict]:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT general_notes FROM commissioning_records WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            return [] if row is None else parse_json_list(row[0])

    def append_general_note(
        self,
        record_id: int,
        operator: str | None,
        note: str,
        expected_version: int | None = None,
    ) -> bool:
        now = now_iso()
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT general_notes, version FROM commissioning_records WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return False
            current_version = row["version"]
            if (
                expected_version is not None
                and current_version != expected_version
            ):
                raise RecordConflictError(
                    record_id, expected_version, current_version
                )

            notes_list = append_note(
                parse_json_list(row[0]),
                operator=operator,
                note=note,
                timestamp=now,
            )
            return self.update_versioned_json_list(
                cursor=cursor,
                table_name="commissioning_records",
                row_id=record_id,
                column_name="general_notes",
                payload=notes_list,
                updated_at=now,
                expected_version=expected_version,
                missing_message=f"Record {record_id} not found",
            )

    def update_general_note(
        self,
        record_id: int,
        note_index: int,
        operator: str | None,
        note: str,
        expected_version: int | None = None,
    ) -> bool:
        now = now_iso()
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT general_notes, version FROM commissioning_records WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return False
            current_version = row["version"]
            if (
                expected_version is not None
                and current_version != expected_version
            ):
                raise RecordConflictError(
                    record_id, expected_version, current_version
                )

            notes_list = update_note(
                parse_json_list(row[0]),
                note_index=note_index,
                operator=operator,
                note=note,
                timestamp=now,
            )
            if notes_list is None:
                return False
            return self.update_versioned_json_list(
                cursor=cursor,
                table_name="commissioning_records",
                row_id=record_id,
                column_name="general_notes",
                payload=notes_list,
                updated_at=now,
                expected_version=expected_version,
                missing_message=f"Record {record_id} not found",
            )
