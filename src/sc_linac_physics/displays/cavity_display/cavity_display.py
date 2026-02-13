from PyQt5.QtCore import QTimer, QSettings
from PyQt5.QtGui import QColor, QCursor
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QApplication,
    QStatusBar,
    QLabel,
)
from lcls_tools.common.frontend.display.util import showDisplay
from pydm import Display
from pydm.utilities import IconFont
from pydm.widgets import PyDMByteIndicator, PyDMLabel

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

        self.groupbox_vlayout.addLayout(self.gui_machine.main_layout)

        self.groupbox = QGroupBox()
        self.groupbox.setLayout(self.groupbox_vlayout)
        self.vlayout.addWidget(self.groupbox)

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
        available_width = self.width() - 40

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

    def closeEvent(self, event):
        """Clean up and save state when window closes."""
        # Save window state
        self.settings.setValue("window_geometry", self.saveGeometry())
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
