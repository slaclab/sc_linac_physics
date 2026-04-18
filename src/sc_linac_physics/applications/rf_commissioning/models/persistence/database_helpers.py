"""Shared helpers for RF commissioning database code."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    PhaseStatus,
)

STATUS_MAP: dict[str, PhaseStatus] = {
    "not_started": PhaseStatus.NOT_STARTED,
    "in_progress": PhaseStatus.IN_PROGRESS,
    "complete": PhaseStatus.COMPLETE,
    "failed": PhaseStatus.FAILED,
    "skipped": PhaseStatus.SKIPPED,
}


def now_iso() -> str:
    """Return the current wall-clock timestamp in ISO format."""
    return datetime.now().isoformat()


def dumps_json(value: Any) -> str:
    """Serialize a Python value to JSON."""
    return json.dumps(value)


def serialize_measurement_data(measurement_data: Any) -> str:
    """Serialize measurement payloads, supporting model objects."""
    if hasattr(measurement_data, "to_dict"):
        measurement_data = measurement_data.to_dict()
    return dumps_json(measurement_data)


def parse_json_list(payload: str | None) -> list[dict]:
    """Return a JSON list payload, tolerating missing or legacy values."""
    if not payload:
        return []

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []
    return parsed


def build_note_entry(
    *,
    operator: str | None,
    note: str,
    timestamp: str | None = None,
    edited_at: str | None = None,
) -> dict[str, str | None]:
    """Build a canonical note payload."""
    entry: dict[str, str | None] = {
        "timestamp": timestamp or now_iso(),
        "operator": operator,
        "note": note,
    }
    if edited_at is not None:
        entry["edited_at"] = edited_at
    return entry


def append_note(
    notes: list[dict],
    *,
    operator: str | None,
    note: str,
    timestamp: str | None = None,
) -> list[dict]:
    """Return notes with a new note appended."""
    return [
        *notes,
        build_note_entry(operator=operator, note=note, timestamp=timestamp),
    ]


def update_note(
    notes: list[dict],
    *,
    note_index: int,
    operator: str | None,
    note: str,
    timestamp: str | None = None,
) -> list[dict] | None:
    """Return notes with one entry replaced, or None if index is invalid."""
    if note_index < 0 or note_index >= len(notes):
        return None

    stamp = timestamp or now_iso()
    updated = list(notes)
    updated[note_index] = build_note_entry(
        operator=operator,
        note=note,
        timestamp=stamp,
        edited_at=stamp,
    )
    return updated


def coerce_phase(value: str | CommissioningPhase | None) -> CommissioningPhase:
    """Convert stored phase values to a known enum value."""
    if isinstance(value, CommissioningPhase):
        return value

    try:
        return CommissioningPhase(str(value))
    except ValueError:
        return CommissioningPhase.PIEZO_PRE_RF


def empty_phase_status_map() -> dict[CommissioningPhase, PhaseStatus]:
    """Return a phase-status map initialized to not-started."""
    return {
        phase: PhaseStatus.NOT_STARTED
        for phase in CommissioningPhase.get_phase_order()
    }


def build_workflow_state(
    run: Mapping[str, Any] | None,
    phase_rows: Iterable[Mapping[str, Any]],
) -> tuple[CommissioningPhase, str, dict[CommissioningPhase, PhaseStatus]]:
    """Project normalized workflow rows into UI-friendly workflow state."""
    phase_status = empty_phase_status_map()

    if run is None:
        phase_status[CommissioningPhase.PIEZO_PRE_RF] = PhaseStatus.IN_PROGRESS
        return CommissioningPhase.PIEZO_PRE_RF, "not_started", phase_status

    current_phase = coerce_phase(run["current_phase"])
    overall_status = str(run["status"] or "not_started")

    latest_by_phase: dict[CommissioningPhase, tuple[int, str]] = {}
    for phase_row in phase_rows:
        try:
            phase = CommissioningPhase(str(phase_row["phase"]))
        except ValueError:
            continue

        attempt = int(phase_row["attempt_number"])
        previous = latest_by_phase.get(phase)
        if previous is None or attempt >= previous[0]:
            latest_by_phase[phase] = (attempt, str(phase_row["status"]))

    for phase, (_, status) in latest_by_phase.items():
        phase_status[phase] = STATUS_MAP.get(status, PhaseStatus.NOT_STARTED)

    if overall_status == "in_progress" and not latest_by_phase:
        phase_status[current_phase] = PhaseStatus.IN_PROGRESS

    return current_phase, overall_status, phase_status
