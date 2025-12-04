from typing import Optional

import epics

from sc_linac_physics.utils.epics.core import PV
from sc_linac_physics.utils.epics.exceptions import PVConnectionError
from sc_linac_physics.utils.epics.logger import get_logger


def create_pv_safe(
    pvname: str,
    connection_timeout: Optional[float] = None,
    raise_on_failure: bool = True,
    **kwargs,
) -> Optional[PV]:
    """
    Safely create a PV with better error handling.

    Args:
        pvname: PV name
        connection_timeout: Connection timeout
        raise_on_failure: If True, raise exception on failure. If False, return None.
        **kwargs: Additional arguments to pass to PV constructor

    Returns:
        PV object or None if connection failed and raise_on_failure=False

    Raises:
        PVConnectionError: If connection fails and raise_on_failure=True
    """
    try:
        pv = PV(pvname, connection_timeout=connection_timeout, **kwargs)
        return pv
    except PVConnectionError as e:
        if raise_on_failure:
            raise
        else:
            get_logger().warning(f"Failed to create PV {pvname}: {e}")
            return None


def diagnose_pv_connection(pvname: str, timeout: float = 10.0) -> dict:
    """
    Diagnose PV connection issues.

    Args:
        pvname: PV name to diagnose
        timeout: Connection timeout

    Returns:
        Dictionary with diagnostic information
    """
    info = {
        "pvname": pvname,
        "caget_works": False,
        "pv_connects": False,
        "value": None,
        "error": None,
        "host": None,
        "type": None,
        "count": None,
    }

    try:
        # Try simple caget first
        get_logger().info(f"Testing caget for {pvname}...")
        value = epics.caget(pvname, timeout=timeout)
        if value is not None:
            info["caget_works"] = True
            info["value"] = value
            get_logger().info(f"caget successful: {value}")
        else:
            get_logger().warning(f"caget returned None for {pvname}")

        # Try creating PV object
        get_logger().info(f"Testing PV object creation for {pvname}...")
        test_pv = epics.PV(pvname, connection_timeout=timeout)

        if test_pv.wait_for_connection(timeout=timeout):
            info["pv_connects"] = True
            info["host"] = test_pv.host
            info["type"] = test_pv.type
            info["count"] = test_pv.count

            try:
                val = test_pv.get(timeout=timeout)
                if val is not None:
                    info["value"] = val
                get_logger().info(f"PV.get() successful: {val}")
            except Exception as e:
                get_logger().warning(f"PV.get() failed: {e}")
                info["error"] = f"get failed: {str(e)}"
        else:
            get_logger().warning(f"PV object failed to connect for {pvname}")
            info["error"] = "PV object connection timeout"

        test_pv.disconnect()

    except Exception as e:
        info["error"] = str(e)
        get_logger().error(f"Diagnostic error for {pvname}: {e}")

    get_logger().info(f"PV Diagnostics for {pvname}: {info}")
    return info
