from unittest.mock import Mock

import pytest

from sc_linac_physics.displays.plot.utils import (
    PVGroup,
    LinacPVs,
    CryomodulePVs,
    RackPVs,
    CavityPVs,
    MachinePVs,
    HierarchicalPVs,
    PVExtractor,
    get_pvs_all_groupings,
    _is_pv_attribute,
)


class TestPVGroup:
    """Test PVGroup dataclass."""

    def test_pv_group_creation(self):
        """Test creating a PVGroup."""
        pv_group = PVGroup()
        assert pv_group.pvs == {}

    def test_pv_group_with_data(self):
        """Test PVGroup with data."""
        pv_group = PVGroup()
        pv_group.pvs[("Cavity", "ades_pv")] = ["ACCL:L1B:0210:ADES"]

        assert len(pv_group.pvs) == 1
        assert pv_group.pvs[("Cavity", "ades_pv")] == ["ACCL:L1B:0210:ADES"]

    def test_pv_group_getitem_with_tuple(self):
        """Test accessing PVs with tuple key."""
        pv_group = PVGroup()
        pv_group.pvs[("Cavity", "ades_pv")] = ["ACCL:L1B:0210:ADES"]

        result = pv_group[("Cavity", "ades_pv")]
        assert result == ["ACCL:L1B:0210:ADES"]

    def test_pv_group_getitem_with_string(self):
        """Test accessing PVs with string key (gets all matching)."""
        pv_group = PVGroup()
        pv_group.pvs[("Cavity", "ades_pv")] = ["ACCL:L1B:0210:ADES"]
        pv_group.pvs[("Linac", "ades_pv")] = ["ACCL:L1B:ADES"]

        result = pv_group["ades_pv"]
        assert len(result) == 2
        assert "ACCL:L1B:0210:ADES" in result
        assert "ACCL:L1B:ADES" in result

    def test_pv_group_getitem_missing_key(self):
        """Test accessing non-existent key returns empty list."""
        pv_group = PVGroup()
        result = pv_group[("Cavity", "nonexistent_pv")]
        assert result == []

        result = pv_group["nonexistent_pv"]
        assert result == []


class TestHierarchicalPVsDataClasses:
    """Test hierarchical PV dataclasses."""

    def test_machine_pvs_creation(self):
        """Test MachinePVs creation."""
        machine_pvs = MachinePVs()
        assert machine_pvs.pvs is not None
        assert isinstance(machine_pvs.pvs, PVGroup)

    def test_linac_pvs_creation(self):
        """Test LinacPVs creation."""
        linac_pvs = LinacPVs(name="L0B", pvs=PVGroup())
        assert linac_pvs.name == "L0B"
        assert isinstance(linac_pvs.pvs, PVGroup)

    def test_cryomodule_pvs_creation(self):
        """Test CryomodulePVs creation."""
        cm_pvs = CryomodulePVs(name="02", linac_name="L1B", pvs=PVGroup())
        assert cm_pvs.name == "02"
        assert cm_pvs.linac_name == "L1B"
        assert isinstance(cm_pvs.pvs, PVGroup)

    def test_rack_pvs_creation(self):
        """Test RackPVs creation."""
        rack_pvs = RackPVs(
            rack_name="A", cryomodule_name="02", linac_name="L1B", pvs=PVGroup()
        )
        assert rack_pvs.rack_name == "A"
        assert rack_pvs.cryomodule_name == "02"
        assert rack_pvs.linac_name == "L1B"

    def test_cavity_pvs_creation(self):
        """Test CavityPVs creation."""
        cavity_pvs = CavityPVs(
            number=1,
            rack_name="A",
            cryomodule_name="02",
            linac_name="L1B",
            pvs=PVGroup(),
        )
        assert cavity_pvs.number == 1
        assert cavity_pvs.rack_name == "A"
        assert cavity_pvs.cryomodule_name == "02"
        assert cavity_pvs.linac_name == "L1B"


