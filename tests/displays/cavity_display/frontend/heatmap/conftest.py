from unittest.mock import Mock

import pytest

from sc_linac_physics.displays.cavity_display.backend.fault import FaultCounter
from sc_linac_physics.displays.cavity_display.frontend.heatmap.color_mapper import (
    ColorMapper,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.fault_data_fetcher import (
    CavityFaultResult,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.severity_filter import (
    SeverityFilter,
)


@pytest.fixture
def color_mapper():
    return ColorMapper(vmin=0.0, vmax=100.0)


@pytest.fixture
def severity_filter():
    return SeverityFilter()


@pytest.fixture
def sample_fault_counter():
    return FaultCounter(
        alarm_count=10, ok_count=500, invalid_count=3, warning_count=7
    )


@pytest.fixture
def zero_fault_counter():
    return FaultCounter(
        alarm_count=0, ok_count=0, invalid_count=0, warning_count=0
    )


def make_result(
    cm_name: str = "01",
    cavity_num: int = 1,
    alarm: int = 0,
    warning: int = 0,
    invalid: int = 0,
    ok: int = 0,
) -> CavityFaultResult:
    """Create a successful CavityFaultResult with the given fault counts."""
    return CavityFaultResult(
        cm_name=cm_name,
        cavity_num=cavity_num,
        fault_counts_by_tlc={"ALL": FaultCounter(alarm, ok, invalid, warning)},
    )


def make_error_result(
    cm_name: str = "01",
    cavity_num: int = 1,
    error: str = "PV timeout",
) -> CavityFaultResult:
    """Create an error CavityFaultResult."""
    return CavityFaultResult(
        cm_name=cm_name,
        cavity_num=cavity_num,
        error=error,
    )


def make_machine(num_cavities: int = 1) -> Mock:
    """Create a mock BackendMachine with one linac, one CM, and N cavities."""
    machine = Mock()
    linac = Mock()
    cm = Mock()
    cavities = {}
    for i in range(1, num_cavities + 1):
        cav = Mock()
        cav.get_fault_counts = Mock(return_value={})
        cavities[i] = cav
    cm.cavities = cavities
    linac.cryomodules = {"01": cm}
    machine.linacs = [linac]
    return machine
