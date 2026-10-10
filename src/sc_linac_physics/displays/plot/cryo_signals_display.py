"""`sc-linac cryo-signals`: the plotter, opened on its Cryo signals view.

This lives in its own file because PyDM opens a display by file and takes
the first `Display` subclass it finds there, imported ones included. So the
`plotter` module is imported here, not `PlotterDisplay` itself.
"""

from sc_linac_physics.displays.plot import plotter


class CryoSignalsDisplay(plotter.PlotterDisplay):
    INITIAL_VIEW = plotter.CRYO_VIEW
