from time import sleep
from unittest.mock import MagicMock

from epics import PV as EPICS_PV

# Import your custom logger
from sc_linac_physics.utils.logger import custom_logger, BASE_LOG_DIR

# Create a logger for this module
logger = custom_logger(
    __name__, log_dir=str(BASE_LOG_DIR / "epics"), log_filename="pv_operations"
)

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
    ):
        if connection_timeout is None:
            connection_timeout = self.DEFAULT_CONNECTION_TIMEOUT

        super().__init__(
            pvname=pvname,
            connection_timeout=connection_timeout,
            callback=callback,
            form=form,
            verbose=verbose,
            auto_monitor=auto_monitor,
            count=count,
            connection_callback=connection_callback,
            access_callback=access_callback,
        )

        # Wait for initial connection
        if not self.wait_for_connection(timeout=connection_timeout):
            error_msg = (
                f"PV {pvname} failed to connect within {connection_timeout}s"
            )
            logger.error(error_msg)
            raise PVConnectionError(error_msg)

    def __str__(self):
        return f"{self.pvname}"

    def __repr__(self):
        status = "connected" if self.connected else "disconnected"
        return f"PV('{self.pvname}', {status})"

    @property
    def val(self):
        """Shorthand for getting current value"""
        return self.get()

    def _ensure_connected(self, timeout=None):
        """
        Ensure PV is connected, raise exception if not

        Raises:
            PVConnectionError: If connection fails
        """
        if self.connected:
            return

        timeout = timeout or self.DEFAULT_CONNECTION_TIMEOUT

        if not self.wait_for_connection(timeout=timeout):
            error_msg = f"PV {self.pvname} failed to connect within {timeout}s"
            logger.error(error_msg)
            raise PVConnectionError(error_msg)

        logger.warning(f"PV {self.pvname} reconnected after disconnection")

    def get(
        self,
        count=None,
        as_string=False,
        as_numpy=True,
        timeout=None,
        with_ctrlvars=False,
        use_monitor=None,
    ):
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
                    return value

                if attempt < self.MAX_RETRIES:
                    logger.warning(
                        f"PV {self.pvname} returned None "
                        f"(attempt {attempt}/{self.MAX_RETRIES})"
                    )
            except Exception as e:
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    logger.warning(
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
        try:
            self._ensure_connected(timeout=timeout)
        except PVConnectionError:
            pass  # Will be caught in next retry attempt

    def _raise_get_error(self, last_exception):
        """Raise appropriate error after all retries exhausted"""
        if last_exception:
            error_msg = (
                f"PV {self.pvname} get failed after {self.MAX_RETRIES} attempts. "
                f"Last exception: {last_exception}"
            )
            logger.error(error_msg)
            raise PVGetError(error_msg) from last_exception
        else:
            error_msg = (
                f"PV {self.pvname} get returned None after "
                f"{self.MAX_RETRIES} attempts"
            )
            logger.error(error_msg)
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
                    return  # Success

                if attempt < self.MAX_RETRIES:
                    logger.warning(
                        f"PV {self.pvname} put({value}) returned status {status} "
                        f"(attempt {attempt}/{self.MAX_RETRIES})"
                    )
            except Exception as e:
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    logger.warning(
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
            logger.error(error_msg)
            raise PVPutError(error_msg) from last_exception
        else:
            error_msg = (
                f"PV {self.pvname} put({value}) failed after "
                f"{self.MAX_RETRIES} attempts"
            )
            logger.error(error_msg)
            raise PVPutError(error_msg)

    def validate_value(
        self, value, min_val=None, max_val=None, allowed_values=None
    ):
        """
        Validate a PV value against constraints

        Args:
            value: Value to validate
            min_val: Minimum allowed value (optional)
            max_val: Maximum allowed value (optional)
            allowed_values: List/set of allowed values (optional)

        Raises:
            PVInvalidError: If value is invalid
        """
        if min_val is not None and value < min_val:
            error_msg = (
                f"PV {self.pvname} value {value} below minimum {min_val}"
            )
            logger.error(error_msg)
            raise PVInvalidError(error_msg)

        if max_val is not None and value > max_val:
            error_msg = (
                f"PV {self.pvname} value {value} above maximum {max_val}"
            )
            logger.error(error_msg)
            raise PVInvalidError(error_msg)

        if allowed_values is not None and value not in allowed_values:
            error_msg = f"PV {self.pvname} value {value} not in allowed values {allowed_values}"
            logger.error(error_msg)
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
        severity = self.severity

        # Only log warnings and errors
        if severity == EPICS_MINOR_VAL:
            logger.warning(f"PV {self.pvname} has MINOR alarm")
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} has MINOR alarm")
        elif severity == EPICS_MAJOR_VAL:
            logger.error(f"PV {self.pvname} has MAJOR alarm")
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} has MAJOR alarm")
        elif severity == EPICS_INVALID_VAL:
            logger.error(f"PV {self.pvname} has INVALID alarm")
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} has INVALID alarm")

        return severity


def make_mock_pv(
    pv_name: str = None,
    get_val=None,
    severity=EPICS_NO_ALARM_VAL,
    connected=True,
) -> MagicMock:
    """Create a mock PV for testing"""
    mock = MagicMock(spec=PV)
    mock.pvname = pv_name or "MOCK:PV"
    mock.put.return_value = None
    mock.get.return_value = get_val
    mock.severity = severity
    mock.connected = connected
    mock.auto_monitor = True
    mock.wait_for_connection.return_value = connected
    mock.validate_value.return_value = True
    mock.check_alarm.return_value = severity
    return mock
