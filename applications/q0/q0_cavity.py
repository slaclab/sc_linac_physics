from utils.sc_linac.cavity import Cavity


class Q0Cavity(Cavity):
    def __init__(
        self,
        cavity_num,
        rack_object,
    ):
        super().__init__(cavity_num, rack_object)
        self.ready_for_q0 = False

    def mark_ready(self):
        self.ready_for_q0 = True
