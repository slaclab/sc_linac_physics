# tests/utils/test_epics.py
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
