"""The cavities one tab is running, so no other tab starts on them.

Each controller owns one CavityHold. It takes the cavity before a run writes
anything (to the machine or the database) and releases it when the run ends,
fails or is aborted. Between runs, such as between frequency tuning stages,
the cavity is free.
"""


class CavityHold:
    def __init__(self, tab_name: str):
        self.tab_name = tab_name
        self._cavities: list = []

    def take(self, cavity) -> bool:
        """Claim cavity for this tab. False if another tab is running it."""
        if not cavity.claim(self):
            return False
        if not any(held is cavity for held in self._cavities):
            self._cavities.append(cavity)
        return True

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
        f"{cavity} is running in {tab}. Nothing was started. "
        "Wait for that run to finish, or abort it there."
    )
