"""Tests for real archiver client."""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
import requests

from sc_linac_physics.utils.archiver.client import (
    is_archiver_available,
    real_get_values_over_time_range,
    ArchiverError,
    ArchiverTimeoutError,
    ArchiverConnectionError,
    ARCHIVER_BASE_URL
)
from sc_linac_physics.utils.archiver.models import ArchiveDataHandler


def test_is_archiver_available_success():
    """Test is_archiver_available when archiver is reachable."""
    with patch('requests.head') as mock_head:
        mock_head.return_value.status_code = 200
        
        result = is_archiver_available()
        
        assert result is True
        mock_head.assert_called_once()
        assert ARCHIVER_BASE_URL in mock_head.call_args[0][0]


def test_is_archiver_available_server_error():
    """Test is_archiver_available when archiver returns 5xx."""
    with patch('requests.head') as mock_head:
        mock_head.return_value.status_code = 503
        
        result = is_archiver_available()
        
        assert result is False


def test_is_archiver_available_connection_error():
    """Test is_archiver_available when connection fails."""
    with patch('requests.head') as mock_head:
        mock_head.side_effect = requests.exceptions.ConnectionError()
        
        result = is_archiver_available()
        
        assert result is False


def test_is_archiver_available_timeout():
    """Test is_archiver_available when request times out."""
    with patch('requests.head') as mock_head:
        mock_head.side_effect = requests.exceptions.Timeout
        
        result = is_archiver_available()
        
        assert result is False