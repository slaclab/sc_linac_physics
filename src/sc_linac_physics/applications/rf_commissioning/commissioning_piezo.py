"""
Commissioning-specific Piezo extension.

Adds PVs and functionality needed specifically for RF commissioning procedures.
"""

from typing import Optional, TYPE_CHECKING

from sc_linac_physics.utils.epics import PV
from sc_linac_physics.utils.sc_linac.piezo import Piezo

if TYPE_CHECKING:
    from sc_linac_physics.utils.sc_linac.cavity import Cavity


class CommissioningPiezo(Piezo):
    """
    Extended Piezo class with commissioning-specific PVs.

    Adds pre-RF and with-RF test functionality for cavity commissioning.
    """

    def __init__(self, cavity: "Cavity"):
        super().__init__(cavity)

        # Pre-RF Test PVs
        self.prerf_test_start_pv: str = self.pv_addr("TESTSTRT")
        self._prerf_test_start_pv_obj: Optional[PV] = None

        self.prerf_test_status_pv: str = self.pv_addr("TESTSTS")
        self._prerf_test_status_pv_obj: Optional[PV] = None

        self.prerf_cha_status_pv: str = self.pv_addr("CHA_TESTSTAT")
        self._prerf_cha_status_pv_obj: Optional[PV] = None

        self.prerf_chb_status_pv: str = self.pv_addr("CHB_TESTSTAT")
        self._prerf_chb_status_pv_obj: Optional[PV] = None

        self.prerf_cha_testmsg_pv: str = self.pv_addr("CHA_TESTMSG1")
        self._prerf_cha_testmsg_pv_obj: Optional[PV] = None

        self.prerf_chb_testmsg_pv: str = self.pv_addr("CHA_TESTMSG2")
        self._prerf_chb_testmsg_pv_obj: Optional[PV] = None

        self.capacitance_a_pv: str = self.pv_addr("CHA_C")
        self._capacitance_a_pv_obj: Optional[PV] = None

        self.capacitance_b_pv: str = self.pv_addr("CHB_C")
        self._capacitance_b_pv_obj: Optional[PV] = None

        # With-RF Test PVs
        self.withrf_run_check_pv: str = self.pv_addr("RFTESTSTRT")
        self._withrf_run_check_pv_obj: Optional[PV] = None

        self.withrf_check_status_pv: str = self.pv_addr("RFTESTSTS")
        self._withrf_check_status_pv_obj: Optional[PV] = None

        self.withrf_status_pv: str = self.pv_addr("RFSTESTSTAT")
        self._withrf_status_pv_obj: Optional[PV] = None

        self.amplifiergain_a_pv: str = self.pv_addr("CHA_AMPGAIN")
        self._amplifiergain_a_pv_obj: Optional[PV] = None

        self.amplifiergain_b_pv: str = self.pv_addr("CHB_AMPGAIN")
        self._amplifiergain_b_pv_obj: Optional[PV] = None

        self.withrf_push_dfgain_pv: str = self.pv_addr("PUSH_DFGAIN.PROC")
        self._withrf_push_dfgain_pv_obj: Optional[PV] = None

        self.withrf_save_dfgain_pv: str = self.pv_addr("SAVE_DFGAIN.PROC")
        self._withrf_save_dfgain_pv_obj: Optional[PV] = None

        self.detunegain_new_pv: str = self.pv_addr("DFGAIN_NEW")
        self._detunegain_new_pv_obj: Optional[PV] = None

    # =========================================================================
    # Pre-RF Test Properties
    # =========================================================================

    @property
    def prerf_test_start_pv_obj(self) -> PV:
        if not self._prerf_test_start_pv_obj:
            self._prerf_test_start_pv_obj = PV(self.prerf_test_start_pv)
        return self._prerf_test_start_pv_obj

    @property
    def prerf_test_status_pv_obj(self) -> PV:
        if not self._prerf_test_status_pv_obj:
            self._prerf_test_status_pv_obj = PV(self.prerf_test_status_pv)
        return self._prerf_test_status_pv_obj

    @property
    def prerf_cha_status_pv_obj(self) -> PV:
        if not self._prerf_cha_status_pv_obj:
            self._prerf_cha_status_pv_obj = PV(self.prerf_cha_status_pv)
        return self._prerf_cha_status_pv_obj

    @property
    def prerf_chb_status_pv_obj(self) -> PV:
        if not self._prerf_chb_status_pv_obj:
            self._prerf_chb_status_pv_obj = PV(self.prerf_chb_status_pv)
        return self._prerf_chb_status_pv_obj

    @property
    def prerf_cha_testmsg_pv_obj(self) -> PV:
        if not self._prerf_cha_testmsg_pv_obj:
            self._prerf_cha_testmsg_pv_obj = PV(self.prerf_cha_testmsg_pv)
        return self._prerf_cha_testmsg_pv_obj

    @property
    def prerf_chb_testmsg_pv_obj(self) -> PV:
        if not self._prerf_chb_testmsg_pv_obj:
            self._prerf_chb_testmsg_pv_obj = PV(self.prerf_chb_testmsg_pv)
        return self._prerf_chb_testmsg_pv_obj

    @property
    def capacitance_a_pv_obj(self) -> PV:
        if not self._capacitance_a_pv_obj:
            self._capacitance_a_pv_obj = PV(self.capacitance_a_pv)
        return self._capacitance_a_pv_obj

    @property
    def capacitance_b_pv_obj(self) -> PV:
        if not self._capacitance_b_pv_obj:
            self._capacitance_b_pv_obj = PV(self.capacitance_b_pv)
        return self._capacitance_b_pv_obj

    # =========================================================================
    # With-RF Test Properties
    # =========================================================================

    @property
    def withrf_run_check_pv_obj(self) -> PV:
        if not self._withrf_run_check_pv_obj:
            self._withrf_run_check_pv_obj = PV(self.withrf_run_check_pv)
        return self._withrf_run_check_pv_obj

    @property
    def withrf_check_status_pv_obj(self) -> PV:
        if not self._withrf_check_status_pv_obj:
            self._withrf_check_status_pv_obj = PV(self.withrf_check_status_pv)
        return self._withrf_check_status_pv_obj

    @property
    def withrf_status_pv_obj(self) -> PV:
        if not self._withrf_status_pv_obj:
            self._withrf_status_pv_obj = PV(self.withrf_status_pv)
        return self._withrf_status_pv_obj

    @property
    def amplifiergain_a_pv_obj(self) -> PV:
        if not self._amplifiergain_a_pv_obj:
            self._amplifiergain_a_pv_obj = PV(self.amplifiergain_a_pv)
        return self._amplifiergain_a_pv_obj

    @property
    def amplifiergain_b_pv_obj(self) -> PV:
        if not self._amplifiergain_b_pv_obj:
            self._amplifiergain_b_pv_obj = PV(self.amplifiergain_b_pv)
        return self._amplifiergain_b_pv_obj

    @property
    def withrf_push_dfgain_pv_obj(self) -> PV:
        if not self._withrf_push_dfgain_pv_obj:
            self._withrf_push_dfgain_pv_obj = PV(self.withrf_push_dfgain_pv)
        return self._withrf_push_dfgain_pv_obj

    @property
    def withrf_save_dfgain_pv_obj(self) -> PV:
        if not self._withrf_save_dfgain_pv_obj:
            self._withrf_save_dfgain_pv_obj = PV(self.withrf_save_dfgain_pv)
        return self._withrf_save_dfgain_pv_obj

    @property
    def detunegain_new_pv_obj(self) -> PV:
        if not self._detunegain_new_pv_obj:
            self._detunegain_new_pv_obj = PV(self.detunegain_new_pv)
        return self._detunegain_new_pv_obj