class TestHierarchicalPVs:
    """Test HierarchicalPVs container."""

    def test_hierarchical_pvs_creation(self):
        """Test HierarchicalPVs creation."""
        hier_pvs = HierarchicalPVs()
        assert isinstance(hier_pvs.machine, MachinePVs)
        assert hier_pvs.linacs == {}
        assert hier_pvs.cryomodules == {}
        assert hier_pvs.racks == {}
        assert hier_pvs.cavities == {}

    def test_get_machine(self):
        """Test get_machine method."""
        hier_pvs = HierarchicalPVs()
        machine = hier_pvs.get_machine()
        assert machine is hier_pvs.machine

    def test_get_linac(self):
        """Test get_linac method."""
        hier_pvs = HierarchicalPVs()
        linac_pvs = LinacPVs(name="L0B", pvs=PVGroup())
        hier_pvs.linacs["L0B"] = linac_pvs

        result = hier_pvs.get_linac("L0B")
        assert result is linac_pvs

        # Test missing linac
        result = hier_pvs.get_linac("L9B")
        assert result is None

    def test_get_cryomodule(self):
        """Test get_cryomodule method."""
        hier_pvs = HierarchicalPVs()
        cm_pvs = CryomodulePVs(name="02", linac_name="L1B", pvs=PVGroup())
        hier_pvs.cryomodules["02"] = cm_pvs

        result = hier_pvs.get_cryomodule("02")
        assert result is cm_pvs

    def test_get_rack(self):
        """Test get_rack method."""
        hier_pvs = HierarchicalPVs()
        rack_pvs = RackPVs(
            rack_name="A", cryomodule_name="02", linac_name="L1B", pvs=PVGroup()
        )
        hier_pvs.racks[("02", "A")] = rack_pvs

        result = hier_pvs.get_rack("02", "A")
        assert result is rack_pvs

    def test_get_cavity(self):
        """Test get_cavity method."""
        hier_pvs = HierarchicalPVs()
        cavity_pvs = CavityPVs(
            number=1,
            rack_name="A",
            cryomodule_name="02",
            linac_name="L1B",
            pvs=PVGroup(),
        )
        hier_pvs.cavities[("02", 1)] = cavity_pvs

        result = hier_pvs.get_cavity("02", 1)
        assert result is cavity_pvs


class TestIsPVAttribute:
    """Test _is_pv_attribute helper function."""

    def test_recognizes_pv_attribute(self):
        """Test that _pv attributes are recognized."""
        assert _is_pv_attribute("ades_pv") is True
        assert _is_pv_attribute("status_pv") is True

    def test_recognizes_pvs_attribute(self):
        """Test that _pvs attributes are recognized."""
        assert _is_pv_attribute("beamline_vacuum_pvs") is True
        assert _is_pv_attribute("insulating_vacuum_pvs") is True

    def test_rejects_pv_obj_attribute(self):
        """Test that _pv_obj attributes are rejected."""
        assert _is_pv_attribute("ades_pv_obj") is False
        assert _is_pv_attribute("status_pv_obj") is False

    def test_rejects_non_pv_attribute(self):
        """Test that non-PV attributes are rejected."""
        assert _is_pv_attribute("name") is False
        assert _is_pv_attribute("number") is False
        assert _is_pv_attribute("rack_name") is False


