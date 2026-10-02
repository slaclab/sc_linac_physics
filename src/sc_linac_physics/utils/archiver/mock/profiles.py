"""Per-PV behavior profiles — the user-adjustable layer.

Resolution precedence (highest wins):
    1. Runtime override    (ProfileStore.set_override — e.g. a GUI slider)
    2. User YAML file      ($SC_ARCHIVER_PROFILE or ~/.config/sc_linac/...)
    3. Shipped defaults    (defaults.yaml, seeded from _TREND_RULES/_analog_range)
    4. Kind-based fallback

Both archiver transports read from the process-global PROFILE_STORE via the
generator, so a change here propagates to the fault heatmap AND the PyDM plots
with no call-site edits. Determinism is preserved because the seed mixes in
each PV's profile hash.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Optional

try:  # PyYAML is common in EPICS stacks but keep it optional
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


_DEFAULTS_PATH = Path(__file__).with_name("defaults.yaml")


@dataclass(frozen=True)
class PVProfile:
    """Fully describes one PV's simulated behavior."""

    kind: Optional[str] = None            # FLOAT/INT/ENUM/STRING/CUDSTATUS/CUDSEVR
    base: float = 0.0
    noise: float = 0.1                    # base noise range (in PV units)
    trend: str = "flat"
    trend_amplitude: float = 1.0
    noise_scale: float = 1.0
    spike_prob: float = 0.02
    spike_scale: float = 5.0              # spike magnitude = spike_scale * noise
    sample_rate_hz: float = 1.0

    def merged(self, **overrides) -> "PVProfile":
        clean = {k: v for k, v in overrides.items() if v is not None}
        return replace(self, **clean)

    def hash(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:12]


@dataclass
class _Rule:
    match: str                 # glob against PV name (e.g. "*AACTMEANSUM*")
    profile: dict = field(default_factory=dict)


class ProfileStore:
    """Process-global registry of per-PV profiles."""

    def __init__(self) -> None:
        self._rules: list[_Rule] = []
        self._kind_defaults: dict[str, dict] = {}
        self._overrides: dict[str, dict] = {}   # pv-or-glob -> partial profile
        self.load_defaults()
        self.load_user_file()  # picks up $SC_ARCHIVER_PROFILE if set

    # ---- loading ---------------------------------------------------------
    def load_defaults(self) -> None:
        data = self._read_yaml(_DEFAULTS_PATH)
        if data:
            self._ingest(data)

    def load_user_file(self, path: str | os.PathLike | None = None) -> None:
        p = path or os.getenv("SC_ARCHIVER_PROFILE")
        if not p:
            default_user = Path.home() / ".config" / "sc_linac" / "mock_archiver.yaml"
            p = default_user if default_user.exists() else None
        if not p:
            return
        data = self._read_yaml(Path(p))
        if data:
            self._ingest(data)  # user file appends/overrides

    def _read_yaml(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        if yaml is not None:
            return yaml.safe_load(text) or {}
        # Minimal fallback if PyYAML is missing: allow JSON-formatted files.
        try:
            return json.loads(text)
        except Exception:
            return None

    def _ingest(self, data: dict) -> None:
        for r in data.get("rules", []) or []:
            self._rules.append(_Rule(match=r["match"], profile=r.get("profile", {})))
        for kind, prof in (data.get("defaults") or {}).items():
            self._kind_defaults.setdefault(kind, {}).update(prof or {})

    # ---- runtime adjustment (GUI hook) ----------------------------------
    def set_override(self, pv_or_glob: str, **profile_fields) -> None:
        self._overrides.setdefault(pv_or_glob, {}).update(profile_fields)

    def clear_override(self, pv_or_glob: str) -> None:
        self._overrides.pop(pv_or_glob, None)

    def clear_all_overrides(self) -> None:
        self._overrides.clear()

    def save_overrides(self, path: str | os.PathLike) -> None:
        """Persist current overrides as a shareable YAML/JSON file."""
        payload = {
            "rules": [
                {"match": k, "profile": v} for k, v in self._overrides.items()
            ]
        }
        text = (
            yaml.safe_dump(payload, sort_keys=False)
            if yaml is not None
            else json.dumps(payload, indent=2)
        )
        Path(path).write_text(text, encoding="utf-8")

    # ---- resolution ------------------------------------------------------
    def resolve(self, pv_name: str, kind: str | None = None) -> PVProfile:
        """Build the effective PVProfile for a PV."""
        prof = PVProfile()

        # 3. kind-based defaults
        if kind and kind in self._kind_defaults:
            prof = prof.merged(**self._kind_defaults[kind])

        # 2b. shipped + user rules (first match wins per rule list order)
        for rule in self._rules:
            if fnmatch.fnmatch(pv_name, rule.match):
                prof = prof.merged(**rule.profile)
                break

        # 1. runtime overrides (glob-aware; later overrides win)
        for pat, fields in self._overrides.items():
            if pv_name == pat or fnmatch.fnmatch(pv_name, pat):
                prof = prof.merged(**fields)

        return prof

    def profile_hash(self, pv_name: str, kind: str | None = None) -> str:
        return self.resolve(pv_name, kind).hash()


# Process-global singleton. Import and mutate this from a control panel.
PROFILE_STORE = ProfileStore()