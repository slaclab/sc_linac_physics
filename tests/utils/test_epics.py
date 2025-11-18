from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from sc_linac_physics.utils.epics import (
    PV,
    PVConnectionError,
    PVGetError,
    PVPutError,
    PVInvalidError,
    make_mock_pv,
    EPICS_NO_ALARM_VAL,
    EPICS_MINOR_VAL,
    EPICS_MAJOR_VAL,
    EPICS_INVALID_VAL,
)


class TestPVInitialization:
    """Test PV initialization and connection"""

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_successful_connection(self, mock_wait, mock_init):
        """Test PV connects successfully"""
        mock_init.return_value = None
        mock_wait.return_value = True

        pv = PV("TEST:PV")
        assert pv is not None

        mock_init.assert_called_once()
        mock_wait.assert_called_once_with(timeout=PV.DEFAULT_CONNECTION_TIMEOUT)

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_connection_failure(self, mock_wait, mock_init):
        """Test PV raises exception on connection failure"""
        mock_init.return_value = None
        mock_wait.return_value = False

        with pytest.raises(PVConnectionError, match="failed to connect"):
            PV("TEST:PV")

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_custom_connection_timeout(self, mock_wait, mock_init):
        """Test custom connection timeout is used"""
        mock_init.return_value = None
        mock_wait.return_value = True

        pv = PV("TEST:PV", connection_timeout=10.0)
        assert pv is not None

        mock_wait.assert_called_once_with(timeout=10.0)

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_init_with_all_parameters(self, mock_wait, mock_init):
        """Test initialization with all parameters"""
        mock_init.return_value = None
        mock_wait.return_value = True

        callback = MagicMock()
        conn_callback = MagicMock()
        access_callback = MagicMock()

        pv = PV(
            "TEST:PV",
            connection_timeout=5.0,
            callback=callback,
            form="native",
            verbose=True,
            auto_monitor=False,
            count=10,
            connection_callback=conn_callback,
            access_callback=access_callback,
        )
        assert pv is not None

        # Verify init was called with correct parameters
        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["pvname"] == "TEST:PV"
        assert call_kwargs["connection_timeout"] == 5.0
        assert call_kwargs["callback"] == callback
        assert call_kwargs["form"] == "native"
        assert call_kwargs["verbose"] is True
        assert call_kwargs["auto_monitor"] is False
        assert call_kwargs["count"] == 10
        assert call_kwargs["connection_callback"] == conn_callback
        assert call_kwargs["access_callback"] == access_callback


class TestPVStringRepresentation:
    """Test PV string representations"""

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_str(self, mock_wait, mock_init):
        """Test __str__ returns PV name"""
        mock_init.return_value = None
        mock_wait.return_value = True

        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"

        assert str(pv) == "TEST:PV"

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_repr_connected(self, mock_wait, mock_init):
        """Test __repr__ when connected"""
        mock_init.return_value = None
        mock_wait.return_value = True

        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = True

        assert repr(pv) == "PV('TEST:PV', connected)"

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_repr_disconnected(self, mock_wait, mock_init):
        """Test __repr__ when disconnected"""
        mock_init.return_value = None
        mock_wait.return_value = True

        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = False

        assert repr(pv) == "PV('TEST:PV', disconnected)"


