from datetime import datetime

from PyQt5.QtCore import Qt, QSettings, QTimer
from PyQt5.QtGui import QColor, QCursor, QKeySequence
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QPushButton,
    QGroupBox,
    QSplitter,
    QStatusBar,
    QLabel,
    QShortcut,
    QApplication,
    QLineEdit,
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
from sc_linac_physics.displays.cavity_display.frontend.utils import make_line


class CavityDisplayGUI(Display):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.setStyleSheet(
            "background-color: rgb(35, 35, 35); color: rgb(255, 255, 255); font-size: 15pt;"
        )

        self.gui_machine = GUIMachine()

        # Setup audio alerts - with debug output
        print("Initializing audio manager...")
        self.audio_manager = AudioAlertManager(self.gui_machine, parent=self)
        print(
            f"Audio manager created. Alarm sound: {self.audio_manager.alarm_sound}"
        )
        print(f"Warning sound: {self.audio_manager.warning_sound}")

        # Test audio immediately on startup
        print("Testing audio on startup...")
        QTimer.singleShot(2000, self.test_audio_on_startup)

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

        self.fault_count_display: FaultCountDisplay = FaultCountDisplay()
        self.fault_count_button: QPushButton = QPushButton("Fault Counter")
        self.fault_count_button.setToolTip(
            "See fault history using archived data"
        )
        self.add_header_button(
            self.fault_count_button, self.fault_count_display
        )

        self.setWindowTitle("SRF Cavity Display")

        # Main container for cavity grid (NO SCROLL AREA)
        self.groupbox_vlayout = QVBoxLayout()
        self.groupbox_vlayout.setContentsMargins(
            5, 5, 5, 5
        )  # Padding around entire display
        self.groupbox_vlayout.setSpacing(8)  # Space between top/bottom halves
        self.groupbox_vlayout.addLayout(self.header)

        self.groupbox_vlayout.addLayout(self.gui_machine.top_half)
        self.groupbox_vlayout.addSpacing(5)  # Smaller spacing
        self.groupbox_vlayout.addWidget(make_line(QFrame.HLine))
        self.groupbox_vlayout.addSpacing(5)  # Smaller spacing
        self.groupbox_vlayout.addLayout(self.gui_machine.bottom_half)

        self.groupbox = QGroupBox()
        self.groupbox.setLayout(self.groupbox_vlayout)
        self.groupbox.setStyleSheet(
            """
            QGroupBox {
                border: none;
                background-color: rgb(35, 35, 35);
            }
        """
        )

        # Create alarm sidebar
        self.alarm_sidebar = AlarmSidebarWidget(self.gui_machine, parent=self)
        self.alarm_sidebar.cavity_clicked.connect(self.scroll_to_cavity)

        # Use QSplitter
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.groupbox)  # Direct widget, no scroll area
        self.splitter.addWidget(self.alarm_sidebar)

        # Set initial sizes: cavity display gets 85%, sidebar gets 15%
        self.splitter.setSizes([8500, 1500])

        # Set a minimum size for the cavity display
        self.groupbox.setMinimumWidth(600)

        # Style the splitter handle for visibility
        self.splitter.setStyleSheet(
            """
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
        """
        )

        # Set collapsible
        self.splitter.setCollapsible(
            0, False
        )  # Cavity display can't be collapsed
        self.splitter.setCollapsible(1, True)  # Sidebar can be collapsed

        # Set main layout
        self.vlayout = QVBoxLayout()
        self.vlayout.setContentsMargins(0, 0, 0, 0)
        self.vlayout.addWidget(self.splitter)
        self.setLayout(self.vlayout)

        # Optional: Restore previous splitter state
        self.settings = QSettings("SLAC", "CavityDisplay")
        if self.settings.contains("splitter_state"):
            self.splitter.restoreState(self.settings.value("splitter_state"))

        # Add status bar at bottom
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(
            """
                QStatusBar {
                    background-color: rgb(50, 50, 50);
                    color: white;
                    font-size: 12pt;
                    padding: 5px;
                }
            """
        )

        self.status_label = QLabel("Initializing...")
        self.status_bar.addWidget(self.status_label)

        # Add to layout
        self.vlayout.addWidget(self.splitter)
        self.vlayout.addWidget(self.status_bar)

        # Update status every 5 seconds
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)
        # Connect audio manager to flash window
        if hasattr(self, "audio_manager"):
            self.audio_manager.new_alarm.connect(self.flash_window)

        # Add search box to header
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search CM or Cavity...")
        self.search_box.setStyleSheet(
            """
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
            """
        )
        self.search_box.textChanged.connect(self.filter_cavities)
        self.search_box.setMaximumWidth(200)

        # Clear button
        self.clear_search_btn = QPushButton("✕")
        self.clear_search_btn.setToolTip("Clear search")
        self.clear_search_btn.clicked.connect(lambda: self.search_box.clear())
        self.clear_search_btn.setMaximumWidth(30)
        self.clear_search_btn.setStyleSheet(
            """
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
            """
        )

        self.header.addWidget(QLabel("Search:"))
        self.header.addWidget(self.search_box)
        self.header.addWidget(self.clear_search_btn)
        # Add screenshot button to header
        self.screenshot_btn = QPushButton("📷 Screenshot")
        self.screenshot_btn.setToolTip("Save screenshot of current display")
        self.screenshot_btn.clicked.connect(self.save_screenshot)
        self.header.addWidget(self.screenshot_btn)

    def test_audio_on_startup(self):
        """Test audio system on startup"""
        print("Playing test beep...")
        from PyQt5.QtWidgets import QApplication

        QApplication.beep()
        print("Beep command sent")

        if hasattr(self, "audio_manager"):
            print("Testing alarm sound...")
            self.audio_manager._play_alarm_sound()

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
            # Grab the main widget (without window decorations)
            pixmap = self.groupbox.grab()
            pixmap.save(filename)

            # Update status
            if hasattr(self, "status_label"):
                self.status_label.setText(f"Screenshot saved: {filename}")
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
                        # Show and reset opacity
                        cavity.cavity_widget.setVisible(True)
                        cavity.cavity_widget.setGraphicsEffect(None)
                    else:
                        # Dim non-matching cavities
                        from PyQt5.QtWidgets import QGraphicsOpacityEffect

                        opacity_effect = QGraphicsOpacityEffect()
                        opacity_effect.setOpacity(0.2)
                        cavity.cavity_widget.setGraphicsEffect(opacity_effect)

    def flash_window(self, cavity=None):
        """Flash/alert the window to grab attention"""
        # Flash the window in taskbar
        QApplication.alert(self, 0)  # 0 = flash until focused

        # Optionally bring to front (might be annoying)
        # self.activateWindow()
        # self.raise_()

        # Flash the title bar with alarm info
        if cavity:
            original_title = self.windowTitle()
            alarm_title = f"⚠️ ALARM: CM{cavity.cryomodule.name} Cav{cavity.number} - {original_title}"
            self.setWindowTitle(alarm_title)

            # Reset title after 5 seconds
            QTimer.singleShot(5000, lambda: self.setWindowTitle(original_title))

    def update_status(self):
        """Update status bar with summary"""
        total = 0
        alarms = 0
        warnings = 0
        ok = 0

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
                    if severity == 2:
                        alarms += 1
                    elif severity == 1:
                        warnings += 1
                    else:
                        ok += 1

        # Build status message with consistent formatting
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

        # Color based on severity
        if alarms > 0:
            bg_color = "rgb(150, 0, 0)"
            text_color = "white"
        elif warnings > 0:
            bg_color = "rgb(200, 120, 0)"
            text_color = "white"
        else:
            bg_color = "rgb(0, 100, 0)"
            text_color = "white"

        self.status_label.setText(status_text)
        self.status_bar.setStyleSheet(
            f"""
            QStatusBar {{
                background-color: {bg_color};
                color: {text_color};
                font-size: 12pt;
                font-weight: bold;
                padding: 5px;
            }}
        """
        )

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

    def add_header_button(self, button: QPushButton, display: Display):
        button.clicked.connect(lambda: showDisplay(display))

        icon = IconFont().icon("file")
        button.setIcon(icon)
        button.setCursor(QCursor(icon.pixmap(16, 16)))
        button.openInNewWindow = True
        self.header.addWidget(button)

    def scroll_to_cavity(self, cavity):
        """
        Highlight a specific cavity when clicked from alarm sidebar.
        No scrolling needed since everything is visible.

        Args:
            cavity: GUICavity object to highlight
        """
        if hasattr(cavity, "cavity_widget"):
            # Just highlight the cavity
            cavity.cavity_widget.highlight()

    def closeEvent(self, event):
        """Clean up and save state when window closes"""
        # Save splitter position
        self.settings.setValue("splitter_state", self.splitter.saveState())

        # Cleanup
        self.alarm_sidebar.stop_refresh()
        super().closeEvent(event)
