from unittest.mock import patch

import pytest

from tests.applications.q0 import pyepics_shim


@pytest.fixture(autouse=True)
def _q0_pvs_through_pyepics_shim():
    """Route Q0Cryomodule's PV objects to pyepics_shim's caget/caput mocks."""
    pyepics_shim.reset()
    with patch(
        "sc_linac_physics.applications.q0.q0_cryomodule.PV",
        pyepics_shim.FakePV,
    ):
        yield
