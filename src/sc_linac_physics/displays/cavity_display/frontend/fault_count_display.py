from concurrent.futures import Future, ThreadPoolExecutor
from typing import Dict, Optional, List

import pyqtgraph as pg
from PyQt5.QtCore import QDateTime, pyqtSignal
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QDateTimeEdit,
    QLabel,
)
from pydm import Display

from sc_linac_physics.displays.cavity_display.backend.backend_cavity import (
    BackendCavity,
)
from sc_linac_physics.displays.cavity_display.backend.backend_machine import (
    BackendMachine,
)
from sc_linac_physics.displays.cavity_display.backend.fault import FaultCounter
from sc_linac_physics.displays.cavity_display.frontend.cavity_widget import (
    DARK_GRAY_COLOR,
    RED_FILL_COLOR,
    PURPLE_FILL_COLOR,
    YELLOW_FILL_COLOR,
)
from sc_linac_physics.displays.cavity_display.utils import utils
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


class FaultCountDisplay(Display):
    # request id, Dict[str, FaultCounter]; emitted from the fetch thread,
    # delivered on the Qt main thread (queued connection)
    counts_ready = pyqtSignal(int, object)

    fault_tlc_list: List[str] = sorted(
        set(map(lambda d: d["Three Letter Code"], utils.parse_csv()))
    )

    def __init__(self, lazy_fault_pvs=True):
        super().__init__()
        self.setWindowTitle("Fault Count Display")

        self.machine = BackendMachine(lazy_fault_pvs=lazy_fault_pvs)

        main_v_layout = QVBoxLayout()
        input_h_layout = QHBoxLayout()
        omit_fault_h_layout = QHBoxLayout()

        self.plot_window = pg.plot()
        self.plot_window.setBackground(DARK_GRAY_COLOR)

        main_v_layout.addLayout(input_h_layout)
        main_v_layout.addWidget(self.plot_window)
        main_v_layout.addLayout(omit_fault_h_layout)
        self.setLayout(main_v_layout)

        self.cm_combo_box = QComboBox()
        self.cav_combo_box = QComboBox()

        end_date_time = QDateTime.currentDateTime()
        intermediate_time = QDateTime.addSecs(end_date_time, -30 * 60)  # 30 min
        min_date_time = QDateTime.addYears(end_date_time, -3)  # 3 years

        self.start_selector = QDateTimeEdit()
        self.start_selector.setCalendarPopup(True)

        self.end_selector = QDateTimeEdit()
        self.end_selector.setCalendarPopup(True)

        self.start_selector.setMinimumDateTime(min_date_time)
        self.start_selector.setDateTime(intermediate_time)
        self.end_selector.setDateTime(end_date_time)
        self.start_selector.editingFinished.connect(self.update_plot)
        self.end_selector.editingFinished.connect(self.update_plot)

        self.omit_tlc_text = QLabel(text="Select a fault to omit:")
        self.hide_fault_combo_box = QComboBox()
        self.hide_fault_combo_box.addItems(
            ["No fault selected"] + self.fault_tlc_list
        )
        self.hide_fault_combo_box.currentIndexChanged.connect(self.update_plot)

        input_h_layout.addWidget(QLabel("Cryomodule:"))
        input_h_layout.addWidget(self.cm_combo_box)
        input_h_layout.addWidget(QLabel("Cavity:"))
        input_h_layout.addWidget(self.cav_combo_box)
        input_h_layout.addStretch()
        input_h_layout.addWidget(QLabel("Start:"))
        input_h_layout.addWidget(self.start_selector)
        input_h_layout.addWidget(QLabel("End:"))
        input_h_layout.addWidget(self.end_selector)

        omit_fault_h_layout.addWidget(self.omit_tlc_text)
        omit_fault_h_layout.addWidget(self.hide_fault_combo_box)
        omit_fault_h_layout.addStretch()

        self.cm_combo_box.addItems([""] + ALL_CRYOMODULES)
        self.cav_combo_box.addItems([""] + [str(i) for i in range(1, 9)])

        self.num_faults = []
        self.num_invalids = []
        self.num_warnings = []
        self.y_data = None
        self.data: Dict[str, FaultCounter] = None

        self.cavity: Optional[BackendCavity] = None
        # get_fault_counts queries the archiver. A failing query retries for
        # up to a few minutes (utils/archiver.py MAX_RETRIES x RANGE_TIMEOUT),
        # so it runs here instead of on the Qt main thread. A plain executor,
        # not QThread: QThreads outliving their owner have crashed this
        # repo's test workers (#307, #308).
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._pending: Optional[Future] = None
        # Only the newest request is drawn; an older fetch that finishes
        # late (e.g. after switching cavity) is dropped.
        self._request_id = 0
        self.counts_ready.connect(self._on_counts_ready)
        self.cm_combo_box.currentIndexChanged.connect(self.update_cavity)
        self.cav_combo_box.currentIndexChanged.connect(self.update_cavity)

    def update_cavity(self):
        cm_name = self.cm_combo_box.currentText()
        cav_num = self.cav_combo_box.currentText()

        if not cm_name or not cav_num:
            return

        self.cavity: BackendCavity = self.machine.cryomodules[cm_name].cavities[
            int(cav_num)
        ]
        self.update_plot()

    def get_data(self):
        """Fetch counts for the selected cavity and range, on this thread."""
        start, end = self._selected_range()
        self._store_counts(self.cavity.get_fault_counts(start, end))

    def _selected_range(self):
        return (
            self.start_selector.dateTime().toPyDateTime(),
            self.end_selector.dateTime().toPyDateTime(),
        )

    def _store_counts(self, data: Dict[str, FaultCounter]):
        """
        data is a dictionary with:
            key = fault TLC string i.e. "BCS"
            value = FaultCounter(fault_count=0, ok_count=1, invalid_count=0) <-- Example
        """
        self.num_faults = []
        self.num_invalids = []
        self.num_warnings = []
        self.y_data = []

        data = dict(data)
        fault_tlc = self.hide_fault_combo_box.currentText()
        if fault_tlc in data:
            data.pop(fault_tlc)

        for tlc, counter_obj in data.items():
            self.y_data.append(tlc)
            self.num_faults.append(counter_obj.alarm_count)
            self.num_invalids.append(counter_obj.invalid_count)
            self.num_warnings.append(counter_obj.warning_count)

    def update_plot(self):
        """Start fetching counts; the plot redraws when they arrive."""
        if not self.cavity:
            return
        self.plot_window.clear()
        self._request_id += 1
        request_id = self._request_id
        start, end = self._selected_range()
        if self._pending is not None:
            self._pending.cancel()  # only stops it if it has not started
        self._pending = self._executor.submit(
            self.cavity.get_fault_counts, start, end
        )
        self._pending.add_done_callback(
            lambda future: self._deliver(request_id, future)
        )

    def _deliver(self, request_id: int, future: Future):
        """Runs on the fetch thread; hands the result to the main thread."""
        if future.cancelled():
            return
        try:
            self.counts_ready.emit(request_id, future.result())
        except Exception as e:
            # get_fault_counts already logs archiver errors and returns {};
            # this is anything else, or the display closed mid-fetch.
            utils.cavity_fault_logger.error(f"Fault count fetch failed: {e}")

    def closeEvent(self, event):
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)

    def _on_counts_ready(self, request_id, data):
        if request_id != self._request_id:
            return
        self._store_counts(data)
        self._draw()

    def _draw(self):
        ticks = []
        y_vals_ints = []

        for idy, y_val in enumerate(self.y_data):
            ticks.append((idy, y_val))
            y_vals_ints.append(idy)

        # Create pyqt5graph bar graph for faults
        # then stack invalid then warning faults on same bars
        fault_bars = pg.BarGraphItem(
            x0=0,
            y=y_vals_ints,
            height=0.6,
            width=self.num_faults,
            brush=RED_FILL_COLOR,
        )

        invalid_bars = pg.BarGraphItem(
            x0=self.num_faults,
            y=y_vals_ints,
            height=0.6,
            width=self.num_invalids,
            brush=PURPLE_FILL_COLOR,
        )
        warning_starts = list(
            map(lambda a, b: a + b, self.num_faults, self.num_invalids)
        )
        warning_bars = pg.BarGraphItem(
            x0=warning_starts,
            y=y_vals_ints,
            height=0.6,
            width=self.num_warnings,
            brush=YELLOW_FILL_COLOR,
        )
        tlc_axis = self.plot_window.getAxis("left")
        tlc_axis.setTicks([ticks])
        self.plot_window.showGrid(x=True, y=False, alpha=0.6)
        self.plot_window.addItem(fault_bars)
        self.plot_window.addItem(invalid_bars)
        self.plot_window.addItem(warning_bars)

        print("Displaying plot for", self.cavity.cryomodule, self.cavity.number)
