from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Union


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
        context_map = {
            "Machine": ("machine", current_obj),
            "Linac": ("linac_name", current_obj.name),
            "Cryomodule": ("cryomodule_name", current_obj.name),
            "Rack": ("rack_name", current_obj.rack_name),
            "Cavity": ("cavity_number", current_obj.number),
        }
        if obj_type in context_map:
            key, value = context_map[obj_type]
            self.context[key] = value

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
