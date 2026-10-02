"""Tests for smart routing wrapper."""

import os
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytest

from sc_linac_physics.utils.archiver import (
    get_values_over_time_range,
    start_mock_archiver,
    ArchiveDataHandler
)
from sc_linac_physics.utils.archiver.client import (
    ArchiverConnectionError,
    ArchiverTimeoutError,
    ArchiverError
)


@pytest.fixture
def reset_mock_state():
    """Reset global mock state before each test."""
    import sc_linac_physics.utils.archiver as archiver_module
    archiver_module._mock_archiver_enabled = False
    yield
    archiver_module._mock_archiver_enabled = False


@pytest.fixture
def sample_time_range():
    """Sample start and end times for tests."""
    return (
        datetime(2024, 1, 15, 12, 0, 0),
        datetime(2024, 1, 15, 12, 1, 0)
    )


def test_get_values_with_env_var(reset_mock_state, sample_time_range, monkeypatch):
    """Test routing to mock when SC_ARCHIVER_MOCK=1 env var set."""
    monkeypatch.setenv("SC_ARCHIVER_MOCK", "1")
    start, end = sample_time_range
    
    result = get_values_over_time_range(
        pv_list=["ACCL:L1B:0110:ADES"],
        start_time=start,
        end_time=end
    )
    
    # Should return mock data
    assert isinstance(result, dict)
    assert "ACCL:L1B:0110:ADES" in result
    assert isinstance(result["ACCL:L1B:0110:ADES"], ArchiveDataHandler)
    
    # Verify it's mock data (gradient values around 16.5)
    handler = result["ACCL:L1B:0110:ADES"]
    assert len(handler.values) > 0
    avg_value = sum(handler.values) / len(handler.values)
    assert 15.0 <= avg_value <= 18.0, "Expected mock gradient values around 16.5"


def test_get_values_with_start_mock_archiver(reset_mock_state, sample_time_range):
    """Test routing to mock when start_mock_archiver() called."""
    start, end = sample_time_range
    
    # Enable mock mode
    start_mock_archiver()
    
    result = get_values_over_time_range(
        pv_list=["ACCL:L1B:0110:PDES"],
        start_time=start,
        end_time=end
    )
    
    # Should return mock data
    assert isinstance(result, dict)
    assert "ACCL:L1B:0110:PDES" in result
    
    # Verify it's mock data (phase values around 0)
    handler = result["ACCL:L1B:0110:PDES"]
    assert len(handler.values) > 0
    assert all(-5.0 <= v <= 5.0 for v in handler.values), "Expected mock phase values around 0"


def test_get_values_archiver_unavailable(reset_mock_state, sample_time_range):
    """Test routing to mock when archiver unavailable."""
    start, end = sample_time_range
    
    with patch('sc_linac_physics.utils.archiver.is_archiver_available') as mock_available:
        mock_available.return_value = False
        
        result = get_values_over_time_range(
            pv_list=["ACCL:L1B:0110:ADES"],
            start_time=start,
            end_time=end
        )
        
        # Should return mock data
        assert isinstance(result, dict)
        assert "ACCL:L1B:0110:ADES" in result
        mock_available.assert_called_once()


def test_get_values_real_archiver_success(reset_mock_state, sample_time_range):
    """Test routing to real archiver when available and working."""
    start, end = sample_time_range
    
    # Mock successful real archiver response
    fake_real_data = {
        "ACCL:L1B:0110:ADES": ArchiveDataHandler(
            pv_name="ACCL:L1B:0110:ADES",
            values=[16.5, 16.52],
            timestamps=[start, start],
            severities=[0, 0],
            statuses=[0, 0]
        )
    }
    
    with patch('sc_linac_physics.utils.archiver.is_archiver_available') as mock_available, \
         patch('sc_linac_physics.utils.archiver.real_get_values_over_time_range') as mock_real:
        
        mock_available.return_value = True
        mock_real.return_value = fake_real_data
        
        result = get_values_over_time_range(
            pv_list=["ACCL:L1B:0110:ADES"],
            start_time=start,
            end_time=end
        )
        
        # Should return real data
        assert result == fake_real_data
        mock_available.assert_called_once()
        mock_real.assert_called_once_with(["ACCL:L1B:0110:ADES"], start, end)


def test_get_values_fallback_on_connection_error(reset_mock_state, sample_time_range):
    """Test fallback to mock when real archiver raises ConnectionError."""
    start, end = sample_time_range
    
    with patch('sc_linac_physics.utils.archiver.is_archiver_available') as mock_available, \
         patch('sc_linac_physics.utils.archiver.real_get_values_over_time_range') as mock_real:
        
        mock_available.return_value = True
        mock_real.side_effect = ArchiverConnectionError("Cannot connect")
        
        result = get_values_over_time_range(
            pv_list=["ACCL:L1B:0110:ADES"],
            start_time=start,
            end_time=end
        )
        
        # Should fall back to mock
        assert isinstance(result, dict)
        assert "ACCL:L1B:0110:ADES" in result
        
        # Verify mock was used (gradient values)
        handler = result["ACCL:L1B:0110:ADES"]
        avg_value = sum(handler.values) / len(handler.values)
        assert 15.0 <= avg_value <= 18.0


