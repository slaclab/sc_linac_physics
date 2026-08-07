import time
from typing import Type, Dict, Iterable, Optional, TYPE_CHECKING

from sc_linac_physics.utils.epics import PV
from sc_linac_physics.utils.sc_linac import linac_utils
from sc_linac_physics.utils.sc_linac.linac_utils import SCLinacObject
from sc_linac_physics.utils.sc_linac.rfstation import RFStation

if TYPE_CHECKING:
    from cavity import Cavity
    from cryomodule import Cryomodule

_FSCAN_STAT_SCAN_DONE = 5
_FSCAN_STAT_SCAN_ABORTED = 6
_FSCAN_STAT_FREQ_RESTORE_FAIL = 7
_FSCAN_STATE_NAMES = {
    0: "Await request",
    1: "No cav selected",
    2: "Bad range",
    3: "Search in progress",
    4: "Shift mode",
    5: "Scan done",
    6: "Scan aborted",
    7: "Freq restore fail",
}


class Rack(SCLinacObject):
    """
    Python representation of LCLS II RF Racks. This class functions mostly as a
    container for cavities.
    Rack A has cavities 1 through 4, Rack B has cavities 5 through 8.
    """

    def __init__(
        self,
        rack_name: str,
        cryomodule_object: "Cryomodule",
    ):
        """
        Parameters
        ----------
        rack_name: str name of rack (always either "A" or "B")
        cryomodule_object: the cryomodule object this rack belongs to
        """

        self.cryomodule: "Cryomodule" = cryomodule_object
        self.rack_name = rack_name

        self.cavity_class: Type["Cavity"] = self.cryomodule.cavity_class
        self.ssa_class = self.cryomodule.ssa_class
        self.stepper_class = self.cryomodule.stepper_class
        self.piezo_class = self.cryomodule.piezo_class

        self.cavities: Dict[int, "Cavity"] = {}
        self._pv_prefix = self.cryomodule.pv_addr(
            "RACK{RACK}:".format(RACK=self.rack_name)
        )
        self.rfs1 = RFStation(num=1, rack_object=self)
        self.rfs2 = RFStation(num=2, rack_object=self)

        # FSCAN (π-mode scan) rack-level PVs.
        self.fscan_freq_start_pv: str = self.pv_addr("FSCAN:FREQ_START")
        self._fscan_freq_start_pv_obj: Optional[PV] = None
        self.fscan_freq_stop_pv: str = self.pv_addr("FSCAN:FREQ_STOP")
        self._fscan_freq_stop_pv_obj: Optional[PV] = None
        self.fscan_rms_thresh_pv: str = self.pv_addr("FSCAN:RMS_THRESH")
        self._fscan_rms_thresh_pv_obj: Optional[PV] = None
        self.fscan_mode_overlap_pv: str = self.pv_addr("FSCAN:MODE_OVERLAP")
        self._fscan_mode_overlap_pv_obj: Optional[PV] = None
        self.fscan_start_pv: str = self.pv_addr("FSCAN:START")
        self._fscan_start_pv_obj: Optional[PV] = None
        self.fscan_stat_pv: str = self.pv_addr("FSCAN:STAT")
        self._fscan_stat_pv_obj: Optional[PV] = None

        if rack_name == "A":
            # rack A always has cavities 1 - 4
            for cavityNum in range(1, 5):
                self.cavities[cavityNum] = self.cavity_class(
                    cavity_num=cavityNum, rack_object=self
                )

        elif rack_name == "B":
            # rack B always has cavities 5 - 8
            for cavityNum in range(5, 9):
                self.cavities[cavityNum] = self.cavity_class(
                    cavity_num=cavityNum, rack_object=self
                )

        else:
            raise Exception(f"Bad rack name {rack_name}")

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def fscan_freq_start_pv_obj(self) -> PV:
        if not self._fscan_freq_start_pv_obj:
            self._fscan_freq_start_pv_obj = PV(self.fscan_freq_start_pv)
        return self._fscan_freq_start_pv_obj

    @property
    def fscan_freq_stop_pv_obj(self) -> PV:
        if not self._fscan_freq_stop_pv_obj:
            self._fscan_freq_stop_pv_obj = PV(self.fscan_freq_stop_pv)
        return self._fscan_freq_stop_pv_obj

    @property
    def fscan_rms_thresh_pv_obj(self) -> PV:
        if not self._fscan_rms_thresh_pv_obj:
            self._fscan_rms_thresh_pv_obj = PV(self.fscan_rms_thresh_pv)
        return self._fscan_rms_thresh_pv_obj

    @property
    def fscan_mode_overlap_pv_obj(self) -> PV:
        if not self._fscan_mode_overlap_pv_obj:
            self._fscan_mode_overlap_pv_obj = PV(self.fscan_mode_overlap_pv)
        return self._fscan_mode_overlap_pv_obj

    @property
    def fscan_start_pv_obj(self) -> PV:
        if not self._fscan_start_pv_obj:
            self._fscan_start_pv_obj = PV(self.fscan_start_pv)
        return self._fscan_start_pv_obj

    @property
    def fscan_stat_pv_obj(self) -> PV:
        if not self._fscan_stat_pv_obj:
            self._fscan_stat_pv_obj = PV(self.fscan_stat_pv)
        return self._fscan_stat_pv_obj

    def run_fscan(
        self,
        cavities: "Iterable[Cavity]",
        *,
        freq_start: int,
        freq_stop: int,
        rms_thresh: float,
        mode_overlap: int,
        poll_interval: float = 2.0,
        timeout_seconds: float = 300.0,
        status_callback=None,
        should_abort=None,
    ) -> None:
        """Configure and run an FSCAN on this rack over ``cavities``.

        ``cavities`` is any combination of this rack's cavities to scan.
        Selects exactly those (FSCAN:SEL), writes the scan parameters,
        triggers the scan, polls FSCAN:STAT to completion, then pushes each
        selected cavity's π-mode results.

        Raises FSCANError on scan failure or timeout, and CavityAbortError if
        ``should_abort`` returns True while polling.  Callers read the mode
        frequencies off each cavity afterwards.
        """
        cavities = list(cavities)
        selected_nums = {cav.number for cav in cavities}
        for num, cav in self.cavities.items():
            cav.fscan_sel_pv_obj.put(1 if num in selected_nums else 0)

        self.fscan_freq_start_pv_obj.put(freq_start)
        self.fscan_freq_stop_pv_obj.put(freq_stop)
        self.fscan_rms_thresh_pv_obj.put(rms_thresh)
        self.fscan_mode_overlap_pv_obj.put(mode_overlap)
        self.fscan_start_pv_obj.put(1)

        self._poll_fscan(
            poll_interval, timeout_seconds, status_callback, should_abort
        )

        for cav in cavities:
            cav.fscan_push_8pi9_pv_obj.put(1)
            cav.fscan_push_7pi9_pv_obj.put(1)

    def _poll_fscan(
        self, poll_interval, timeout_seconds, status_callback, should_abort
    ) -> None:
        """Poll FSCAN:STAT until done; raise on failure/timeout/abort."""
        scan_start = time.monotonic()
        deadline = scan_start + timeout_seconds
        while time.monotonic() < deadline:
            if should_abort is not None and should_abort():
                raise linac_utils.CavityAbortError(
                    f"Abort requested while waiting for {self} FSCAN"
                )
            stat = int(self.fscan_stat_pv_obj.get())
            if stat == _FSCAN_STAT_SCAN_DONE:
                return
            if stat in (
                _FSCAN_STAT_SCAN_ABORTED,
                _FSCAN_STAT_FREQ_RESTORE_FAIL,
            ):
                name = _FSCAN_STATE_NAMES.get(stat, str(stat))
                raise linac_utils.FSCANError(
                    f"{self} FSCAN failed: {name} (state {stat})"
                )
            if status_callback is not None:
                elapsed = time.monotonic() - scan_start
                name = _FSCAN_STATE_NAMES.get(stat, str(stat))
                status_callback(f"FSCAN: {name} ({elapsed:.0f}s elapsed)")
            time.sleep(poll_interval)
        raise linac_utils.FSCANError(
            f"{self} FSCAN did not complete within {timeout_seconds:.0f} s"
        )

    def __str__(self):
        return f"{self.cryomodule} Rack {self.rack_name}"
