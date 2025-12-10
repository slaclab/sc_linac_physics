from PyQt5.QtWidgets import QListWidgetItem, QDialog, QMessageBox
from pydm import Display
from pydm.widgets import PyDMLabel, PyDMArchiverTimePlot
from pydm.widgets.timeplot import updateMode
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QComboBox,
    QListWidget,
    QGroupBox,
    QPushButton,
    QSplitter,
    QCheckBox,
    QLineEdit,
    QLabel,
)

from sc_linac_physics.displays.plot.utils import (
    get_pvs_all_groupings,
    AxisRangeDialog,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


class PVGroupArchiverDisplay(Display):
    """
    PyDM Display for selecting and plotting PV groups from the accelerator hierarchy
    using the archiver time plot.
    """

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle("SC Linac Physics Plotter")

        # Initialize machine and get PV groupings
        self.machine = Machine()
        self.pv_groups = get_pvs_all_groupings(self.machine)

        # Track which PVs are currently plotted
        self.plotted_pvs = {}  # {pv_name: pv_key}
        self.pv_curves = {}  # {pv_name: curve_object}
        self.axis_settings = (
            {}
        )  # {axis_name: {'auto_scale': bool, 'range': (min, max)}}

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        main_layout = QVBoxLayout()

        # Create splitter for selection panel and plot
        splitter = QSplitter(Qt.Horizontal)

        # Left panel: Selection controls
        selection_panel = self.create_selection_panel()
        splitter.addWidget(selection_panel)

        # Right panel: Archiver time plot
        plot_panel = self.create_plot_panel()
        splitter.addWidget(plot_panel)

        # Set initial splitter sizes (30% selection, 70% plot)
        splitter.setSizes([300, 700])

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def create_selection_panel(self):
        """Create the PV selection panel."""
        panel = QWidget()
        layout = QVBoxLayout()

        # Hierarchy level selection
        level_group = QGroupBox("1. Select Hierarchy Level")
        level_layout = QVBoxLayout()

        self.level_combo = QComboBox()
        self.level_combo.addItems(
            ["Machine", "Linac", "Cryomodule", "Rack", "Cavity"]
        )
        self.level_combo.currentTextChanged.connect(self.on_level_changed)
        level_layout.addWidget(self.level_combo)

        level_group.setLayout(level_layout)
        layout.addWidget(level_group)

        # Object selection
        object_group = QGroupBox("2. Select Object")
        object_layout = QVBoxLayout()

        self.object_combo = QComboBox()
        self.object_combo.currentTextChanged.connect(self.on_object_changed)
        object_layout.addWidget(self.object_combo)

        object_group.setLayout(object_layout)
        layout.addWidget(object_group)

        # PV type selection
        pv_type_group = QGroupBox("3. Select PV Types")
        pv_type_layout = QVBoxLayout()

        # Filter box
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter PV types...")
        self.filter_edit.textChanged.connect(self.filter_pv_types)
        pv_type_layout.addWidget(self.filter_edit)

        # PV type list
        self.pv_type_list = QListWidget()
        self.pv_type_list.setSelectionMode(QListWidget.MultiSelection)
        pv_type_layout.addWidget(self.pv_type_list)

        # Select all/none buttons
        selection_button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_pv_types)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_no_pv_types)
        selection_button_layout.addWidget(select_all_btn)
        selection_button_layout.addWidget(select_none_btn)
        pv_type_layout.addLayout(selection_button_layout)

        # Add to Plot button
        self.add_btn = QPushButton("Add to Plot")
        self.add_btn.clicked.connect(self.add_selected_pvs)
        self.add_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;"
        )
        pv_type_layout.addWidget(self.add_btn)

        pv_type_group.setLayout(pv_type_layout)
        layout.addWidget(pv_type_group)

        # Plot controls
        plot_control_group = QGroupBox("4. Plot Controls")
        plot_control_layout = QVBoxLayout()

        # Time range controls
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Time Range:"))

        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(
            [
                "5 minutes",
                "15 minutes",
                "30 minutes",
                "1 hour",
                "2 hours",
                "6 hours",
                "12 hours",
                "24 hours",
            ]
        )
        self.time_range_combo.setCurrentText("1 hour")
        self.time_range_combo.currentTextChanged.connect(
            self.on_time_range_changed
        )
        time_layout.addWidget(self.time_range_combo)
        plot_control_layout.addLayout(time_layout)

        # Legend controls
        self.show_legend_check = QCheckBox("Show Legend")
        self.show_legend_check.setChecked(True)
        self.show_legend_check.stateChanged.connect(self.on_show_legend_changed)
        plot_control_layout.addWidget(self.show_legend_check)

        # Y-axis range control button
        axis_range_btn = QPushButton("Configure Y-Axis Ranges")
        axis_range_btn.clicked.connect(self.open_axis_range_dialog)
        plot_control_layout.addWidget(axis_range_btn)

        plot_control_group.setLayout(plot_control_layout)
        layout.addWidget(plot_control_group)

        # Currently plotted PVs
        plotted_group = QGroupBox("Currently Plotted PVs")
        plotted_layout = QVBoxLayout()

        self.plotted_list = QListWidget()
        self.plotted_list.setSelectionMode(QListWidget.MultiSelection)
        plotted_layout.addWidget(self.plotted_list)

        # Info label
        self.info_label = PyDMLabel()
        self.info_label.setText("0 PVs plotted")
        plotted_layout.addWidget(self.info_label)

        # Remove and Clear buttons
        plotted_button_layout = QHBoxLayout()

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_pvs)
        self.remove_btn.setStyleSheet(
            "background-color: #ff5252; color: white; font-weight: bold; padding: 8px;"
        )
        plotted_button_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_all_pvs)
        self.clear_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; font-weight: bold; padding: 8px;"
        )
        plotted_button_layout.addWidget(self.clear_btn)

        plotted_layout.addLayout(plotted_button_layout)

        plotted_group.setLayout(plotted_layout)
        layout.addWidget(plotted_group)

        layout.addStretch()
        panel.setLayout(layout)

        # Initialize with Machine level
        self.on_level_changed("Machine")

        return panel

    def create_plot_panel(self):
        """Create the archiver time plot panel."""
        panel = QWidget()
        layout = QVBoxLayout()

        # Archiver time plot
        self.archiver_plot = PyDMArchiverTimePlot()

        # Set to fixed rate update mode
        self.archiver_plot.updateMode = updateMode.AtFixedRate

        # Enable legend - PyDM handles it automatically
        self.archiver_plot.showLegend = True

        # Set default time span (1 hour)
        self.archiver_plot.setTimeSpan(3600)

        # Get reference to legend and ensure it's visible
        plot_item = self.archiver_plot.getPlotItem()
        self.legend = plot_item.legend

        if self.legend:
            self.legend.setVisible(True)
            self.legend.show()

        layout.addWidget(self.archiver_plot)

        panel.setLayout(layout)
        return panel

    def on_show_legend_changed(self, state):
        """Handle legend visibility change."""
        show_legend = state == Qt.Checked

        if self.legend:
            self.legend.setVisible(show_legend)

        print(f"Legend {'shown' if show_legend else 'hidden'}")

    def on_time_range_changed(self, time_range_text):
        """Handle time range change."""
        time_map = {
            "5 minutes": 5 * 60,
            "15 minutes": 15 * 60,
            "30 minutes": 30 * 60,
            "1 hour": 3600,
            "2 hours": 2 * 3600,
            "6 hours": 6 * 3600,
            "12 hours": 12 * 3600,
            "24 hours": 24 * 3600,
            "2 days": 2 * 24 * 3600,
            "7 days": 7 * 24 * 3600,
        }

        seconds = time_map.get(time_range_text, 3600)
        self.archiver_plot.setTimeSpan(seconds)
        print(f"Time range set to {time_range_text}")

    def on_level_changed(self, level):
        """Handle hierarchy level change."""
        self.object_combo.clear()

        if level == "Machine":
            # For machine level, leave object selection empty
            # Directly trigger PV list population
            pv_group = self.pv_groups.get_machine()
            self.pv_type_list.clear()
            self.filter_edit.clear()
            if pv_group:
                self._populate_pv_type_list(pv_group)
        elif level == "Linac":
            objects = sorted(self.pv_groups.linacs.keys())
            self.object_combo.addItems(objects)
        elif level == "Cryomodule":
            objects = sorted(self.pv_groups.cryomodules.keys())
            self.object_combo.addItems(objects)
        elif level == "Rack":
            objects = [
                f"CM{cm} Rack {rack}"
                for cm, rack in sorted(self.pv_groups.racks.keys())
            ]
            self.object_combo.addItems(objects)
        elif level == "Cavity":
            objects = [
                f"CM{cm} Cavity {cav}"
                for cm, cav in sorted(self.pv_groups.cavities.keys())
            ]
            self.object_combo.addItems(objects)

    def on_object_changed(self, object_name):
        """Handle object selection change."""
        if not object_name:
            return

        level = self.level_combo.currentText()

        # Get the PV group for this object
        pv_group = self._get_pv_group(level, object_name)

        # Update PV type list
        self.pv_type_list.clear()
        self.filter_edit.clear()

        if pv_group:
            self._populate_pv_type_list(pv_group)

    def _get_pv_group(self, level, object_name):
        """Get PV group based on level and object name."""
        if level == "Machine":
            return self.pv_groups.get_machine()
        elif level == "Linac":
            return self.pv_groups.get_linac(object_name)
        elif level == "Cryomodule":
            return self.pv_groups.get_cryomodule(object_name)
        elif level == "Rack":
            parts = object_name.split()
            cm_name = parts[0].replace("CM", "")
            rack_name = parts[2]
            return self.pv_groups.get_rack(cm_name, rack_name)
        elif level == "Cavity":
            parts = object_name.split()
            cm_name = parts[0].replace("CM", "")
            cav_num = int(parts[2])
            return self.pv_groups.get_cavity(cm_name, cav_num)
        return None

    def filter_pv_types(self, text):
        """Filter PV types based on search text."""
        for i in range(self.pv_type_list.count()):
            item = self.pv_type_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def select_all_pv_types(self):
        """Select all visible PV types in the list."""
        for i in range(self.pv_type_list.count()):
            item = self.pv_type_list.item(i)
            if not item.isHidden():
                item.setSelected(True)

    def select_no_pv_types(self):
        """Deselect all PV types in the list."""
        self.pv_type_list.clearSelection()

    def _populate_pv_type_list(self, pv_group):
        """Populate the PV type list widget with source level tracking."""
        # pv_group.pvs.pvs is now Dict[(source_level, pv_type), List[str]]

        # Sort by source level, then by pv_type
        sorted_keys = sorted(
            pv_group.pvs.pvs.keys(), key=lambda x: (x[0], x[1])
        )

        for source_level, pv_type in sorted_keys:
            num_pvs = len(pv_group.pvs.pvs[(source_level, pv_type)])

            # Create display name with source indicator
            display_name = f"[{source_level}] {pv_type} ({num_pvs} PVs)"

            item = QListWidgetItem(display_name)
            # Store the full key (source_level, pv_type)
            item.setData(Qt.UserRole, (source_level, pv_type))
            self.pv_type_list.addItem(item)

    def add_selected_pvs(self):
        """Add selected PVs to the time plot with rainbow colors."""
        level = self.level_combo.currentText()

        # For Machine level, object_name is not needed
        if level == "Machine":
            pv_group = self.pv_groups.get_machine()
        else:
            object_name = self.object_combo.currentText()

            if not object_name:
                return

            pv_group = self._get_pv_group(level, object_name)

        if not pv_group:
            return

        selected_items = self.pv_type_list.selectedItems()

        pvs_added = 0
        for item in selected_items:
            # Get the full key (source_level, pv_type)
            pv_key = item.data(Qt.UserRole)
            pvs = pv_group.pvs[pv_key]

            for pv in pvs:
                if pv not in self.plotted_pvs:
                    # Store both the PV and its key (source_level, pv_type)
                    self.plotted_pvs[pv] = pv_key

                    # Add to plotted list
                    self.plotted_list.addItem(pv)
                    pvs_added += 1

        # Regenerate plot with all curves
        if pvs_added > 0:
            self._regenerate_plot()

        # Update info
        self.update_info_label()

        if pvs_added > 0:
            print(f"Added {pvs_added} PVs to plot")

    def remove_selected_pvs(self):
        """Remove selected PVs from the archiver time plot."""
        selected_items = self.plotted_list.selectedItems()

        if not selected_items:
            return

        pvs_removed = 0
        for item in selected_items:
            pv = item.text()

            # Remove from tracking
            if pv in self.plotted_pvs:
                del self.plotted_pvs[pv]

            if pv in self.pv_curves:
                del self.pv_curves[pv]

            # Remove from list
            row = self.plotted_list.row(item)
            self.plotted_list.takeItem(row)
            pvs_removed += 1

        # Regenerate plot with remaining curves (this will handle axis cleanup)
        if pvs_removed > 0:
            self._regenerate_plot()

            # Clean up axis settings for axes that no longer exist
            self._cleanup_axis_settings()

        # Update info
        self.update_info_label()

        if pvs_removed > 0:
            print(f"Removed {pvs_removed} PVs from plot")

    def _cleanup_axis_settings(self):
        """Remove axis settings for axes that no longer exist in the plot."""
        # Get current axis names
        current_axes = set()
        pv_groups = self._group_pvs_by_source()

        for pv_key in pv_groups.keys():
            source_level, pv_type = pv_key
            axis_name = f"{source_level} - {pv_type}"
            current_axes.add(axis_name)

        # Remove settings for axes that no longer exist
        axes_to_remove = [
            axis_name
            for axis_name in self.axis_settings.keys()
            if axis_name not in current_axes
        ]

        for axis_name in axes_to_remove:
            del self.axis_settings[axis_name]
            print(f"Cleaned up settings for removed axis: {axis_name}")

    def clear_all_pvs(self):
        """Clear all PVs from the plot."""
        # Clear all curves at once
        self.archiver_plot.clearCurves()

        self.plotted_pvs.clear()
        self.plotted_list.clear()
        self.pv_curves.clear()
        self.axis_settings.clear()

        # Clear legend
        if self.legend:
            self.legend.clear()

        # Clear all Y axes except the default ones
        essential_axes = {"left", "bottom", "right", "top"}
        try:
            if hasattr(self.archiver_plot.plotItem, "axes"):
                # Get list of axes to remove (make a copy of keys to avoid modification during iteration)
                axes_to_remove = [
                    axis_name
                    for axis_name in list(
                        self.archiver_plot.plotItem.axes.keys()
                    )
                    if axis_name not in essential_axes
                ]

                for axis_name in axes_to_remove:
                    axis_dict = self.archiver_plot.plotItem.axes[axis_name]
                    if "item" in axis_dict:
                        # Remove the axis item from the scene
                        axis_item = axis_dict["item"]
                        self.archiver_plot.plotItem.layout.removeItem(axis_item)
                        # Also remove from the scene
                        if axis_item.scene() is not None:
                            axis_item.scene().removeItem(axis_item)
                    # Remove from axes dict
                    del self.archiver_plot.plotItem.axes[axis_name]
                    print(f"Removed axis: {axis_name}")
        except Exception as e:
            print(f"Could not clear axes: {e}")
            import traceback

            traceback.print_exc()

        # Force a redraw
        self.archiver_plot.plotItem.update()

        # Update info
        self.update_info_label()

        print("Cleared all PVs from plot")

    def _regenerate_plot(self):
        """Regenerate the plot with all currently selected PVs using rainbow colors."""
        # Clear existing plot elements
        self._clear_plot_elements()

        # Clear all custom Y axes
        self._clear_custom_axes()

        # Group PVs by their source type
        pv_groups = self._group_pvs_by_source()

        # Add all PV groups to the plot
        self._add_pv_groups_to_plot(pv_groups)

        # Ensure legend is visible
        if self.legend:
            self.legend.setVisible(True)

        print(
            f"Regenerated plot with {len(self.plotted_pvs)} curves on {len(pv_groups)} axes"
        )

    def _clear_plot_elements(self):
        """Clear all existing curves and legend items."""
        self.archiver_plot.clearCurves()
        self.pv_curves.clear()

        if self.legend:
            self.legend.clear()

    def _clear_custom_axes(self):
        """Clear all custom Y axes, preserving essential axes."""
        essential_axes = {"left", "bottom", "right", "top"}
        try:
            if hasattr(self.archiver_plot.plotItem, "axes"):
                axes_to_remove = [
                    axis_name
                    for axis_name in list(
                        self.archiver_plot.plotItem.axes.keys()
                    )
                    if axis_name not in essential_axes
                ]

                for axis_name in axes_to_remove:
                    self._remove_axis(axis_name)
        except Exception as e:
            print(f"Could not clear custom axes: {e}")

    def _remove_axis(self, axis_name):
        """Remove a specific axis from the plot."""
        axis_dict = self.archiver_plot.plotItem.axes[axis_name]
        if "item" in axis_dict:
            axis_item = axis_dict["item"]
            # Remove from layout
            self.archiver_plot.plotItem.layout.removeItem(axis_item)
            # Also remove from the scene
            if axis_item.scene() is not None:
                axis_item.scene().removeItem(axis_item)
        del self.archiver_plot.plotItem.axes[axis_name]

    def _group_pvs_by_source(self):
        """Group PVs by their source type (source_level, pv_type)."""
        pv_groups = {}
        for pv, pv_key in self.plotted_pvs.items():
            if pv_key not in pv_groups:
                pv_groups[pv_key] = []
            pv_groups[pv_key].append(pv)
        return pv_groups

    def _add_pv_groups_to_plot(self, pv_groups):
        """Add all PV groups to the plot with appropriate axes and colors."""
        plot_item = self.archiver_plot.getPlotItem()
        color_index = 0

        for pv_key, pvs in pv_groups.items():
            source_level, pv_type = pv_key
            axis_name = f"{source_level} - {pv_type}"

            # Add all PVs in this group
            for pv in pvs:
                color = self._get_rainbow_color(color_index)
                self._add_pv_to_plot(pv, axis_name, color, plot_item)
                color_index += 1

            # Set the axis label
            self._set_axis_label(axis_name)

            # Apply saved axis settings if they exist
            if axis_name in self.axis_settings:
                self._apply_single_axis_setting(
                    axis_name, self.axis_settings[axis_name]
                )

    def _apply_single_axis_setting(self, axis_name, setting):
        """Apply settings to a single axis."""
        plot_item = self.archiver_plot.getPlotItem()

        try:
            if hasattr(plot_item, "axes") and axis_name in plot_item.axes:
                axis_dict = plot_item.axes[axis_name]
                view_box = axis_dict.get("view", None)

                if view_box:
                    if setting["auto_scale"]:
                        view_box.enableAutoRange(axis="y")
                    else:
                        if setting["range"]:
                            y_min, y_max = setting["range"]
                            view_box.setYRange(y_min, y_max, padding=0)
                            view_box.disableAutoRange(axis="y")
        except Exception as e:
            print(f"Error applying setting to {axis_name}: {e}")

    def _add_pv_to_plot(self, pv, axis_name, color, plot_item):
        """Add a single PV to the plot with specified axis and color."""
        # Add the channel with specific axis - PyDM handles the legend
        self.archiver_plot.addYChannel(
            y_channel=pv,  # Use keyword argument
            name=pv,  # Add name for legend
            color=color,
            yAxisName=axis_name,
            useArchiveData=True,
        )

        # Get the curve that was just added and store it
        if len(plot_item.curves) > 0:
            curve = plot_item.curves[-1]
            self.pv_curves[pv] = curve

    def _set_axis_label(self, axis_name):
        """Set the label for a specific axis."""
        try:
            if hasattr(self.archiver_plot, "plotItem"):
                axes = self.archiver_plot.plotItem.axes
                if axes and axis_name in axes:
                    axis_item = axes[axis_name]["item"]
                    axis_item.setLabel(axis_name)
        except Exception as e:
            print(f"Could not set axis label: {e}")

    def _get_rainbow_color(self, index):
        """
        Get a color from the rainbow spectrum based on index.

        Args:
            index: The index of the curve (0-based)

        Returns:
            QColor object with rainbow color
        """
        from qtpy.QtGui import QColor
        import colorsys

        # Get total number of curves to distribute colors evenly
        total_curves = len(self.plotted_pvs)

        if total_curves == 0:
            total_curves = 1

        # Linear distribution across full hue spectrum (0 to 1)
        # This ensures maximum color separation
        hue = index / max(total_curves, 1)
        saturation = 0.9  # High saturation for vibrant colors
        value = 0.95  # High value for bright colors

        # Convert HSV to RGB (values 0-1)
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)

        # Convert to 0-255 range and create QColor
        return QColor(int(r * 255), int(g * 255), int(b * 255))

    def update_info_label(self):
        """Update the info label with current PV count."""
        count = len(self.plotted_pvs)
        self.info_label.setText(
            f"{count} PV{'s' if count != 1 else ''} plotted"
        )

    def open_axis_range_dialog(self):
        """Open dialog to configure Y-axis ranges."""
        # Get current axis names from the plot
        axis_names = []
        pv_groups = self._group_pvs_by_source()

        for pv_key in pv_groups.keys():
            source_level, pv_type = pv_key
            axis_name = f"{source_level} - {pv_type}"
            axis_names.append(axis_name)

        if not axis_names:
            QMessageBox.information(
                self,
                "No Axes",
                "No Y-axes are currently plotted. Add some PVs first.",
            )
            return

        dialog = AxisRangeDialog(axis_names, self.axis_settings, self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.apply_axis_settings(settings)

    def apply_axis_settings(self, settings):
        """Apply axis range settings to the plot."""
        # Update stored settings
        self.axis_settings.update(settings)

        plot_item = self.archiver_plot.getPlotItem()

        # Map axes to viewboxes
        for axis_name, setting in settings.items():
            # Find the axis item
            if hasattr(plot_item, "axes") and axis_name in plot_item.axes:
                axis_item = plot_item.axes[axis_name].get("item")

                # Try to find linked ViewBox
                if hasattr(axis_item, "linkedView"):
                    view_box = axis_item.linkedView()

                    if view_box:
                        if setting["auto_scale"]:
                            view_box.enableAutoRange(axis="y")
                            view_box.setAutoVisible(y=True)
                        else:
                            if setting["range"]:
                                y_min, y_max = setting["range"]

                                # Disable auto-range first
                                view_box.disableAutoRange(axis="y")
                                view_box.setAutoVisible(y=False)

                                # Set the range
                                view_box.setYRange(y_min, y_max, padding=0)

                                # Set limits to prevent auto-scaling
                                view_box.setLimits(yMin=y_min, yMax=y_max)

                                # Force immediate update
                                view_box.updateViewRange()

        # Force a redraw of the entire plot
        plot_item.update()
        self.archiver_plot.update()

    def ui_filename(self):
        """Return None since we're building UI programmatically."""
        return None


if __name__ == "__main__":
    from pydm import PyDMApplication
    import sys

    app = PyDMApplication()
    display = PVGroupArchiverDisplay()
    display.show()
    sys.exit(app.exec_())
