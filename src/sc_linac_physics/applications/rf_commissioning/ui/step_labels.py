"""Human-readable labels for frequency tuning phase steps.

Deliberately dependency-free (no imports at all). This lives outside the
controller because PhaseDisplayBase._on_step_progress() needs a label on every
progress update, and it previously got one by importing
frequency_tuning_controller inside that call — so a shared base class reached
into one phase's controller for a private helper, on a hot path, once per tick.

Note on a rationale that does not hold: that import also pulls in
utils.sc_linac.linac, which builds a Machine at module scope, but it is not the
cause of a first-tick stall. ui/__init__ imports the displays, which import the
controller, so the Machine is already built by the time any display exists.
The reason to move this is the dependency direction and the per-call import,
not the Machine build.
"""

STEP_LABELS: dict[str, str] = {
    "verify_initial_state": "Verifying cavity state",
    "record_cold_landing": "Recording cold landing frequency",
    "check_state_for_stage_2": "Checking prerequisites",
    "probe_stepper_direction": "Probing stepper direction",
    "check_state_for_stage_3": "Checking prerequisites",
    "apply_hz_per_step": "Applying Hz/step calibration",
    "tune_to_resonance": "Tuning to resonance",
    "check_state_for_stage_4": "Checking prerequisites",
    "measure_pi_modes": "Measuring pi modes",
    "record_results": "Saving results",
}


def step_label(step_name: str) -> str:
    """Return a display label for a step, falling back to a title-cased name."""
    return STEP_LABELS.get(step_name, step_name.replace("_", " ").title())
