from random import randint
from unittest import TestCase
from unittest.mock import MagicMock

from numpy.random import choice

from applications.auto_setup.setup_linac import (
    SetupMachine,
    SETUP_MACHINE,
    SetupLinac,
    SetupCryomodule,
)


class TestSetupMachine(TestCase):
    def setUp(self):
        self.machine = SetupMachine()

    def test_pv_prefix(self):
        self.assertEqual("ACCL:SYS0:SC:", self.machine.pv_prefix)

    def test_clear_abort(self):
        for cm in self.machine.cryomodules.values():
            cm.clear_abort = MagicMock()
        self.machine.clear_abort()
        for cm in self.machine.cryomodules.values():
            cm.clear_abort.assert_called()


class TestSetupLinac(TestCase):
    def setUp(self):
        self.idx = randint(0, 3)
        self.linac: SetupLinac = SETUP_MACHINE.linacs[self.idx]
        print(f"Testing {self.linac}")

    def test_pv_prefix(self):
        self.assertEqual(f"ACCL:L{self.idx}B:1:", self.linac.pv_prefix)

    def test_clear_abort(self):
        for cm in self.linac.cryomodules.values():
            cm.clear_abort = MagicMock()
        self.linac.clear_abort()
        for cm in self.linac.cryomodules.values():
            cm.clear_abort.assert_called()


class TestSetupCryomodule(TestCase):
    def setUp(self):
        self.cryomodule: SetupCryomodule = choice(
            list(SETUP_MACHINE.cryomodules.values())
        )
        print(f"Testing {self.cryomodule}")

    def test_clear_abort(self):
        for cavity in self.cryomodule.cavities.values():
            cavity.clear_abort = MagicMock()
        self.cryomodule.clear_abort()
        for cavity in self.cryomodule.cavities.values():
            cavity.clear_abort.assert_called()
