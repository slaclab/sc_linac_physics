"""The cavities one tab is using, so no other tab starts on them.

Each controller owns one CavityHold. It takes the cavity before a run writes
anything (to the machine or the database). Frequency tuning and piezo with RF
keep it across their stages and segments, and release it when the phase
completes, fails or is aborted, or when the tab moves to another cavity. The
other tabs release it when each run ends.
"""


class CavityHold:
    def __init__(self, tab_name: str):
        self.tab_name = tab_name
        self._cavities: list = []

    def take(self, cavity) -> bool:
        """Claim cavity for this tab. False if another tab is running it.

        A new claim clears cavity.abort_flag and stepper_tuner.abort_flag.
        All tabs share one Machine, so an abort another tab set after its
        last check_abort() would otherwise stop this tab's run. No run in
        this app is using a cavity nobody holds, so any flag left set is
        stale. A tab taking a cavity it already holds keeps its flags.
        """
        if not cavity.claim(self):
            return False
        if not self.holds(cavity):
            self._cavities.append(cavity)
            cavity.abort_flag = False
            cavity.stepper_tuner.abort_flag = False
        return True

    def holds(self, cavity) -> bool:
        return any(held is cavity for held in self._cavities)

    def release(self) -> None:
        """Free every cavity this tab holds."""
        for cavity in self._cavities:
            cavity.release(self)
        self._cavities = []


def refusal_message(cavity) -> str:
    """Error text for a start refused because another tab has the cavity."""
    holder = cavity.claimed_by
    tab = getattr(holder, "tab_name", "another tab")
    return (
        f"{cavity} is in use in {tab}. Nothing was started. "
        "Finish or abort it there, or select another cavity in that tab."
    )
