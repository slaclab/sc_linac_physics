import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QHBoxLayout,
    QPushButton,
)
from edmbutton import PyDMEDMDisplayButton
from pydm import Display
from pydm.widgets import (
    PyDMRelatedDisplayButton,
)

from sc_linac_physics.cli.cli import DISPLAY_LIST
from sc_linac_physics.cli.watcher_commands import WATCHER_CONFIGS
from sc_linac_physics.displays.srfhome.utils import (
    make_link_button,
    make_watcher_groupbox,
)
from sc_linac_physics.utils.qt import get_dimensions


class SRFHome(Display):
    def __init__(self):
        super().__init__()
        self.root_dir = os.getenv(
            "SRF_ROOT_DIR", "/home/physics/srf/sc_linac_physics"
        )
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

        extras_layout = QVBoxLayout()
        extras_layout.addWidget(self.mini_home_groupbox)
        extras_layout.addWidget(self.links_groupbox)

        # Automatically create all watcher groupboxes
        self.watcher_layout = QVBoxLayout()
        self.setup_watcher_groupboxes()

        self.main_layout.addLayout(extras_layout)
        self.main_layout.addLayout(self.watcher_layout)
        self.child_windows = []

    def setup_watcher_groupboxes(self):
        """Create groupboxes for all configured watchers"""

        # Create a groupbox for each watcher in WATCHER_CONFIGS
        for watcher_name in WATCHER_CONFIGS.keys():
            groupbox = make_watcher_groupbox(watcher_name)
            self.watcher_layout.addWidget(groupbox)

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

        # TODO migrate microphonics gui
        microphonics_button = PyDMRelatedDisplayButton(
            filename="/home/physics/srf/gitRepos/microphonics/CommMicro.py"
        )
        microphonics_button.setText("Microphonics GUI")
        buttons.append(microphonics_button)

        for decarad in [1, 2]:
            decarad_button = PyDMRelatedDisplayButton(
                filename="$TOOLS/pydm/display/ads/decarad_main.ui"
            )
            decarad_button.setText(f"Decarad {decarad}")
            decarad_button.macros = f"P=RADM:SYS0:{decarad}00,M={decarad}"
            buttons.append(decarad_button)

        for display in DISPLAY_LIST:
            if display.name == "srf-home":
                continue
            button = QPushButton(display.name)

            def make_handler(disp):
                def handler():
                    window = disp.launcher(standalone=False)
                    if window:
                        self.child_windows.append(window)

                return handler

            button.clicked.connect(make_handler(display))
            buttons.append(button)

        col_count = get_dimensions(buttons)
        for idx, button in enumerate(buttons):
            link_layout.addWidget(button, int(idx / col_count), idx % col_count)

    def fill_mini_home_groupbox(self):
        mini_home_groupbox_layout = QGridLayout()
        self.mini_home_groupbox.setLayout(mini_home_groupbox_layout)

        for col, col_label in enumerate(
            ["", "Global"] + [f"L{i}B" for i in range(4)]
        ):
            label = QLabel(col_label)
            label.setAlignment(Qt.AlignCenter)
            mini_home_groupbox_layout.addWidget(label, 0, col)

        for row, row_label in enumerate(
            ["", "RF", "Cryo", "Magnets", "Vacuum"]
        ):
            q_label = QLabel(row_label)
            q_label.setAlignment(Qt.AlignCenter)
            mini_home_groupbox_layout.addWidget(q_label, row, 0)

        for linac in range(4):
            col = linac + 2
            rf_button = PyDMRelatedDisplayButton(
                filename=f"$PYDM/rf/l{linac}b_main.ui"
            )
            rf_button.setToolTip(f"L{linac}B RF")
            cryo_button = PyDMEDMDisplayButton(
                filename=f"$EDM/cryo/cryo_l{linac}b_main.edl"
            )
            cryo_button.setToolTip(f"L{linac}B Cryo")
            magnet_button = PyDMRelatedDisplayButton(
                filename=f"$PYDM/mgnt/l{linac}b_main.ui"
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

        global_rf_button = PyDMRelatedDisplayButton(
            filename="$PYDM/rf/global_main.ui"
        )
        global_cryo_button = PyDMRelatedDisplayButton(
            filename="$PYDM/cryo/global_main.ui"
        )
        mini_home_groupbox_layout.addWidget(global_rf_button, 1, 1)
        mini_home_groupbox_layout.addWidget(global_cryo_button, 2, 1)
