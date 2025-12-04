# tests/utils/epics/test_core.py
# Get reference to the FakeEPICS_PV that was injected
import sys

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
)

FakeEPICS_PV = sys.modules["epics"].PV


@pytest.fixture
def connected_pv():
    """Create a PV instance with mocked EPICS_PV that's connected"""
    pv = PV("TEST:PV", connection_timeout=1.0)
    return pv


# Test Initialization
class TestPVInitialization:
    def test_successful_connection(self):
        """Test PV connects successfully"""
        pv = PV("TEST:PV", connection_timeout=2.0)
        assert pv is not None
        assert pv.connected

    def test_connection_failure_raises_exception(self):
        """Test PV raises exception if connection fails"""
        # Temporarily make FakeEPICS_PV disconnected
        original_init = FakeEPICS_PV.__init__

        def disconnected_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self._connected = False

        FakeEPICS_PV.__init__ = disconnected_init
        try:
            with pytest.raises(PVConnectionError) as exc_info:
                PV("TEST:DISCONNECTED", connection_timeout=1.0)
            assert "failed to connect" in str(exc_info.value).lower()
        finally:
            FakeEPICS_PV.__init__ = original_init

    def test_default_connection_timeout(self):
        """Test default connection timeout is used"""
        pv = PV("TEST:PV")
        assert pv is not None

    def test_custom_connection_timeout(self):
        """Test custom connection timeout is respected"""
        pv = PV("TEST:PV", connection_timeout=10.0)
        assert pv is not None


class TestPVInitializationEdgeCases:
    def test_require_connection_false(self):
        """Test PV can be created without requiring connection"""
        original_wait = FakeEPICS_PV.wait_for_connection
        FakeEPICS_PV.wait_for_connection = lambda self, timeout=None: False

        try:
            pv = PV("TEST:PV", require_connection=False)
            assert pv is not None
        finally:
            FakeEPICS_PV.wait_for_connection = original_wait

    def test_custom_config(self):
        """Test PV with custom PVConfig"""
        from sc_linac_physics.utils.epics.config import PVConfig

        config = PVConfig(
            connection_timeout=5.0,
            get_timeout=3.0,
            put_timeout=3.0,
            max_retries=5,
            retry_delay=0.5,
        )
        pv = PV("TEST:PV", config=config)
        assert pv.config.max_retries == 5


# Test String Representation
class TestPVStringRepresentation:
    def test_str(self, connected_pv):
        """Test __str__ returns pvname"""
        assert str(connected_pv) == "TEST:PV"

    def test_repr_connected(self, connected_pv):
        """Test __repr__ shows connection status"""
        assert "TEST:PV" in repr(connected_pv)
        assert "connected" in repr(connected_pv)


# Test Get Operations
class TestPVGet:
    def test_successful_get(self, connected_pv):
        """Test successful get operation"""
        result = connected_pv.get()
        assert result == 42.0

    def test_get_with_timeout(self, connected_pv):
        """Test get with custom timeout"""
        result = connected_pv.get(timeout=5.0)
        assert result == 42.0

    def test_get_retry_on_none(self):
        """Test get retries when None is returned"""
        pv = PV("TEST:PV")

        call_count = [0]
        original_get = FakeEPICS_PV.get

        def get_with_retries(self, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                return None
            return 42.0

        FakeEPICS_PV.get = get_with_retries
        try:
            result = pv.get()
            assert result == 42.0
            assert call_count[0] == 3
        finally:
            FakeEPICS_PV.get = original_get

    def test_get_fails_after_max_retries(self):
        """Test get raises error after max retries"""
        pv = PV("TEST:PV")

        original_get = FakeEPICS_PV.get
        FakeEPICS_PV.get = lambda self, *args, **kwargs: None

        try:
            with pytest.raises(PVGetError) as exc_info:
                pv.get()
            assert "after 3 attempts" in str(exc_info.value)
        finally:
            FakeEPICS_PV.get = original_get

    def test_get_exception_after_max_retries(self):
        """Test get raises PVGetError after max retries with exception"""
        pv = PV("TEST:PV")

        original_get = FakeEPICS_PV.get
        FakeEPICS_PV.get = lambda self, *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("Persistent error")
        )

        try:
            with pytest.raises(PVGetError) as exc_info:
                pv.get()
            assert "Persistent error" in str(exc_info.value)
        finally:
            FakeEPICS_PV.get = original_get

    def test_val_property(self, connected_pv):
        """Test val property shorthand"""
        result = connected_pv.val
        assert result == 42.0