def test_get_values_fallback_on_timeout_error(reset_mock_state, sample_time_range):
    """Test fallback to mock when real archiver times out."""
    start, end = sample_time_range
    
    with patch('sc_linac_physics.utils.archiver.is_archiver_available') as mock_available, \
         patch('sc_linac_physics.utils.archiver.real_get_values_over_time_range') as mock_real:
        
        mock_available.return_value = True
        mock_real.side_effect = ArchiverTimeoutError("Request timed out")
        
        result = get_values_over_time_range(
            pv_list=["ACCL:L1B:0110:ADES"],
            start_time=start,
            end_time=end
        )
        
        # Should fall back to mock
        assert isinstance(result, dict)
        assert "ACCL:L1B:0110:ADES" in result


def test_get_values_fallback_on_archiver_error(reset_mock_state, sample_time_range):
    """Test fallback to mock when real archiver returns HTTP error."""
    start, end = sample_time_range
    
    with patch('sc_linac_physics.utils.archiver.is_archiver_available') as mock_available, \
         patch('sc_linac_physics.utils.archiver.real_get_values_over_time_range') as mock_real:
        
        mock_available.return_value = True
        mock_real.side_effect = ArchiverError("HTTP 500")
        
        result = get_values_over_time_range(
            pv_list=["ACCL:L1B:0110:ADES"],
            start_time=start,
            end_time=end
        )
        
        # Should fall back to mock
        assert isinstance(result, dict)
        assert "ACCL:L1B:0110:ADES" in result


def test_get_values_multiple_pvs(reset_mock_state, sample_time_range):
    """Test get_values_over_time_range with multiple PVs."""
    start, end = sample_time_range
    
    with patch('sc_linac_physics.utils.archiver.is_archiver_available') as mock_available:
        mock_available.return_value = False  # Force mock
        
        result = get_values_over_time_range(
            pv_list=[
                "ACCL:L1B:0110:ADES",
                "ACCL:L1B:0110:PDES",
                "ACCL:L1B:0110:CUDSTATUS"
            ],
            start_time=start,
            end_time=end
        )
        
        # Should have all three PVs
        assert len(result) == 3
        assert "ACCL:L1B:0110:ADES" in result
        assert "ACCL:L1B:0110:PDES" in result
        assert "ACCL:L1B:0110:CUDSTATUS" in result
        
        # All should be ArchiveDataHandler
        for handler in result.values():
            assert isinstance(handler, ArchiveDataHandler)


def test_start_mock_archiver_enables_flag(reset_mock_state):
    """Test that start_mock_archiver() sets global flag."""
    import sc_linac_physics.utils.archiver as archiver_module
    
    # Initially disabled
    assert archiver_module._mock_archiver_enabled is False
    
    # Enable mock
    start_mock_archiver()
    
    # Should be enabled
    assert archiver_module._mock_archiver_enabled is True


def test_env_var_takes_precedence(reset_mock_state, sample_time_range, monkeypatch):
    """Test that SC_ARCHIVER_MOCK env var takes precedence over availability."""
    start, end = sample_time_range
    monkeypatch.setenv("SC_ARCHIVER_MOCK", "1")
    
    # Even if archiver is available, should use mock
    with patch('sc_linac_physics.utils.archiver.is_archiver_available') as mock_available, \
         patch('sc_linac_physics.utils.archiver.real_get_values_over_time_range') as mock_real:
        
        mock_available.return_value = True
        
        result = get_values_over_time_range(
            pv_list=["ACCL:L1B:0110:ADES"],
            start_time=start,
            end_time=end
        )
        
        # Should NOT call real archiver
        mock_real.assert_not_called()
        
        # Should return mock data
        assert isinstance(result, dict)
        assert "ACCL:L1B:0110:ADES" in result


def test_start_mock_takes_precedence_over_availability(reset_mock_state, sample_time_range):
    """Test that start_mock_archiver() takes precedence over archiver availability."""
    start, end = sample_time_range
    start_mock_archiver()
    
    # Even if archiver is available, should use mock
    with patch('sc_linac_physics.utils.archiver.is_archiver_available') as mock_available, \
         patch('sc_linac_physics.utils.archiver.real_get_values_over_time_range') as mock_real:
        
        mock_available.return_value = True
        
        result = get_values_over_time_range(
            pv_list=["ACCL:L1B:0110:ADES"],
            start_time=start,
            end_time=end
        )
        
        # Should NOT call real archiver
        mock_real.assert_not_called()
        
        # Should return mock data
        assert isinstance(result, dict)


def test_empty_pv_list(reset_mock_state, sample_time_range):
    """Test get_values_over_time_range with empty PV list."""
    start, end = sample_time_range
    
    result = get_values_over_time_range(
        pv_list=[],
        start_time=start,
        end_time=end
    )
    
    assert isinstance(result, dict)
    assert len(result) == 0