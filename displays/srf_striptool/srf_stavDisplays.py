#
# Gotcha ./srf at beginning of system command
# How to hardcode or not the directory structure?
#
# srf_stavDisplays.py
#
# J. Nelson
# 17 March 2022
#
# pydm class to go with srf_stavDisplays.ui
#
# This loads up the combo boxes on the ui then
# when Go! is pushed, it reads out the boxes and
# writes the command to make a config file and start
# StripTool or archive Viewer
#

from os import path, system, environ

from pydm import Display

import srf_srtiptool_utils as util

# on dev
uname = environ.get("LOGNAME")
if uname == "physics":
    DEBUG = 0
else:
    print("uname {}".format(uname))
    DEBUG = 1


class MyDisplay(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(MyDisplay, self).__init__(parent=parent, args=args, macros=macros)

        # Get variables from utility file
        self.CM_IDs = util.CM_IDs()
        self.plots = util.plots()
        self.descs = util.descs()
        self.reqcav = util.reqcav()
        self.reqcm = util.reqcm()

        # Connect go button to function
        self.ui.GoButton.clicked.connect(self.Go)

        # connect spinner boxes to functions
        self.ui.DispComboBox.activated.connect(self.ChangeDisplay)
        self.ui.CMComboBox.activated.connect(self.ChangeCM)
        self.ui.CavComboBox.activated.connect(self.ChangeCav)

        # Fill in ui components

        # CM selector
        for cmid in self.CM_IDs:
            self.ui.CMComboBox.addItem(cmid)

        # Display selector
        for plot in self.plots:
            self.ui.DispComboBox.addItem(plot)

        # Display description
        defaultDevice = 0
        self.ui.DescLabel.setWordWrap(True)
        self.ui.DescLabel.setText(self.descs[defaultDevice])

        # Cavity spinner
        for cavnum in range(8):
            self.ui.CavComboBox.addItem(str(cavnum + 1))

        # show cavity spinner if needed
        if self.reqcav[defaultDevice]:  # cavity spinner needed
            self.ui.CavComboBox.show()
            self.ui.CavLabel.show()
        else:
            self.ui.CavComboBox.hide()
            self.ui.CavLabel.hide()

        # set striptool as default
        self.ui.STradioButton.setChecked(True)
        self.ui.AVradioButton.setChecked(False)

    # DEBUG
    #    foo=system('echo 123')
    #    foo=self.ui.DispComboBox.currentText()
    #    print(foo)
    #    foo=self.ui.CMComboBox.currentText()
    #    print(foo)
    #    foo=self.ui.CavComboBox.currentText()
    #    print(foo)
    #    foo=self.ui.STradioButton.isChecked()
    #    print(foo)
    #    foo=self.ui.AVradioButton.isChecked()
    #    print(foo)

    def Go(self):
        #    print("Go")
        # gather variables to pass to python script
        dispname = self.ui.DispComboBox.currentText()
        idx = self.plots.index(dispname)
        cmid = self.CMComboBox.currentText()
        if self.reqcav[idx]:
            cavnum = self.CavComboBox.currentText()
        else:
            cavnum = " "
        if self.ui.STradioButton.isChecked():
            stav = "st "
        else:
            stav = "av "

        if DEBUG:
            print("debug")
            cmd = "./srf_stavDisplaysCfg.py "
        else:
            cmd = "/home/physics/srf/gitRepos/makeAutoPlot/srf_stavDisplaysCfg.py "
        cmd = cmd + stav + dispname + " " + cmid + " " + cavnum + " ; "
        if stav == "st ":
            cmd = cmd + "StripTool $STRIP_CONFIGFILE_DIR/srf_"
            cmd = cmd + dispname + ".stp &"
        else:
            cmd = cmd + ' lclsarch "srf_' + dispname + '.xml -plot" &'

        #    print(cmd)
        system(cmd)

    def ChangeDisplay(self):
        #    print("changeDisplay")
        idx = self.plots.index(self.ui.DispComboBox.currentText())
        #    print(idx)
        # Show cavity spinner if needed
        if self.reqcav[idx]:
            self.ui.CavComboBox.show()
            self.ui.CavLabel.show()
        else:
            self.ui.CavComboBox.hide()
            self.ui.CavLabel.hide()

        # Show cryomodule spinner if needed
        if self.reqcm[idx]:
            self.ui.CMComboBox.show()
            self.ui.CMLabel.show()
        else:
            self.ui.CMComboBox.hide()
            self.ui.CMLabel.hide()

        # Update description box
        self.ui.DescLabel.setText(self.descs[idx])

    def ui_filename(self):
        return "srf_stavDisplays.ui"

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())