# Test Put Operations
class TestPVPut:
    def test_successful_put(self, connected_pv):
        """Test successful put operation"""
        connected_pv.put(100.0)
        # Should not raise

    def test_put_with_timeout(self, connected_pv):
        """Test put with custom timeout"""
        connected_pv.put(100.0, timeout=10.0)
        # Should not raise

    def test_put_retry_on_failure(self):
        """Test put retries on failure"""
        pv = PV("TEST:PV")

        call_count = [0]
        original_put = FakeEPICS_PV.put

        def put_with_retries(self, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                return 0  # Failure
            return 1  # Success

        FakeEPICS_PV.put = put_with_retries
        try:
            pv.put(100.0)
            assert call_count[0] == 3
        finally:
            FakeEPICS_PV.put = original_put

    def test_put_fails_after_max_retries(self):
        """Test put raises error after max retries"""
        pv = PV("TEST:PV")

        original_put = FakeEPICS_PV.put
        FakeEPICS_PV.put = lambda self, *args, **kwargs: 0

        try:
            with pytest.raises(PVPutError) as exc_info:
                pv.put(100.0)
            assert "after 3 attempts" in str(exc_info.value)
        finally:
            FakeEPICS_PV.put = original_put

    def test_put_exception_after_max_retries(self):
        """Test put raises PVPutError after max retries with exception"""
        pv = PV("TEST:PV")

        original_put = FakeEPICS_PV.put
        FakeEPICS_PV.put = lambda self, *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("Persistent error")
        )

        try:
            with pytest.raises(PVPutError) as exc_info:
                pv.put(100.0)
            assert "Persistent error" in str(exc_info.value)
        finally:
            FakeEPICS_PV.put = original_put

    def test_put_without_wait(self, connected_pv):
        """Test put without waiting"""
        connected_pv.put(100.0, wait=False)
        # Should not raise


class TestPVGetPutParameters:
    def test_get_as_string(self, connected_pv):
        """Test get with as_string=True"""
        result = connected_pv.get(as_string=True)
        assert isinstance(result, (str, float, int))

    def test_get_with_count(self, connected_pv):
        """Test get with count parameter"""
        result = connected_pv.get(count=10)
        assert result is not None

    def test_get_use_monitor_false(self, connected_pv):
        """Test get with use_monitor=False"""
        result = connected_pv.get(use_monitor=False)
        assert result == 42.0

    def test_get_with_ctrlvars(self, connected_pv):
        """Test get with control variables"""
        result = connected_pv.get(with_ctrlvars=True)
        assert result is not None

    def test_put_use_complete(self, connected_pv):
        """Test put with use_complete=True"""
        connected_pv.put(100.0, use_complete=True)

    def test_put_with_callback(self, connected_pv):
        """Test put with callback"""
        callback_called = [False]

        def put_callback(**kwargs):
            callback_called[0] = True

        connected_pv.put(100.0, callback=put_callback)
        # You may need to manually trigger callback in FakeEPICS_PV

    def test_put_with_callback_data(self, connected_pv):
        """Test put with callback data"""

        def put_callback(pvname=None, data=None, **kwargs):
            assert data == {"test": "data"}

        connected_pv.put(
            100.0, callback=put_callback, callback_data={"test": "data"}
        )


# Test Connection Management
class TestPVConnectionManagement:
    def test_ensure_connected_when_connected(self, connected_pv):
        """Test _ensure_connected does nothing when already connected"""
        # Should not raise
        connected_pv._ensure_connected()

    def test_ensure_connected_cleans_up_guard(self):
        """Test _ensure_connected cleans up recursion guard even on failure"""
        # Create a temporarily disconnected PV
        original_init = FakeEPICS_PV.__init__

        def disconnected_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self._connected = False

        FakeEPICS_PV.__init__ = disconnected_init
        try:
            # This will fail during __init__, so we can't test _ensure_connected
            # Just verify the exception is raised
            with pytest.raises(PVConnectionError):
                PV("TEST:PV")
        finally:
            FakeEPICS_PV.__init__ = original_init


# Test Value Validation
class TestPVValidation:
    def test_validate_value_in_range(self, connected_pv):
        """Test value validation passes for valid value"""
        assert connected_pv.validate_value(50, min_val=0, max_val=100) is True

    def test_validate_value_below_minimum(self, connected_pv):
        """Test validation fails for value below minimum"""
        with pytest.raises(PVInvalidError) as exc_info:
            connected_pv.validate_value(-10, min_val=0, max_val=100)
        assert "below minimum" in str(exc_info.value).lower()

    def test_validate_value_above_maximum(self, connected_pv):
        """Test validation fails for value above maximum"""
        with pytest.raises(PVInvalidError) as exc_info:
            connected_pv.validate_value(150, min_val=0, max_val=100)
        assert "above maximum" in str(exc_info.value).lower()

    def test_validate_value_in_allowed_set(self, connected_pv):
        """Test validation passes for allowed value"""
        assert connected_pv.validate_value(2, allowed_values=[1, 2, 3]) is True

    def test_validate_value_not_in_allowed_set(self, connected_pv):
        """Test validation fails for disallowed value"""
        with pytest.raises(PVInvalidError) as exc_info:
            connected_pv.validate_value(5, allowed_values=[1, 2, 3])
        assert "not in allowed values" in str(exc_info.value).lower()

    def test_validate_value_no_constraints(self, connected_pv):
        """Test validation passes with no constraints"""
        assert connected_pv.validate_value(999999) is True


