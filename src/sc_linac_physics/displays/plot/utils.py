from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Union

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QLineEdit,
)
from qtpy.QtWidgets import QDialog, QScrollArea, QGridLayout


class AxisRangeDialog(QDialog):
    """Dialog for controlling Y-axis ranges."""

    def __init__(self, axis_names, axis_settings, parent=None):
        super().__init__(parent)
        self.axis_names = axis_names
        self.axis_settings = axis_settings
        self.axis_controls = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Y-Axis Range Control")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout()

        # Info label
        info = QLabel("Configure range settings for each Y-axis:")
        info.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info)

        # Create controls for each axis
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        for axis_name in self.axis_names:
            axis_group = self.create_axis_control(axis_name)
            scroll_layout.addWidget(axis_group)

        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.accept)
        apply_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 5px;"
        )
        close_btn = QPushButton("Cancel")
        close_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_axis_control(self, axis_name):
        """Create control widgets for a single axis."""
        group = QGroupBox(axis_name)
        layout = QVBoxLayout()

        # Auto-scale checkbox
        auto_check = QCheckBox("Auto-scale")
        current_settings = self.axis_settings.get(axis_name, {})
        auto_check.setChecked(current_settings.get("auto_scale", True))
        layout.addWidget(auto_check)

        # Manual range inputs
        range_layout = QGridLayout()
        range_layout.addWidget(QLabel("Y Min:"), 0, 0)
        y_min_input = QLineEdit()
        y_min_input.setEnabled(not auto_check.isChecked())
        if current_settings.get("range"):
            y_min_input.setText(str(current_settings["range"][0]))
        range_layout.addWidget(y_min_input, 0, 1)

        range_layout.addWidget(QLabel("Y Max:"), 1, 0)
        y_max_input = QLineEdit()
        y_max_input.setEnabled(not auto_check.isChecked())
        if current_settings.get("range"):
            y_max_input.setText(str(current_settings["range"][1]))
        range_layout.addWidget(y_max_input, 1, 1)

        layout.addLayout(range_layout)

        # Connect checkbox to enable/disable inputs
        auto_check.stateChanged.connect(
            lambda state, min_input=y_min_input, max_input=y_max_input: self.toggle_inputs(
                min_input, max_input, state == Qt.Checked
            )
        )

        # Store references
        self.axis_controls[axis_name] = {
            "auto_check": auto_check,
            "y_min": y_min_input,
            "y_max": y_max_input,
        }

        group.setLayout(layout)
        return group

    def toggle_inputs(self, y_min_input, y_max_input, is_auto):
        """Toggle manual input fields."""
        y_min_input.setEnabled(not is_auto)
        y_max_input.setEnabled(not is_auto)

    def get_settings(self):
        """Get all axis settings from the dialog."""
        settings = {}
        for axis_name, controls in self.axis_controls.items():
            is_auto = controls["auto_check"].isChecked()
            settings[axis_name] = {"auto_scale": is_auto, "range": None}

            if not is_auto:
                try:
                    y_min_text = controls["y_min"].text().strip()
                    y_max_text = controls["y_max"].text().strip()

                    if y_min_text and y_max_text:
                        y_min = float(y_min_text)
                        y_max = float(y_max_text)
                        if y_min < y_max:
                            settings[axis_name]["range"] = (y_min, y_max)
                        else:
                            settings[axis_name][
                                "auto_scale"
                            ] = True  # Revert to auto if invalid
                except ValueError:
                    settings[axis_name][
                        "auto_scale"
                    ] = True  # Revert to auto if invalid input

        return settings


@dataclass
class PVGroup:
    """Container for PVs grouped by attribute name with source level."""

    pvs: Dict[Tuple[str, str], List[str]] = field(
        default_factory=dict
    )  # {(source_level, pv_type): [pvs]}

    def __getitem__(self, key: Union[str, Tuple[str, str]]) -> List[str]:
        """Allow dictionary-style access."""
        if isinstance(key, str):
            # If just a string, return all PVs with that name regardless of source
            result = []
            for (source, pv_type), pvs in self.pvs.items():
                if pv_type == key:
                    result.extend(pvs)
            return result
        else:
            # If tuple, return PVs from specific source
            return self.pvs.get(key, [])

    def __repr__(self):
        num_types = len(self.pvs)
        total_pvs = sum(len(v) for v in self.pvs.values())
        return f"PVGroup({num_types} types, {total_pvs} total PVs)"


@dataclass
class LinacPVs:
    """PVs organized by linac."""

    name: str
    pvs: PVGroup = field(default_factory=PVGroup)