class TestPVExtractor:
    """Test PVExtractor class."""

    def test_pv_extractor_initialization(self):
        """Test PVExtractor initialization."""
        extractor = PVExtractor()
        assert isinstance(extractor.result, HierarchicalPVs)
        assert extractor.processed_objects == set()
        assert extractor.context["machine"] is None
        assert extractor.context["linac_name"] is None

    def test_update_context_machine(self):
        """Test updating context for Machine."""
        extractor = PVExtractor()
        machine = Mock()

        extractor.update_context("Machine", machine)
        assert extractor.context["machine"] is machine

    def test_update_context_linac(self):
        """Test updating context for Linac."""
        extractor = PVExtractor()
        linac = Mock()
        linac.name = "L0B"

        extractor.update_context("Linac", linac)
        assert extractor.context["linac_name"] == "L0B"

    def test_update_context_cryomodule(self):
        """Test updating context for Cryomodule."""
        extractor = PVExtractor()
        cm = Mock()
        cm.name = "02"

        extractor.update_context("Cryomodule", cm)
        assert extractor.context["cryomodule_name"] == "02"

    def test_update_context_rack(self):
        """Test updating context for Rack."""
        extractor = PVExtractor()
        rack = Mock()
        rack.rack_name = "A"

        extractor.update_context("Rack", rack)
        assert extractor.context["rack_name"] == "A"

    def test_update_context_cavity(self):
        """Test updating context for Cavity."""
        extractor = PVExtractor()
        cavity = Mock()
        cavity.number = 1

        extractor.update_context("Cavity", cavity)
        assert extractor.context["cavity_number"] == 1

    def test_add_to_machine_group(self):
        """Test adding PVs to machine group."""
        extractor = PVExtractor()
        machine = Mock()
        extractor.context["machine"] = machine

        pv_key = ("Machine", "global_heater_feedback_pv")
        pv_list = ["CHTR:CM00:0:HTR_POWER_TOT"]

        extractor.add_to_machine_group(pv_key, pv_list)

        assert pv_key in extractor.result.machine.pvs.pvs
        assert extractor.result.machine.pvs.pvs[pv_key] == pv_list

    def test_add_to_linac_group(self):
        """Test adding PVs to linac group."""
        extractor = PVExtractor()
        extractor.context["linac_name"] = "L0B"

        pv_key = ("Linac", "beamline_vacuum_pvs")
        pv_list = ["VGXX:L0B:0198:COMBO_P"]

        extractor.add_to_linac_group(pv_key, pv_list)

        assert "L0B" in extractor.result.linacs
        assert pv_key in extractor.result.linacs["L0B"].pvs.pvs
        assert extractor.result.linacs["L0B"].pvs.pvs[pv_key] == pv_list

    def test_add_to_cryomodule_group(self):
        """Test adding PVs to cryomodule group."""
        extractor = PVExtractor()
        extractor.context["linac_name"] = "L1B"
        extractor.context["cryomodule_name"] = "02"

        pv_key = ("Cryomodule", "ds_level_pv")
        pv_list = ["CLL:CM02:2301:DS:LVL"]

        extractor.add_to_cryomodule_group(pv_key, pv_list)

        assert "02" in extractor.result.cryomodules
        assert pv_key in extractor.result.cryomodules["02"].pvs.pvs

    def test_add_to_rack_group(self):
        """Test adding PVs to rack group."""
        extractor = PVExtractor()
        extractor.context["linac_name"] = "L1B"
        extractor.context["cryomodule_name"] = "02"
        extractor.context["rack_name"] = "A"

        pv_key = ("Cavity", "ades_pv")
        pv_list = ["ACCL:L1B:0210:ADES"]

        extractor.add_to_rack_group(pv_key, pv_list)

        assert ("02", "A") in extractor.result.racks
        assert pv_key in extractor.result.racks[("02", "A")].pvs.pvs

    def test_add_to_cavity_group(self):
        """Test adding PVs to cavity group."""
        extractor = PVExtractor()
        extractor.context["linac_name"] = "L1B"
        extractor.context["cryomodule_name"] = "02"
        extractor.context["rack_name"] = "A"
        extractor.context["cavity_number"] = 1

        pv_key = ("Cavity", "ades_pv")
        pv_list = ["ACCL:L1B:0210:ADES"]

        extractor.add_to_cavity_group(pv_key, pv_list)

        assert ("02", 1) in extractor.result.cavities
        assert pv_key in extractor.result.cavities[("02", 1)].pvs.pvs