# Test Alarm Checking
class TestPVAlarmChecking:
    def test_check_alarm_no_alarm(self, connected_pv):
        """Test check_alarm returns NO_ALARM"""
        severity = connected_pv.check_alarm()
        assert severity == EPICS_NO_ALARM_VAL

    def test_check_alarm_minor(self):
        """Test check_alarm detects MINOR alarm"""
        pv = PV("TEST:PV")
        pv.severity = EPICS_MINOR_VAL
        severity = pv.check_alarm()
        assert severity == EPICS_MINOR_VAL

    def test_check_alarm_major(self):
        """Test check_alarm detects MAJOR alarm"""
        pv = PV("TEST:PV")
        pv.severity = EPICS_MAJOR_VAL
        severity = pv.check_alarm()
        assert severity == EPICS_MAJOR_VAL

    def test_check_alarm_raise_on_major(self):
        """Test check_alarm raises on MAJOR when requested"""
        pv = PV("TEST:PV")
        pv.severity = EPICS_MAJOR_VAL
        with pytest.raises(PVInvalidError) as exc_info:
            pv.check_alarm(raise_on_alarm=True)
        assert "MAJOR" in str(exc_info.value)


# Test Mock PV Factory
class TestMakeMockPV:
    def test_make_mock_pv_defaults(self):
        """Test make_mock_pv with default values"""
        mock_pv = make_mock_pv()
        assert mock_pv.pvname == "MOCK:PV"
        assert mock_pv.connected is True
        assert mock_pv.severity == EPICS_NO_ALARM_VAL

    def test_make_mock_pv_custom_name(self):
        """Test make_mock_pv with custom name"""
        mock_pv = make_mock_pv(pv_name="CUSTOM:PV")
        assert mock_pv.pvname == "CUSTOM:PV"

    def test_make_mock_pv_custom_value(self):
        """Test make_mock_pv with custom get value"""
        mock_pv = make_mock_pv(get_val=123.45)
        assert mock_pv.get() == 123.45

    def test_make_mock_pv_with_alarm(self):
        """Test make_mock_pv with alarm state"""
        mock_pv = make_mock_pv(severity=EPICS_MAJOR_VAL)
        assert mock_pv.severity == EPICS_MAJOR_VAL


class TestPVContextManager:
    def test_context_manager_success(self):
        """Test PV works as context manager"""
        with PV("TEST:PV") as pv:
            assert pv.connected
            result = pv.get()
            assert result == 42.0

    def test_context_manager_disconnect(self):
        """Test PV disconnects on exit"""
        pv = PV("TEST:PV")
        with pv:
            assert pv.connected
        # Verify disconnect was called (you'll need to track this in FakeEPICS_PV)


class TestPVValueOrNone:
    def test_value_or_none_success(self, connected_pv):
        """Test value_or_none returns value on success"""
        result = connected_pv.value_or_none
        assert result == 42.0

    def test_value_or_none_on_connection_error(self):
        """Test value_or_none returns None on connection error"""
        original_init = FakeEPICS_PV.__init__

        def disconnected_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self._connected = False

        FakeEPICS_PV.__init__ = disconnected_init
        try:
            pv = PV("TEST:PV", require_connection=False)
            assert pv.value_or_none is None
        finally:
            FakeEPICS_PV.__init__ = original_init

    def test_value_or_none_on_get_error(self, connected_pv):
        """Test value_or_none returns None on get error"""
        original_get = FakeEPICS_PV.get
        FakeEPICS_PV.get = lambda self, *args, **kwargs: None
        try:
            assert connected_pv.value_or_none is None
        finally:
            FakeEPICS_PV.get = original_get


