from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QCursor
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QApplication,
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

    def scroll_to_cavity(self, cavity):
        """
        Highlight a specific cavity when clicked from alarm sidebar.
        No scrolling needed since everything is visible.

        Args:
            cavity: GUICavity object to highlight
        """
        if hasattr(cavity, "cavity_widget"):
            cavity.cavity_widget.highlight()
