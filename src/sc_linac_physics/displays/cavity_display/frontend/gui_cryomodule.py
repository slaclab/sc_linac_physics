from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QSizePolicy, QFrame

from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule

if TYPE_CHECKING:
    from sc_linac_physics.utils.sc_linac.linac import Linac


class GUICryomodule(Cryomodule):
    """GUI representation of a cryomodule with status indicators."""

    def __init__(self, cryo_name: str, linac_object: "Linac"):
        super().__init__(cryo_name, linac_object)

        # Build layout
        self.vlayout = QVBoxLayout()
        self.vlayout.setSpacing(0)
        self.vlayout.setContentsMargins(2, 2, 2, 2)

        # Add header
        self.label = self._create_header_label(cryo_name)
        self.status_bar = self._create_status_bar()

        self.vlayout.addWidget(self.label)
        self.vlayout.addWidget(self.status_bar)
        self.vlayout.addSpacing(1)

        # Add cavities
        for gui_cavity in self.cavities.values():
            self.vlayout.addLayout(gui_cavity.vert_layout)
            gui_cavity.cavity_widget.severity_changed.connect(
                self.on_cavity_severity_changed
            )

        # Initial status update
        self.update_cm_status()

    @property
    def pydm_macros(self):
        """
        Currenlty only used for NIRP fault, but I think we can just keep adding
        to this list
        :return:
        """
        return "AREA={linac_name},CM={cm_name},RFNAME=CM{cm_name}".format(
            linac_name=self.linac.name, cm_name=self.name
        )

    def _create_header_label(self, cryo_name):
        """Create the cryomodule name label."""
        label = QLabel(cryo_name)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 9pt;
                color: white;
                background-color: rgb(50, 50, 50);
                padding: 2px;
                border-radius: 2px;
            }
        """)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        label.setMinimumWidth(30)
        label.setMaximumHeight(20)
        label.setMinimumHeight(15)

        return label

    def _create_status_bar(self):
        """Create the status indicator bar."""
        status_bar = QFrame()
        status_bar.setFixedHeight(3)
        status_bar.setStyleSheet("background-color: rgb(0, 255, 0);")

        return status_bar

    def on_cavity_severity_changed(self, severity):
        """Handle cavity severity changes."""
        self.update_cm_status()

    def update_cm_status(self):
        """Update cryomodule status based on cavity states."""
        alarm_count, warning_count = self._count_cavity_issues()

        if alarm_count > 0:
            self._set_alarm_state(alarm_count)
        elif warning_count > 0:
            self._set_warning_state(warning_count)
        else:
            self._set_ok_state()

    def _count_cavity_issues(self):
        """Count alarms and warnings across all cavities."""
        alarm_count = 0
        warning_count = 0

        cavities = (
            self.cavities.values()
            if isinstance(self.cavities, dict)
            else self.cavities
        )

        for cavity in cavities:
            severity = getattr(cavity.cavity_widget, "_last_severity", None)
            if severity == 2:
                alarm_count += 1
            elif severity == 1:
                warning_count += 1

        return alarm_count, warning_count

    def _set_alarm_state(self, count):
        """Set visual state for alarm condition."""
        self.status_bar.setStyleSheet("background-color: rgb(255, 0, 0);")
        tooltip = f"{count} ALARM{'S' if count != 1 else ''}"

        self.label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 9pt;
                color: white;
                background-color: rgb(100, 0, 0);
                padding: 2px;
                border-radius: 2px;
            }
        """)

        self.label.setToolTip(tooltip)
        self.status_bar.setToolTip(tooltip)

    def _set_warning_state(self, count):
        """Set visual state for warning condition."""
        self.status_bar.setStyleSheet("background-color: rgb(255, 165, 0);")
        tooltip = f"{count} WARNING{'S' if count != 1 else ''}"

        self.label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 9pt;
                color: white;
                background-color: rgb(150, 100, 0);
                padding: 2px;
                border-radius: 2px;
            }
        """)

        self.label.setToolTip(tooltip)
        self.status_bar.setToolTip(tooltip)

    def _set_ok_state(self):
        """Set visual state for OK condition."""
        self.status_bar.setStyleSheet("background-color: rgb(0, 255, 0);")
        tooltip = "All OK"

        self.label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 9pt;
                color: white;
                background-color: rgb(50, 50, 50);
                padding: 2px;
                border-radius: 2px;
            }
        """)

        self.label.setToolTip(tooltip)
        self.status_bar.setToolTip(tooltip)
