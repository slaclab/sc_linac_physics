import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QSizePolicy,
)
from edmbutton import PyDMEDMDisplayButton
from pydm import Display
from pydm.widgets import (
    PyDMRelatedDisplayButton,
)

from displays.srfhome.utils import make_link_button, make_watcher_groupbox


class SRFHome(Display):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRF Home")
        self.vlayout = QVBoxLayout()
        self.mini_home_groupbox = QGroupBox()
        self.mini_home_groupbox.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Maximum
        )
        self.fill_mini_home_groupbox()

        self.setLayout(self.vlayout)
        self.vlayout.addWidget(self.mini_home_groupbox)

        self.links_groupbox = QGroupBox("Shortcuts & Bookmarks")
        self.fill_link_groupbox()

        sel_opt_path = (
            os.getenv("SRF_ROOT_DIR", "/home/physics/srf/sc_linac_physics")
            + "/applications/sel_phase_optimizer/sel_phase_optimizer.py"
        )
        self.sel_phase_opt_groupbox = make_watcher_groupbox(
            watcher_name="SC_SEL_PHAS_OPT", script_path=sel_opt_path
        )

        self.vlayout.addWidget(self.links_groupbox)
        self.vlayout.addWidget(self.sel_phase_opt_groupbox)

    def fill_link_groupbox(self):
        link_layout = QVBoxLayout()
        self.links_groupbox.setLayout(link_layout)

        link_layout.addWidget(
            make_link_button(
                text="SRF Confluence Page",
                link="https://confluence.slac.stanford.edu/display/SRF/",
            )
        )
        link_layout.addWidget(
            make_link_button(
                text="MCC E-Log",
                link="https://mccelog.slac.stanford.edu/elog/wbin/elog.php",
            )
        )
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
            link_layout.addWidget(decarad_button)

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
            cryo_button = PyDMEDMDisplayButton(
                filename=f"$EDM/cryo/cryo_l{linac}b_main.edl"
            )
            magnet_button = PyDMEDMDisplayButton(
                filename=f"$EDM/lcls/mgnt_l{linac}b_main.edl"
            )
            vacuum_button = PyDMRelatedDisplayButton(
                filename=f"$PYDM/vac/l{linac}b_main.ui"
            )
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
