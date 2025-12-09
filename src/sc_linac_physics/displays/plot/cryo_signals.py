import math

from pydm import Display
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QWidget,
    QLabel,
    QGroupBox,
    QComboBox,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QDialog,
    QScrollArea,
)

from sc_linac_physics.displays.plot.embeddable_plots import (
    EmbeddableArchiverPlot,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


class GlobalAxisRangeDialog(QDialog):
    """Dialog for configuring Y-axis ranges for all plots of a given PV type."""

    def __init__(self, pv_attributes, parent=None):
        super().__init__(parent)
        self.pv_attributes = pv_attributes
        self.axis_controls = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Global Y-Axis Range Control")
        self.setMinimumWidth(500)

        layout = QVBoxLayout()

        # Info label
        info = QLabel(
            "Configure Y-axis ranges for each PV type across all plots:"
        )
        layout.addWidget(info)

        # Scroll area for controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        for pv_attr in self.pv_attributes:
            control_group = self._create_pv_control(pv_attr)
            scroll_layout.addWidget(control_group)

        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.accept)
        close_btn = QPushButton("Cancel")
        close_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_pv_control(self, pv_attr):
        """Create control widgets for a single PV type."""
        # Create readable label
        label_text = pv_attr.replace("_pv", "").replace("_", " ").title()
        group = QGroupBox(label_text)
        layout = QVBoxLayout()

        # Auto-scale checkbox
        auto_check = QCheckBox("Auto-scale")
        auto_check.setChecked(True)
        layout.addWidget(auto_check)

        # Manual range inputs
        range_layout = QGridLayout()
        range_layout.addWidget(QLabel("Y Min:"), 0, 0)
        y_min_input = QLineEdit()
        y_min_input.setEnabled(False)
        y_min_input.setPlaceholderText("e.g., 0")
        range_layout.addWidget(y_min_input, 0, 1)

        range_layout.addWidget(QLabel("Y Max:"), 1, 0)
        y_max_input = QLineEdit()
        y_max_input.setEnabled(False)
        y_max_input.setPlaceholderText("e.g., 100")
        range_layout.addWidget(y_max_input, 1, 1)

        layout.addLayout(range_layout)

        # Connect checkbox to enable/disable inputs
        auto_check.stateChanged.connect(
            lambda state, min_input=y_min_input, max_input=y_max_input: self._toggle_inputs(
                min_input, max_input, state == Qt.Checked
            )
        )

        # Store references
        self.axis_controls[pv_attr] = {
            "auto_check": auto_check,
            "y_min": y_min_input,
            "y_max": y_max_input,
        }

        group.setLayout(layout)
        return group

    def _toggle_inputs(self, y_min_input, y_max_input, is_auto):
        """Toggle manual input fields."""
        y_min_input.setEnabled(not is_auto)
        y_max_input.setEnabled(not is_auto)

    def get_settings(self):
        """Get all axis settings from the dialog."""
        settings = {}
        for pv_attr, controls in self.axis_controls.items():
            is_auto = controls["auto_check"].isChecked()
            settings[pv_attr] = {"auto_scale": is_auto, "range": None}

            if not is_auto:
                try:
                    y_min_text = controls["y_min"].text().strip()
                    y_max_text = controls["y_max"].text().strip()

                    if y_min_text and y_max_text:
                        y_min = float(y_min_text)
                        y_max = float(y_max_text)
                        if y_min < y_max:
                            settings[pv_attr]["range"] = (y_min, y_max)
                        else:
                            settings[pv_attr]["auto_scale"] = True
                except ValueError:
                    settings[pv_attr]["auto_scale"] = True

        return settings


