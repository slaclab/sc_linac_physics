from typing import Dict, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFrame,
    QLabel,
    QSizePolicy,
    QHBoxLayout,
    QPushButton,
)

from sc_linac_physics.displays.cavity_display.frontend.heatmap.heatmap_cavity_widget import (  # noqa: E501
    HeatmapCavityWidget,
)


def format_cm_display_name(cm_name: str) -> str:
    return cm_name if cm_name.startswith("H") else f"CM{cm_name}"


class ClickableLabel(QLabel):
    """QLabel that emits a clicked signal on left mouse press."""

    clicked = pyqtSignal()

    def __init__(
        self, text: str = "", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class HeatmapCMWidget(QWidget):
    """Column of 8 cavity widgets with a cryomodule label on top."""

    cavity_clicked = pyqtSignal(str, int)
    cavity_double_clicked = pyqtSignal(str, int)
    cm_label_clicked = pyqtSignal(str)

    NUM_CAVITIES = 8
    LABEL_FONT_SIZE = 9

    BAR_NO_DATA_COLOR = QColor(80, 80, 80)
    BAR_OK_COLOR = QColor(0, 140, 0)
    BAR_FAULTED_COLOR = QColor(255, 160, 0)
    BAR_CRITICAL_COLOR = QColor(200, 0, 0)
    BAR_HEIGHT = 3

    def __init__(self, cm_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._cm_name = cm_name
        self._cavity_widgets: Dict[int, HeatmapCavityWidget] = {}
        self._cavity_counts: Dict[int, int] = {}
        self._has_highlight: bool = False
        self._last_bar_color: Optional[QColor] = None
        self._setup_ui()

    @property
    def cm_name(self) -> str:
        return self._cm_name

    @property
    def cavity_widgets(self) -> Dict[int, HeatmapCavityWidget]:
        return self._cavity_widgets

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(1)
        self.setLayout(main_layout)

        # Top: label + status bar
        label_row = QHBoxLayout()
        label_row.setContentsMargins(0, 0, 0, 0)
        label_row.setSpacing(2)

        self._label = ClickableLabel(format_cm_display_name(self._cm_name))
        self._label.setAlignment(Qt.AlignCenter)
        label_font = QFont()
        label_font.setPointSize(self.LABEL_FONT_SIZE)
        label_font.setBold(True)
        self._label.setFont(label_font)
        self._label.setToolTip("Click to select/deselect all 8 cavities")
        self._label.setStyleSheet(
            "QLabel:hover { text-decoration: underline; }"
        )
        self._label.clicked.connect(self._on_cm_label_clicked)
        label_row.addWidget(self._label, stretch=1)

        self._select_all_btn = QPushButton("\u25a3")  # ▣
        self._select_all_btn.setFixedSize(16, 16)
        self._select_all_btn.setToolTip(
            f"Select all cavities in "
            f"{format_cm_display_name(self._cm_name)}"
        )
        self._select_all_btn.setStyleSheet(
            "QPushButton { padding: 0px; font-size: 9pt; }"
        )
        self._select_all_btn.clicked.connect(self._on_cm_label_clicked)
        label_row.addWidget(self._select_all_btn)

        main_layout.addLayout(label_row)

        self._status_bar = QFrame()
        self._status_bar.setFixedHeight(self.BAR_HEIGHT)
        self._status_bar.setStyleSheet(
            self._color_to_bg_stylesheet(self.BAR_NO_DATA_COLOR)
        )
        self._last_bar_color = self.BAR_NO_DATA_COLOR
        main_layout.addWidget(self._status_bar)

        for cav_num in range(1, self.NUM_CAVITIES + 1):
            widget = HeatmapCavityWidget(cavity_num=cav_num)
            widget.clicked.connect(self._on_cavity_clicked)
            widget.double_clicked.connect(self._on_cavity_double_clicked)
            main_layout.addWidget(widget, stretch=1)
            self._cavity_widgets[cav_num] = widget

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

    def _on_cavity_clicked(self, cavity_num: int) -> None:
        self.cavity_clicked.emit(self._cm_name, cavity_num)

    def _on_cavity_double_clicked(self, cavity_num: int) -> None:
        self.cavity_double_clicked.emit(self._cm_name, cavity_num)

    def _on_cm_label_clicked(self) -> None:
        self.cm_label_clicked.emit(self._cm_name)

    def update_cavity(
        self,
        cavity_num: int,
        count: int,
        color: QColor,
        tooltip: str,
        highlight: bool = False,
    ) -> None:
        widget = self._cavity_widgets.get(cavity_num)
        if widget:
            widget.set_fault_data(count, color, tooltip, highlight=highlight)
            self._cavity_counts[cavity_num] = count
            if highlight:
                self._has_highlight = True
            self._update_label_and_bar()

    def set_cavity_data_pending(self, cavity_num: int) -> None:
        widget = self._cavity_widgets.get(cavity_num)
        if widget:
            widget.set_data_pending()

    def set_cavity_error(
        self, cavity_num: int, error_msg: str = "Error loading data"
    ) -> None:  # noqa: E501
        widget = self._cavity_widgets.get(cavity_num)
        if widget:
            widget.set_error_state(error_msg)

    def set_cavity_selected(self, cavity_num: int, selected: bool) -> None:
        widget = self._cavity_widgets.get(cavity_num)
        if widget:
            widget.set_selected(selected)

    def select_all(self) -> None:
        for widget in self._cavity_widgets.values():
            widget.set_selected(True)

    def deselect_all(self) -> None:
        for widget in self._cavity_widgets.values():
            widget.set_selected(False)

    def all_selected(self) -> bool:
        return all(w.selected for w in self._cavity_widgets.values())

    def set_scale(self, scale: float) -> None:
        font_size = max(6, int(self.LABEL_FONT_SIZE * scale))
        font = self._label.font()
        font.setPointSize(font_size)
        self._label.setFont(font)

    @staticmethod
    def _color_to_bg_stylesheet(color: QColor) -> str:
        return (
            f"background-color: rgb({color.red()},"
            f"{color.green()},{color.blue()});"
        )

    def reset_highlight(self) -> None:
        """Reset highlight tracking so _update_label_and_bar recalculates."""
        self._has_highlight = False

    def clear_all(self) -> None:
        self._cavity_counts.clear()
        self._has_highlight = False
        self._update_label_and_bar()
        for widget in self._cavity_widgets.values():
            widget.clear()

    def _update_label_and_bar(self) -> None:
        base = format_cm_display_name(self._cm_name)
        if self._cavity_counts:
            total = sum(self._cavity_counts.values())
            self._label.setText(f"{base} ({total})")
            if self._has_highlight:
                color = self.BAR_CRITICAL_COLOR
            elif total > 0:
                color = self.BAR_FAULTED_COLOR
            else:
                color = self.BAR_OK_COLOR
        else:
            self._label.setText(base)
            color = self.BAR_NO_DATA_COLOR
        if color != self._last_bar_color:
            self._status_bar.setStyleSheet(self._color_to_bg_stylesheet(color))
            self._last_bar_color = color
