from PyQt5.QtCore import QTimer, QSettings
from PyQt5.QtGui import QColor, QCursor
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QLabel,
    QApplication,
    QLineEdit,
    QFileDialog,
)
from lcls_tools.common.frontend.display.util import showDisplay
from pydm import Display
from pydm.utilities import IconFont
from pydm.widgets import PyDMByteIndicator, PyDMLabel
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

        # Set window size constraints (from PR 4)
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
        heartbeat_indicator.showLabels = False

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

        # Search box (from PR 5)
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

        # Clear search button (from PR 5)
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

        # Screenshot button (from PR 5)
        self.screenshot_btn = QPushButton("📷 Screenshot")
        self.screenshot_btn.setToolTip("Save screenshot of current display")
        self.screenshot_btn.clicked.connect(self.save_screenshot)
        self.header.addWidget(self.screenshot_btn)

        # Audio toggle button (NEW in PR 7)
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

        self.setWindowTitle("SRF Cavity Display")

        self.vlayout = QVBoxLayout()
        self.vlayout.setContentsMargins(0, 0, 0, 0)
        self.groupbox_vlayout = QVBoxLayout()
        self.groupbox_vlayout.addLayout(self.header)
        self.setLayout(self.vlayout)

        # Use main_layout from PR 4
        self.groupbox_vlayout.addLayout(self.gui_machine.main_layout)

        self.groupbox = QGroupBox()
        self.groupbox.setLayout(self.groupbox_vlayout)
        self.vlayout.addWidget(self.groupbox)

        # Auto-zoom tracking (from PR 3)
        self.current_zoom = 60
        self._resize_timer = None

        # Apply initial zoom
        QTimer.singleShot(100, lambda: self.apply_zoom(60))

        # Audio manager - create but don't activate yet (NEW in PR 7)
        self.audio_manager = AudioAlertManager(self.gui_machine, parent=self)
        self.audio_manager.setEnabled(False)  # Start disabled

        # Settings (NEW in PR 7)
        self.settings = QSettings("SLAC", "CavityDisplay")

        # Restore saved audio preference (NEW in PR 7)
        if self.settings.contains("audio_enabled"):
            saved_audio = self.settings.value("audio_enabled", type=bool)
            if saved_audio:
                self.audio_toggle_btn.setChecked(True)
                self.toggle_audio()  # Apply the saved setting

    def add_header_button(self, button: QPushButton, display: Display):
        button.clicked.connect(lambda: showDisplay(display))

        icon = IconFont().icon("file")
        button.setIcon(icon)
        button.setCursor(QCursor(icon.pixmap(16, 16)))
        button.openInNewWindow = True
        self.header.addWidget(button)

    def apply_zoom(self, zoom_percent):
        """Apply zoom to the entire display."""
        scale = zoom_percent / 100.0

        # Apply scaling to machine
        self.gui_machine.set_zoom_level(zoom_percent)

        # Update CM label fonts
        for cm_widget in self.gui_machine.cm_widgets:
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

        # Force layout update
        QApplication.processEvents()
        self.groupbox.updateGeometry()
        self.groupbox.adjustSize()
        self.update()

    def showEvent(self, event):
        """Auto-fit zoom when window is first shown."""
        super().showEvent(event)
        QTimer.singleShot(200, lambda: self.apply_zoom(60))

    def resizeEvent(self, event):
        """Auto-adjust zoom when user resizes window."""
        super().resizeEvent(event)

        if self._resize_timer:
            self._resize_timer.stop()

        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.auto_fit_on_resize)
        self._resize_timer.start(300)

    def auto_fit_on_resize(self):
        """Calculate optimal zoom when user resizes window."""
        if not hasattr(self, "groupbox") or not self.groupbox:
            return

        # Don't recalculate at minimum size
        if self.width() <= 800 or self.height() <= 600:
            if abs(self.current_zoom - 55) > 2:
                self.current_zoom = 55
                self.apply_zoom(55)
            return

        # Get available space
        available_height = self.height() - 200
        available_width = self.width() - 40

        # Measure content at 100%
        self.gui_machine.set_zoom_level(100)
        QApplication.processEvents()

        content_height = self.groupbox.sizeHint().height()
        content_width = self.groupbox.sizeHint().width()

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

    def filter_cavities(self):
        """Filter cavities based on search text."""
        search_text = self.search_box.text().strip().upper()

        for linac in self.gui_machine.linacs:
            cryomodules = (
                linac.cryomodules.values()
                if isinstance(linac.cryomodules, dict)
                else linac.cryomodules
            )

            for cm in cryomodules:
                cavities = (
                    cm.cavities.values()
                    if isinstance(cm.cavities, dict)
                    else cm.cavities
                )

                for cavity in cavities:
                    # Check if CM name or cavity number matches
                    cm_match = cm.name.upper().startswith(search_text)
                    cav_match = str(cavity.number).startswith(
                        search_text.replace("CAV", "").replace("CAVITY", "")
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

    def save_screenshot(self):
        """Save a screenshot of the current display."""
        from datetime import datetime

        default_filename = (
            f"cavity_display_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Screenshot",
            default_filename,
            "PNG Files (*.png);;All Files (*)",
        )

        if filename:
            pixmap = self.groupbox.grab()
            pixmap.save(filename)
            print(f"Screenshot saved: {filename}")

    def toggle_audio(self):
        """Toggle audio alerts on/off."""
        self.audio_enabled = self.audio_toggle_btn.isChecked()

        if self.audio_enabled:
            self.audio_toggle_btn.setText("🔊 Audio On")
            self.audio_manager.setEnabled(True)
            self.audio_manager.start_monitoring()
            print("✓ Audio alerts enabled")
        else:
            self.audio_toggle_btn.setText("🔇 Audio Off")
            self.audio_manager.setEnabled(False)
            self.audio_manager.stop_monitoring()
            print("Audio alerts disabled")

    def closeEvent(self, event):
        """Clean up and save state when window closes."""
        # Save audio preference
        self.settings.setValue("audio_enabled", self.audio_enabled)

        # Cleanup audio
        if hasattr(self, "audio_manager"):
            self.audio_manager.stop_monitoring()

        super().closeEvent(event)
