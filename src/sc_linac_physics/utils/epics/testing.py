from typing import Any
from unittest.mock import MagicMock

from sc_linac_physics.utils.epics.config import EPICS_NO_ALARM_VAL


def make_mock_pv(
    pv_name: str = "MOCK:PV",
    get_val: Any = 0.0,
    connected: bool = True,
    severity: int = EPICS_NO_ALARM_VAL,
    fail_count: int = 0,
) -> MagicMock:
    """
    Create a mock PV object for testing.

    Args:
        pv_name: PV name
        get_val: Value to return from get()
        connected: Connection status
        severity: Alarm severity
        fail_count: Number of times get/put should fail before succeeding

    Returns:
        MagicMock configured to behave like a PV

    Example:
        >>> mock_pv = make_mock_pv("TEST:PV", get_val=42.0)
        >>> assert mock_pv.get() == 42.0
        >>> mock_pv.put(100.0)
        >>> mock_pv.put.assert_called_once_with(100.0)
    """
    mock_pv = MagicMock()

    # Basic attributes
    mock_pv.pvname = pv_name
    mock_pv.connected = connected
    mock_pv.severity = severity
    mock_pv.auto_monitor = True
    mock_pv.val = get_val

    # Setup failure simulation
    if fail_count > 0:
        call_counts = {"get": 0, "put": 0}

        def get_with_failures(*args, **kwargs):
            call_counts["get"] += 1
            if call_counts["get"] <= fail_count:
                return None  # Simulate failure
            return get_val

        def put_with_failures(*args, **kwargs):
            call_counts["put"] += 1
            if call_counts["put"] <= fail_count:
                return 0  # Simulate failure
            return 1  # Success

        mock_pv.get.side_effect = get_with_failures
        mock_pv.put.side_effect = put_with_failures
    else:
        # Normal operation
        mock_pv.get.return_value = get_val
        mock_pv.put.return_value = 1

    # Other methods
    mock_pv.wait_for_connection.return_value = connected
    mock_pv.validate_value.return_value = True
    mock_pv.check_alarm.return_value = severity
    mock_pv.disconnect.return_value = None

    # Context manager support
    mock_pv.__enter__.return_value = mock_pv
    mock_pv.__exit__.return_value = False

    # String representations
    mock_pv.__str__.return_value = pv_name
    mock_pv.__repr__.return_value = f"MockPV('{pv_name}')"

    return mock_pv
