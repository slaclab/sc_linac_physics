from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from edmbutton import PyDMEDMDisplayButton
from lcls_tools.common.frontend.display.util import ERROR_STYLESHEET
from pydm.widgets import PyDMLabel
from pydm.widgets import analog_indicator
from pydm.widgets.display_format import DisplayFormat

from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings

_SETUP_STYLE = "background-color: #1e5799; color: white;"


class CavityPanel(QWidget):
    """Inline per-cryomodule cavity grid.

    Columns: C# | ACON | AACT | Status + Note | Progress | Set Up | Turn Off | Abort | EDM
    Embedded directly in the CM section (not a popup).
    """

    def __init__(
        self,
        cm_name: str,
        linac_idx: int,
        settings: Settings,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self._cm_name = cm_name
        self._settings = settings

        outer = QVBoxLayout()
        outer.setContentsMargins(16, 4, 8, 8)
        self.setLayout(outer)

        grid = QGridLayout()
        grid.setSpacing(6)

        for col, text in enumerate(
            ["", "ACON", "AACT", "Status / Note", "Progress", "", "", "", ""]
        ):
            if text:
                lbl = QLabel(text)
                lbl.setStyleSheet(
                    "font-weight: bold; color: #aaaaaa; font-size: 11px;"
                )
                grid.addWidget(lbl, 0, col)

        for cav_num in range(1, 9):
            row = cav_num
            prefix = f"ACCL:L{linac_idx}B:{cm_name}{cav_num}0:"
            cavity = SETUP_MACHINE.cryomodules[cm_name].cavities[cav_num]

            num_lbl = QLabel(f"C{cav_num}")
            num_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            num_lbl.setStyleSheet("color: #aaaaaa;")
            grid.addWidget(num_lbl, row, 0)

            acon = PyDMLabel(init_channel=prefix + "ACON")
            acon.alarmSensitiveContent = True
            acon.alarmSensitiveBorder = True
            acon.showUnits = True
            acon.precisionFromPV = False
            acon.precision = 1
            acon.setMinimumWidth(60)
            grid.addWidget(acon, row, 1)

            aact = PyDMLabel(init_channel=prefix + "AACTMEAN")
            aact.alarmSensitiveContent = True
            aact.alarmSensitiveBorder = True
            aact.showUnits = True
            aact.precisionFromPV = False
            aact.precision = 1
            aact.setMinimumWidth(60)
            grid.addWidget(aact, row, 2)

            # Status and note stacked in one cell to keep grid width manageable
            info = QWidget()
            info_layout = QVBoxLayout()
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(1)
            info.setLayout(info_layout)

            status = PyDMLabel(init_channel=cavity.status_msg_pv)
            status.displayFormat = DisplayFormat.String
            status.alarmSensitiveContent = True
            status.alarmSensitiveBorder = True
            info_layout.addWidget(status)

            note = PyDMLabel(init_channel=cavity.note_pv)
            note.displayFormat = DisplayFormat.String
            note.alarmSensitiveContent = True
            note.alarmSensitiveBorder = True
            note.setStyleSheet("color: #aaaaaa; font-size: 11px;")
            info_layout.addWidget(note)

            grid.addWidget(info, row, 3)

            progress = analog_indicator.PyDMAnalogIndicator(
                init_channel=cavity.progress_pv
            )
            progress.backgroundSizeRate = 0.2
            progress.setFixedWidth(80)
            progress.setFixedHeight(24)
            grid.addWidget(progress, row, 4)

            setup_btn = QPushButton("Set Up")
            setup_btn.setStyleSheet(_SETUP_STYLE)
            setup_btn.clicked.connect(
                lambda checked=False, c=cavity: self._trigger_setup(c)
            )
            grid.addWidget(setup_btn, row, 5)

            off_btn = QPushButton("Turn Off")
            off_btn.clicked.connect(
                lambda checked=False, c=cavity: c.trigger_shutdown()
            )
            grid.addWidget(off_btn, row, 6)

            abort_btn = QPushButton("Abort")
            abort_btn.setStyleSheet(ERROR_STYLESHEET)
            abort_btn.clicked.connect(
                lambda checked=False, c=cavity: c.trigger_abort()
            )
            grid.addWidget(abort_btn, row, 7)

            edm_btn = PyDMEDMDisplayButton()
            edm_btn.filenames = ["$EDM/llrf/rf_srf_cavity_main.edl"]
            edm_btn.macros = cavity.edm_macro_string + ",SELTAB=0,SELCHAR=3"
            edm_btn.setToolTip("EDM expert screens")
            grid.addWidget(edm_btn, row, 8)

        grid.setColumnStretch(3, 1)
        outer.addLayout(grid)

    def _trigger_setup(self, cavity) -> None:
        if cavity.script_is_running or not cavity.is_online:
            return
        cavity.ssa_cal_requested = self._settings.ssa_cal_checkbox.isChecked()
        cavity.auto_tune_requested = (
            self._settings.auto_tune_checkbox.isChecked()
        )
        cavity.cav_char_requested = self._settings.cav_char_checkbox.isChecked()
        cavity.rf_ramp_requested = self._settings.rf_ramp_checkbox.isChecked()
        cavity.trigger_start()