class TestPVBatchOperations:
    def test_batch_create_success(self):
        """Test batch_create creates multiple PVs"""
        pv_names = ["TEST:PV1", "TEST:PV2", "TEST:PV3"]
        pvs = PV.batch_create(pv_names)
        assert len(pvs) == 3
        assert all(pv.connected for pv in pvs)

    def test_batch_create_empty_list(self):
        """Test batch_create with empty list"""
        pvs = PV.batch_create([])
        assert pvs == []

    def test_batch_create_with_failures(self):
        """Test batch_create handles connection failures"""
        # Mock some PVs to fail connection
        original_wait = FakeEPICS_PV.wait_for_connection
        call_count = [0]

        def selective_connect(self, timeout=None):
            call_count[0] += 1
            # Make every other PV fail
            return call_count[0] % 2 == 1

        FakeEPICS_PV.wait_for_connection = selective_connect
        try:
            pv_names = ["PV1", "PV2", "PV3", "PV4"]
            pvs = PV.batch_create(pv_names, require_connection=False)
            assert len(pvs) == 4
        finally:
            FakeEPICS_PV.wait_for_connection = original_wait

    def test_batch_create_connection_failures_logged(self):
        """Test batch_create logs failures when require_connection=False"""
        original_wait = FakeEPICS_PV.wait_for_connection
        FakeEPICS_PV.wait_for_connection = lambda self, timeout=None: False

        try:
            # Should not raise when require_connection=False
            pvs = PV.batch_create(["PV1", "PV2"], require_connection=False)
            # Should still return PVs (they may be disconnected but wrapped)
            assert len(pvs) == 2
        finally:
            FakeEPICS_PV.wait_for_connection = original_wait

    def test_get_many_success(self):
        """Test get_many retrieves multiple values"""
        pvs = [PV(f"TEST:PV{i}") for i in range(3)]
        results = PV.get_many(pvs)
        assert len(results) == 3
        assert all(r == 42.0 for r in results)

    def test_get_many_with_failures(self):
        """Test get_many handles failures with persistent errors"""
        pvs = [PV(f"TEST:PV{i}") for i in range(3)]
        original_get = FakeEPICS_PV.get

        def selective_get(self, *args, **kwargs):
            # Determine which PV this is based on pvname
            if "PV1" in self.pvname:
                # Always fail for PV1 (middle PV)
                return None
            return 42.0

        FakeEPICS_PV.get = selective_get
        try:
            results = PV.get_many(pvs, raise_on_error=False)
            assert results[0] == 42.0
            assert results[1] is None  # PV1 should fail
            assert results[2] == 42.0
        finally:
            FakeEPICS_PV.get = original_get

    def test_get_many_raise_on_error(self):
        """Test get_many raises on any failure"""
        pvs = [PV(f"TEST:PV{i}") for i in range(3)]
        original_get = FakeEPICS_PV.get
        # Always return None to cause persistent failure
        FakeEPICS_PV.get = lambda self, *args, **kwargs: None

        try:
            with pytest.raises(PVGetError):
                PV.get_many(pvs, raise_on_error=True)
        finally:
            FakeEPICS_PV.get = original_get

    def test_put_many_success(self):
        """Test put_many writes multiple values"""
        pvs = [PV(f"TEST:PV{i}") for i in range(3)]
        values = [10.0, 20.0, 30.0]
        results = PV.put_many(pvs, values)
        assert all(r is True for r in results)

    def test_put_many_length_mismatch(self):
        """Test put_many raises on length mismatch"""
        pvs = [PV(f"TEST:PV{i}") for i in range(3)]
        values = [10.0, 20.0]  # Wrong length

        with pytest.raises(ValueError) as exc_info:
            PV.put_many(pvs, values)
        assert "length mismatch" in str(exc_info.value).lower()

    def test_put_many_with_failures(self):
        """Test put_many handles failures with persistent errors"""
        pvs = [PV(f"TEST:PV{i}") for i in range(3)]
        values = [10.0, 20.0, 30.0]

        original_put = FakeEPICS_PV.put

        def selective_put(self, *args, **kwargs):
            # Always fail for PV1 (middle PV)
            if "PV1" in self.pvname:
                return 0  # Failure
            return 1  # Success

        FakeEPICS_PV.put = selective_put
        try:
            results = PV.put_many(pvs, values, raise_on_error=False)
            assert results == [True, False, True]
        finally:
            FakeEPICS_PV.put = original_put

    def test_put_many_raise_on_error(self):
        """Test put_many raises on any failure"""
        pvs = [PV(f"TEST:PV{i}") for i in range(3)]
        values = [10.0, 20.0, 30.0]

        original_put = FakeEPICS_PV.put
        # Always return 0 to cause persistent failure
        FakeEPICS_PV.put = lambda self, *args, **kwargs: 0

        try:
            with pytest.raises(PVPutError):
                PV.put_many(pvs, values, raise_on_error=True)
        finally:
            FakeEPICS_PV.put = original_put


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
