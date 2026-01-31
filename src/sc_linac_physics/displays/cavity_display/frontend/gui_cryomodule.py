from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QSizePolicy, QFrame

from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule

if TYPE_CHECKING:
    from sc_linac_physics.utils.sc_linac.linac import Linac


class GUICryomodule(Cryomodule):
    def __init__(self, cryo_name: str, linac_object: "Linac"):
        super().__init__(cryo_name, linac_object)

        self.vlayout = QVBoxLayout()
        self.vlayout.setSpacing(1)
        self.vlayout.setContentsMargins(3, 3, 3, 3)

        # CM name label - full width, centered
        self.label = QLabel(cryo_name)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            """
            font-weight: bold;
            font-size: 11pt;
            color: white;
            background-color: rgb(50, 50, 50);
            padding: 3px;
            border-radius: 3px;
        """
        )
        self.label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # Optional: Status indicator bar below name (subtle)
        self.status_bar = QFrame()
        self.status_bar.setFixedHeight(3)
        self.status_bar.setStyleSheet(
            "background-color: rgb(0, 255, 0);"
        )  # Green = OK

        self.vlayout.addWidget(self.label)
        self.vlayout.addWidget(self.status_bar)
        self.vlayout.addSpacing(2)

        print(f"Adding cavity widgets to cm{self.name}")
        for gui_cavity in self.cavities.values():
            self.vlayout.addLayout(gui_cavity.vert_layout)

            # Connect to severity change signal
            gui_cavity.cavity_widget.severity_changed.connect(
                self.on_cavity_severity_changed
            )

        # Initial status update
        self.update_cm_status()

    def on_cavity_severity_changed(self, severity):
        """Slot called when any cavity severity changes"""
        print(f"CM{self.name}: Cavity severity changed to {severity}")
        self.update_cm_status()

    def update_cm_status(self):
        """Update cryomodule status bar based on cavity states"""
        alarm_count = 0
        warning_count = 0

        cavities = self.cavities
        if isinstance(cavities, dict):
            cavities = cavities.values()

        for cavity in cavities:
            severity = getattr(cavity.cavity_widget, "_last_severity", None)
            if severity == 2:
                alarm_count += 1
            elif severity == 1:
                warning_count += 1

        print(
            f"CM{self.name} status: {alarm_count} alarms, {warning_count} warnings"
        )

        # Update status bar color and tooltip
        if alarm_count > 0:
            self.status_bar.setStyleSheet("background-color: rgb(255, 0, 0);")
            tooltip = f"{alarm_count} ALARM{'S' if alarm_count != 1 else ''}"
            self.label.setStyleSheet(
                """
                font-weight: bold;
                font-size: 11pt;
                color: white;
                background-color: rgb(100, 0, 0);
                padding: 3px;
                border-radius: 3px;
            """
            )
        elif warning_count > 0:
            self.status_bar.setStyleSheet("background-color: rgb(255, 165, 0);")
            tooltip = (
                f"{warning_count} WARNING{'S' if warning_count != 1 else ''}"
            )
            self.label.setStyleSheet(
                """
                font-weight: bold;
                font-size: 11pt;
                color: white;
                background-color: rgb(150, 100, 0);
                padding: 3px;
                border-radius: 3px;
            """
            )
        else:
            self.status_bar.setStyleSheet("background-color: rgb(0, 255, 0);")
            tooltip = "All OK"
            self.label.setStyleSheet(
                """
                font-weight: bold;
                font-size: 11pt;
                color: white;
                background-color: rgb(50, 50, 50);
                padding: 3px;
                border-radius: 3px;
            """
            )

        self.label.setToolTip(tooltip)
        self.status_bar.setToolTip(tooltip)
