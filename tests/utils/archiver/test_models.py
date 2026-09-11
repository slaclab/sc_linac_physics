"""Tests for archiver data models."""

from datetime import datetime
import pytest

from sc_linac_physics.utils.archiver.models import ArchiverValue, ArchiveDataHandler


def test_archiver_value_creation():
    """Test ArchiverValue dataclass instantiation."""
    timestamp = datetime(2024, 1, 15, 12, 0, 0)
    value = ArchiverValue(
        value=16.5,
        timestamp=timestamp,
        severity=0,
        status=0
    )
    
    assert value.value == 16.5
    assert value.timestamp == timestamp
    assert value.severity == 0
    assert value.status == 0


def test_archiver_value_with_string():
    """Test ArchiverValue with string value (fault codes)."""
    timestamp = datetime(2024, 1, 15, 12, 0, 0)
    value = ArchiverValue(
        value="TLC",
        timestamp=timestamp,
        severity=1,
        status=1
    )
    
    assert value.value == "TLC"
    assert value.severity == 1
    assert value.status == 1


def test_archive_data_handler_from_values():
    """Test ArchiveDataHandler.from_archiver_values() classmethod."""
    # Create list of ArchiverValue objects
    archiver_values = [
        ArchiverValue(16.5, datetime(2024, 1, 15, 12, 0, 0), 0, 0),
        ArchiverValue(16.52, datetime(2024, 1, 15, 12, 0, 1), 0, 0),
        ArchiverValue(16.48, datetime(2024, 1, 15, 12, 0, 2), 0, 0),
    ]
    
    # Create handler from values
    handler = ArchiveDataHandler.from_archiver_values(
        pv_name="ACCL:L1B:0110:ADES",
        archiver_values=archiver_values
    )
    
    # Verify structure
    assert handler.pv_name == "ACCL:L1B:0110:ADES"
    assert len(handler.values) == 3
    assert len(handler.timestamps) == 3
    assert len(handler.severities) == 3
    assert len(handler.statuses) == 3
    
    # Verify values extracted correctly
    assert handler.values == [16.5, 16.52, 16.48]
    assert handler.timestamps[0] == datetime(2024, 1, 15, 12, 0, 0)
    assert handler.severities == [0, 0, 0]
    assert handler.statuses == [0, 0, 0]


def test_archive_data_handler_empty_list():
    """Test ArchiveDataHandler with empty archiver_values list."""
    handler = ArchiveDataHandler.from_archiver_values(
        pv_name="ACCL:L1B:0110:ADES",
        archiver_values=[]
    )
    
    assert handler.pv_name == "ACCL:L1B:0110:ADES"
    assert handler.values == []
    assert handler.timestamps == []
    assert handler.severities == []
    assert handler.statuses == []


def test_archive_data_handler_direct_instantiation():
    """Test ArchiveDataHandler direct instantiation."""
    handler = ArchiveDataHandler(
        pv_name="ACCL:L1B:0110:PDES",
        values=[0.0, 0.1, -0.05],
        timestamps=[
            datetime(2024, 1, 15, 12, 0, 0),
            datetime(2024, 1, 15, 12, 0, 1),
            datetime(2024, 1, 15, 12, 0, 2),
        ],
        severities=[0, 0, 0],
        statuses=[0, 0, 0]
    )
    
    assert handler.pv_name == "ACCL:L1B:0110:PDES"
    assert len(handler.values) == 3
    assert handler.values[1] == 0.1