class LinacGroupedCryomodulePlotDisplay(Display):
    """Display with linac selector showing cryomodules in a dynamic grid."""

    # Define which PV attributes to plot from the Cryomodule class
    SELECTED_PV_ATTRIBUTES = [
        "jt_valve_readback_pv",
        "ds_level_pv",
        "us_level_pv",
        "heater_readback_pv",
        "aact_mean_sum_pv",
    ]

    # Default Y-axis ranges for each PV type
    DEFAULT_AXIS_RANGES = {
        "aact_mean_sum_pv": (0, 144),
        "ds_level_pv": (80, 100),
        "us_level_pv": (60, 80),
        "jt_valve_readback_pv": None,  # Auto-scale
        "heater_readback_pv": None,  # Auto-scale
    }

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle("Linac Cryomodule Plots")

        self.machine = Machine()
        self.cryomodule_plots = {}  # {(linac_name, cm_name): plot_display}
        self.current_linac_widget = None

        # Initialize with default settings
        self.global_axis_settings = {}
        for pv_attr, default_range in self.DEFAULT_AXIS_RANGES.items():
            if default_range:
                self.global_axis_settings[pv_attr] = {
                    "auto_scale": False,
                    "range": default_range,
                }
            else:
                self.global_axis_settings[pv_attr] = {
                    "auto_scale": True,
                    "range": None,
                }

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(2)

        # Top controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(5, 5, 5, 5)
        controls_layout.setSpacing(10)

        # Linac selector
        selector_label = QLabel("Linac:")
        controls_layout.addWidget(selector_label)

        self.linac_combo = QComboBox()
        for linac in self.machine.linacs:
            self.linac_combo.addItem(linac.name, linac)
        self.linac_combo.currentIndexChanged.connect(self.on_linac_changed)
        controls_layout.addWidget(self.linac_combo)

        controls_layout.addStretch()

        # Global axis range button
        axis_range_btn = QPushButton("Configure Y-Axis Ranges")
        axis_range_btn.clicked.connect(self.open_global_axis_range_dialog)
        controls_layout.addWidget(axis_range_btn)

        main_layout.addLayout(controls_layout)

        # Container for the linac grid
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.content_container.setLayout(self.content_layout)
        main_layout.addWidget(self.content_container)

        self.setLayout(main_layout)

        # Load first linac
        if self.linac_combo.count() > 0:
            self.on_linac_changed(0)

    def open_global_axis_range_dialog(self):
        """Open dialog to configure global Y-axis ranges."""
        dialog = GlobalAxisRangeDialog(self.SELECTED_PV_ATTRIBUTES, self)

        # Pre-populate with existing settings (which start as defaults)
        for pv_attr, controls in dialog.axis_controls.items():
            if pv_attr in self.global_axis_settings:
                settings = self.global_axis_settings[pv_attr]
                controls["auto_check"].setChecked(settings["auto_scale"])
                if settings["range"]:
                    controls["y_min"].setText(str(settings["range"][0]))
                    controls["y_max"].setText(str(settings["range"][1]))
            elif pv_attr in self.DEFAULT_AXIS_RANGES:
                # Fallback to defaults if not in settings
                default_range = self.DEFAULT_AXIS_RANGES[pv_attr]
                if default_range:
                    controls["auto_check"].setChecked(False)
                    controls["y_min"].setText(str(default_range[0]))
                    controls["y_max"].setText(str(default_range[1]))

        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.apply_global_axis_settings(settings)

    def apply_global_axis_settings(self, settings):
        """Apply global axis settings to all current plots."""
        self.global_axis_settings = settings

        # Apply to all currently loaded plots
        for (
            linac_name,
            cm_name,
        ), plot_display in self.cryomodule_plots.items():
            self._apply_settings_to_plot(plot_display)

    def _apply_settings_to_plot(self, plot_display):
        """Apply global axis settings to a specific plot."""
        plot_item = plot_display.archiver_plot.getPlotItem()

        # Apply settings to each axis based on PV attribute
        for pv_attr, setting in self.global_axis_settings.items():
            # Create axis name from PV attribute
            axis_name = pv_attr.replace("_pv", "").replace("_", " ").title()

            # Find the axis in the plot
            if hasattr(plot_item, "axes") and axis_name in plot_item.axes:
                axis_item = plot_item.axes[axis_name].get("item")

                if hasattr(axis_item, "linkedView"):
                    view_box = axis_item.linkedView()

                    if view_box:
                        if setting["auto_scale"]:
                            view_box.enableAutoRange(axis="y")
                            view_box.setAutoVisible(y=True)
                            view_box.setLimits(yMin=None, yMax=None)
                        else:
                            if setting["range"]:
                                y_min, y_max = setting["range"]
                                view_box.disableAutoRange(axis="y")
                                view_box.setAutoVisible(y=False)
                                view_box.setYRange(y_min, y_max, padding=0)
                                view_box.setLimits(yMin=y_min, yMax=y_max)
                                view_box.updateViewRange()

        # Force update
        plot_item.update()
        plot_display.archiver_plot.update()

    def _calculate_grid_dimensions(self, num_items):
        """
        Calculate grid dimensions aiming for a square or near-square layout.

        Args:
            num_items: Number of items to arrange in grid

        Returns:
            tuple: (num_columns, num_rows)
        """
        if num_items == 0:
            return (0, 0)

        cols = math.ceil(math.sqrt(num_items))
        rows = math.ceil(num_items / cols)

        return (cols, rows)

    def on_linac_changed(self, index):
        """Handle linac selection change."""
        linac = self.linac_combo.itemData(index)
        if not linac:
            return

        # Clear current content
        if self.current_linac_widget:
            self.content_layout.removeWidget(self.current_linac_widget)
            self.current_linac_widget.setParent(None)
            self.current_linac_widget.deleteLater()

        # Clear current plots from tracking (but keep settings)
        self.cryomodule_plots.clear()

        # Create new linac widget
        self.current_linac_widget = self._create_linac_widget(linac)
        self.content_layout.addWidget(self.current_linac_widget)

        # Apply global axis settings to new plots
        if self.global_axis_settings:
            for plot_display in self.cryomodule_plots.values():
                self._apply_settings_to_plot(plot_display)

    def _create_linac_widget(self, linac):
        """Create a widget for a linac with cryomodules in a dynamic grid layout."""
        linac_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Get cryomodules for this linac (sorted)
        cryomodules = sorted(linac.cryomodules.keys())

        if not cryomodules:
            no_cm_label = QLabel(f"No cryomodules found for {linac.name}")
            no_cm_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(no_cm_label)
        else:
            # Grid layout
            grid_layout = QGridLayout()
            grid_layout.setSpacing(3)
            grid_layout.setContentsMargins(0, 0, 0, 0)

            # Calculate grid dimensions
            num_cms = len(cryomodules)
            columns, rows = self._calculate_grid_dimensions(num_cms)

            # Create plot for each cryomodule
            for idx, cm_name in enumerate(cryomodules):
                row = idx // columns
                col = idx % columns

                cm_obj = linac.cryomodules[cm_name]

                plot_widget = self._create_cryomodule_plot_widget(
                    linac.name, cm_obj
                )

                grid_layout.addWidget(plot_widget, row, col)
                grid_layout.setRowStretch(row, 1)
                grid_layout.setColumnStretch(col, 1)

            layout.addLayout(grid_layout, 1)

        linac_widget.setLayout(layout)
        return linac_widget

    def _create_cryomodule_plot_widget(self, linac_name, cryomodule):
        """Create a plot widget for a specific cryomodule."""
        group = QGroupBox(f"CM {cryomodule.name}")
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # Use the embeddable plot component
        plot_widget = EmbeddableArchiverPlot(title=f"CM {cryomodule.name}")

        # Add PVs
        self._add_pvs_to_plot(plot_widget, cryomodule)

        # Store reference
        self.cryomodule_plots[(linac_name, cryomodule.name)] = plot_widget

        layout.addWidget(plot_widget)
        group.setLayout(layout)

        return group

    def _add_pvs_to_plot(self, plot_widget, cryomodule):
        """Add PVs directly from cryomodule object attributes."""
        for idx, pv_attr in enumerate(self.SELECTED_PV_ATTRIBUTES):
            if hasattr(cryomodule, pv_attr):
                pv_name = getattr(cryomodule, pv_attr)
                if pv_name:
                    label = pv_attr.replace("_pv", "").replace("_", " ").title()

                    plot_widget.add_pv(
                        pv_name=pv_name,
                        label=label,
                        axis_name=label,
                        color=plot_widget._get_rainbow_color(
                            idx, len(self.SELECTED_PV_ATTRIBUTES)
                        ),
                    )

    def _hide_selection_panel(self, plot_display):
        """Hide the left selection panel and other UI elements from the plot display."""
        if hasattr(plot_display, "children"):
            for child in plot_display.children():
                if hasattr(child, "widget") and hasattr(child, "setSizes"):
                    # Hide left panel
                    left_panel = child.widget(0)
                    if left_panel:
                        left_panel.setVisible(False)

                    # Hide extra UI in right panel
                    right_panel = child.widget(1)
                    if right_panel:
                        if hasattr(right_panel, "children"):
                            for widget in right_panel.findChildren(QWidget):
                                if isinstance(widget, QGroupBox):
                                    if (
                                        "Currently Plotted" in widget.title()
                                        or "Plot Controls" in widget.title()
                                    ):
                                        widget.setVisible(False)

                    child.setSizes([0, 1000])
                    break

    def ui_filename(self):
        """Return None since we're building UI programmatically."""
        return None


if __name__ == "__main__":
    from pydm import PyDMApplication
    import sys

    app = PyDMApplication()
    display = LinacGroupedCryomodulePlotDisplay()
    display.show()
    sys.exit(app.exec_())