class TestPVGet:
    """Test PV get operations"""

    def _setup_pv(self, mock_init, mock_wait):
        """Helper to setup a PV with required attributes"""
        mock_init.return_value = None
        mock_wait.return_value = True
        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = True
        pv._auto_monitor = True
        pv.context = 123  # Mock context ID
        return pv

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    def test_successful_get(self, mock_get, mock_wait, mock_init):
        """Test successful get operation"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_get.return_value = 42.0

        result = pv.get()

        assert result == 42.0
        mock_get.assert_called_once()

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    def test_get_with_val_property(self, mock_get, mock_wait, mock_init):
        """Test .val property uses get()"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_get.return_value = 42.0

        result = pv.val

        assert result == 42.0

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    def test_get_disconnected_raises_error(
        self, mock_get, mock_wait, mock_init
    ):
        """Test get raises error when disconnected"""
        mock_init.return_value = None
        mock_wait.side_effect = [
            True,
            False,
        ]  # Connect initially, fail on reconnect

        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = False
        pv._auto_monitor = True
        pv.context = 123

        with pytest.raises(PVConnectionError):
            pv.get()

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    @patch("sc_linac_physics.utils.epics.sleep")
    def test_get_retries_on_none(
        self, mock_sleep, mock_get, mock_wait, mock_init
    ):
        """Test get retries when None is returned"""
        pv = self._setup_pv(mock_init, mock_wait)
        pv._auto_monitor = False
        mock_get.side_effect = [
            None,
            None,
            42.0,
        ]  # Fail twice, succeed third time

        result = pv.get()

        assert result == 42.0
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    @patch("sc_linac_physics.utils.epics.sleep")
    def test_get_raises_after_max_retries(
        self, mock_sleep, mock_get, mock_wait, mock_init
    ):
        """Test get raises error after max retries"""
        pv = self._setup_pv(mock_init, mock_wait)
        pv._auto_monitor = False
        mock_get.return_value = None  # Always return None

        with pytest.raises(PVGetError, match="returned None after"):
            pv.get()

        assert mock_get.call_count == PV.MAX_RETRIES

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    @patch("sc_linac_physics.utils.epics.sleep")
    def test_get_retries_on_exception(
        self, mock_sleep, mock_get, mock_wait, mock_init
    ):
        """Test get retries on exception"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_get.side_effect = [
            RuntimeError("Error 1"),
            RuntimeError("Error 2"),
            42.0,
        ]

        result = pv.get()

        assert result == 42.0
        assert mock_get.call_count == 3

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    @patch("sc_linac_physics.utils.epics.sleep")
    def test_get_raises_with_exception_chain(
        self, mock_sleep, mock_get, mock_wait, mock_init
    ):
        """Test get raises error with exception chain after max retries"""
        pv = self._setup_pv(mock_init, mock_wait)
        test_error = RuntimeError("Test error")
        mock_get.side_effect = test_error

        with pytest.raises(PVGetError) as exc_info:
            pv.get()

        # Check exception chaining
        assert exc_info.value.__cause__ == test_error

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    def test_get_passes_parameters(self, mock_get, mock_wait, mock_init):
        """Test get passes all parameters correctly"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_get.return_value = [1, 2, 3]

        pv.get(count=3, as_string=True, timeout=5.0)

        mock_get.assert_called_once_with(
            count=3,
            as_string=True,
            as_numpy=True,
            timeout=5.0,
            with_ctrlvars=False,
            use_monitor=True,
        )

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    def test_get_with_use_monitor_false(self, mock_get, mock_wait, mock_init):
        """Test get with use_monitor=False"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_get.return_value = 42.0

        pv.get(use_monitor=False)

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["use_monitor"] is False

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    def test_get_uses_auto_monitor_by_default(
        self, mock_get, mock_wait, mock_init
    ):
        """Test get uses auto_monitor setting by default"""
        pv = self._setup_pv(mock_init, mock_wait)
        pv._auto_monitor = False
        mock_get.return_value = 42.0

        pv.get()

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["use_monitor"] is False


class TestPVPut:
    """Test PV put operations"""

    def _setup_pv(self, mock_init, mock_wait):
        """Helper to setup a PV with required attributes"""
        mock_init.return_value = None
        mock_wait.return_value = True
        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = True
        pv.context = 123
        return pv

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.put")
    def test_successful_put(self, mock_put, mock_wait, mock_init):
        """Test successful put operation"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_put.return_value = 1  # Success status

        pv.put(42.0)

        mock_put.assert_called_once()

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.put")
    def test_put_disconnected_raises_error(
        self, mock_put, mock_wait, mock_init
    ):
        """Test put raises error when disconnected"""
        mock_init.return_value = None
        mock_wait.side_effect = [True, False]

        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = False

        with pytest.raises(PVConnectionError):
            pv.put(42.0)

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.put")
    @patch("sc_linac_physics.utils.epics.sleep")
    def test_put_retries_on_failure(
        self, mock_sleep, mock_put, mock_wait, mock_init
    ):
        """Test put retries on failure"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_put.side_effect = [0, 0, 1]  # Fail twice, succeed third time

        pv.put(42.0)

        assert mock_put.call_count == 3

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.put")
    @patch("sc_linac_physics.utils.epics.sleep")
    def test_put_raises_after_max_retries(
        self, mock_sleep, mock_put, mock_wait, mock_init
    ):
        """Test put raises error after max retries"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_put.return_value = 0  # Always fail

        with pytest.raises(PVPutError, match="failed after"):
            pv.put(42.0)

        assert mock_put.call_count == PV.MAX_RETRIES

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.put")
    @patch("sc_linac_physics.utils.epics.sleep")
    def test_put_retries_on_exception(
        self, mock_sleep, mock_put, mock_wait, mock_init
    ):
        """Test put retries on exception"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_put.side_effect = [
            RuntimeError("Error"),
            RuntimeError("Error 2"),
            1,
        ]

        pv.put(42.0)

        assert mock_put.call_count == 3

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.put")
    def test_put_passes_parameters(self, mock_put, mock_wait, mock_init):
        """Test put passes all parameters correctly"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_put.return_value = 1

        callback = MagicMock()
        pv.put(42.0, wait=False, timeout=10.0, callback=callback)

        mock_put.assert_called_once_with(
            42.0,
            wait=False,
            timeout=10.0,
            use_complete=False,
            callback=callback,
            callback_data=None,
        )

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.put")
    @patch("sc_linac_physics.utils.epics.sleep")
    def test_put_raises_with_exception_chain(
        self, mock_sleep, mock_put, mock_wait, mock_init
    ):
        """Test put raises error with exception chain after max retries"""
        pv = self._setup_pv(mock_init, mock_wait)
        test_error = RuntimeError("Test error")
        mock_put.side_effect = test_error

        with pytest.raises(PVPutError) as exc_info:
            pv.put(42.0)

        # Check exception chaining
        assert exc_info.value.__cause__ == test_error


