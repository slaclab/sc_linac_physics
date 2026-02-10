from PyQt5.QtGui import QColor, QCursor
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QPushButton,
    QGroupBox,
    QLabel,
    QFileDialog,
    QLineEdit,
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
from sc_linac_physics.displays.cavity_display.frontend.utils import make_line


class CavityDisplayGUI(Display):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.setStyleSheet(
            "background-color: rgb(35, 35, 35); color: rgb(255, 255, 255); font-size: 15pt;"
        )

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

        self.groupbox_vlayout.addLayout(self.gui_machine.top_half)
        self.groupbox_vlayout.addSpacing(10)
        self.groupbox_vlayout.addWidget(make_line(QFrame.HLine))
        self.groupbox_vlayout.addLayout(self.gui_machine.bottom_half)

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

        # Screenshot button
        self.screenshot_btn = QPushButton("📷 Screenshot")
        self.screenshot_btn.setToolTip("Save screenshot of current display")
        self.screenshot_btn.clicked.connect(self.save_screenshot)
        self.header.addWidget(self.screenshot_btn)

        # Auto-zoom tracking
        self.current_zoom = 60
        self._resize_timer = None

    def add_header_button(self, button: QPushButton, display: Display):
        button.clicked.connect(lambda: showDisplay(display))

        icon = IconFont().icon("file")
        button.setIcon(icon)
        button.setCursor(QCursor(icon.pixmap(16, 16)))
        button.openInNewWindow = True
        self.header.addWidget(button)

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

            # Could add status message here if status bar exists
            print(f"Screenshot saved: {filename}")

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
