import os

from utils.simulation.launcher_pv_group import LauncherPVGroup


class TuningPVGroup(LauncherPVGroup):
    def __init__(self, prefix: str):
        super().__init__(prefix)
        self.launcher_dir = os.path.join(
            self.srf_root_dir, "applications/tuning/launcher"
        )
        # TODO replace with actual PV when it's live
        super().__init__(prefix + "TUNING:")
