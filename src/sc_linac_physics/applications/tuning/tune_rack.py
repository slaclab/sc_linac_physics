from sc_linac_physics.applications.tuning.tune_utils import ColdLinacObject
from sc_linac_physics.utils.sc_linac.rack import Rack


class TuneRack(Rack, ColdLinacObject):
    def __init__(self, rack_name: str, cryomodule_object):
        Rack.__init__(self, rack_name=rack_name, cryomodule_object=cryomodule_object)
        ColdLinacObject.__init__(self)
