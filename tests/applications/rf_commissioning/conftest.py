"""Fixtures shared by the RF commissioning tests."""

import pytest

from sc_linac_physics.applications.rf_commissioning.models import (
    commissioning_machine,
)


@pytest.fixture(autouse=True)
def fresh_commissioning_machine(monkeypatch):
    """Give each test its own shared Machine.

    get_commissioning_machine() keeps one Machine per process, so a cavity
    claimed in one test would still be claimed in the next.
    """
    monkeypatch.setattr(commissioning_machine, "_shared_machine", None)
