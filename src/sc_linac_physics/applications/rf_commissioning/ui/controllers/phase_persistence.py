"""Database writes at the end of a phase, with a retry of only what failed.

Shared by the piezo with RF and MP processing controllers. Writes nothing to
the cavity.
"""

from collections.abc import Callable

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)

# In the order they are written.
FINISH_WRITES = ("complete", "save", "history")


def persist_finished_phase(
    session,
    phase: CommissioningPhase,
    phase_instance_id: int | None,
    data,
    operator: str,
    unsaved: set[str],
    log: Callable[[str], None],
) -> set[str]:
    """Run each write named in unsaved; return the ones that failed.

    "complete" closes the phase instance with data.to_dict() as its
    artifact, "save" saves the active record, and "history" adds data to
    the measurement history. A write whose call returns False or raises
    stays in the returned set, so the caller can keep the instance id and
    retry later. A missing instance id or data counts as done.
    """
    writes = {
        "complete": lambda: (
            phase_instance_id is None
            or session.complete_active_phase_instance(
                phase_instance_id=phase_instance_id,
                phase=phase,
                artifact_payload=data.to_dict() if data else None,
            )
        ),
        "save": session.save_active_record,
        "history": lambda: (
            data is None
            or session.add_measurement_to_history(
                phase,
                data,
                operator=operator,
                phase_instance_id=phase_instance_id,
            )
        ),
    }
    remaining = set(unsaved)
    for name in FINISH_WRITES:
        if name not in remaining:
            continue
        try:
            ok = writes[name]()
        except Exception as exc:
            log(f"Warning: {name} failed: {exc}")
            ok = False
        if ok:
            remaining.discard(name)
    return remaining
