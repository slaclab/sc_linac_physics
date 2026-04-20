"""SQLite database interface for RF commissioning records."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sc_linac_physics.applications.rf_commissioning.models.cryomodule_models import (
    CRYOMODULE_PHASE_REGISTRY,
    CryomoduleCheckoutRecord,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PHASE_REGISTRY,
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database_errors import (
    RecordDeletionDisabledError,
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database_schema import (
    initialize_database_schema,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.repositories import (
    CryomoduleRepository,
    MeasurementRepository,
    NotesRepository,
    OperatorRepository,
    QueryRepository,
    RecordRepository,
)

__all__ = [
    "CommissioningDatabase",
    "RecordConflictError",
    "RecordDeletionDisabledError",
]


class CommissioningDatabase:
    """SQLite database manager for commissioning records.

    Maintains one canonical commissioning record per cavity coordinate
    (linac, cryomodule, cavity). Historical execution data is stored in
    normalized workflow/measurement tables.
    """

    PHASE_DATA_MODELS: dict[str, type] = {
        reg.record_attr: reg.data_model
        for reg in PHASE_REGISTRY.values()
        if reg.record_attr and reg.data_model
    }
    CRYOMODULE_PHASE_DATA_MODELS: dict[str, type] = {
        reg.record_attr: reg.data_model
        for reg in CRYOMODULE_PHASE_REGISTRY.values()
        if reg.record_attr and reg.data_model
    }

    def __init__(self, db_path: str = "commissioning.db"):
        self.db_path = Path(db_path)
        self._records: RecordRepository = RecordRepository(self)
        self._queries: QueryRepository = QueryRepository(self)
        self._measurements: MeasurementRepository = MeasurementRepository(self)
        self._notes: NotesRepository = NotesRepository(self)
        self._operators: OperatorRepository = OperatorRepository(self)
        self._cryomodules: CryomoduleRepository = CryomoduleRepository(self)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def connection(self):
        return self._get_connection()

    def initialize(self):
        with self._get_connection() as conn:
            initialize_database_schema(
                conn.cursor(),
                phase_column_names=self.PHASE_DATA_MODELS,
                cryomodule_phase_column_names=self.CRYOMODULE_PHASE_DATA_MODELS,
            )

    def save_record(
        self,
        record: CommissioningRecord,
        record_id: int | None = None,
        expected_version: int | None = None,
    ) -> int:
        return self._records.save_record(record, record_id, expected_version)

    def get_record(self, record_id: int) -> CommissioningRecord | None:
        return self._records.get_record(record_id)

    def get_record_with_version(
        self, record_id: int
    ) -> tuple[CommissioningRecord, int] | None:
        return self._records.get_record_with_version(record_id)

    def _row_to_record(self, row: sqlite3.Row, cursor: sqlite3.Cursor):
        return self._records.row_to_record(row, cursor)

    def _load_workflow_state(
        self,
        *,
        cursor: sqlite3.Cursor,
        record_id: int,
    ) -> tuple[CommissioningPhase, str, dict[CommissioningPhase, PhaseStatus]]:
        return self._records.load_workflow_state(
            cursor=cursor,
            record_id=record_id,
        )

    def get_record_by_cavity(
        self,
        linac: int,
        cryomodule: str,
        cavity_number: str,
        active_only: bool = True,
    ) -> CommissioningRecord | None:
        return self._queries.get_record_by_cavity(
            linac,
            cryomodule,
            cavity_number,
            active_only,
        )

    def get_records_by_cryomodule(
        self, cryomodule: str, active_only: bool = False
    ) -> list[CommissioningRecord]:
        return self._queries.get_records_by_cryomodule(
            cryomodule,
            active_only,
        )

    def find_records_for_cavity(
        self, linac: int, cryomodule: str, cavity_number: str
    ) -> list[dict]:
        return self._queries.find_records_for_cavity(
            linac,
            cryomodule,
            cavity_number,
        )

    def get_record_id_for_cavity(
        self, linac: int, cryomodule: str, cavity_number: str
    ) -> int | None:
        return self._queries.get_record_id_for_cavity(
            linac,
            cryomodule,
            cavity_number,
        )

    def get_active_record_id_for_cavity(
        self, linac: int, cryomodule: str, cavity_number: str
    ) -> int | None:
        return self._queries.get_active_record_id_for_cavity(
            linac,
            cryomodule,
            cavity_number,
        )

    def get_cryomodule_record_id(
        self, linac: str, cryomodule: str
    ) -> int | None:
        return self._cryomodules.get_cryomodule_record_id(linac, cryomodule)

    def _get_record_summaries(
        self, where_clause: str = "", params: list | None = None
    ) -> list[dict]:
        return self._queries.get_record_summaries(where_clause, params)

    def get_all_records(self) -> list[dict]:
        return self._queries.get_all_records()

    def get_active_records(self) -> list[CommissioningRecord]:
        return self._queries.get_active_records()

    def delete_record(self, record_id: int) -> bool:
        raise RecordDeletionDisabledError(record_id)

    def get_database_stats(self) -> dict:
        return self._queries.get_database_stats()

    def add_measurement_history(
        self,
        record_id: int,
        phase: CommissioningPhase,
        measurement_data,
        operator: str | None = None,
        notes: str | None = None,
        phase_instance_id: int | None = None,
    ) -> int:
        return self._measurements.add_measurement_history(
            record_id,
            phase,
            measurement_data,
            operator,
            notes,
            phase_instance_id,
        )

    def get_workflow_run(self, record_id: int) -> dict | None:
        return self._queries.get_workflow_run(record_id)

    def get_phase_instances(self, record_id: int) -> list[dict]:
        return self._queries.get_phase_instances(record_id)

    def get_operators(self) -> list[str]:
        return self._operators.get_operators()

    def add_operator(self, name: str) -> bool:
        return self._operators.add_operator(name)

    def get_measurement_history(
        self,
        record_id: int,
        phase: CommissioningPhase | None = None,
    ) -> list[dict]:
        return self._measurements.get_measurement_history(record_id, phase)

    def get_measurement_notes(
        self,
        record_id: int,
        phase: CommissioningPhase | None = None,
    ) -> list[dict]:
        return self._measurements.get_measurement_notes(record_id, phase)

    def append_measurement_note(
        self,
        entry_id: int,
        operator: str | None,
        note: str,
    ) -> bool:
        return self._measurements.append_measurement_note(
            entry_id,
            operator,
            note,
        )

    def get_general_notes(self, record_id: int) -> list[dict]:
        return self._notes.get_general_notes(record_id)

    def append_general_note(
        self,
        record_id: int,
        operator: str | None,
        note: str,
        expected_version: int | None = None,
    ) -> bool:
        return self._notes.append_general_note(
            record_id,
            operator,
            note,
            expected_version,
        )

    def update_general_note(
        self,
        record_id: int,
        note_index: int,
        operator: str | None,
        note: str,
        expected_version: int | None = None,
    ) -> bool:
        return self._notes.update_general_note(
            record_id,
            note_index,
            operator,
            note,
            expected_version,
        )

    def update_measurement_note(
        self,
        entry_id: int,
        note_index: int,
        operator: str | None,
        note: str,
    ) -> bool:
        return self._measurements.update_measurement_note(
            entry_id,
            note_index,
            operator,
            note,
        )

    def save_cryomodule_record(
        self,
        record: CryomoduleCheckoutRecord,
        record_id: int | None = None,
        expected_version: int | None = None,
    ) -> int:
        return self._cryomodules.save_cryomodule_record(
            record,
            record_id,
            expected_version,
        )

    def get_cryomodule_record(
        self, linac: str, cryomodule: str
    ) -> CryomoduleCheckoutRecord | None:
        return self._cryomodules.get_cryomodule_record(linac, cryomodule)

    def get_cryomodule_record_with_version(
        self, linac: str, cryomodule: str
    ) -> tuple[CryomoduleCheckoutRecord, int] | None:
        return self._cryomodules.get_cryomodule_record_with_version(
            linac,
            cryomodule,
        )

    def _cm_row_to_record(self, row: sqlite3.Row) -> CryomoduleCheckoutRecord:
        return self._cryomodules.cm_row_to_record(row)
