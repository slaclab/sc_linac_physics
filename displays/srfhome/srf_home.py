import os
import pathlib
from typing import List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QHBoxLayout,
)
from edmbutton import PyDMEDMDisplayButton
from pydm import Display
from pydm.widgets import (
    PyDMRelatedDisplayButton,
)

from displays.srfhome.utils import make_link_button, make_watcher_groupbox
from utils.qt import get_dimensions


class SRFHome(Display):
    def __init__(self):
        super().__init__()
        self.root_dir = os.getenv("SRF_ROOT_DIR", "/home/physics/srf/sc_linac_physics")
        self.setWindowTitle("SRF Home")
        self.main_layout = QHBoxLayout()
        self.mini_home_groupbox = QGroupBox()
        self.mini_home_groupbox.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Maximum
        )
        self.fill_mini_home_groupbox()

        self.setLayout(self.main_layout)

        self.links_groupbox = QGroupBox("Shortcuts && Bookmarks")
        self.fill_link_groupbox()

        sel_opt_path = (
            f"{self.root_dir}/applications/sel_phase_optimizer/sel_phase_optimizer.py"
        )
        quench_reset_path = (
            f"{self.root_dir}/applications/quench_processing/quench_resetter.py"
        )
        cav_disp_backend_path = (
            f"{self.root_dir}/displays/cavity_display/backend/runner.py"
        )

        self.sel_phase_opt_groupbox = make_watcher_groupbox(
            watcher_name="SC_SEL_PHAS_OPT", script_path=sel_opt_path
        )
        self.quench_reset_groupbox = make_watcher_groupbox(
            watcher_name="SC_CAV_QNCH_RESET", script_path=quench_reset_path
        )
        self.cav_disp_groupbox = make_watcher_groupbox(
            watcher_name="SC_CAV_FAULT", script_path=cav_disp_backend_path
        )
        extras_layout = QVBoxLayout()
        watcher_layout = QVBoxLayout()
        extras_layout.addWidget(self.mini_home_groupbox)
        extras_layout.addWidget(self.links_groupbox)
        watcher_layout.addWidget(self.sel_phase_opt_groupbox)
        watcher_layout.addWidget(self.quench_reset_groupbox)
        watcher_layout.addWidget(self.cav_disp_groupbox)

        self.main_layout.addLayout(extras_layout)
        self.main_layout.addLayout(watcher_layout)

        app_button_layout = QVBoxLayout()

    def fill_link_groupbox(self):
        link_layout = QGridLayout()
        self.links_groupbox.setLayout(link_layout)
        buttons = [
            make_link_button(
                text="SRF Confluence Page",
                link="https://confluence.slac.stanford.edu/display/SRF/",
            ),
            make_link_button(
                text="MCC E-Log",
                link="https://mccelog.slac.stanford.edu/elog/wbin/elog.php",
            ),
        ]
        unit_test_button = PyDMEDMDisplayButton(
            filename="$EDM/llrf/rf_srf_cavity_unit_all.edl"
        )
        unit_test_button.setText("All CM Unit Tests")
        buttons.append(unit_test_button)

        # TODO write python auto plot to replace striptool-based repo
        auto_plot_button = PyDMRelatedDisplayButton(
            filename="/home/physics/srf/gitRepos/makeAutoPlot/srf_stavDispMulti.py"
        )
        auto_plot_button.setText("SRF Auto Plot")
        buttons.append(auto_plot_button)

        # TODO decide if we still need/want these links

        # link_layout.addWidget(
        #     make_link_button(
        #         text="BigPics Directory",
        #         link="https://slac.stanford.edu/grp/ad/srf/slaconly/",
        #     )
        # )

        # link_layout.addWidget(
        #     make_link_button(
        #         text="LCLS-II Physics Log",
        #         link="http://physics-elog.slac.stanford.edu/lcls2elog/index.jsp",
        #     )
        # )

        for decarad in [1, 2]:
            decarad_button = PyDMRelatedDisplayButton(
                filename="$TOOLS/pydm/display/ads/decarad_main.ui"
            )
            decarad_button.setText(f"Decarad {decarad}")
            decarad_button.macros = f"P=RADM:SYS0:{decarad}00,M={decarad}"
            buttons.append(decarad_button)

        self.add_buttons_from_path(buttons, "*gui.py")
        self.add_buttons_from_path(buttons, "*display.py")

        col_count = get_dimensions(buttons)
        for idx, button in enumerate(buttons):
            link_layout.addWidget(button, int(idx / col_count), idx % col_count)

    def add_buttons_from_path(self, buttons: List[PyDMRelatedDisplayButton], suffix):
        for file in pathlib.Path(self.root_dir).rglob(suffix):
            name: str = file.name
            if name.startswith("test"):
                continue
            gui_button = PyDMRelatedDisplayButton(
                filename=os.path.join(self.root_dir, file)
            )
            parsed_name = name.split(".")[0].replace("_", " ")
            gui_button.setText(parsed_name.title().replace("Gui", "GUI"))
            buttons.append(gui_button)

    def fill_mini_home_groupbox(self):
        mini_home_groupbox_layout = QGridLayout()
        self.mini_home_groupbox.setLayout(mini_home_groupbox_layout)

        for col, col_label in enumerate(["", "Global"] + [f"L{i}B" for i in range(4)]):
            label = QLabel(col_label)
            label.setAlignment(Qt.AlignCenter)
            mini_home_groupbox_layout.addWidget(label, 0, col)

        for row, row_label in enumerate(["", "RF", "Cryo", "Magnets", "Vacuum"]):
            q_label = QLabel(row_label)
            q_label.setAlignment(Qt.AlignCenter)
            mini_home_groupbox_layout.addWidget(q_label, row, 0)

        for linac in range(4):
            col = linac + 2
            rf_button = PyDMRelatedDisplayButton(filename=f"$PYDM/rf/l{linac}b_main.ui")
            rf_button.setToolTip(f"L{linac}B RF")
            cryo_button = PyDMEDMDisplayButton(
                filename=f"$EDM/cryo/cryo_l{linac}b_main.edl"
            )
            cryo_button.setToolTip(f"L{linac}B Cryo")
            magnet_button = PyDMEDMDisplayButton(
                filename=f"$EDM/lcls/mgnt_l{linac}b_main.edl"
            )
            magnet_button.setToolTip(f"L{linac}B Magnets")
            vacuum_button = PyDMRelatedDisplayButton(
                filename=f"$PYDM/vac/l{linac}b_main.ui"
            )
            vacuum_button.setToolTip(f"L{linac}B Vacuum")
            mini_home_groupbox_layout.addWidget(rf_button, 1, col)
            mini_home_groupbox_layout.addWidget(cryo_button, 2, col)
            mini_home_groupbox_layout.addWidget(magnet_button, 3, col)
            mini_home_groupbox_layout.addWidget(vacuum_button, 4, col)

        global_rf_button = PyDMEDMDisplayButton(filename="$EDM/lcls/rf_global_main.edl")
        global_cryo_button = PyDMEDMDisplayButton(
            filename="$EDM/cryo/cryo_global_main.edl"
        )
        mini_home_groupbox_layout.addWidget(global_rf_button, 1, 1)
        mini_home_groupbox_layout.addWidget(global_cryo_button, 2, 1)
