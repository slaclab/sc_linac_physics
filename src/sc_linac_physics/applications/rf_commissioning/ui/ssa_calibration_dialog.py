"""Ask whether to rerun an SSA calibration that is old or not Good.

Shared by the cavity char and frequency tuning displays. A good calibration
under an hour old (cavity_setup.RECENT_RESULT_SECONDS) is kept without
asking, so this only comes up for an older or bad one.
"""

from PyQt5.QtWidgets import QMessageBox


def ask_rerun_ssa_calibration(parent, last: str, before: str) -> str:
    """Return "rerun", "skip" or "cancel". Rerun is the default button.

    last is LastSetupResult.describe(); before names what follows the
    calibration, e.g. "characterizing". The caller records the operator's
    name when they choose Skip.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("SSA calibration is old")
    box.setText(
        f"The last {last}.\n\n"
        "Rerun calibrates the SSA and pushes the new slope before "
        f"{before}. Skip keeps the slope the SSA has now, and records your "
        "name on the result."
    )
    rerun = box.addButton("Rerun calibration", QMessageBox.AcceptRole)
    skip = box.addButton("Skip", QMessageBox.DestructiveRole)
    box.addButton(QMessageBox.Cancel)
    box.setDefaultButton(rerun)
    box.exec_()
    clicked = box.clickedButton()
    if clicked is rerun:
        return "rerun"
    if clicked is skip:
        return "skip"
    return "cancel"
