"""Shared repository utilities for RF commissioning persistence."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from sc_linac_physics.applications.rf_commissioning.models.persistence.database_errors import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database_helpers import (
    dumps_json,
)
from sc_linac_physics.applications.rf_commissioning.models.serialization import (
    deserialize_model,
)

if TYPE_CHECKING:
    from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
        CommissioningDatabase,
    )


class BaseRepository:
    """Base repository with shared database helpers."""

    def __init__(self, db: "CommissioningDatabase"):
        self.db = db

    @property
    def phase_data_models(self) -> dict[str, type]:
        return self.db.PHASE_DATA_MODELS

    @property
    def cryomodule_phase_data_models(self) -> dict[str, type]:
        return self.db.CRYOMODULE_PHASE_DATA_MODELS

    @staticmethod
    def serialize_phase_data(phase_data) -> str | None:
        if phase_data is None:
            return None
        return json.dumps(phase_data.to_dict())

    @staticmethod
    def deserialize_phase_data(payload: str | None, model_cls):
        if not payload:
            return None
        return deserialize_model(model_cls, json.loads(payload))

    @staticmethod
    def raise_conflict_error(
        *,
        cursor: sqlite3.Cursor,
        table_name: str,
        row_id: int,
        expected_version: int,
        missing_message: str,
    ) -> None:
        cursor.execute(
            f"SELECT version FROM {table_name} WHERE id = ?",
            (row_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(missing_message)
        raise RecordConflictError(row_id, expected_version, int(row["version"]))

    def update_versioned_row(
        self,
        *,
        cursor: sqlite3.Cursor,
        table_name: str,
        row_id: int,
        set_clause: str,
        params: tuple,
        expected_version: int | None,
        missing_message: str,
    ) -> bool:
        """Run ``UPDATE table_name SET set_clause`` on one row, bumping version.

        With ``expected_version``, only a row at that version is updated. A
        miss raises ``RecordConflictError``, or ``ValueError`` if the row is
        gone. Without it, the row is updated whatever its version, and a miss
        returns False so the caller decides what a missing row means.
        """
        sql = (
            f"UPDATE {table_name} SET {set_clause}, version = version + 1 "
            "WHERE id = ?"
        )
        args = (*params, row_id)
        if expected_version is not None:
            sql += " AND version = ?"
            args = (*args, expected_version)
        cursor.execute(sql, args)
        if cursor.rowcount > 0:
            return True
        if expected_version is not None:
            self.raise_conflict_error(
                cursor=cursor,
                table_name=table_name,
                row_id=row_id,
                expected_version=expected_version,
                missing_message=missing_message,
            )
        return False

    def update_versioned_json_list(
        self,
        *,
        cursor: sqlite3.Cursor,
        table_name: str,
        row_id: int,
        column_name: str,
        payload: list[dict],
        updated_at: str,
        expected_version: int | None,
        missing_message: str,
    ) -> bool:
        return self.update_versioned_row(
            cursor=cursor,
            table_name=table_name,
            row_id=row_id,
            set_clause=f"{column_name} = ?, updated_at = ?",
            params=(dumps_json(payload), updated_at),
            expected_version=expected_version,
            missing_message=missing_message,
        )
