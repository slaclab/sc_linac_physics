"""Per-PV profiles: how each mocked PV's data looks.

A PV's profile is built from, lowest precedence first:

1. ``defaults`` in the shipped defaults.yaml, by the PV's kind
2. the first matching ``rules`` entry, from defaults.yaml or a user file
   ($SC_ARCHIVER_PROFILE, else ~/.config/sc_linac/mock_archiver.yaml)
3. runtime overrides set with ProfileStore.set_override

Ported from #280 (Sandy Paez Olivarez).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

DEFAULTS_PATH = Path(__file__).with_name("defaults.yaml")
USER_PROFILE_ENV = "SC_ARCHIVER_PROFILE"
USER_PROFILE_PATH = Path.home() / ".config" / "sc_linac" / "mock_archiver.yaml"


@dataclass(frozen=True)
class PVProfile:
    """One PV's simulated behavior.

    noise is the half-width of the uniform noise, in the PV's units. A spike
    adds up to spike_scale times that, with probability spike_prob per sample.
    """

    kind: Optional[str] = None  # FLOAT, INT or ENUM; None: guess from the name
    base: float = 0.0
    noise: float = 0.1
    trend: str = "flat"
    trend_amplitude: float = 1.0
    noise_scale: float = 1.0
    spike_prob: float = 0.02
    spike_scale: float = 5.0
    sample_rate_hz: float = 1.0

    def merged(self, **fields) -> "PVProfile":
        return replace(
            self, **{k: v for k, v in fields.items() if v is not None}
        )

    def hash(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


class ProfileStore:
    """Rules, kind defaults and runtime overrides, read by the generator."""

    def __init__(self, user_file: Optional[Path] = None):
        self._rules: List[Tuple[str, dict]] = []
        self._kind_defaults: Dict[str, dict] = {}
        self._overrides: Dict[str, dict] = {}
        self._ingest(_read_yaml(DEFAULTS_PATH))
        path = user_file or os.getenv(USER_PROFILE_ENV) or USER_PROFILE_PATH
        if Path(path).exists():
            self.load_user_file(path)

    def load_user_file(self, path) -> None:
        """Add a YAML file's rules after the shipped ones, and its kind
        defaults over the shipped ones."""
        self._ingest(_read_yaml(Path(path)))

    def _ingest(self, data: dict) -> None:
        for rule in data.get("rules") or []:
            self._rules.append((rule["match"], rule.get("profile") or {}))
        for kind, fields in (data.get("defaults") or {}).items():
            self._kind_defaults.setdefault(kind, {}).update(fields or {})

    def set_override(self, pv_or_glob: str, **fields) -> None:
        self._overrides.setdefault(pv_or_glob, {}).update(fields)

    def clear_override(self, pv_or_glob: str) -> None:
        self._overrides.pop(pv_or_glob, None)

    def clear_all_overrides(self) -> None:
        self._overrides.clear()

    def save_overrides(self, path) -> None:
        """Write the current overrides as a user file other people can load."""
        rules = [{"match": k, "profile": v} for k, v in self._overrides.items()]
        Path(path).write_text(yaml.safe_dump({"rules": rules}, sort_keys=False))

    def resolve(self, pv: str, kind: str) -> PVProfile:
        """The effective profile for a PV whose kind is already known."""
        profile = PVProfile().merged(**self._kind_defaults.get(kind, {}))
        for pattern, fields in self._rules:
            if fnmatch.fnmatch(pv, pattern):
                profile = profile.merged(**fields)
                break
        for pattern, fields in self._overrides.items():
            if pv == pattern or fnmatch.fnmatch(pv, pattern):
                profile = profile.merged(**fields)
        return profile

    def rule_kind(self, pv: str) -> Optional[str]:
        """The kind the first matching rule or override sets, if any."""
        kind = None
        for pattern, fields in self._rules:
            if fnmatch.fnmatch(pv, pattern):
                kind = fields.get("kind")
                break
        for pattern, fields in self._overrides.items():
            if pv == pattern or fnmatch.fnmatch(pv, pattern):
                kind = fields.get("kind", kind)
        return kind


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# The store the generator uses unless given another; change it at runtime
PROFILE_STORE = ProfileStore()
