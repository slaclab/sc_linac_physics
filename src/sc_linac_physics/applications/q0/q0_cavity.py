from sc_linac_physics.utils.sc_linac.cavity import Cavity


class Q0Cavity(Cavity):
    def __init__(
        self,
        cavity_num,
        rack_object,
    ):
        super().__init__(cavity_num, rack_object)
        self.ready_for_q0 = False
        self.r_over_q = (
            1012 if not self.cryomodule.is_harmonic_linearizer else 750
        )

    def mark_ready(self):
        self.ready_for_q0 = True