@dataclass
class CryomodulePVs:
    """PVs organized by cryomodule."""

    name: str
    linac_name: str
    pvs: PVGroup = field(default_factory=PVGroup)


@dataclass
class RackPVs:
    """PVs organized by rack."""

    rack_name: str
    cryomodule_name: str
    linac_name: str
    pvs: PVGroup = field(default_factory=PVGroup)


@dataclass
class CavityPVs:
    """PVs organized by cavity."""

    number: int
    rack_name: str
    cryomodule_name: str
    linac_name: str
    pvs: PVGroup = field(default_factory=PVGroup)


@dataclass
class MachinePVs:
    """PVs organized by machine."""

    pvs: PVGroup = field(default_factory=PVGroup)


@dataclass
class HierarchicalPVs:
    """All PVs organized by different hierarchy levels."""

    machine: MachinePVs = field(default_factory=MachinePVs)
    linacs: Dict[str, LinacPVs] = field(default_factory=dict)
    cryomodules: Dict[str, CryomodulePVs] = field(default_factory=dict)
    racks: Dict[tuple, RackPVs] = field(
        default_factory=dict
    )  # (cm_name, rack_name)
    cavities: Dict[tuple, CavityPVs] = field(
        default_factory=dict
    )  # (cm_name, cav_num)

    def get_machine(self) -> MachinePVs:
        """Get PVs for the machine."""
        return self.machine

    def get_linac(self, name: str) -> LinacPVs:
        """Get PVs for a specific linac."""
        return self.linacs.get(name)

    def get_cryomodule(self, name: str) -> CryomodulePVs:
        """Get PVs for a specific cryomodule."""
        return self.cryomodules.get(name)

    def get_rack(self, cm_name: str, rack_name: str) -> RackPVs:
        """Get PVs for a specific rack."""
        return self.racks.get((cm_name, rack_name))

    def get_cavity(self, cm_name: str, cav_num: int) -> CavityPVs:
        """Get PVs for a specific cavity."""
        return self.cavities.get((cm_name, cav_num))


def _is_pv_attribute(attr_name: str) -> bool:
    """Check if attribute name indicates it's a PV."""
    return (
        attr_name.endswith("_pv") or attr_name.endswith("_pvs")
    ) and not attr_name.endswith("_pv_obj")


