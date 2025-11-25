import threading
from time import sleep
from typing import Optional, Union, List, Any
from unittest.mock import MagicMock

import epics
import numpy as np
from epics import PV as EPICS_PV

# Import your custom logger
from sc_linac_physics.utils.logger import custom_logger, BASE_LOG_DIR

# Don't create logger at module level - use lazy initialization
_logger = None


def _get_logger():
    """Lazy logger initialization"""
    global _logger
    if _logger is None:
        _logger = custom_logger(
            __name__,
            log_dir=str(BASE_LOG_DIR / "epics"),
            log_filename="pv_operations",
        )
    return _logger


# These are the values that decide whether a PV is alarming (and if so, how)
EPICS_NO_ALARM_VAL = 0
EPICS_MINOR_VAL = 1
EPICS_MAJOR_VAL = 2
EPICS_INVALID_VAL = 3


class PVConnectionError(Exception):
    """Raised when PV fails to connect"""

    pass


class PVGetError(Exception):
    """Raised when PV get operation fails"""

    pass


class PVPutError(Exception):
    """Raised when PV put operation fails"""

    pass


class PVInvalidError(Exception):
    """Raised when PV value is invalid"""

    pass


class PV(EPICS_PV):
    """
    Enhanced EPICS PV that always raises exceptions on failure
    Never returns None - either returns a value or raises an exception
    """

    DEFAULT_CONNECTION_TIMEOUT = 5.0
    DEFAULT_GET_TIMEOUT = 2.0
    DEFAULT_PUT_TIMEOUT = 30.0
    MAX_RETRIES = 3
    RETRY_DELAY = 0.5

    def __init__(
        self,
        pvname,
        connection_timeout=None,
        callback=None,
        form="time",
        verbose=False,
        auto_monitor=True,
        count=None,
        connection_callback=None,
        access_callback=None,
        require_connection=True,
    ):
        # Initialize all guards and defaults BEFORE calling super().__init__
        self._connection_lock = threading.RLock()
        self._user_callback = callback
        self._require_connection = require_connection

        if connection_timeout is None:
            connection_timeout = self.DEFAULT_CONNECTION_TIMEOUT

        # Initialize parent without user callback first
        super().__init__(
            pvname=pvname,
            connection_timeout=connection_timeout,
            callback=None,
            form=form,
            verbose=verbose,
            auto_monitor=auto_monitor,
            count=count,
            connection_callback=connection_callback,
            access_callback=access_callback,
        )

        # Give pyepics a moment to process the connection request
        # This can help with timing issues in multithreaded environments
        if not self.connected:
            sleep(0.01)  # Small delay to allow connection to establish

        # Wait for initial connection with multiple attempts
        connected = self._wait_for_initial_connection(connection_timeout)

        if not connected:
            error_msg = (
                f"PV {pvname} failed to connect within {connection_timeout}s"
            )
            if require_connection:
                _get_logger().error(error_msg)
                raise PVConnectionError(error_msg)
            else:
                _get_logger().warning(error_msg + " (connection not required)")

        # Now add user callback if provided and connected
        if self._user_callback is not None and self.connected:
            self.add_callback(self._user_callback)

    def _wait_for_initial_connection(self, timeout: float) -> bool:
        """
        Wait for initial connection with retry logic

        Args:
            timeout: Total timeout to wait

        Returns:
            True if connected, False otherwise
        """
        # If already connected, return immediately
        if self.connected:
            return True

        # Try waiting for connection
        if self.wait_for_connection(timeout=timeout):
            return True

        # First attempt failed, try a few quick retries
        # Sometimes pyepics needs a second chance, especially in multithreaded apps
        retry_attempts = 2
        retry_timeout = min(1.0, timeout / 2)

        for attempt in range(retry_attempts):
            _get_logger().debug(
                f"Retry connection attempt {attempt + 1}/{retry_attempts} for {self.pvname}"
            )
            sleep(0.1)  # Brief pause

            if self.wait_for_connection(timeout=retry_timeout):
                _get_logger().info(
                    f"PV {self.pvname} connected on retry attempt {attempt + 1}"
                )
                return True

        return False

    def __str__(self):
        return f"{self.pvname}"

    def __repr__(self):
        status = "connected" if self.connected else "disconnected"
        return f"PV('{self.pvname}', {status})"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    def _ensure_connected(self, timeout=None):
        """
        Ensure PV is connected, raise exception if not
        Thread-safe with reentrant lock.

        Raises:
            PVConnectionError: If connection fails
        """
        # Quick check - if already connected, return immediately
        if self.connected:
            return

        # Use reentrant lock to prevent race conditions
        with self._connection_lock:
            # Double-check after acquiring lock
            if self.connected:
                return

            timeout = timeout or self.DEFAULT_CONNECTION_TIMEOUT

            # Log reconnection attempt
            _get_logger().warning(
                f"PV {self.pvname} disconnected, attempting to reconnect"
            )

            if not self.wait_for_connection(timeout=timeout):
                error_msg = (
                    f"PV {self.pvname} failed to reconnect within {timeout}s"
                )
                _get_logger().error(error_msg)
                raise PVConnectionError(error_msg)

            _get_logger().info(f"PV {self.pvname} reconnected successfully")

    def disconnect(self, deepclean=True):
        """Clean disconnect"""
        try:
            super().disconnect(deepclean=deepclean)
        except Exception as e:
            _get_logger().warning(f"Error disconnecting PV {self.pvname}: {e}")

    @property
    def val(self):
        """Shorthand for getting current value"""
        return self.get()

    @property
    def value_or_none(self) -> Optional[Union[int, float, str, np.ndarray]]:
        """Get value without raising exception, returns None on failure"""
        try:
            return self.get()
        except (PVConnectionError, PVGetError):
            return None

    def get(
        self,
        count: Optional[int] = None,
        as_string: bool = False,
        as_numpy: bool = True,
        timeout: Optional[float] = None,
        with_ctrlvars: bool = False,
        use_monitor: Optional[bool] = None,
    ) -> Union[int, float, str, np.ndarray, List]:
        """
        Get PV value with automatic retry logic

        Args:
            count: Number of elements to fetch
            as_string: Return value as string
            as_numpy: Return array values as numpy arrays
            timeout: Timeout for get operation
            with_ctrlvars: Include control variables
            use_monitor: Use cached monitored value (default: True if auto_monitor enabled)

        Returns:
            PV value (never None)

        Raises:
            PVConnectionError: If PV is not connected
            PVGetError: If get operation fails after retries
        """
        timeout = timeout or self.DEFAULT_GET_TIMEOUT
        use_monitor = self._determine_use_monitor(use_monitor)

        self._ensure_connected(timeout=timeout)

        return self._get_with_retry(
            count=count,
            as_string=as_string,
            as_numpy=as_numpy,
            timeout=timeout,
            with_ctrlvars=with_ctrlvars,
            use_monitor=use_monitor,
        )

    def _determine_use_monitor(self, use_monitor):
        """Determine whether to use monitor based on config"""
        if use_monitor is None:
            return self.auto_monitor
        return use_monitor

    def _get_with_retry(
        self, count, as_string, as_numpy, timeout, with_ctrlvars, use_monitor
    ):
        """Execute get operation with retry logic"""
        last_exception = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                value = self._attempt_get(
                    count,
                    as_string,
                    as_numpy,
                    timeout,
                    with_ctrlvars,
                    use_monitor,
                )
                if value is not None:
                    if attempt > 1:
                        _get_logger().info(
                            f"PV {self.pvname} get succeeded on attempt {attempt}"
                        )
                    return value

                if attempt < self.MAX_RETRIES:
                    _get_logger().warning(
                        f"PV {self.pvname} returned None "
                        f"(attempt {attempt}/{self.MAX_RETRIES})"
                    )
            except Exception as e:
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    _get_logger().warning(
                        f"PV {self.pvname} get raised exception: {e} "
                        f"(attempt {attempt}/{self.MAX_RETRIES})"
                    )

            if attempt < self.MAX_RETRIES:
                self._retry_backoff(attempt, timeout)

        # All retries exhausted
        self._raise_get_error(last_exception)

    def _attempt_get(
        self, count, as_string, as_numpy, timeout, with_ctrlvars, use_monitor
    ):
        """Attempt a single get operation"""
        return super().get(
            count=count,
            as_string=as_string,
            as_numpy=as_numpy,
            timeout=timeout,
            with_ctrlvars=with_ctrlvars,
            use_monitor=use_monitor,
        )

    def _retry_backoff(self, attempt, timeout):
        """Handle retry delay and reconnection"""
        sleep(self.RETRY_DELAY * attempt)  # Exponential backoff

        # Try to reconnect if disconnected, but don't fail the retry attempt
        if not self.connected:
            try:
                self._ensure_connected(timeout=timeout)
            except PVConnectionError as e:
                _get_logger().debug(f"Reconnection attempt failed: {e}")
                # Will be caught in next get/put attempt

    def _raise_get_error(self, last_exception):
        """Raise appropriate error after all retries exhausted"""
        if last_exception:
            error_msg = (
                f"PV {self.pvname} get failed after {self.MAX_RETRIES} attempts. "
                f"Last exception: {last_exception}"
            )
            _get_logger().error(error_msg)
            raise PVGetError(error_msg) from last_exception
        else:
            error_msg = (
                f"PV {self.pvname} get returned None after "
                f"{self.MAX_RETRIES} attempts"
            )
            _get_logger().error(error_msg)
            raise PVGetError(error_msg)

    def put(
        self,
        value,
        wait=True,
        timeout=None,
        use_complete=False,
        callback=None,
        callback_data=None,
    ):
        """
        Put value to PV with automatic retry logic

        Args:
            value: Value to write
            wait: Wait for completion
            timeout: Timeout for put operation
            use_complete: Use completion callback
            callback: Callback function
            callback_data: Data to pass to callback

        Raises:
            PVConnectionError: If PV is not connected
            PVPutError: If put operation fails after retries
        """
        timeout = timeout or self.DEFAULT_PUT_TIMEOUT

        self._ensure_connected(timeout=timeout)

        self._put_with_retry(
            value=value,
            wait=wait,
            timeout=timeout,
            use_complete=use_complete,
            callback=callback,
            callback_data=callback_data,
        )

    def _put_with_retry(
        self, value, wait, timeout, use_complete, callback, callback_data
    ):
        """Execute put operation with retry logic"""
        last_exception = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                status = self._attempt_put(
                    value, wait, timeout, use_complete, callback, callback_data
                )
                if status == 1:
                    if attempt > 1:
                        _get_logger().info(
                            f"PV {self.pvname} put({value}) succeeded on attempt {attempt}"
                        )
                    return  # Success

                if attempt < self.MAX_RETRIES:
                    _get_logger().warning(
                        f"PV {self.pvname} put({value}) returned status {status} "
                        f"(attempt {attempt}/{self.MAX_RETRIES})"
                    )
            except Exception as e:
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    _get_logger().warning(
                        f"PV {self.pvname} put({value}) raised exception: {e} "
                        f"(attempt {attempt}/{self.MAX_RETRIES})"
                    )

            if attempt < self.MAX_RETRIES:
                self._retry_backoff(attempt, timeout)

        # All retries exhausted
        self._raise_put_error(value, last_exception)

    def _attempt_put(
        self, value, wait, timeout, use_complete, callback, callback_data
    ):
        """Attempt a single put operation"""
        return super().put(
            value,
            wait=wait,
            timeout=timeout,
            use_complete=use_complete,
            callback=callback,
            callback_data=callback_data,
        )

    def _raise_put_error(self, value, last_exception):
        """Raise appropriate error after all retries exhausted"""
        if last_exception:
            error_msg = (
                f"PV {self.pvname} put({value}) failed after {self.MAX_RETRIES} attempts. "
                f"Last exception: {last_exception}"
            )
            _get_logger().error(error_msg)
            raise PVPutError(error_msg) from last_exception
        else:
            error_msg = (
                f"PV {self.pvname} put({value}) failed after "
                f"{self.MAX_RETRIES} attempts"
            )
            _get_logger().error(error_msg)
            raise PVPutError(error_msg)

    def validate_value(
        self, value, min_val=None, max_val=None, allowed_values=None
    ):
        """
        Validate a PV value against constraints

        Args:
            value: Value to validate
            min_val: Minimum allowed value (optional) max_val: Maximum allowed value (optional)
            allowed_values: List/set of allowed values (optional)

        Raises:
            PVInvalidError: If value is invalid
        """
        if min_val is not None and value < min_val:
            error_msg = (
                f"PV {self.pvname} value {value} below minimum {min_val}"
            )
            _get_logger().error(error_msg)
            raise PVInvalidError(error_msg)

        if max_val is not None and value > max_val:
            error_msg = (
                f"PV {self.pvname} value {value} above maximum {max_val}"
            )
            _get_logger().error(error_msg)
            raise PVInvalidError(error_msg)

        if allowed_values is not None and value not in allowed_values:
            error_msg = f"PV {self.pvname} value {value} not in allowed values {allowed_values}"
            _get_logger().error(error_msg)
            raise PVInvalidError(error_msg)

        return True

    def check_alarm(self, raise_on_alarm=False):
        """
        Check PV alarm status

        Args:
            raise_on_alarm: If True, raise PVInvalidError on alarm condition

        Returns:
            Alarm severity value

        Raises:
            PVInvalidError: If raise_on_alarm=True and PV is alarming
        """
        self._ensure_connected()

        severity_snapshot = self.severity

        # Handle None severity
        if severity_snapshot is None:
            _get_logger().warning(f"PV {self.pvname} severity is None")
            severity_snapshot = EPICS_INVALID_VAL
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} severity unavailable")

        # Only log warnings and errors
        if severity_snapshot == EPICS_MINOR_VAL:
            _get_logger().warning(f"PV {self.pvname} has MINOR alarm")
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} has MINOR alarm")
        elif severity_snapshot == EPICS_MAJOR_VAL:
            _get_logger().error(f"PV {self.pvname} has MAJOR alarm")
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} has MAJOR alarm")
        elif severity_snapshot == EPICS_INVALID_VAL:
            _get_logger().error(f"PV {self.pvname} has INVALID alarm")
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} has INVALID alarm")

        return severity_snapshot

    @staticmethod
    def get_many(
        pvs: List["PV"],
        timeout: Optional[float] = None,
        raise_on_error: bool = True,
    ) -> List[Any]:
        """
        Get multiple PV values efficiently

        Args:
            pvs: List of PV objects
            timeout: Timeout for each get
            raise_on_error: If True, raise exception on any failure.
                           If False, failed PVs will have None in results.

        Returns:
            List of values in same order as input PVs

        Raises:
            PVGetError: If any PV fails to get and raise_on_error=True
        """
        results = []
        errors = []

        for pv in pvs:
            try:
                results.append(pv.get(timeout=timeout))
            except (PVConnectionError, PVGetError) as e:
                errors.append((pv.pvname, str(e)))
                results.append(None)

        if errors and raise_on_error:
            error_msg = f"Failed to get {len(errors)} PVs: {errors}"
            _get_logger().error(error_msg)
            raise PVGetError(error_msg)

        return results

    @staticmethod
    def put_many(
        pvs: List["PV"],
        values: List[Any],
        timeout: Optional[float] = None,
        wait: bool = True,
        raise_on_error: bool = True,
    ) -> List[bool]:
        """
        Put values to multiple PVs

        Args:
            pvs: List of PV objects
            values: List of values to write (must match length of pvs)
            timeout: Timeout for each put
            wait: Wait for completion
            raise_on_error: If True, raise exception on any failure

        Returns:
            List of success status (True/False) for each PV

        Raises:
            ValueError: If pvs and values lengths don't match
            PVPutError: If any PV fails to put and raise_on_error=True
        """
        if len(pvs) != len(values):
            raise ValueError(
                f"Length mismatch: {len(pvs)} PVs but {len(values)} values"
            )

        results = []
        errors = []

        for pv, value in zip(pvs, values):
            try:
                pv.put(value, timeout=timeout, wait=wait)
                results.append(True)
            except (PVConnectionError, PVPutError) as e:
                errors.append((pv.pvname, value, str(e)))
                results.append(False)

        if errors and raise_on_error:
            error_msg = f"Failed to put {len(errors)} PVs: {errors}"
            _get_logger().error(error_msg)
            raise PVPutError(error_msg)

        return results


