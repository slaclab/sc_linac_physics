from datetime import datetime

from PyQt5.QtCore import QSettings, QTimer, Qt
from PyQt5.QtGui import QColor, QCursor, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QShortcut,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
)
from lcls_tools.common.frontend.display.util import showDisplay
from pydm import Display
from pydm.utilities import IconFont
from pydm.widgets import PyDMByteIndicator, PyDMLabel
from sc_linac_physics.displays.cavity_display.frontend.audio_manager import (
    AudioAlertManager,
)

from sc_linac_physics.displays.cavity_display.frontend.alarm_sidebar import (
    AlarmSidebarWidget,
)
from sc_linac_physics.displays.cavity_display.frontend.fault_count_display import (
    FaultCountDisplay,
)
from sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display import (
    DecoderDisplay,
)
from sc_linac_physics.displays.cavity_display.frontend.gui_machine import (
    GUIMachine,
)


class CavityDisplayGUI(Display):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.setStyleSheet(
            "background-color: rgb(35, 35, 35); color: rgb(255, 255, 255); font-size: 15pt;"
        )
        self.setWindowTitle("SRF Cavity Display")

        self.resize(1200, 800)
        self.setMinimumSize(1100, 700)

        self.gui_machine = GUIMachine()

        self.header = QHBoxLayout()

        heartbeat_indicator = PyDMByteIndicator(
            init_channel="ALRM:SYS0:SC_CAV_FAULT:ALHBERR"
        )
        heartbeat_indicator.onColor = QColor(255, 0, 0)
        heartbeat_indicator.offColor = QColor(0, 255, 0)
        heartbeat_indicator.showLabels = False
        heartbeat_indicator.circles = True

        heartbeat_label = PyDMLabel(
            init_channel="ALRM:SYS0:SC_CAV_FAULT:ALHBERR"
        )
        heartbeat_counter = PyDMLabel(
            init_channel="PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT"
        )

        self.header.addWidget(heartbeat_indicator)
        self.header.addWidget(heartbeat_label)
        self.header.addWidget(heartbeat_counter)
        self.header.addStretch()

        self.decoder_window = DecoderDisplay()
        self.decoder_button = QPushButton("Three Letter Code Decoder")
        self.add_header_button(self.decoder_button, self.decoder_window)

        self.fault_count_display = FaultCountDisplay()
        self.fault_count_button = QPushButton("Fault Counter")
        self.fault_count_button.setToolTip(
            "See fault history using archived data"
        )
        self.add_header_button(
            self.fault_count_button, self.fault_count_display
        )

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search CM or Cavity...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: rgb(50, 50, 50);
                color: white;
                border: 1px solid rgb(100, 100, 100);
                border-radius: 3px;
                padding: 5px;
                font-size: 11pt;
            }
            QLineEdit:focus {
                border: 2px solid rgb(100, 150, 255);
            }
            """)
        self.search_box.textChanged.connect(self.filter_cavities)
        self.search_box.setMaximumWidth(200)

        self.clear_search_btn = QPushButton("✕")
        self.clear_search_btn.setToolTip("Clear search")
        self.clear_search_btn.clicked.connect(lambda: self.search_box.clear())
        self.clear_search_btn.setMaximumWidth(30)
        self.clear_search_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(60, 60, 60);
                color: white;
                border: 1px solid rgb(100, 100, 100);
                border-radius: 3px;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: rgb(80, 80, 80);
            }
            """)

        self.header.addWidget(QLabel("Search:"))
        self.header.addWidget(self.search_box)
        self.header.addWidget(self.clear_search_btn)

        self.screenshot_btn = QPushButton("📷 Screenshot")
        self.screenshot_btn.setToolTip("Save screenshot of current display")
        self.screenshot_btn.clicked.connect(self.save_screenshot)
        self.header.addWidget(self.screenshot_btn)

        self.audio_enabled = False
        self.audio_toggle_btn = QPushButton("🔇 Audio Off")
        self.audio_toggle_btn.setCheckable(True)
        self.audio_toggle_btn.setChecked(False)
        self.audio_toggle_btn.setToolTip("Enable/disable audio alerts")
        self.audio_toggle_btn.clicked.connect(self.toggle_audio)
        self.audio_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(60, 60, 60);
                color: white;
                border: 1px solid rgb(100, 100, 100);
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 10pt;
            }
            QPushButton:checked {
                background-color: rgb(0, 100, 0);
                border: 1px solid rgb(0, 150, 0);
            }
            QPushButton:hover {
                background-color: rgb(80, 80, 80);
            }
            """)
        self.header.addWidget(self.audio_toggle_btn)

        self.vlayout = QVBoxLayout()
        self.vlayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.vlayout)

        self.groupbox_vlayout = QVBoxLayout()
        self.groupbox_vlayout.setContentsMargins(5, 5, 5, 5)
        self.groupbox_vlayout.setSpacing(8)
        self.groupbox_vlayout.addLayout(self.header)
        self.groupbox_vlayout.addLayout(self.gui_machine.main_layout)

        self.groupbox = QGroupBox()
        self.groupbox.setLayout(self.groupbox_vlayout)
        self.groupbox.setStyleSheet("""
            QGroupBox {
                border: none;
                background-color: rgb(35, 35, 35);
            }
            """)

        self.alarm_sidebar = AlarmSidebarWidget(self.gui_machine, parent=self)
        self.alarm_sidebar.cavity_clicked.connect(self.scroll_to_cavity)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.groupbox)
        self.splitter.addWidget(self.alarm_sidebar)
        self.splitter.setSizes([8500, 1500])
        self.groupbox.setMinimumWidth(600)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgb(100, 100, 100);
                width: 3px;
            }
            QSplitter::handle:hover {
                background-color: rgb(150, 150, 150);
            }
            QSplitter::handle:pressed {
                background-color: rgb(200, 200, 200);
            }
            """)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        self.vlayout.addWidget(self.splitter)

        self.settings = QSettings("SLAC", "CavityDisplay")
        if self.settings.contains("window_geometry"):
            self.restoreGeometry(self.settings.value("window_geometry"))
        if self.settings.contains("splitter_state"):
            self.splitter.restoreState(self.settings.value("splitter_state"))

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: rgb(50, 50, 50);
                color: white;
                font-size: 11pt;
                padding: 3px;
                max-height: 30px;
            }
            """)
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("font-size: 11pt;")
        self.status_bar.addWidget(self.status_label)
        self.vlayout.addWidget(self.status_bar)

        # Create status_timer with parent for proper lifecycle management
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)

        self.audio_manager = AudioAlertManager(self.gui_machine, parent=self)
        self.audio_manager.setEnabled(False)

        saved_audio_enabled = bool(
            self.settings.value("audio_enabled", False, type=bool)
        )
        self.audio_toggle_btn.setChecked(saved_audio_enabled)
        self.toggle_audio()

        self._setup_shortcuts()

        # Create resize timer once with parent
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.auto_fit_on_resize)

        self.current_zoom = 60

    def toggle_audio(self):
        self.audio_enabled = self.audio_toggle_btn.isChecked()

        if self.audio_enabled:
            self.audio_toggle_btn.setText("🔊 Audio On")
            self.audio_manager.setEnabled(True)
            self.audio_manager.start_monitoring()
            self.status_label.setText("✓ Audio alerts enabled")
        else:
            self.audio_toggle_btn.setText("🔇 Audio Off")
            self.audio_manager.setEnabled(False)
            self.audio_manager.stop_monitoring()
            self.status_label.setText("Audio alerts disabled")

        QTimer.singleShot(3000, self.update_status)

    def add_header_button(self, button: QPushButton, display: Display):
        button.clicked.connect(lambda: showDisplay(display))

        icon = IconFont().icon("file")
        button.setIcon(icon)
        button.setCursor(QCursor(icon.pixmap(16, 16)))
        button.openInNewWindow = True
        self.header.addWidget(button)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(200, lambda: self.apply_zoom(60))

    def resizeEvent(self, event):
        super().resizeEvent(event)

        # Reuse existing timer instead of creating new ones
        self._resize_timer.start(300)

    def auto_fit_on_resize(self):
        if not hasattr(self, "groupbox") or self.groupbox is None:
            return

        if (
            self.width() <= self.minimumWidth() + 50
            or self.height() <= self.minimumHeight() + 50
        ):
            if abs(self.current_zoom - 55) > 2:
                self.current_zoom = 55
                self.apply_zoom(55)
            return

        available_height = self.height() - 200
        sidebar_width = (
            self.alarm_sidebar.width() if self.alarm_sidebar.isVisible() else 0
        )
        available_width = self.width() - sidebar_width - 40

        self.gui_machine.set_zoom_level(100)
        QApplication.processEvents()

        content_height = self.groupbox.sizeHint().height()
        content_width = self.groupbox.sizeHint().width()

        height_zoom = (
            (available_height / content_height * 100)
            if content_height > 0
            else 100
        )
        width_zoom = (
            (available_width / content_width * 100)
            if content_width > 0
            else 100
        )

        optimal_zoom = min(height_zoom, width_zoom)
        optimal_zoom = max(55, min(100, optimal_zoom))
        optimal_zoom = round(optimal_zoom / 5) * 5

        if abs(optimal_zoom - self.current_zoom) > 2:
            self.current_zoom = optimal_zoom
            self.apply_zoom(optimal_zoom)

    def apply_zoom(self, zoom_percent):
        if not hasattr(self, "groupbox") or self.groupbox is None:
            return

        try:
            self.groupbox.objectName()
        except RuntimeError:
            return

        self.gui_machine.set_zoom_level(zoom_percent)

        scale = zoom_percent / 100.0
        for cm_widget in getattr(self.gui_machine, "cm_widgets", []):
            cm_layout = cm_widget.layout()
            if cm_layout and cm_layout.count() > 0:
                label_widget = cm_layout.itemAt(0).widget()
                if isinstance(label_widget, QLabel):
                    label_widget.setStyleSheet(f"""
                        QLabel {{
                            font-weight: bold;
                            font-size: {max(6, int(9 * scale))}pt;
                            color: white;
                            background-color: rgb(50, 50, 50);
                            padding: {max(1, int(2 * scale))}px;
                            border-radius: {max(1, int(2 * scale))}px;
                        }}
                        """)

        QApplication.processEvents()

        try:
            self.groupbox.updateGeometry()
            self.groupbox.adjustSize()
        except RuntimeError:
            return

        self.update()

    def _setup_shortcuts(self):
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self.alarm_sidebar.update_alarm_list)

        toggle_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        toggle_shortcut.activated.connect(self.toggle_sidebar)

        next_alarm_shortcut = QShortcut(QKeySequence("F3"), self)
        next_alarm_shortcut.activated.connect(self.jump_to_next_alarm)

        prev_alarm_shortcut = QShortcut(QKeySequence("Shift+F3"), self)
        prev_alarm_shortcut.activated.connect(self.jump_to_previous_alarm)

    def toggle_sidebar(self):
        if self.alarm_sidebar.isVisible():
            self.alarm_sidebar.hide()
        else:
            self.alarm_sidebar.show()

    def jump_to_next_alarm(self):
        current_row = self.alarm_sidebar.alarm_list.currentRow()
        next_row = current_row + 1

        if next_row < self.alarm_sidebar.alarm_list.count():
            self.alarm_sidebar.alarm_list.setCurrentRow(next_row)
            item = self.alarm_sidebar.alarm_list.currentItem()
            if item:
                cavity = item.data(Qt.UserRole)
                self.scroll_to_cavity(cavity)

    def jump_to_previous_alarm(self):
        current_row = self.alarm_sidebar.alarm_list.currentRow()
        prev_row = current_row - 1

        if prev_row >= 0:
            self.alarm_sidebar.alarm_list.setCurrentRow(prev_row)
            item = self.alarm_sidebar.alarm_list.currentItem()
            if item:
                cavity = item.data(Qt.UserRole)
                self.scroll_to_cavity(cavity)

    def scroll_to_cavity(self, cavity):
        if hasattr(cavity, "cavity_widget"):
            cavity.cavity_widget.highlight()

    def filter_cavities(self, search_text):
        search_text = search_text.lower().strip()

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
                    cm_match = f"{cm.name}".lower() in search_text
                    cav_match = (
                        f"cav{cavity.number}".lower() in search_text
                        or f"{cavity.number}" == search_text
                    )

                    if search_text == "" or cm_match or cav_match:
                        cavity.cavity_widget.setVisible(True)
                        cavity.cavity_widget.setGraphicsEffect(None)
                    else:
                        opacity_effect = QGraphicsOpacityEffect()
                        opacity_effect.setOpacity(0.2)
                        cavity.cavity_widget.setGraphicsEffect(opacity_effect)

    def save_screenshot(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"cavity_display_{timestamp}.png"

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Screenshot",
            default_filename,
            "PNG Files (*.png);;All Files (*)",
        )

        if filename:
            pixmap = self.groupbox.grab()
            # Check return value to detect save failures
            if pixmap.save(filename):
                self.status_label.setText(f"✓ Screenshot saved: {filename}")
            else:
                self.status_label.setText(
                    f"✗ Failed to save screenshot: {filename}"
                )
            QTimer.singleShot(5000, self.update_status)

    def update_status(self):
        total = 0
        alarms = 0
        warnings = 0
        ok = 0
        invalid = 0

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
                    total += 1
                    severity = getattr(
                        cavity.cavity_widget, "_last_severity", None
                    )

                    if severity == 3:
                        invalid += 1
                    elif severity == 2:
                        alarms += 1
                    elif severity == 1:
                        warnings += 1
                    else:
                        ok += 1

        self._update_status_display(total, alarms, warnings, ok, invalid)

    def _update_status_display(self, total, alarms, warnings, ok, invalid):
        status_parts = []

        if alarms > 0:
            status_parts.append(
                f"🔴 {alarms} ALARM{'S' if alarms != 1 else ''}"
            )

        if warnings > 0:
            status_parts.append(
                f"🟡 {warnings} WARNING{'S' if warnings != 1 else ''}"
            )

        status_parts.append(f"✓ {ok} OK")

        if invalid > 0:
            status_parts.append(f"🟣 {invalid} INVALID")

        status_parts.append(f"Total: {total}")
        self.status_label.setText(" | ".join(status_parts))

        if alarms > 0:
            bg_color = "rgb(150, 0, 0)"
        elif warnings > 0:
            bg_color = "rgb(200, 120, 0)"
        elif invalid > 0:
            bg_color = "rgb(100, 50, 150)"
        else:
            bg_color = "rgb(0, 100, 0)"

        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {bg_color};
                color: white;
                font-size: 11pt;
                font-weight: bold;
                padding: 3px;
                max-height: 30px;
            }}
            """)

    def closeEvent(self, event):
        self.settings.setValue("splitter_state", self.splitter.saveState())
        self.settings.setValue("window_geometry", self.saveGeometry())
        self.settings.setValue("audio_enabled", self.audio_enabled)

        if hasattr(self, "alarm_sidebar"):
            self.alarm_sidebar.stop_refresh()

        if hasattr(self, "audio_manager"):
            self.audio_manager.stop_monitoring()

        # Stop timers explicitly before close (good practice)
        if hasattr(self, "status_timer"):
            self.status_timer.stop()

        if hasattr(self, "_resize_timer"):
            self._resize_timer.stop()

        super().closeEvent(event)
