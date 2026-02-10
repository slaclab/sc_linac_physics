from dataclasses import dataclass
from typing import Optional

import numpy as np
from PyQt5.QtWidgets import QApplication, QMessageBox, QMenu
from pydm import Display, PyDMChannel
from pydm.widgets.drawing import PyDMDrawingPolygon
from qtpy.QtCore import Signal, QPoint, QRectF, Property as qtProperty, Qt, Slot
from qtpy.QtGui import (
    QColor,
    QCursor,
    QFontMetrics,
    QPainter,
    QPen,
    QMouseEvent,
    QTextOption,
)

GREEN_FILL_COLOR = QColor(9, 141, 0)
YELLOW_FILL_COLOR = QColor(255, 165, 0, 200)
RED_FILL_COLOR = QColor(150, 0, 0)
PURPLE_FILL_COLOR = QColor(131, 61, 235)
GRAY_FILL_COLOR = QColor(127, 127, 127)
BLUE_FILL_COLOR = QColor(14, 191, 255)
LIMEGREEN_FILL_COLOR = QColor(92, 253, 92)

BLACK_TEXT_COLOR = QColor(0, 0, 0)
DARK_GRAY_COLOR = QColor(40, 40, 40)
WHITE_TEXT_COLOR = QColor(250, 250, 250)


@dataclass
class ShapeParameters:
    fillColor: QColor
    borderColor: QColor
    numPoints: int
    rotation: float


SHAPE_PARAMETER_DICT = {
    0: ShapeParameters(GREEN_FILL_COLOR, BLACK_TEXT_COLOR, 4, 0),
    1: ShapeParameters(YELLOW_FILL_COLOR, BLACK_TEXT_COLOR, 3, 0),
    2: ShapeParameters(RED_FILL_COLOR, BLACK_TEXT_COLOR, 6, 0),
    3: ShapeParameters(PURPLE_FILL_COLOR, BLACK_TEXT_COLOR, 20, 0),
    4: ShapeParameters(GRAY_FILL_COLOR, BLACK_TEXT_COLOR, 10, 0),
    5: ShapeParameters(DARK_GRAY_COLOR, WHITE_TEXT_COLOR, 10, 0),
}


