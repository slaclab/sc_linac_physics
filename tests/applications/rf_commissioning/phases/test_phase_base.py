"""Tests for shared PhaseBase retry behavior."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseBase,
    PhaseContext,
    PhaseResult,
    PhaseStepResult,
)


class _RetryBehaviorPhase(PhaseBase):
    def __init__(self, context: PhaseContext, outcomes, sleep_calls):
        super().__init__(context=context, sleep_fn=sleep_calls.append)
        self._outcomes = list(outcomes)

    @property
    def phase_type(self) -> CommissioningPhase:
        return CommissioningPhase.PIEZO_PRE_RF

    def validate_prerequisites(self) -> tuple[bool, str]:
        return True, "ok"

    def get_phase_steps(self) -> list[str]:
        return ["single_step"]

    def execute_step(self, step_name: str) -> PhaseStepResult:
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def finalize_phase(self) -> None:
        return None


def _new_context() -> PhaseContext:
    return PhaseContext(
        record=CommissioningRecord(linac=1, cryomodule="02", cavity_number=1),
        operator="tester",
    )


def test_retry_result_honors_retry_delay_seconds():
    sleep_calls = []
    phase = _RetryBehaviorPhase(
        context=_new_context(),
        outcomes=[
            PhaseStepResult(
                result=PhaseResult.RETRY,
                message="temporary issue",
                retry_delay_seconds=1.25,
            ),
            PhaseStepResult(result=PhaseResult.SUCCESS, message="done"),
        ],
        sleep_calls=sleep_calls,
    )

    assert phase.run() is True
    assert sleep_calls == [1.25]


def test_exception_retry_uses_default_backoff_delay():
    sleep_calls = []
    phase = _RetryBehaviorPhase(
        context=_new_context(),
        outcomes=[
            RuntimeError("transient failure"),
            PhaseStepResult(result=PhaseResult.SUCCESS, message="done"),
        ],
        sleep_calls=sleep_calls,
    )

    assert phase.run() is True
    assert sleep_calls == [5.0]
