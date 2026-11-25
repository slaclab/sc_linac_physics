"""Ask Rerun or Skip for each stale result Cavity.setup_rf would re-run.

Shared by the piezo with RF and MP processing tabs. Both phases'
verify_initial_state returns, for the SSA calibration and the
characterization, the last run's time, whether it ended Good/Complete, and
whether it is recent (cavity_setup.RECENT_RESULT_SECONDS, 1 h). setup_rf
then reads context.parameters["rerun_ssa_calibration"] and
["rerun_characterization"]; a missing answer means re-run.
"""

from collections.abc import Callable
from datetime import datetime

from PyQt5.QtWidgets import QMessageBox

# Stale results setup_rf would re-run: data key prefix, parameter, label, PV.
STALE_PROMPTS = (
    ("ssa_calibration", "rerun_ssa_calibration", "SSA calibration", "CALTS"),
    (
        "characterization",
        "rerun_characterization",
        "characterization",
        "PROBECALTS",
    ),
)

# label, PV, last run time, ended Good/Complete -> True, False or None.
AskRerun = Callable[[str, str, datetime | None, bool | None], bool | None]


def age_text(stamp: datetime | None, now: datetime | None = None) -> str:
    """'3 h 05 min' from a timestamp; 'unknown' without one."""
    if stamp is None:
        return "unknown"
    minutes = int(((now or datetime.now()) - stamp).total_seconds() // 60)
    return f"{minutes // 60} h {minutes % 60:02d} min"


def ask_rerun(
    parent, label: str, pv: str, stamp: datetime | None, good: bool | None
) -> bool | None:
    """Rerun (True), Skip (False) or closed (None) for one stale result."""
    why = (
        f"is {age_text(stamp)} old (over 1 h)"
        if good
        else "did not finish Good/Complete"
    )
    when = f"{stamp:%Y-%m-%d %H:%M}" if stamp else "unknown"
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(f"{label[0].upper()}{label[1:]} is stale")
    box.setText(f"The last {label} {why}.")
    box.setInformativeText(
        f"Last run: {when} ({pv}).\n\n"
        f"Rerun: setup_rf re-runs the {label}.\n"
        "Skip: keep the values already on the machine; the record "
        "notes that you skipped it."
    )
    rerun = box.addButton("Rerun", QMessageBox.AcceptRole)
    skip = box.addButton("Skip", QMessageBox.RejectRole)
    box.addButton(QMessageBox.Cancel)
    box.exec_()
    clicked = box.clickedButton()
    if clicked is rerun:
        return True
    if clicked is skip:
        return False
    return None


def ask_about_stale_results(
    ask: AskRerun,
    parameters: dict,
    data: dict,
    log: Callable[[str], None],
) -> bool:
    """One prompt per stale result in data. False if the operator cancelled.

    data is verify_initial_state's data. Each answer goes in parameters
    under the name setup_rf reads. A recent result is not asked about and
    gets no parameter.
    """
    for key, param, label, pv in STALE_PROMPTS:
        if data.get(f"{key}_recent", True):
            continue
        good = data.get(f"{key}_good", data.get(f"{key}_complete"))
        answer = ask(label, pv, data.get(f"{key}_time"), good)
        if answer is None:
            return False
        parameters[param] = answer
        log(f"{label}: operator chose {'Rerun' if answer else 'Skip'}")
    return True