class PVExtractor:
    """Helper class to extract PVs from hierarchy and organize them."""

    HIERARCHY = {
        "Machine": ["linacs", "cryomodules"],
        "Linac": ["cryomodules"],
        "Cryomodule": ["rack_a", "rack_b", "quad", "xcor", "ycor"],
        "Rack": ["rfs1", "rfs2", "cavities"],
        "Cavity": ["stepper_tuner", "piezo", "ssa"],
        "Magnet": [],
        "RFStation": [],
        "SSA": [],
        "Piezo": [],
        "StepperTuner": [],
    }

    def __init__(self):
        self.result = HierarchicalPVs()
        self.processed_objects = set()
        self.context = {
            "machine": None,
            "linac_name": None,
            "cryomodule_name": None,
            "rack_name": None,
            "cavity_number": None,
        }

    def update_context(self, obj_type: str, current_obj: Any):
        """Update the context based on object type."""
        if obj_type == "Machine":
            self.context["machine"] = current_obj
        elif obj_type == "Linac":
            self.context["linac_name"] = current_obj.name
        elif obj_type == "Cryomodule":
            self.context["cryomodule_name"] = current_obj.name
        elif obj_type == "Rack":
            self.context["rack_name"] = current_obj.rack_name
        elif obj_type == "Cavity":
            self.context["cavity_number"] = current_obj.number

    def add_to_machine_group(self, pv_key: Tuple[str, str], pv_list: List[str]):
        """Add PVs to machine grouping."""
        if self.context["machine"]:
            if pv_key not in self.result.machine.pvs.pvs:
                self.result.machine.pvs.pvs[pv_key] = []
            self.result.machine.pvs.pvs[pv_key].extend(pv_list)

    def add_to_linac_group(self, pv_key: Tuple[str, str], pv_list: List[str]):
        """Add PVs to linac grouping."""
        if not self.context["linac_name"]:
            return

        linac_name = self.context["linac_name"]
        if linac_name not in self.result.linacs:
            self.result.linacs[linac_name] = LinacPVs(
                name=linac_name, pvs=PVGroup()
            )
        if pv_key not in self.result.linacs[linac_name].pvs.pvs:
            self.result.linacs[linac_name].pvs.pvs[pv_key] = []
        self.result.linacs[linac_name].pvs.pvs[pv_key].extend(pv_list)

    def add_to_cryomodule_group(
        self, pv_key: Tuple[str, str], pv_list: List[str]
    ):
        """Add PVs to cryomodule grouping."""
        if not self.context["cryomodule_name"]:
            return

        cm_name = self.context["cryomodule_name"]
        if cm_name not in self.result.cryomodules:
            self.result.cryomodules[cm_name] = CryomodulePVs(
                name=cm_name,
                linac_name=self.context["linac_name"],
                pvs=PVGroup(),
            )
        if pv_key not in self.result.cryomodules[cm_name].pvs.pvs:
            self.result.cryomodules[cm_name].pvs.pvs[pv_key] = []
        self.result.cryomodules[cm_name].pvs.pvs[pv_key].extend(pv_list)

    def add_to_rack_group(self, pv_key: Tuple[str, str], pv_list: List[str]):
        """Add PVs to rack grouping."""
        if not self.context["rack_name"]:
            return

        rack_key = (self.context["cryomodule_name"], self.context["rack_name"])
        if rack_key not in self.result.racks:
            self.result.racks[rack_key] = RackPVs(
                rack_name=self.context["rack_name"],
                cryomodule_name=self.context["cryomodule_name"],
                linac_name=self.context["linac_name"],
                pvs=PVGroup(),
            )
        if pv_key not in self.result.racks[rack_key].pvs.pvs:
            self.result.racks[rack_key].pvs.pvs[pv_key] = []
        self.result.racks[rack_key].pvs.pvs[pv_key].extend(pv_list)

    def add_to_cavity_group(self, pv_key: Tuple[str, str], pv_list: List[str]):
        """Add PVs to cavity grouping."""
        if not self.context["cavity_number"]:
            return

        cavity_key = (
            self.context["cryomodule_name"],
            self.context["cavity_number"],
        )
        if cavity_key not in self.result.cavities:
            self.result.cavities[cavity_key] = CavityPVs(
                number=self.context["cavity_number"],
                rack_name=self.context["rack_name"],
                cryomodule_name=self.context["cryomodule_name"],
                linac_name=self.context["linac_name"],
                pvs=PVGroup(),
            )
        if pv_key not in self.result.cavities[cavity_key].pvs.pvs:
            self.result.cavities[cavity_key].pvs.pvs[pv_key] = []
        self.result.cavities[cavity_key].pvs.pvs[pv_key].extend(pv_list)

    def add_to_all_groups(self, pv_key: Tuple[str, str], pv_list: List[str]):
        """Add PVs to all applicable hierarchy groups."""
        self.add_to_machine_group(pv_key, pv_list)
        self.add_to_linac_group(pv_key, pv_list)
        self.add_to_cryomodule_group(pv_key, pv_list)
        self.add_to_rack_group(pv_key, pv_list)
        self.add_to_cavity_group(pv_key, pv_list)

    def process_child_container(self, child_container: Any):
        """Process a child container (dict, list, or single object)."""
        if isinstance(child_container, dict):
            for child_obj in child_container.values():
                self.extract_pvs(child_obj)
        elif isinstance(child_container, (list, tuple)):
            for child_obj in child_container:
                self.extract_pvs(child_obj)
        else:
            self.extract_pvs(child_container)

    def extract_pvs(self, current_obj: Any):
        """Recursively extract PVs from an object and its children."""
        obj_id = id(current_obj)
        if obj_id in self.processed_objects:
            return
        self.processed_objects.add(obj_id)

        obj_type = type(current_obj).__name__
        self.update_context(obj_type, current_obj)

        # Extract PVs
        for attr, value in vars(current_obj).items():
            if _is_pv_attribute(attr):
                pv_list = value if isinstance(value, list) else [value]
                pv_key = (obj_type, attr)
                self.add_to_all_groups(pv_key, pv_list)

        # Recursive traversal
        child_attrs = self.HIERARCHY.get(obj_type, [])
        for child_attr in child_attrs:
            child_container = getattr(current_obj, child_attr, None)
            if child_container is not None:
                self.process_child_container(child_container)


def get_pvs_all_groupings(obj: Any) -> HierarchicalPVs:
    """
    Extract PVs grouped by ALL hierarchy levels in a single traversal.

    Args:
        obj: Root object (typically Machine or Linac)

    Returns:
        HierarchicalPVs object with PVs organized by machine, linac, cryomodule, rack, and cavity.

    Examples:
        machine = Machine()
        all_pvs = get_pvs_all_groupings(machine)

        # Access machine-level PVs
        machine_pvs = all_pvs.get_machine()

        # Access linac-level PVs
        l0b_pvs = all_pvs.get_linac('L0B')
    """
    extractor = PVExtractor()
    extractor.extract_pvs(obj)
    return extractor.result
