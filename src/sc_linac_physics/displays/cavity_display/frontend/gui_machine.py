from collections import OrderedDict

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QLabel,
    QSizePolicy,
)

from sc_linac_physics.displays.cavity_display.frontend.gui_cavity import (
    GUICavity,
)
from sc_linac_physics.displays.cavity_display.frontend.gui_cryomodule import (
    GUICryomodule,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


class GUIMachine(Machine):
    """GUI representation of the machine with all linacs and cryomodules."""

    # Linac color scheme (avoiding status colors: green, yellow, red, purple, gray)
    LINAC_COLORS = {
        0: {
            "border": "rgb(100, 180, 255)",
            "text": "rgb(100, 180, 255)",
            "bg": "rgb(20, 40, 80)",
        },
        1: {
            "border": "rgb(0, 200, 200)",
            "text": "rgb(0, 220, 220)",
            "bg": "rgb(0, 60, 60)",
        },
        2: {
            "border": "rgb(255, 140, 0)",
            "text": "rgb(255, 160, 40)",
            "bg": "rgb(80, 50, 10)",
        },
        3: {
            "border": "rgb(255, 100, 180)",
            "text": "rgb(255, 120, 200)",
            "bg": "rgb(80, 30, 60)",
        },
        4: {
            "border": "rgb(100, 200, 255)",
            "text": "rgb(120, 200, 255)",
            "bg": "rgb(30, 50, 80)",
        },
    }

    DEFAULT_COLORS = {
        "border": "rgb(100, 100, 100)",
        "text": "rgb(200, 200, 200)",
        "bg": "rgb(50, 50, 50)",
    }

    def __init__(self, lazy_fault_pvs=True):
        self.lazy_fault_pvs = lazy_fault_pvs
        super().__init__(cavity_class=GUICavity, cryomodule_class=GUICryomodule)

        # Layout configuration
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(4)
        self.main_layout.setContentsMargins(2, 2, 2, 2)

        # Storage for zoom and layout management
        self.cm_widgets = []
        self.row_layouts = []
        self.linac_sections = []
        self.cms_per_row = 30

        # Build the display
        self._build_layout()

        print(
            f"GUI Machine initialized with {len(self.cm_widgets)} cryomodules"
        )

    def _build_layout(self):
        """Build the complete GUI layout with all linacs and cryomodules."""
        all_cms_with_linac = self._collect_all_cms()

        # Create rows
        for row_start in range(0, len(all_cms_with_linac), self.cms_per_row):
            row_end = min(row_start + self.cms_per_row, len(all_cms_with_linac))
            row_cms = all_cms_with_linac[row_start:row_end]

            row_layout = self._create_row(row_cms)
            self.row_layouts.append(row_layout)
            self.main_layout.addLayout(row_layout)

    def _collect_all_cms(self):
        """Collect all cryomodules with their linac information."""
        all_cms = []

        linacs = self.linacs
        if isinstance(linacs, dict):
            linacs = [(key, linacs[key]) for key in sorted(linacs.keys())]
        else:
            linacs = [(i, linac) for i, linac in enumerate(linacs)]

        for linac_key, linac in linacs:
            cryomodules = linac.cryomodules
            if isinstance(cryomodules, dict):
                cryomodules = [
                    (key, cryomodules[key])
                    for key in sorted(cryomodules.keys())
                ]
            else:
                cryomodules = [(i, cm) for i, cm in enumerate(cryomodules)]

            for _, gui_cm in cryomodules:
                all_cms.append((linac_key, gui_cm))

        return all_cms

    def _create_row(self, row_cms):
        """Create a row layout containing linac sections."""
        row_layout = QHBoxLayout()
        row_layout.setSpacing(4)
        row_layout.setContentsMargins(0, 0, 0, 0)

        # Group CMs by linac
        linac_groups = OrderedDict()
        for linac_key, gui_cm in row_cms:
            if linac_key not in linac_groups:
                linac_groups[linac_key] = []
            linac_groups[linac_key].append(gui_cm)

        # Create bordered section for each linac
        for linac_key, cms in linac_groups.items():
            section = self._create_linac_section(linac_key, cms)
            self.linac_sections.append(section)
            row_layout.addWidget(
                section, len(cms)
            )  # Stretch proportional to CM count

        return row_layout

    def _create_linac_section(self, linac_key, cms):
        """Create a bordered section for a linac with its cryomodules."""
        section = QWidget()
        section_layout = QVBoxLayout()
        section_layout.setSpacing(2)
        section_layout.setContentsMargins(3, 3, 3, 3)

        # Add linac header
        header = self._create_linac_header(linac_key)
        section_layout.addWidget(header)

        # Add cryomodules in horizontal layout
        cms_layout = QHBoxLayout()
        cms_layout.setSpacing(2)
        cms_layout.setContentsMargins(0, 0, 0, 0)

        for gui_cm in cms:
            cm_widget = self._wrap_cm(gui_cm)
            cms_layout.addWidget(cm_widget, 1)  # Equal stretch for all CMs

        section_layout.addLayout(cms_layout, 1)
        section.setLayout(section_layout)

        # Apply styling
        self._style_linac_section(section, linac_key)

        return section

    def _create_linac_header(self, linac_key):
        """Create header label for a linac section."""
        linac_name = (
            f"L{linac_key}B" if isinstance(linac_key, int) else str(linac_key)
        )
        label = QLabel(linac_name)
        label.setAlignment(Qt.AlignCenter)

        colors = self.LINAC_COLORS.get(linac_key, self.DEFAULT_COLORS)

        label.setStyleSheet(
            f"""
            QLabel {{
                font-weight: bold;
                font-size: 10pt;
                color: {colors['text']};
                background-color: {colors['bg']};
                padding: 3px;
                border-radius: 2px;
                margin-bottom: 2px;
            }}
        """
        )
        label.setFixedHeight(20)

        return label

    def _wrap_cm(self, gui_cm):
        """Wrap a cryomodule in a widget for the layout."""
        cm_widget = QWidget()
        cm_widget.setLayout(gui_cm.vlayout)
        cm_widget.setStyleSheet(
            """
            QWidget {
                background-color: rgb(40, 40, 40);
                border: none;
            }
        """
        )
        cm_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.cm_widgets.append(cm_widget)
        return cm_widget

    def _style_linac_section(self, section, linac_key):
        """Apply border and styling to a linac section."""
        colors = self.LINAC_COLORS.get(linac_key, self.DEFAULT_COLORS)

        section.setStyleSheet(
            f"""
            QWidget {{
                background-color: rgb(35, 35, 35);
                border: 2px solid {colors['border']};
                border-radius: 3px;
            }}
        """
        )

        section.linac_key = linac_key
        section.border_color = colors["border"]
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_zoom_level(self, zoom_percent):
        """Apply zoom scaling to all elements."""
        scale = zoom_percent / 100.0

        # Scale all cavities
        self._scale_cavities(scale)

        # Scale spacing
        self._scale_spacing(scale)

        # Scale borders
        self._scale_borders(scale)

        # Update widget sizes
        for cm_widget in self.cm_widgets:
            cm_widget.adjustSize()
            cm_widget.updateGeometry()

    def _scale_cavities(self, scale):
        """Scale all cavity widgets."""
        linacs = (
            self.linacs
            if isinstance(self.linacs, list)
            else list(self.linacs.values())
        )

        for linac in linacs:
            cryomodules = linac.cryomodules
            if isinstance(cryomodules, dict):
                cryomodules = cryomodules.values()

            for cm in cryomodules:
                cavities = cm.cavities
                if isinstance(cavities, dict):
                    cavities = cavities.values()

                for cavity in cavities:
                    cavity.set_scale(scale)

    def _scale_spacing(self, scale):
        """Scale spacing between elements."""
        section_spacing = max(2, int(4 * scale))
        row_spacing = max(2, int(4 * scale))

        for row_layout in self.row_layouts:
            row_layout.setSpacing(section_spacing)

        self.main_layout.setSpacing(row_spacing)

    def _scale_borders(self, scale):
        """Scale borders and padding of linac sections."""
        border_width = 1 if scale < 0.75 else 2
        border_radius = max(2, int(3 * scale))
        padding = max(2, int(3 * scale))

        for section in self.linac_sections:
            if hasattr(section, "border_color"):
                section.setStyleSheet(
                    f"""
                    QWidget {{
                        background-color: rgb(35, 35, 35);
                        border: {border_width}px solid {section.border_color};
                        border-radius: {border_radius}px;
                    }}
                """
                )
                if section.layout():
                    section.layout().setContentsMargins(
                        padding, padding, padding, padding
                    )
