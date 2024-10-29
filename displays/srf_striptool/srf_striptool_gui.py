#
# srf_striptool_gui.py
#
# J. Nelson
# 13 April 2022
#
# pydm class to go with srf_stavDispMulti.ui
#
# This loads up the combo & check boxes on the ui then
# when Go! is pushed, it reads out the boxes and
# writes the command(s) to make a config file and start
# StripTool or archive Viewer
#
import pathlib
import time
from os import path, system, environ

from pydm import Display
from qtpy.QtWidgets import QCheckBox

import srf_srtiptool_utils as utils
from displays.srf_striptool.srf_striptool_maker import make_plotz

# on dev
uname = environ.get("PHYSICS_USER")
if uname == "jnelson":
    DEBUG = 1
    print("uname {}".format(uname))
else:
    DEBUG = 0


class SRFStriptoolGUI(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(SRFStriptoolGUI, self).__init__(parent=parent, args=args, macros=macros)

        # Wait time between calls to script to open tools
        self.waitTime = 0.5

        # Get variables from utility files
        self.CM_IDs = utils.CRYOMODULE_IDS
        self.usualPlots = utils.USUALSUSPECTS
        self.plot_z = make_plotz()
        self.plots = list(self.plot_z.keys())
        if DEBUG:
            print(self.plots)
            print(self.plots[0])
            print(self.plot_z[self.plots[0]].name)

        # Connect pushbuttons to functions
        self.ui.GoButton.clicked.connect(self.go)
        self.ui.UsualPB.clicked.connect(self.usual_suspects)
        self.ui.ClearPB.clicked.connect(self.clear_selection)

        # Fill in ui components

        # CM selector
        for cmid in self.CM_IDs:
            self.ui.CMComboBox.addItem(cmid)

        # Cavity spinner
        for cavnum in range(8):
            self.ui.CavComboBox.addItem(str(cavnum + 1))

        # set striptool as default
        self.ui.STradioButton.setChecked(True)
        self.ui.AVradioButton.setChecked(False)

        # Make grid (4 col, 6 rows) of checkboxes
        (nr, nc) = utils.aspectRatio(len(self.plots))
        self.dispCBs = []
        for xx in range(nr):
            for yy in range(nc):
                if (nc * xx + yy) < len(self.plots):
                    self.dispCBs.append(
                        QCheckBox(self.plot_z[self.plots[nc * xx + yy]].name)
                    )
                    self.dispCBs[-1].setToolTip(
                        self.plot_z[self.plots[nc * xx + yy]].desc
                    )
                    self.ui.CheckBoxGrid.addWidget(self.dispCBs[-1], xx, yy)

    def go(self):
        # gather variables to pass to python script
        for idx, checkbox in enumerate(self.dispCBs):
            if checkbox.isChecked():
                dispname = self.plots[idx]
                cmid = self.CMComboBox.currentText()
                if self.plot_z[dispname].needCav:
                    cavnum = self.CavComboBox.currentText()
                else:
                    cavnum = " "
                if self.ui.STradioButton.isChecked():
                    stav = "st"
                else:
                    stav = "av"

                config_path = (
                    f"{pathlib.Path(__file__).parent.resolve()}/srf_stavDisplaysCfg.py"
                )
                cmd = f"{config_path} {stav} {dispname} {cmid} {cavnum} ; "
                if stav == "st":
                    cmd = cmd + "StripTool $STRIP_CONFIGFILE_DIR/SRF/srf_"
                    cmd = cmd + dispname + ".stp &"
                else:
                    cmd = cmd + ' lclsarch "SRF/srf_' + dispname + '.xml -plot" &'

                system(cmd)
                time.sleep(self.waitTime)

    def usual_suspects(self):
        self.clear_selection()

        for pidx in self.usualPlots:
            self.dispCBs[pidx].setChecked(True)

    def clear_selection(self):
        for checkBox in self.dispCBs:
            checkBox.setChecked(False)

    def ui_filename(self):
        return "srf_stavDispMulti.ui"

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())