class CavityWidget(PyDMDrawingPolygon):
    press_pos: Optional[QPoint] = None
    clicked = Signal()  # Changed from pyqtSignal()

    def __init__(self, parent=None, init_channel=None):
        super(CavityWidget, self).__init__(parent, init_channel)
        self._num_points = 4
        self._cavity_text = ""
        self._underline = False
        self._pen = QPen(BLACK_TEXT_COLOR)  # Shape's border color
        self._rotation = 0
        self._brush.setColor(QColor(201, 255, 203))  # Shape's fill color
        self._pen.setWidth(1)
        self._severity_channel: Optional[PyDMChannel] = None
        self._description_channel: Optional[PyDMChannel] = None
        self.alarmSensitiveBorder = False
        self.alarmSensitiveContent = False
        self._faultDisplay: Display = None
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setContentsMargins(0, 0, 0, 0)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for left-click and right-click."""
        if event.button() == Qt.LeftButton:
            self.press_pos = event.pos()
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.globalPos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle left-click release to emit clicked signal."""
        if (
            self.press_pos is not None
            and event.button() == Qt.LeftButton
            and event.pos() in self.rect()
        ):
            self.clicked.emit()
        self.press_pos = None

    def show_context_menu(self, global_pos):
        """Display context menu with cavity actions."""
        cavity = getattr(self, "_parent_cavity", None)
        if not cavity:
            return

        menu = QMenu()

        # Fault Details
        details_action = menu.addAction("📋 Fault Details")
        details_action.triggered.connect(lambda: cavity.show_fault_display())

        # Acknowledge (only if there's an alarm or warning)
        severity = getattr(self, "_last_severity", None)
        if severity == 2:
            ack_action = menu.addAction("✓ Acknowledge Alarm")
            ack_action.triggered.connect(
                lambda: self.acknowledge_issue(cavity, "Alarm")
            )
        elif severity == 1:
            ack_action = menu.addAction("✓ Acknowledge Warning")
            ack_action.triggered.connect(
                lambda: self.acknowledge_issue(cavity, "Warning")
            )

        menu.addSeparator()

        # Copy Info
        copy_action = menu.addAction("📄 Copy Info")
        copy_action.triggered.connect(lambda: self.copy_cavity_info(cavity))

        menu.exec_(global_pos)

    def acknowledge_issue(self, cavity, severity_text):
        """Acknowledge an alarm or warning and stop audio."""
        description = (
            self._cavity_description
            if self._cavity_description
            else "No description available"
        )
        reply = QMessageBox.question(
            None,
            f"Acknowledge {severity_text}",
            f"Acknowledge {severity_text.lower()} for CM{cavity.cryomodule.name} Cavity {cavity.number}?\n\n"
            f"Description: {description}",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            cavity_id = f"{cavity.cryomodule.name}_{cavity.number}"

            # Find parent display and stop audio
            parent_display = self._get_parent_display()
            if parent_display and hasattr(parent_display, "audio_manager"):
                parent_display.audio_manager.acknowledge_cavity(cavity_id)
                print(
                    f"✓ Acknowledged {severity_text} for CM{cavity.cryomodule.name} Cav{cavity.number}"
                )

    def _get_parent_display(self):
        """Walk up widget tree to find CavityDisplayGUI."""
        widget = self
        max_depth = 20

        for _ in range(max_depth):
            widget = widget.parent() if hasattr(widget, "parent") else None
            if widget and hasattr(widget, "audio_manager"):
                return widget

        return None

    def copy_cavity_info(self, cavity):
        """Copy cavity information to clipboard."""
        info = f"CM{cavity.cryomodule.name} Cavity {cavity.number}\n"
        info += f"Description: {self._cavity_description if self._cavity_description else 'None'}\n"
        info += f"Severity: {self._last_severity}"

        clipboard = QApplication.clipboard()
        clipboard.setText(info)

    @qtProperty(str)
    def cavity_text(self):
        return self._cavity_text

    @cavity_text.setter
    def cavity_text(self, text):
        self._cavity_text = text

    @qtProperty(str)
    def description_channel(self):
        if self._description_channel:
            return self._description_channel.address
        return ""

    @description_channel.setter
    def description_channel(self, value: str):
        # Clean up existing channel
        if hasattr(self, "_description_channel") and self._description_channel:
            self._description_channel.disconnect()

        if value:  # Only create channel if value is not empty
            self._description_channel = PyDMChannel(
                address=value, value_slot=self.description_changed
            )
            self._description_channel.connect()

    @qtProperty(str)
    def severity_channel(self):
        return self._severity_channel.address

    @severity_channel.setter
    def severity_channel(self, value: str):
        self._severity_channel = PyDMChannel(
            address=value, value_slot=self.severity_channel_value_changed
        )
        self._severity_channel.connect()

    @Slot(int)
    def severity_channel_value_changed(self, value: int):
        """Handle severity channel value changes with better error handling."""
        try:
            shape_params = SHAPE_PARAMETER_DICT.get(
                value, SHAPE_PARAMETER_DICT[3]
            )
            self.change_shape(shape_params)
        except Exception as e:
            print(f"Error updating severity: {e}")
            # Fallback to default state
            self.change_shape(SHAPE_PARAMETER_DICT[3])

    @Slot()
    @Slot(object)
    @Slot(str)
    @Slot(np.ndarray)
    def description_changed(self, value=None):
        if value is None:
            self.setToolTip("No description available")
        else:
            try:
                if isinstance(value, np.ndarray):
                    # Handle numpy array
                    if value.size == 0:
                        desc = "Empty array"
                    else:
                        desc = "".join(
                            chr(int(i)) for i in value if 0 <= int(i) <= 127
                        )
                elif isinstance(value, (bytes, bytearray)):
                    # Handle bytes
                    desc = value.decode("utf-8", errors="ignore")
                else:
                    # Handle string or other types
                    desc = str(value)

                self.setToolTip(desc.strip())
            except Exception as e:
                print(f"Error processing description: {e}")
                self.setToolTip("Description processing error")

        self.update()

    def change_shape(self, shape_parameter_object):
        self.brush.setColor(shape_parameter_object.fillColor)
        self.penColor = shape_parameter_object.borderColor
        self.numberOfPoints = shape_parameter_object.numPoints
        self.rotation = shape_parameter_object.rotation
        self.update()

    @qtProperty(bool)
    def underline(self):
        return self._underline

    @underline.setter
    def underline(self, underline: bool):
        self._underline = underline

    def value_changed(self, new_val):
        super(CavityWidget, self).value_changed(new_val)
        self.cavity_text = new_val
        self.update()

    def draw_item(self, painter: QPainter):
        super(CavityWidget, self).draw_item(painter)
        x, y, w, h = self.get_bounds(maxsize=True)
        rectf = QRectF(x, y, w, h)
        fm = QFontMetrics(painter.font())

        if self._cavity_text:
            sx = rectf.width() / fm.horizontalAdvance(self._cavity_text)

            try:
                int(self._cavity_text)
                sx = sx / 2
            except ValueError:
                pass

            sy = rectf.height() / fm.height()

            painter.save()
            painter.translate(rectf.center())
            painter.scale(sx, sy)
            painter.translate(-rectf.center())

            # Text color
            pen = QPen(QColor(240, 240, 240))
            pen.setWidth(5)

            painter.setPen(pen)
            text_option = QTextOption()
            text_option.setAlignment(Qt.AlignCenter)
            painter.drawText(rectf, self._cavity_text, text_option)
            painter.setPen(self._pen)
            painter.restore()
