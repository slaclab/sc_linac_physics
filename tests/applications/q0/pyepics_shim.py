"""Test stand-in for pyepics' caget/caput/camonitor, behind Q0's PV objects.

Q0Cryomodule reads and writes through sc_linac_physics.utils.epics.PV. The
Q0 tests were written against module-level caget/caput/camonitor mocks.
FakePV forwards each PV call to the functions below, in the shape the old
code used, so those tests keep asserting the same PV, value and wait:

    get()                     -> caget(name)
    put(value, wait=True)     -> caput(name, value, wait=True)
    put(value, wait=False)    -> caput(name, value)          (pyepics default)
    add_callback(cb)          -> camonitor(name, callback=cb)
    remove_callback(index)    -> camonitor_clear(name)

Tests patch these names, e.g. patch("tests.applications.q0.pyepics_shim.caget").
"""

from unittest.mock import Mock

caget = Mock(return_value=50.0)
caput = Mock()
camonitor = Mock()
camonitor_clear = Mock()

_this = __import__(__name__, fromlist=["caget"])


class FakePV:
    def __init__(self, pvname, *args, **kwargs):
        self.pvname = pvname

    def get(self, *args, **kwargs):
        return _this.caget(self.pvname)

    def put(self, value, wait=True, *args, **kwargs):
        if wait:
            return _this.caput(self.pvname, value, wait=True)
        return _this.caput(self.pvname, value)

    def add_callback(self, callback, *args, **kwargs):
        _this.camonitor(self.pvname, callback=callback)
        return 1

    def remove_callback(self, index=None):
        _this.camonitor_clear(self.pvname)


def reset():
    for name in ("caget", "caput", "camonitor", "camonitor_clear"):
        getattr(_this, name).reset_mock(return_value=True, side_effect=True)
    _this.caget.return_value = 50.0