def create_pv_safe(
    pvname: str,
    connection_timeout: Optional[float] = None,
    raise_on_failure: bool = True,
    **kwargs,
) -> Optional[PV]:
    """
    Safely create a PV with better error handling

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
            _get_logger().warning(f"Failed to create PV {pvname}: {e}")
            return None


def diagnose_pv_connection(pvname: str, timeout: float = 10.0) -> dict:
    """
    Diagnose PV connection issues

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
        _get_logger().info(f"Testing caget for {pvname}...")
        value = epics.caget(pvname, timeout=timeout)
        if value is not None:
            info["caget_works"] = True
            info["value"] = value
            _get_logger().info(f"caget successful: {value}")
        else:
            _get_logger().warning(f"caget returned None for {pvname}")

        # Try creating PV object
        _get_logger().info(f"Testing PV object creation for {pvname}...")
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
                _get_logger().info(f"PV.get() successful: {val}")
            except Exception as e:
                _get_logger().warning(f"PV.get() failed: {e}")
                info["error"] = f"get failed: {str(e)}"
        else:
            _get_logger().warning(f"PV object failed to connect for {pvname}")
            info["error"] = "PV object connection timeout"

        test_pv.disconnect()

    except Exception as e:
        info["error"] = str(e)
        _get_logger().error(f"Diagnostic error for {pvname}: {e}")

    _get_logger().info(f"PV Diagnostics for {pvname}: {info}")
    return info


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
    """
    # Don't use spec=PV to allow flexible attribute setting
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

    return mock_pv
