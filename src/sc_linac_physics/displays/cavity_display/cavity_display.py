from datetime import datetime

from PyQt5.QtCore import QTimer, QSettings, Qt
from PyQt5.QtGui import QColor, QCursor, QKeySequence
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QApplication,
    QStatusBar,
    QLabel,
    QLineEdit,
    QSplitter,
    QShortcut,
    QFileDialog,
)
from lcls_tools.common.frontend.display.util import showDisplay
from pydm import Display
from pydm.utilities import IconFont
from pydm.widgets import PyDMByteIndicator, PyDMLabel

from sc_linac_physics.displays.cavity_display.frontend.alarm_sidebar import (
    AlarmSidebarWidget,
)
from sc_linac_physics.displays.cavity_display.frontend.audio_manager import (
    AudioAlertManager,
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

        # Set window size constraints
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

        self.decoder_window: DecoderDisplay = DecoderDisplay()
        self.decoder_button = QPushButton("Three Letter Code Decoder")
        self.add_header_button(self.decoder_button, self.decoder_window)

        self.setWindowTitle("SRF Cavity Display")

        self.vlayout = QVBoxLayout()
        self.vlayout.setContentsMargins(0, 0, 0, 0)
        self.groupbox_vlayout = QVBoxLayout()
        self.groupbox_vlayout.addLayout(self.header)
        self.setLayout(self.vlayout)

        self.audio_enabled = False  # Default OFF
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

        # Search box
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

        # Screenshot button
        self.screenshot_btn = QPushButton("📷 Screenshot")
        self.screenshot_btn.setToolTip("Save screenshot of current display")
        self.screenshot_btn.clicked.connect(self.save_screenshot)
        self.header.addWidget(self.screenshot_btn)

        # Clear search button
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

        self.groupbox_vlayout.addLayout(self.gui_machine.main_layout)

        # Main groupbox
        self.groupbox = QGroupBox()
        self.groupbox.setLayout(self.groupbox_vlayout)
        self.groupbox.setStyleSheet("""
                    QGroupBox {
                        border: none;
                        background-color: rgb(35, 35, 35);
                    }
                    """)

        # Alarm sidebar
        self.alarm_sidebar = AlarmSidebarWidget(self.gui_machine, parent=self)
        self.alarm_sidebar.cavity_clicked.connect(self.scroll_to_cavity)

        # Splitter for main display and sidebar
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.groupbox)
        self.splitter.addWidget(self.alarm_sidebar)
        self.splitter.setSizes([8500, 1500])
        self.groupbox.setMinimumWidth(600)

        # Splitter styling
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

        # Replace self.vlayout.addWidget(self.groupbox) with:
        self.vlayout.addWidget(self.splitter)

        self.fault_count_display: FaultCountDisplay = FaultCountDisplay()
        self.fault_count_button: QPushButton = QPushButton("Fault Counter")
        self.fault_count_button.setToolTip(
            "See fault history using archived data"
        )
        self.add_header_button(
            self.fault_count_button, self.fault_count_display
        )

        # Settings
        self.settings = QSettings("SLAC", "CavityDisplay")

        # Restore saved geometry
        if self.settings.contains("window_geometry"):
            self.restoreGeometry(self.settings.value("window_geometry"))

        if self.settings.contains("splitter_state"):
            self.splitter.restoreState(self.settings.value("splitter_state"))

        # Status bar
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

        # Add status bar to layout
        self.vlayout.addWidget(self.status_bar)

        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)

        # Audio manager - create but don't activate yet
        self.audio_manager = AudioAlertManager(self.gui_machine, parent=self)
        self.audio_manager.setEnabled(False)  # Start disabled

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        # Auto-zoom tracking
        self.current_zoom = 60
        self._resize_timer = None

        # Apply initial zoom
        QTimer.singleShot(100, lambda: self.apply_zoom(60))

        self.setWindowTitle("SRF Cavity Display")

    def add_header_button(self, button: QPushButton, display: Display):
        button.clicked.connect(lambda: showDisplay(display))

        icon = IconFont().icon("file")
        button.setIcon(icon)
        button.setCursor(QCursor(icon.pixmap(16, 16)))
        button.openInNewWindow = True
        self.header.addWidget(button)

    def apply_zoom(self, zoom_percent):
        """Apply zoom to the entire display."""

        # Safety check: ensure widgets exist and haven't been deleted
        if not hasattr(self, "groupbox") or self.groupbox is None:
            return

        try:
            # Check if C++ object still exists (will raise RuntimeError if deleted)
            self.groupbox.objectName()
        except RuntimeError:
            # Widget was deleted, abort safely
            return

        # Apply scaling to machine
        self.gui_machine.set_zoom_level(zoom_percent)

        # Force layout update
        QApplication.processEvents()

        # Additional safety check before updateGeometry
        try:
            self.groupbox.updateGeometry()
            self.groupbox.adjustSize()
        except RuntimeError:
            # Widget was deleted during processing
            return

        self.update()

    def toggle_audio(self):
        """Toggle audio alerts on/off."""
        self.audio_enabled = self.audio_toggle_btn.isChecked()

        if self.audio_enabled:
            self.audio_toggle_btn.setText("🔊 Audio On")
            self.audio_manager.setEnabled(True)
            self.audio_manager.start_monitoring()
            if hasattr(self, "status_label"):
                self.status_label.setText("✓ Audio alerts enabled")
                QTimer.singleShot(3000, self.update_status)
        else:
            self.audio_toggle_btn.setText("🔇 Audio Off")
            self.audio_manager.setEnabled(False)
            self.audio_manager.stop_monitoring()
            if hasattr(self, "status_label"):
                self.status_label.setText("Audio alerts disabled")
                QTimer.singleShot(3000, self.update_status)

    def showEvent(self, event):
        """Auto-fit zoom when window is first shown."""
        super().showEvent(event)

        # Use parented timer
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.apply_zoom(60))
        timer.start(200)

    def auto_fit_on_resize(self):
        """Calculate optimal zoom when user resizes window."""
        if not hasattr(self, "groupbox") or not self.groupbox:
            return

        # Add safety check
        try:
            self.groupbox.objectName()
        except RuntimeError:
            return

        # Don't recalculate at minimum size
        if self.width() <= 800 or self.height() <= 600:
            if abs(self.current_zoom - 55) > 2:
                self.current_zoom = 55
                self.apply_zoom(55)
            return

        # Get available space
        available_height = self.height() - 200
        # Get available space
        sidebar_width = (
            self.alarm_sidebar.width() if self.alarm_sidebar.isVisible() else 0
        )
        available_width = self.width() - sidebar_width - 40

        # Measure content at 100%
        self.gui_machine.set_zoom_level(100)
        QApplication.processEvents()

        try:
            content_height = self.groupbox.sizeHint().height()
            content_width = self.groupbox.sizeHint().width()
        except RuntimeError:
            return

        # Calculate optimal zoom
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

    def resizeEvent(self, event):
        """Auto-adjust zoom when user resizes window."""
        super().resizeEvent(event)

        if self._resize_timer:
            self._resize_timer.stop()

        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.auto_fit_on_resize)
        self._resize_timer.start(300)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for common actions"""
        # F5 - Refresh alarm list
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self.alarm_sidebar.update_alarm_list)

        # Ctrl+H - Toggle sidebar
        toggle_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        toggle_shortcut.activated.connect(self.toggle_sidebar)

        # F3 - Jump to next alarm
        next_alarm_shortcut = QShortcut(QKeySequence("F3"), self)
        next_alarm_shortcut.activated.connect(self.jump_to_next_alarm)

        # Shift+F3 - Jump to previous alarm
        prev_alarm_shortcut = QShortcut(QKeySequence("Shift+F3"), self)
        prev_alarm_shortcut.activated.connect(self.jump_to_previous_alarm)

    def toggle_sidebar(self):
        """Toggle sidebar visibility"""
        if self.alarm_sidebar.isVisible():
            self.alarm_sidebar.hide()
        else:
            self.alarm_sidebar.show()

    def jump_to_next_alarm(self):
        """Jump to next alarm in the list"""
        current_row = self.alarm_sidebar.alarm_list.currentRow()
        next_row = current_row + 1

        if next_row < self.alarm_sidebar.alarm_list.count():
            self.alarm_sidebar.alarm_list.setCurrentRow(next_row)
            item = self.alarm_sidebar.alarm_list.currentItem()
            if item:
                cavity = item.data(Qt.UserRole)
                self.scroll_to_cavity(cavity)

    def jump_to_previous_alarm(self):
        """Jump to previous alarm in the list"""
        current_row = self.alarm_sidebar.alarm_list.currentRow()
        prev_row = current_row - 1

        if prev_row >= 0:
            self.alarm_sidebar.alarm_list.setCurrentRow(prev_row)
            item = self.alarm_sidebar.alarm_list.currentItem()
            if item:
                cavity = item.data(Qt.UserRole)
                self.scroll_to_cavity(cavity)

    def closeEvent(self, event):
        """Clean up and save state when window closes."""
        # Save window state
        self.settings.setValue("splitter_state", self.splitter.saveState())
        self.settings.setValue("window_geometry", self.saveGeometry())

        # Cleanup
        if hasattr(self, "alarm_sidebar"):
            self.alarm_sidebar.stop_refresh()

        if hasattr(self, "audio_manager"):
            self.audio_manager.stop_monitoring()

        super().closeEvent(event)

    def update_status(self):
        """Update status bar with summary"""
        total = 0
        alarms = 0
        warnings = 0
        ok = 0

        for linac in self.gui_machine.linacs:
            for cm in linac.cryomodules.values():
                for cavity in cm.cavities.values():
                    total += 1
                    severity = getattr(
                        cavity.cavity_widget, "_last_severity", None
                    )
                    if severity == 2:
                        alarms += 1
                    elif severity == 1:
                        warnings += 1
                    else:
                        ok += 1

        # Build status message
        self._update_status_display(total, alarms, warnings, ok)

    def _update_status_display(self, total, alarms, warnings, ok):
        """Update the status bar display with counts."""
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
        status_parts.append(f"Total: {total}")

        status_text = " | ".join(status_parts)

        # Determine color based on severity
        if alarms > 0:
            bg_color = "rgb(150, 0, 0)"
        elif warnings > 0:
            bg_color = "rgb(200, 120, 0)"
        else:
            bg_color = "rgb(0, 100, 0)"

        self.status_label.setText(status_text)
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

    def save_screenshot(self):
        """Save a screenshot of the current display"""
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
            pixmap.save(filename)

            if hasattr(self, "status_label"):
                self.status_label.setText(f"✓ Screenshot saved: {filename}")
                QTimer.singleShot(5000, self.update_status)

    def filter_cavities(self, search_text):
        """Filter/highlight cavities based on search text"""
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
                        from PyQt5.QtWidgets import QGraphicsOpacityEffect

                        opacity_effect = QGraphicsOpacityEffect()
                        opacity_effect.setOpacity(0.2)
                        cavity.cavity_widget.setGraphicsEffect(opacity_effect)

    def scroll_to_cavity(self, cavity):
        """
        Highlight a specific cavity when clicked from alarm sidebar.
        No scrolling needed since everything is visible.

        Args:
            cavity: GUICavity object to highlight
        """
        if hasattr(cavity, "cavity_widget"):
            cavity.cavity_widget.highlight()