class TestGetPVsAllGroupings:
    """Test get_pvs_all_groupings function."""

    def test_extract_machine_level_pvs(self):
        """Test extracting machine-level PVs."""
        machine = Mock(spec=["global_heater_feedback_pv", "linacs"])
        machine.__class__.__name__ = "Machine"
        machine.global_heater_feedback_pv = "CHTR:CM00:0:HTR_POWER_TOT"
        machine.linacs = []

        result = get_pvs_all_groupings(machine)

        assert isinstance(result, HierarchicalPVs)
        assert (
            "Machine",
            "global_heater_feedback_pv",
        ) in result.machine.pvs.pvs
        assert result.machine.pvs.pvs[
            ("Machine", "global_heater_feedback_pv")
        ] == ["CHTR:CM00:0:HTR_POWER_TOT"]

    def test_extract_linac_level_pvs(self):
        """Test extracting linac-level PVs."""
        linac = Mock(spec=["name", "beamline_vacuum_pvs", "cryomodules"])
        linac.__class__.__name__ = "Linac"
        linac.name = "L0B"
        linac.beamline_vacuum_pvs = ["VGXX:L0B:0198:COMBO_P"]
        linac.cryomodules = {}

        machine = Mock(spec=["linacs"])
        machine.__class__.__name__ = "Machine"
        machine.linacs = [linac]

        result = get_pvs_all_groupings(machine)

        assert "L0B" in result.linacs
        assert ("Linac", "beamline_vacuum_pvs") in result.linacs["L0B"].pvs.pvs

    def test_extract_cavity_level_pvs(self):
        """Test extracting cavity-level PVs."""
        cavity = Mock(
            spec=["number", "ades_pv", "stepper_tuner", "piezo", "ssa"]
        )
        cavity.__class__.__name__ = "Cavity"
        cavity.number = 1
        cavity.ades_pv = "ACCL:L1B:0210:ADES"
        cavity.stepper_tuner = None
        cavity.piezo = None
        cavity.ssa = None

        rack = Mock(spec=["rack_name", "cavities", "rfs1", "rfs2"])
        rack.__class__.__name__ = "Rack"
        rack.rack_name = "A"
        rack.cavities = {1: cavity}
        rack.rfs1 = None
        rack.rfs2 = None

        cm = Mock(spec=["name", "rack_a", "rack_b", "quad", "xcor", "ycor"])
        cm.__class__.__name__ = "Cryomodule"
        cm.name = "02"
        cm.rack_a = rack
        cm.rack_b = None
        cm.quad = None
        cm.xcor = None
        cm.ycor = None

        linac = Mock(spec=["name", "cryomodules"])
        linac.__class__.__name__ = "Linac"
        linac.name = "L1B"
        linac.cryomodules = {"02": cm}

        machine = Mock(spec=["linacs"])
        machine.__class__.__name__ = "Machine"
        machine.linacs = [linac]

        result = get_pvs_all_groupings(machine)

        assert ("02", 1) in result.cavities
        assert ("Cavity", "ades_pv") in result.cavities[("02", 1)].pvs.pvs

    def test_handles_list_pv_attributes(self):
        """Test handling list-type PV attributes."""
        linac = Mock(spec=["name", "beamline_vacuum_pvs", "cryomodules"])
        linac.__class__.__name__ = "Linac"
        linac.name = "L0B"
        linac.beamline_vacuum_pvs = [
            "VGXX:L0B:0198:COMBO_P",
            "VGXX:L0B:0199:COMBO_P",
        ]
        linac.cryomodules = {}

        machine = Mock(spec=["linacs"])
        machine.__class__.__name__ = "Machine"
        machine.linacs = [linac]

        result = get_pvs_all_groupings(machine)

        pvs = result.linacs["L0B"].pvs.pvs[("Linac", "beamline_vacuum_pvs")]
        assert len(pvs) == 2
        assert "VGXX:L0B:0198:COMBO_P" in pvs
        assert "VGXX:L0B:0199:COMBO_P" in pvs

    def test_handles_string_pv_attributes(self):
        """Test handling string-type PV attributes."""
        cavity = Mock(
            spec=["number", "ades_pv", "stepper_tuner", "piezo", "ssa"]
        )
        cavity.__class__.__name__ = "Cavity"
        cavity.number = 1
        cavity.ades_pv = "ACCL:L1B:0210:ADES"
        cavity.stepper_tuner = None
        cavity.piezo = None
        cavity.ssa = None

        rack = Mock(spec=["rack_name", "cavities", "rfs1", "rfs2"])
        rack.__class__.__name__ = "Rack"
        rack.rack_name = "A"
        rack.cavities = {1: cavity}
        rack.rfs1 = None
        rack.rfs2 = None

        cm = Mock(spec=["name", "rack_a", "rack_b", "quad", "xcor", "ycor"])
        cm.__class__.__name__ = "Cryomodule"
        cm.name = "02"
        cm.rack_a = rack
        cm.rack_b = None
        cm.quad = None
        cm.xcor = None
        cm.ycor = None

        linac = Mock(spec=["name", "cryomodules"])
        linac.__class__.__name__ = "Linac"
        linac.name = "L1B"
        linac.cryomodules = {"02": cm}

        machine = Mock(spec=["linacs"])
        machine.__class__.__name__ = "Machine"
        machine.linacs = [linac]

        result = get_pvs_all_groupings(machine)

        pvs = result.cavities[("02", 1)].pvs.pvs[("Cavity", "ades_pv")]
        assert len(pvs) == 1
        assert pvs[0] == "ACCL:L1B:0210:ADES"

    def test_avoids_processing_same_object_twice(self):
        """Test that same object isn't processed multiple times."""
        cavity = Mock(
            spec=["number", "ades_pv", "stepper_tuner", "piezo", "ssa"]
        )
        cavity.__class__.__name__ = "Cavity"
        cavity.number = 1
        cavity.ades_pv = "ACCL:L1B:0210:ADES"
        cavity.stepper_tuner = None
        cavity.piezo = None
        cavity.ssa = None

        # Create a circular reference (shouldn't happen in practice, but tests robustness)
        rack = Mock(spec=["rack_name", "cavities", "rfs1", "rfs2"])
        rack.__class__.__name__ = "Rack"
        rack.rack_name = "A"
        rack.cavities = {1: cavity}
        rack.rfs1 = None
        rack.rfs2 = None

        cm = Mock(spec=["name", "rack_a", "rack_b", "quad", "xcor", "ycor"])
        cm.__class__.__name__ = "Cryomodule"
        cm.name = "02"
        cm.rack_a = rack
        cm.rack_b = rack  # Same rack referenced twice
        cm.quad = None
        cm.xcor = None
        cm.ycor = None

        linac = Mock(spec=["name", "cryomodules"])
        linac.__class__.__name__ = "Linac"
        linac.name = "L1B"
        linac.cryomodules = {"02": cm}

        machine = Mock(spec=["linacs"])
        machine.__class__.__name__ = "Machine"
        machine.linacs = [linac]

        # Should not raise an error or infinite loop
        result = get_pvs_all_groupings(machine)

        # Should only have one cavity entry
        assert len(result.cavities) == 1

    def test_pv_aggregation_across_hierarchy(self):
        """Test that PVs are aggregated correctly across hierarchy."""
        # Create a simple hierarchy
        cavity = Mock(
            spec=["number", "ades_pv", "stepper_tuner", "piezo", "ssa"]
        )
        cavity.__class__.__name__ = "Cavity"
        cavity.number = 1
        cavity.ades_pv = "ACCL:L1B:0210:ADES"
        cavity.stepper_tuner = None
        cavity.piezo = None
        cavity.ssa = None

        rack = Mock(spec=["rack_name", "cavities", "rfs1", "rfs2"])
        rack.__class__.__name__ = "Rack"
        rack.rack_name = "A"
        rack.cavities = {1: cavity}
        rack.rfs1 = None
        rack.rfs2 = None

        cm = Mock(
            spec=[
                "name",
                "ds_level_pv",
                "rack_a",
                "rack_b",
                "quad",
                "xcor",
                "ycor",
            ]
        )
        cm.__class__.__name__ = "Cryomodule"
        cm.name = "02"
        cm.ds_level_pv = "CLL:CM02:2301:DS:LVL"
        cm.rack_a = rack
        cm.rack_b = None
        cm.quad = None
        cm.xcor = None
        cm.ycor = None

        linac = Mock(spec=["name", "beamline_vacuum_pvs", "cryomodules"])
        linac.__class__.__name__ = "Linac"
        linac.name = "L1B"
        linac.beamline_vacuum_pvs = ["VGXX:L1B:0198:COMBO_P"]
        linac.cryomodules = {"02": cm}

        machine = Mock(spec=["global_heater_feedback_pv", "linacs"])
        machine.__class__.__name__ = "Machine"
        machine.global_heater_feedback_pv = "CHTR:CM00:0:HTR_POWER_TOT"
        machine.linacs = [linac]

        result = get_pvs_all_groupings(machine)

        # Check that machine level has all PVs
        assert (
            "Machine",
            "global_heater_feedback_pv",
        ) in result.machine.pvs.pvs
        assert ("Linac", "beamline_vacuum_pvs") in result.machine.pvs.pvs
        assert ("Cryomodule", "ds_level_pv") in result.machine.pvs.pvs
        assert ("Cavity", "ades_pv") in result.machine.pvs.pvs

        # Check that linac level has linac PVs and below
        assert ("Linac", "beamline_vacuum_pvs") in result.linacs["L1B"].pvs.pvs
        assert ("Cryomodule", "ds_level_pv") in result.linacs["L1B"].pvs.pvs
        assert ("Cavity", "ades_pv") in result.linacs["L1B"].pvs.pvs

        # Check that cryomodule level has CM PVs and below
        assert ("Cryomodule", "ds_level_pv") in result.cryomodules["02"].pvs.pvs
        assert ("Cavity", "ades_pv") in result.cryomodules["02"].pvs.pvs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
