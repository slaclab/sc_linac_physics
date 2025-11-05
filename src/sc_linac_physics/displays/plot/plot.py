from PyQt5.QtWidgets import QListWidgetItem
from pydm import Display
from pydm.widgets import PyDMLabel
from pydm.widgets.timeplot import PyDMTimePlot
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

from sc_linac_physics.displays.plot.utils import get_pvs_all_groupings
from sc_linac_physics.utils.sc_linac.linac import Machine


class PVGroupArchiverDisplay(Display):
    """
    PyDM Display for selecting and plotting PV groups from the accelerator hierarchy
    using the archiver time plot.
    """

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)

        # Initialize machine and get PV groupings
        self.machine = Machine()
        self.pv_groups = get_pvs_all_groupings(self.machine)

        # Track which PVs are currently plotted
        self.plotted_pvs = {}  # {pv_name: True}

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
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_pv_types)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_no_pv_types)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        pv_type_layout.addLayout(button_layout)

        pv_type_group.setLayout(pv_type_layout)
        layout.addWidget(pv_type_group)

        # Action buttons
        action_group = QGroupBox("4. Actions")
        action_layout = QVBoxLayout()

        self.add_btn = QPushButton("Add to Plot")
        self.add_btn.clicked.connect(self.add_selected_pvs)
        self.add_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;"
        )
        action_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_pvs)
        self.remove_btn.setStyleSheet(
            "background-color: #f44336; color: white; font-weight: bold; padding: 8px;"
        )
        action_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_all_pvs)
        self.clear_btn.setStyleSheet("padding: 8px;")
        action_layout.addWidget(self.clear_btn)

        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # Plot controls (moved from plot panel)
        plot_control_group = QGroupBox("5. Plot Controls")
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

        plotted_group.setLayout(plotted_layout)
        layout.addWidget(plotted_group)

        layout.addStretch()
        panel.setLayout(layout)

        # Initialize with Machine level
        self.on_level_changed("Machine")

        return panel

    def create_plot_panel(self):
        """Create the time plot panel."""
        panel = QWidget()
        layout = QVBoxLayout()

        # Title
        header_layout = QHBoxLayout()

        title = PyDMLabel()
        title.setText("Time Plot")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Time plot
        self.time_plot = PyDMTimePlot()

        # Set to fixed rate update mode
        self.time_plot.updateMode = updateMode.AtFixedRate

        # Enable legend
        self.time_plot.showLegend = True

        # Set default time span (1 hour)
        self.time_plot.setTimeSpan(3600)

        layout.addWidget(self.time_plot)

        panel.setLayout(layout)
        return panel

    def on_show_legend_changed(self, state):
        """Handle legend visibility change."""
        show_legend = state == Qt.Checked
        self.time_plot.showLegend = show_legend
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
        self.time_plot.setTimeSpan(seconds)
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
                    self.plotted_pvs[pv] = True

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
        """Remove selected PVs from the time plot."""
        selected_items = self.plotted_list.selectedItems()

        if not selected_items:
            return

        pvs_removed = 0
        for item in selected_items:
            pv = item.text()

            # Remove from tracking
            if pv in self.plotted_pvs:
                del self.plotted_pvs[pv]

            # Remove from list
            row = self.plotted_list.row(item)
            self.plotted_list.takeItem(row)
            pvs_removed += 1

        # Regenerate plot with remaining curves
        if pvs_removed > 0:
            self._regenerate_plot()

        # Update info
        self.update_info_label()

        if pvs_removed > 0:
            print(f"Removed {pvs_removed} PVs from plot")

    def clear_all_pvs(self):
        """Clear all PVs from the plot."""
        self.plotted_pvs.clear()
        self.plotted_list.clear()

        # Clear the plot
        self.time_plot.clearCurves()

        # Update info
        self.update_info_label()

        print("Cleared all PVs from plot")

    def _regenerate_plot(self):
        """Regenerate the plot with all currently selected PVs using rainbow colors."""
        # Clear all existing curves
        self.time_plot.clearCurves()

        # Re-add all curves with rainbow colors
        for index, pv in enumerate(self.plotted_pvs.keys()):
            color = self._get_rainbow_color(index)
            self.time_plot.addYChannel(pv, color=color)

        print(f"Regenerated plot with {len(self.plotted_pvs)} curves")

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
