import threading
from time import sleep
from typing import List, Any, Optional, Callable, Union

import epics
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
        require_connection: bool = True,
        config: Optional[PVConfig] = None,
        _skip_connection_wait: bool = False,
    ):
        """
        Initialize PV with enhanced error handling.

        Args:
            pvname: Process variable name
            connection_timeout: Timeout for initial connection
            callback: User callback for value updates
            form: Data form ('time', 'ctrl', or 'native')
            verbose: Enable verbose output
            auto_monitor: Automatically monitor for changes
            count: Number of array elements to fetch
            connection_callback: Callback when connection state changes
            access_callback: Callback when access rights change
            require_connection: Raise error if connection fails
            config: Custom PVConfig (uses default_config if None)
            _skip_connection_wait: Internal flag for batch creation
        """
        # Initialize configuration and guards
        self.config = config or self.default_config
        self._connection_lock = threading.RLock()
        self._user_callback = callback
        self._require_connection = require_connection

        if connection_timeout is None:
            connection_timeout = self.config.connection_timeout

        # Initialize parent (without user callback initially)
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

        # Skip connection wait for batch operations
        if _skip_connection_wait:
            self._add_user_callback_if_connected()
            return

        # Wait for initial connection
        self._wait_for_connection_with_retry(connection_timeout)
        self._add_user_callback_if_connected()

    def _add_user_callback_if_connected(self):
        """Add user callback if PV is connected"""
        if self._user_callback is not None and self.connected:
            self.add_callback(self._user_callback)

    def _wait_for_connection_with_retry(self, timeout: float):
        """Wait for initial connection with retry logic"""
        # Quick initial check
        if self.connected:
            return

        # Give pyepics a moment to process
        sleep(0.01)

        # First connection attempt
        if self.wait_for_connection(timeout=timeout):
            return

        # Retry logic
        retry_attempts = 2
        retry_timeout = min(1.0, timeout / 2)

        for attempt in range(retry_attempts):
            get_logger().debug(
                f"Retry connection attempt {attempt + 1}/{retry_attempts} for {self.pvname}"
            )
            sleep(0.1)

            if self.wait_for_connection(timeout=retry_timeout):
                get_logger().info(
                    f"PV {self.pvname} connected on retry attempt {attempt + 1}"
                )
                return

        # Connection failed
        error_msg = f"PV {self.pvname} failed to connect within {timeout}s"
        if self._require_connection:
            get_logger().error(error_msg)
            raise PVConnectionError(error_msg)
        else:
            get_logger().warning(error_msg + " (connection not required)")

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
            return

        # Use reentrant lock to prevent race conditions
        with self._connection_lock:
            # Double-check after acquiring lock
            if self.connected:
                return

            timeout = timeout or self.config.connection_timeout

            get_logger().warning(
                f"PV {self.pvname} disconnected, attempting to reconnect"
            )

            if not self.wait_for_connection(timeout=timeout):
                error_msg = (
                    f"PV {self.pvname} failed to reconnect within {timeout}s"
                )
                get_logger().error(error_msg)
                raise PVConnectionError(error_msg)

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
        timeout = timeout or self.config.get_timeout
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
        Put value to PV with automatic retry logic.

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
        timeout = timeout or self.config.put_timeout

        self._ensure_connected(timeout=timeout)

        self._execute_with_retry(
            operation="put",
            operation_func=lambda: super(PV, self).put(
                value,
                wait=wait,
                timeout=timeout,
                use_complete=use_complete,
                callback=callback,
                callback_data=callback_data,
            ),
            timeout=timeout,
            context={"value": value},
        )

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

                # Check success based on operation type
                if operation == "get":
                    success = result is not None
                else:  # put
                    success = result == 1

                if success:
                    if attempt > 1:
                        get_logger().info(
                            f"PV {self.pvname} {operation} succeeded on attempt {attempt}"
                        )
                    return result if operation == "get" else None

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
        # Exponential backoff
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

    @classmethod
    def batch_create(
        cls,
        pv_names: List[str],
        connection_timeout: float = 0.5,
        auto_monitor: bool = False,
        require_connection: bool = False,
        config: Optional[PVConfig] = None,
    ) -> List["PV"]:
        """
        Create multiple PVs with optimized batch connection.

        This method is significantly faster than creating PVs one at a time
        because it allows EPICS Channel Access to connect to multiple PVs
        simultaneously in the background.

        Args:
            pv_names: List of PV names to create
            connection_timeout: Timeout for each PV connection (seconds)
            auto_monitor: Whether to enable automatic monitoring
            require_connection: If True, raise error if any PV fails to connect
            config: Custom PVConfig to use for all PVs

        Returns:
            List of PV objects in the same order as pv_names

        Raises:
            PVConnectionError: If require_connection=True and any PV fails

        Example:
            >>> pv_names = ["PV:1", "PV:2", "PV:3"]
            >>> pvs = PV.batch_create(pv_names, connection_timeout=1.0)
            >>> # Much faster than:
            >>> # pvs = [PV(name) for name in pv_names]
        """
        if not pv_names:
            return []

        # Phase 1: Create raw EPICS PVs (non-blocking, fast)
        raw_pvs = cls._create_raw_pvs(
            pv_names, auto_monitor, connection_timeout
        )

        # Phase 2: Wait for all connections in batch
        failed_pvs = cls._wait_for_connections(
            pv_names, raw_pvs, connection_timeout
        )

        # Phase 3: Wrap in our PV class
        return cls._wrap_pvs(
            pv_names,
            auto_monitor,
            require_connection,
            config,
            failed_pvs,
        )

    @staticmethod
    def _create_raw_pvs(
        pv_names: List[str],
        auto_monitor: bool,
        connection_timeout: float,
    ) -> List[Optional[epics.PV]]:
        """Create raw EPICS PV objects without waiting for connection."""
        raw_pvs = []
        for pv_name in pv_names:
            try:
                raw_pv = epics.PV(
                    pv_name,
                    auto_monitor=auto_monitor,
                    connection_timeout=connection_timeout,
                )
                raw_pvs.append(raw_pv)
            except Exception as e:
                get_logger().warning(f"Failed to create raw PV {pv_name}: {e}")
                raw_pvs.append(None)
        return raw_pvs

    @staticmethod
    def _wait_for_connections(
        pv_names: List[str],
        raw_pvs: List[Optional[epics.PV]],
        connection_timeout: float,
    ) -> List[str]:
        """Wait for raw PVs to connect and return list of failed PV names."""
        failed_pvs = []

        for pv_name, raw_pv in zip(pv_names, raw_pvs):
            if raw_pv is None:
                failed_pvs.append(pv_name)
                continue

            if not raw_pv.wait_for_connection(timeout=connection_timeout):
                failed_pvs.append(pv_name)

        if failed_pvs:
            get_logger().warning(
                f"Failed to connect to {len(failed_pvs)} PVs: "
                f"{failed_pvs[:5]}"
                + (
                    f" and {len(failed_pvs)-5} more"
                    if len(failed_pvs) > 5
                    else ""
                )
            )

        return failed_pvs

    @classmethod
    def _wrap_pvs(
        cls,
        pv_names: List[str],
        auto_monitor: bool,
        require_connection: bool,
        config: Optional[PVConfig],
        failed_pvs: List[str],
    ) -> List[Optional["PV"]]:
        """Wrap raw EPICS PVs in our PV class."""
        wrapped_pvs = []
        for pv_name in pv_names:
            try:
                pv = cls(
                    pv_name,
                    connection_timeout=0.1,  # Short timeout since already connected
                    auto_monitor=auto_monitor,
                    require_connection=require_connection,
                    config=config,
                    _skip_connection_wait=True,  # Skip wait, already connected
                )
                wrapped_pvs.append(pv)
            except Exception as e:
                if require_connection:
                    raise PVConnectionError(
                        f"Failed to create PV {pv_name} in batch: {e}"
                    )
                else:
                    get_logger().warning(f"Failed to wrap PV {pv_name}: {e}")
                    wrapped_pvs.append(None)

        return wrapped_pvs

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
