from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QComboBox,
)

if TYPE_CHECKING:
    from sc_linac_physics.displays.cavity_display.frontend.gui_machine import (
        GUIMachine,
    )


class AlarmSidebarWidget(QWidget):
    """
    Responsive sidebar widget that adapts to width.
    Shows full text when wide, compact symbols when narrow.
    """

    cavity_clicked = pyqtSignal(object)

    # Width thresholds for different display modes
    COMPACT_WIDTH = 150
    FULL_WIDTH = 250

    def __init__(self, gui_machine: "GUIMachine", parent=None):
        super().__init__(parent)
        self.gui_machine = gui_machine
        self.alarm_cavities = []
        self.warning_cavities = []
        self.display_mode = "full"  # "compact" or "full"

        self._setup_ui()
        self._start_refresh_timer()

        # Initial update
        self.update_alarm_list()

    def _setup_ui(self):
        """Setup the sidebar UI components"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Alarm count label
        self.alarm_count_label = QLabel("ALARMS: 0")
        self.alarm_count_label.setAlignment(Qt.AlignCenter)
        self.alarm_count_label.setStyleSheet(
            """
            font-size: 16pt;
            font-weight: bold;
            background-color: rgb(150, 0, 0);
            color: white;
            padding: 5px;
            border-radius: 3px;
        """
        )
        self.alarm_count_label.setWordWrap(True)
        self.alarm_count_label.setToolTip("Active Alarms")

        # Warning count label
        self.warning_count_label = QLabel("WARNINGS: 0")
        self.warning_count_label.setAlignment(Qt.AlignCenter)
        self.warning_count_label.setStyleSheet(
            """
            font-size: 14pt;
            font-weight: bold;
            background-color: rgb(255, 165, 0);
            color: black;
            padding: 4px;
            border-radius: 3px;
        """
        )
        self.warning_count_label.setWordWrap(True)
        self.warning_count_label.setToolTip("Active Warnings")

        # List of active issues
        self.alarm_list = QListWidget()
        self.alarm_list.setStyleSheet(
            """
            QListWidget {
                font-size: 10pt;
                background-color: rgb(40, 40, 40);
                border: 1px solid rgb(100, 100, 100);
                border-radius: 2px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid rgb(60, 60, 60);
            }
            QListWidget::item:hover {
                background-color: rgb(60, 60, 60);
            }
            QListWidget::item:selected {
                background-color: rgb(80, 80, 120);
            }
        """
        )
        self.alarm_list.itemClicked.connect(self._on_alarm_clicked)
        self.alarm_list.itemDoubleClicked.connect(self._on_alarm_double_clicked)

        # Refresh button
        self.refresh_button = QPushButton("↻ Refresh")
        self.refresh_button.setToolTip("Refresh alarm list")
        self.refresh_button.clicked.connect(self.update_alarm_list)
        self.refresh_button.setStyleSheet(
            """
            QPushButton {
                background-color: rgb(60, 60, 60);
                color: white;
                border: 1px solid rgb(100, 100, 100);
                padding: 4px;
                border-radius: 2px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: rgb(80, 80, 80);
            }
        """
        )

        # Add widgets to layout
        layout.addWidget(self.alarm_count_label)
        layout.addWidget(self.warning_count_label)
        layout.addWidget(self.alarm_list)
        layout.addWidget(self.refresh_button)

        self.setLayout(layout)
        self.setMinimumWidth(80)
        self.setMaximumWidth(300)

        # Add filter controls
        filter_layout = QHBoxLayout()

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Alarms Only", "Warnings Only"])
        self.filter_combo.currentTextChanged.connect(self.update_alarm_list)
        self.filter_combo.setStyleSheet(
            """
                    QComboBox {
                        background-color: rgb(60, 60, 60);
                        color: white;
                        border: 1px solid rgb(100, 100, 100);
                        padding: 3px;
                        font-size: 9pt;
                    }
                """
        )

        filter_layout.addWidget(QLabel("Filter:"))
        filter_layout.addWidget(self.filter_combo)

        # Add after warning count label
        layout.insertLayout(3, filter_layout)

    def _rebuild_alarm_list_full(self):
        """Rebuild with filtering"""
        self.alarm_list.clear()

        filter_mode = self.filter_combo.currentText()

        if filter_mode in ["All", "Alarms Only"]:
            for cavity in sorted(self.alarm_cavities, ...):
                self._add_cavity_item(cavity, is_alarm=True)

        if filter_mode in ["All", "Warnings Only"]:
            for cavity in sorted(self.warning_cavities, ...):
                self._add_cavity_item(cavity, is_alarm=False)

    def resizeEvent(self, event):
        """Handle resize to switch between compact and full display modes"""
        super().resizeEvent(event)

        new_width = event.size().width()

        # Determine display mode based on width
        if new_width < self.COMPACT_WIDTH:
            new_mode = "compact"
        else:
            new_mode = "full"

        # Only update if mode changed
        if new_mode != self.display_mode:
            self.display_mode = new_mode
            self._update_display_mode()

    def _update_display_mode(self):
        """Update UI elements based on current display mode"""
        alarm_count = len(self.alarm_cavities)
        warning_count = len(self.warning_cavities)

        if self.display_mode == "compact":
            # Compact mode: just emoji and number
            self.alarm_count_label.setText(f"🔴\n{alarm_count}")
            self.warning_count_label.setText(f"🟡\n{warning_count}")
            self.refresh_button.setText("↻")

            # Smaller font for compact mode
            self.alarm_count_label.setStyleSheet(
                """
                font-size: 14pt;
                font-weight: bold;
                background-color: rgb(150, 0, 0);
                color: white;
                padding: 4px;
                border-radius: 3px;
            """
            )
            self.warning_count_label.setStyleSheet(
                """
                font-size: 12pt;
                font-weight: bold;
                background-color: rgb(255, 165, 0);
                color: black;
                padding: 3px;
                border-radius: 3px;
            """
            )

            # Update list items to compact format
            self._rebuild_alarm_list_compact()

        else:
            # Full mode: text labels
            self.alarm_count_label.setText(f"ALARMS: {alarm_count}")
            self.warning_count_label.setText(f"WARNINGS: {warning_count}")
            self.refresh_button.setText("↻ Refresh")

            # Normal font for full mode
            alarm_bg = "rgb(150, 0, 0)" if alarm_count > 0 else "rgb(0, 100, 0)"
            self.alarm_count_label.setStyleSheet(
                f"""
                font-size: 16pt;
                font-weight: bold;
                background-color: {alarm_bg};
                color: white;
                padding: 5px;
                border-radius: 3px;
            """
            )

            warning_bg = (
                "rgb(255, 165, 0)" if warning_count > 0 else "rgb(60, 60, 60)"
            )
            warning_color = (
                "black" if warning_count > 0 else "rgb(180, 180, 180)"
            )
            self.warning_count_label.setStyleSheet(
                f"""
                font-size: 14pt;
                font-weight: bold;
                background-color: {warning_bg};
                color: {warning_color};
                padding: 4px;
                border-radius: 3px;
            """
            )

            # Update list items to full format
            self._rebuild_alarm_list_full()

    def _rebuild_alarm_list_compact(self):
        """Rebuild list in compact format"""
        self.alarm_list.clear()

        # Compact format: "🔴 02-5"
        for cavity in sorted(
            self.alarm_cavities, key=lambda c: (c.cryomodule.name, c.number)
        ):
            cm_name = cavity.cryomodule.name
            cav_num = cavity.number
            text = f"🔴 {cm_name}-{cav_num}"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, cavity)
            item.setForeground(QColor(255, 100, 100))

            # Full info in tooltip
            description = getattr(
                cavity.cavity_widget, "_cavity_description", ""
            )
            tooltip = f"CM{cm_name} Cavity {cav_num}"
            if description:
                tooltip += f": {description}"
            item.setToolTip(tooltip)

            self.alarm_list.addItem(item)

        for cavity in sorted(
            self.warning_cavities, key=lambda c: (c.cryomodule.name, c.number)
        ):
            cm_name = cavity.cryomodule.name
            cav_num = cavity.number
            text = f"🟡 {cm_name}-{cav_num}"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, cavity)
            item.setForeground(QColor(255, 200, 100))

            description = getattr(
                cavity.cavity_widget, "_cavity_description", ""
            )
            tooltip = f"CM{cm_name} Cavity {cav_num}"
            if description:
                tooltip += f": {description}"
            item.setToolTip(tooltip)

            self.alarm_list.addItem(item)

    def _rebuild_alarm_list_full(self):
        """Rebuild list in full format"""
        self.alarm_list.clear()

        # Full format: "🔴 CM02 Cav 5: Description"
        for cavity in sorted(
            self.alarm_cavities, key=lambda c: (c.cryomodule.name, c.number)
        ):
            cm_name = cavity.cryomodule.name
            cav_num = cavity.number

            description = getattr(
                cavity.cavity_widget, "_cavity_description", ""
            )
            if description and len(description) > 25:
                description = description[:22] + "..."

            if description:
                text = f"🔴 CM{cm_name} Cav{cav_num}: {description}"
            else:
                text = f"🔴 CM{cm_name} Cavity {cav_num}"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, cavity)
            item.setForeground(QColor(255, 100, 100))

            # Full description in tooltip
            full_desc = getattr(cavity.cavity_widget, "_cavity_description", "")
            if full_desc:
                item.setToolTip(f"CM{cm_name} Cavity {cav_num}: {full_desc}")

            self.alarm_list.addItem(item)

        for cavity in sorted(
            self.warning_cavities, key=lambda c: (c.cryomodule.name, c.number)
        ):
            cm_name = cavity.cryomodule.name
            cav_num = cavity.number

            description = getattr(
                cavity.cavity_widget, "_cavity_description", ""
            )
            if description and len(description) > 25:
                description = description[:22] + "..."

            if description:
                text = f"🟡 CM{cm_name} Cav{cav_num}: {description}"
            else:
                text = f"🟡 CM{cm_name} Cavity {cav_num}"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, cavity)
            item.setForeground(QColor(255, 200, 100))

            full_desc = getattr(cavity.cavity_widget, "_cavity_description", "")
            if full_desc:
                item.setToolTip(f"CM{cm_name} Cavity {cav_num}: {full_desc}")

            self.alarm_list.addItem(item)

    def _start_refresh_timer(self):
        """Start timer to refresh alarm list periodically"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_alarm_list)
        self.refresh_timer.start(2000)

    def _get_all_cavities(self):
        """Generator to iterate over all cavities"""
        linacs = self.gui_machine.linacs
        if isinstance(linacs, dict):
            linacs = linacs.values()

        for linac in linacs:
            cryomodules = linac.cryomodules
            if isinstance(cryomodules, dict):
                cryomodules = cryomodules.values()

            for cm in cryomodules:
                cavities = cm.cavities
                if isinstance(cavities, dict):
                    cavities = cavities.values()

                for cavity in cavities:
                    yield cavity

    def update_alarm_list(self):
        """Scan all cavities and update the alarm/warning lists"""
        self.alarm_cavities.clear()
        self.warning_cavities.clear()

        # Collect all cavities with issues
        for cavity in self._get_all_cavities():
            severity = getattr(cavity.cavity_widget, "_last_severity", None)

            if severity == 2:  # Red alarm
                self.alarm_cavities.append(cavity)
            elif severity == 1:  # Yellow warning
                self.warning_cavities.append(cavity)

        # Update display based on current mode
        self._update_display_mode()

    def _on_alarm_clicked(self, item: QListWidgetItem):
        """Handle single click - highlight cavity"""
        cavity = item.data(Qt.UserRole)
        if cavity:
            self.cavity_clicked.emit(cavity)

    def _on_alarm_double_clicked(self, item: QListWidgetItem):
        """Handle double click - open fault details"""
        cavity = item.data(Qt.UserRole)
        if cavity:
            self.cavity_clicked.emit(cavity)
            cavity.show_fault_display()

    def stop_refresh(self):
        """Stop the refresh timer (call when closing)"""
        if hasattr(self, "refresh_timer"):
            self.refresh_timer.stop()
