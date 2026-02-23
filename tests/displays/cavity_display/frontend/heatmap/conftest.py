import pytest

from sc_linac_physics.displays.cavity_display.backend.fault import FaultCounter
from sc_linac_physics.displays.cavity_display.frontend.heatmap.color_mapper import (
    ColorMapper,
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
