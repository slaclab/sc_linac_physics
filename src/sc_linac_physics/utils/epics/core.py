import threading
from time import sleep
from typing import List, Any, Optional, Callable, Union

import numpy as np
from epics import PV as EPICS_PV

from sc_linac_physics.utils.epics.config import (
    PVConfig,
    EPICS_INVALID_VAL,
    EPICS_MINOR_VAL,
    EPICS_MAJOR_VAL,
)
from sc_linac_physics.utils.epics.exceptions import (
    PVConnectionError,
    PVGetError,
    PVPutError,
    PVInvalidError,
)
from sc_linac_physics.utils.epics.logger import get_logger


class PV(EPICS_PV):
    """
    Enhanced EPICS PV that always raises exceptions on failure.
    Never returns None - either returns a value or raises an exception.
    """

    # Default configuration (can be overridden per instance)
    default_config = PVConfig()

    def __init__(
        self,
        pvname: str,
        connection_timeout: Optional[float] = None,
        callback: Optional[Callable] = None,
        form: str = "time",
        verbose: bool = False,
        auto_monitor: bool = True,
        count: Optional[int] = None,
        connection_callback: Optional[Callable] = None,
        access_callback: Optional[Callable] = None,
        config: Optional[PVConfig] = None,
    ):
        """
        Create the PV. Does not wait for it to connect.

        The first get()/put() waits up to connection_timeout for the
        connection and raises PVConnectionError if it doesn't come up. To
        fail fast at a known point instead, call ensure_connected().

        Creating many PVs before using any of them lets Channel Access
        search for all of them at once.

        Args:
            pvname: Process variable name
            connection_timeout: Longest wait for the first connection
                (default config.connection_timeout)
            callback: User callback for value updates
            form: Data form ('time', 'ctrl', or 'native')
            verbose: Enable verbose output
            auto_monitor: Automatically monitor for changes
            count: Number of array elements to fetch
            connection_callback: Callback when connection state changes
            access_callback: Callback when access rights change
            config: Custom PVConfig (uses default_config if None)
        """
        self.config = config or self.default_config
        self._connection_lock = threading.RLock()
        self._user_callback = callback
        # First connection gets the full connection_timeout, even when the
        # get()/put() that triggers it passes a shorter one. Reconnects use
        # the caller's timeout.
        self._first_connect_timeout = (
            self.config.connection_timeout
            if connection_timeout is None
            else connection_timeout
        )
        self._has_connected = False

        super().__init__(
            pvname=pvname,
            connection_timeout=self._first_connect_timeout,
            callback=None,
            form=form,
            verbose=verbose,
            auto_monitor=auto_monitor,
            count=count,
            connection_callback=connection_callback,
            access_callback=access_callback,
        )

        # Registered whether or not the PV is connected yet, as pyepics
        # does: monitor callbacks start firing once it connects.
        if self._user_callback is not None:
            self.add_callback(self._user_callback)

    def __str__(self) -> str:
        return self.pvname

    def __repr__(self) -> str:
        status = "connected" if self.connected else "disconnected"
        value_str = ""
        if self.connected:
            try:
                value = self.value_or_none
                if value is not None:
                    value_str = f", value={value}"
            except Exception:
                pass
        return f"PV('{self.pvname}', {status}{value_str})"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    def ensure_connected(self, timeout: Optional[float] = None):
        """
        Wait for the PV to connect, or raise PVConnectionError.

        get() and put() already do this. Call it directly to fail at a
        known point, e.g. right after creating a PV the caller can't run
        without.

        Args:
            timeout: Longest wait. Default: connection_timeout for the
                first connection, config.connection_timeout afterwards.

        Raises:
            PVConnectionError: If the PV doesn't connect within timeout
        """
        self._ensure_connected(timeout=timeout)

    def _ensure_connected(self, timeout: Optional[float] = None):
        """
        Ensure PV is connected, raise exception if not.
        Thread-safe with reentrant lock.

        Args:
            timeout: Connection timeout

        Raises:
            PVConnectionError: If connection fails
        """
        # Quick check without lock
        if self.connected:
            self._has_connected = True
            return

        # Use reentrant lock to prevent race conditions
        with self._connection_lock:
            # Double-check after acquiring lock
            if self.connected:
                self._has_connected = True
                return

            first = not self._has_connected
            if first:
                timeout = max(
                    timeout if timeout is not None else 0.0,
                    self._first_connect_timeout,
                )
                verb = "connect"
                get_logger().debug(f"PV {self.pvname} connecting")
            else:
                if timeout is None:
                    timeout = self.config.connection_timeout
                verb = "reconnect"
                get_logger().warning(
                    f"PV {self.pvname} disconnected, attempting to reconnect"
                )

            if not self.wait_for_connection(timeout=timeout):
                error_msg = (
                    f"PV {self.pvname} failed to {verb} within {timeout}s"
                )
                get_logger().error(error_msg)
                raise PVConnectionError(error_msg)

            self._has_connected = True
            if not first:
                get_logger().info(f"PV {self.pvname} reconnected successfully")

    def disconnect(self, deepclean: bool = True):
        """Clean disconnect"""
        try:
            super().disconnect(deepclean=deepclean)
        except Exception as e:
            get_logger().warning(f"Error disconnecting PV {self.pvname}: {e}")

    @property
    def val(self) -> Union[int, float, str, np.ndarray]:
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
        Get PV value with automatic retry logic.

        Args:
            count: Number of elements to fetch
            as_string: Return value as string
            as_numpy: Return array values as numpy arrays
            timeout: Timeout for get operation
            with_ctrlvars: Include control variables
            use_monitor: Use cached monitored value

        Returns:
            PV value (never None)

        Raises:
            PVConnectionError: If PV is not connected
            PVGetError: If get operation fails after retries
        """
        if timeout is None:
            timeout = self.config.get_timeout
        use_monitor = (
            use_monitor if use_monitor is not None else self.auto_monitor
        )

        self._ensure_connected(timeout=timeout)

        return self._execute_with_retry(
            operation="get",
            operation_func=lambda: super(PV, self).get(
                count=count,
                as_string=as_string,
                as_numpy=as_numpy,
                timeout=timeout,
                with_ctrlvars=with_ctrlvars,
                use_monitor=use_monitor,
            ),
            timeout=timeout,
        )

    def put(
        self,
        value: Any,
        wait: bool = True,
        timeout: Optional[float] = None,
        use_complete: bool = False,
        callback: Optional[Callable] = None,
        callback_data: Optional[Any] = None,
    ):
        """
        Put value to PV. Retried only when nothing was sent.

        pyepics' put returns:
          1    -- sent, and (with wait=True) completion confirmed
          -1   -- sent, but completion not confirmed within timeout
          None -- PV not connected, nothing sent
        It raises on bad values or when CA refuses to queue the request.

        Only None is retried. A -1 or an exception raises PVPutError on
        the first attempt, so a command PV (abort, reset, start) is never
        written twice by this wrapper.

        Args:
            value: Value to write
            wait: Wait for completion
            timeout: Timeout for put operation
            use_complete: Use completion callback
            callback: Callback function
            callback_data: Data to pass to callback

        Raises:
            PVConnectionError: If PV is not connected
            PVPutError: If the put was sent but not confirmed, raised, or
                never got sent after max_retries attempts
        """
        if timeout is None:
            timeout = self.config.put_timeout

        # Reconnect wait is bounded by connection_timeout, not put_timeout:
        # a disconnected PV should not hold a put for 30 s before it starts.
        self._ensure_connected(
            timeout=min(timeout, self.config.connection_timeout)
        )

        for attempt in range(1, self.config.max_retries + 1):
            try:
                status = super().put(
                    value,
                    wait=wait,
                    timeout=timeout,
                    use_complete=use_complete,
                    callback=callback,
                    callback_data=callback_data,
                )
            except Exception as e:
                error_msg = f"PV {self.pvname} put of {value!r} raised: {e}"
                get_logger().error(error_msg)
                raise PVPutError(error_msg) from e

            if status == 1:
                if attempt > 1:
                    get_logger().info(
                        f"PV {self.pvname} put succeeded on attempt {attempt}"
                    )
                return

            if status is not None:
                error_msg = (
                    f"PV {self.pvname} put of {value!r} was sent but not "
                    f"confirmed within {timeout}s (status {status}); "
                    f"not re-sent"
                )
                get_logger().error(error_msg)
                raise PVPutError(error_msg)

            # status is None: not connected, nothing sent. Safe to retry.
            if attempt < self.config.max_retries:
                get_logger().warning(
                    f"PV {self.pvname} put not sent, PV disconnected "
                    f"(attempt {attempt}/{self.config.max_retries})"
                )
                self._retry_backoff(
                    attempt, min(timeout, self.config.connection_timeout)
                )

        error_msg = (
            f"PV {self.pvname} put of {value!r} not sent after "
            f"{self.config.max_retries} attempts: PV disconnected"
        )
        get_logger().error(error_msg)
        raise PVPutError(error_msg)

    def _execute_with_retry(
        self,
        operation: str,
        operation_func: Callable,
        timeout: float,
        context: Optional[dict] = None,
    ) -> Any:
        """
        Execute PV operation with retry logic.

        Args:
            operation: Operation name ('get' or 'put')
            operation_func: Function to execute
            timeout: Operation timeout
            context: Additional context for error messages

        Returns:
            Operation result (for 'get')

        Raises:
            PVGetError or PVPutError: If operation fails after retries
        """
        context = context or {}
        last_exception = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                result = operation_func()

                # Only get() comes through here; put() has its own loop
                # because a put must not be re-sent once it went out.
                if result is not None:
                    if attempt > 1:
                        get_logger().info(
                            f"PV {self.pvname} {operation} succeeded on attempt {attempt}"
                        )
                    return result

                # Operation returned failure status
                if attempt < self.config.max_retries:
                    get_logger().warning(
                        f"PV {self.pvname} {operation} failed "
                        f"(attempt {attempt}/{self.config.max_retries})"
                    )

            except Exception as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    get_logger().warning(
                        f"PV {self.pvname} {operation} raised exception: {e} "
                        f"(attempt {attempt}/{self.config.max_retries})"
                    )

            # Retry with backoff
            if attempt < self.config.max_retries:
                self._retry_backoff(attempt, timeout)

        # All retries exhausted - raise appropriate error
        self._raise_operation_error(operation, last_exception, context)

    def _retry_backoff(self, attempt: int, timeout: float):
        """Handle retry delay and reconnection attempt"""
        # Linear backoff: retry_delay, 2 x retry_delay, ...
        sleep(self.config.retry_delay * attempt)

        # Try to reconnect if disconnected
        if not self.connected:
            try:
                self._ensure_connected(timeout=timeout)
            except PVConnectionError as e:
                get_logger().debug(f"Reconnection attempt failed: {e}")

    def _raise_operation_error(
        self, operation: str, last_exception: Optional[Exception], context: dict
    ):
        """Raise appropriate error after retries exhausted"""
        error_class = PVGetError if operation == "get" else PVPutError

        context_str = ""
        if context:
            context_str = f" with {context}"

        error_msg = (
            f"PV {self.pvname} {operation}{context_str} failed after "
            f"{self.config.max_retries} attempts"
        )

        if last_exception:
            error_msg += f". Last exception: {last_exception}"
            get_logger().error(error_msg)
            raise error_class(error_msg) from last_exception
        else:
            get_logger().error(error_msg)
            raise error_class(error_msg)

    def validate_value(
        self,
        value: Any,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        allowed_values: Optional[set] = None,
    ) -> bool:
        """
        Validate a PV value against constraints.

        Args:
            value: Value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            allowed_values: Set of allowed values

        Returns:
            True if valid

        Raises:
            PVInvalidError: If value is invalid
        """
        if min_val is not None and value < min_val:
            error_msg = (
                f"PV {self.pvname} value {value} below minimum {min_val}"
            )
            get_logger().error(error_msg)
            raise PVInvalidError(error_msg)

        if max_val is not None and value > max_val:
            error_msg = (
                f"PV {self.pvname} value {value} above maximum {max_val}"
            )
            get_logger().error(error_msg)
            raise PVInvalidError(error_msg)

        if allowed_values is not None and value not in allowed_values:
            error_msg = f"PV {self.pvname} value {value} not in allowed values {allowed_values}"
            get_logger().error(error_msg)
            raise PVInvalidError(error_msg)

        return True

    def check_alarm(self, raise_on_alarm: bool = False) -> int:
        """
        Check PV alarm status.

        Args:
            raise_on_alarm: If True, raise PVInvalidError on alarm condition

        Returns:
            Alarm severity value

        Raises:
            PVInvalidError: If raise_on_alarm=True and PV is alarming
        """
        self._ensure_connected()

        severity = self.severity

        if severity is None:
            get_logger().warning(f"PV {self.pvname} severity is None")
            severity = EPICS_INVALID_VAL
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} severity unavailable")

        # Only log warnings and errors
        if severity == EPICS_MINOR_VAL:
            get_logger().warning(f"PV {self.pvname} has MINOR alarm")
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} has MINOR alarm")
        elif severity == EPICS_MAJOR_VAL:
            get_logger().error(f"PV {self.pvname} has MAJOR alarm")
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} has MAJOR alarm")
        elif severity == EPICS_INVALID_VAL:
            get_logger().error(f"PV {self.pvname} has INVALID alarm")
            if raise_on_alarm:
                raise PVInvalidError(f"PV {self.pvname} has INVALID alarm")

        return severity

    @staticmethod
    def get_many(
        pvs: List["PV"],
        timeout: Optional[float] = None,
        raise_on_error: bool = True,
    ) -> List[Any]:
        """
        Get multiple PV values efficiently.

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
            get_logger().error(error_msg)
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
        Put values to multiple PVs.

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
            get_logger().error(error_msg)
            raise PVPutError(error_msg)

        return results