class TestPVValidation:
    """Test PV value validation"""

    def _setup_pv(self, mock_init, mock_wait):
        """Helper to setup a PV with required attributes"""
        mock_init.return_value = None
        mock_wait.return_value = True
        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        return pv

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_validate_min_value_pass(self, mock_wait, mock_init):
        """Test validation passes for value above minimum"""
        pv = self._setup_pv(mock_init, mock_wait)

        assert pv.validate_value(10, min_val=5)

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_validate_min_value_fail(self, mock_wait, mock_init):
        """Test validation fails for value below minimum"""
        pv = self._setup_pv(mock_init, mock_wait)

        with pytest.raises(PVInvalidError, match="below minimum"):
            pv.validate_value(3, min_val=5)

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_validate_max_value_pass(self, mock_wait, mock_init):
        """Test validation passes for value below maximum"""
        pv = self._setup_pv(mock_init, mock_wait)

        assert pv.validate_value(5, max_val=10)

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_validate_max_value_fail(self, mock_wait, mock_init):
        """Test validation fails for value above maximum"""
        pv = self._setup_pv(mock_init, mock_wait)

        with pytest.raises(PVInvalidError, match="above maximum"):
            pv.validate_value(15, max_val=10)

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_validate_allowed_values_pass(self, mock_wait, mock_init):
        """Test validation passes for allowed value"""
        pv = self._setup_pv(mock_init, mock_wait)

        assert pv.validate_value("ON", allowed_values=["ON", "OFF"])

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_validate_allowed_values_fail(self, mock_wait, mock_init):
        """Test validation fails for disallowed value"""
        pv = self._setup_pv(mock_init, mock_wait)

        with pytest.raises(PVInvalidError, match="not in allowed values"):
            pv.validate_value("INVALID", allowed_values=["ON", "OFF"])

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_validate_combined_constraints(self, mock_wait, mock_init):
        """Test validation with multiple constraints"""
        pv = self._setup_pv(mock_init, mock_wait)

        assert pv.validate_value(
            7, min_val=5, max_val=10, allowed_values=[5, 7, 9]
        )


class TestPVAlarmCheck:
    """Test PV alarm checking"""

    def _setup_pv(self, mock_init, mock_wait):
        """Helper to setup a PV with required attributes"""
        mock_init.return_value = None
        mock_wait.return_value = True
        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        return pv

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch(
        "sc_linac_physics.utils.epics.PV.severity", new_callable=PropertyMock
    )
    def test_check_alarm_no_alarm(self, mock_severity, mock_wait, mock_init):
        """Test check_alarm with no alarm"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_severity.return_value = EPICS_NO_ALARM_VAL

        severity = pv.check_alarm()

        assert severity == EPICS_NO_ALARM_VAL

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch(
        "sc_linac_physics.utils.epics.PV.severity", new_callable=PropertyMock
    )
    def test_check_alarm_minor(self, mock_severity, mock_wait, mock_init):
        """Test check_alarm with minor alarm"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_severity.return_value = EPICS_MINOR_VAL

        severity = pv.check_alarm()

        assert severity == EPICS_MINOR_VAL

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch(
        "sc_linac_physics.utils.epics.PV.severity", new_callable=PropertyMock
    )
    def test_check_alarm_minor_raises(
        self, mock_severity, mock_wait, mock_init
    ):
        """Test check_alarm raises on minor alarm when requested"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_severity.return_value = EPICS_MINOR_VAL

        with pytest.raises(PVInvalidError, match="MINOR alarm"):
            pv.check_alarm(raise_on_alarm=True)

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch(
        "sc_linac_physics.utils.epics.PV.severity", new_callable=PropertyMock
    )
    def test_check_alarm_major(self, mock_severity, mock_wait, mock_init):
        """Test check_alarm with major alarm"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_severity.return_value = EPICS_MAJOR_VAL

        severity = pv.check_alarm()

        assert severity == EPICS_MAJOR_VAL

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch(
        "sc_linac_physics.utils.epics.PV.severity", new_callable=PropertyMock
    )
    def test_check_alarm_major_raises(
        self, mock_severity, mock_wait, mock_init
    ):
        """Test check_alarm raises on major alarm when requested"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_severity.return_value = EPICS_MAJOR_VAL

        with pytest.raises(PVInvalidError, match="MAJOR alarm"):
            pv.check_alarm(raise_on_alarm=True)

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch(
        "sc_linac_physics.utils.epics.PV.severity", new_callable=PropertyMock
    )
    def test_check_alarm_invalid(self, mock_severity, mock_wait, mock_init):
        """Test check_alarm with invalid alarm"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_severity.return_value = EPICS_INVALID_VAL

        severity = pv.check_alarm()

        assert severity == EPICS_INVALID_VAL

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch(
        "sc_linac_physics.utils.epics.PV.severity", new_callable=PropertyMock
    )
    def test_check_alarm_invalid_raises(
        self, mock_severity, mock_wait, mock_init
    ):
        """Test check_alarm raises on invalid alarm when requested"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_severity.return_value = EPICS_INVALID_VAL

        with pytest.raises(PVInvalidError, match="INVALID alarm"):
            pv.check_alarm(raise_on_alarm=True)


class TestMakeMockPV:
    """Test mock PV creation utility"""

    def test_make_mock_pv_defaults(self):
        """Test make_mock_pv with default values"""
        mock = make_mock_pv()

        assert mock.pvname == "MOCK:PV"
        assert mock.get.return_value is None
        assert mock.severity == EPICS_NO_ALARM_VAL
        assert mock.connected is True
        assert mock.auto_monitor is True

    def test_make_mock_pv_custom_values(self):
        """Test make_mock_pv with custom values"""
        mock = make_mock_pv(
            pv_name="CUSTOM:PV",
            get_val=42.0,
            severity=EPICS_MINOR_VAL,
            connected=False,
        )

        assert mock.pvname == "CUSTOM:PV"
        assert mock.get.return_value == 42.0
        assert mock.severity == EPICS_MINOR_VAL
        assert mock.connected is False

    def test_make_mock_pv_methods(self):
        """Test mock PV has expected methods"""
        mock = make_mock_pv()

        # Test that methods can be called
        mock.put(42.0)
        mock.get()
        mock.validate_value(10)
        mock.check_alarm()

        # Verify calls
        mock.put.assert_called_once_with(42.0)
        mock.get.assert_called_once()
        mock.validate_value.assert_called_once_with(10)
        mock.check_alarm.assert_called_once()


class TestRetryBackoff:
    """Test retry backoff behavior"""

    def _setup_pv(self, mock_init, mock_wait):
        """Helper to setup a PV with required attributes"""
        mock_init.return_value = None
        mock_wait.return_value = True
        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = True
        pv._auto_monitor = False
        pv.context = 123
        return pv

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.get")
    @patch("sc_linac_physics.utils.epics.sleep")
    def test_exponential_backoff(
        self, mock_sleep, mock_get, mock_wait, mock_init
    ):
        """Test retry uses exponential backoff"""
        pv = self._setup_pv(mock_init, mock_wait)
        mock_get.side_effect = [None, None, 42.0]

        pv.get()

        # Check that sleep was called with increasing delays
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert len(sleep_calls) == 2
        assert sleep_calls[0] < sleep_calls[1]  # Exponential backoff
        assert sleep_calls[0] == PV.RETRY_DELAY * 1
        assert sleep_calls[1] == PV.RETRY_DELAY * 2


class TestEnsureConnected:
    """Test _ensure_connected method"""

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_ensure_connected_when_connected(self, mock_wait, mock_init):
        """Test _ensure_connected does nothing when already connected"""
        mock_init.return_value = None
        mock_wait.return_value = True

        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = True

        pv._ensure_connected()

        # Should not try to reconnect
        assert mock_wait.call_count == 1  # Only initial connection

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_ensure_connected_reconnects(self, mock_wait, mock_init):
        """Test _ensure_connected reconnects when disconnected"""
        mock_init.return_value = None
        mock_wait.return_value = True

        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = False

        pv._ensure_connected()

        # Should attempt reconnection
        assert mock_wait.call_count == 2

    @patch("sc_linac_physics.utils.epics.EPICS_PV.__init__")
    @patch("sc_linac_physics.utils.epics.EPICS_PV.wait_for_connection")
    def test_ensure_connected_fails(self, mock_wait, mock_init):
        """Test _ensure_connected raises error when reconnection fails"""
        mock_init.return_value = None
        mock_wait.side_effect = [True, False]  # Initial success, reconnect fail

        pv = PV("TEST:PV")
        pv.pvname = "TEST:PV"
        pv.connected = False

        with pytest.raises(PVConnectionError):
            pv._ensure_connected()
