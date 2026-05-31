from __future__ import annotations

import uuid
from pathlib import Path

import yaml

from civsim.models.capabilities import CapabilityDefinition, PendingCapability, SuggestedCapability
from civsim.models.world import DEFAULT_ERA

# Modern / future-era keys — not offered to LLM in paleolithic
MODERN_ONLY_KEYS = frozenset(
    {
        "cooling",
        "storm_resistance",
        "flood_resistance",
        "heat_resistance",
        "energy_efficiency",
        "water_dependency",
        "compute_output",
        "compute_demand",
        "energy_output",
        "energy_demand",
        "material_efficiency",
        "ecosystem_impact",
        "scaling_stability",
        "supply_chain_resilience",
        "social_acceptance",
    }
)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, CapabilityDefinition] = {}
        self._pending: dict[str, PendingCapability] = {}
        self._era: str = DEFAULT_ERA
        self._era_keys: set[str] = set()

    @classmethod
    def from_yaml(cls, path: Path) -> CapabilityRegistry:
        registry = cls()
        registry._merge_yaml(path)
        return registry

    @classmethod
    def load_for_era(cls, era: str, data_dir: Path) -> CapabilityRegistry:
        registry = cls()
        base = data_dir / "capabilities.yaml"
        if base.exists():
            registry._merge_yaml(base)
        era_file = data_dir / f"capabilities_{era}.yaml"
        era_keys: set[str] = set()
        if era_file.exists():
            before = set(registry._definitions.keys())
            registry._merge_yaml(era_file)
            era_keys = set(registry._definitions.keys()) - before
            if not era_keys:
                with era_file.open() as f:
                    era_keys = set((yaml.safe_load(f) or {}).keys())
        registry._era = era
        registry._era_keys = era_keys
        return registry

    def _merge_yaml(self, path: Path) -> None:
        with path.open() as f:
            raw = yaml.safe_load(f) or {}
        for key, spec in raw.items():
            r = spec.get("range", [0, 1])
            self._definitions[key] = CapabilityDefinition(
                category=spec["category"],
                range=(float(r[0]), float(r[1])),
                default=float(spec.get("default", 0.0)),
                meaning=spec.get("meaning", ""),
            )

    @property
    def era(self) -> str:
        return self._era

    @property
    def keys(self) -> list[str]:
        return sorted(self._definitions.keys())

    def allowed_keys(self, era: str | None = None) -> list[str]:
        era = era or self._era
        if era == "paleolithic" and self._era_keys:
            return sorted(self._era_keys)
        if era == "paleolithic":
            return sorted(k for k in self._definitions if k not in MODERN_ONLY_KEYS)
        return self.keys

    def get(self, key: str) -> CapabilityDefinition | None:
        return self._definitions.get(key)

    def has(self, key: str) -> bool:
        return key in self._definitions

    def normalize_capabilities(
        self, raw: dict[str, float]
    ) -> tuple[dict[str, float], list[str]]:
        result: dict[str, float] = {}
        unknown: list[str] = []
        for key, value in raw.items():
            if key not in self._definitions:
                unknown.append(key)
                continue
            result[key] = self._clamp(key, value)
        return result, unknown

    def fill_defaults(self, caps: dict[str, float], era: str | None = None) -> dict[str, float]:
        filled = dict(caps)
        for key in self.allowed_keys(era):
            if key not in filled and key in self._definitions:
                filled[key] = self._definitions[key].default
        return filled

    def _clamp(self, key: str, value: float) -> float:
        defn = self._definitions[key]
        lo, hi = defn.range
        return max(lo, min(hi, float(value)))

    def propose_new_capability(
        self, suggestion: SuggestedCapability, source: str = ""
    ) -> PendingCapability | None:
        key = suggestion.key.strip().lower().replace(" ", "_")
        if self.has(key) or key in {p.key for p in self._pending.values()}:
            return None
        pending = PendingCapability(
            id=str(uuid.uuid4())[:8],
            key=key,
            category=suggestion.category,
            meaning=suggestion.meaning,
            default=suggestion.default,
            proposed_from=source,
        )
        self._pending[pending.id] = pending
        return pending

    def approve_pending(self, pending_id: str) -> bool:
        pending = self._pending.pop(pending_id, None)
        if not pending:
            return False
        self._definitions[pending.key] = CapabilityDefinition(
            category=pending.category,
            range=(0.0, 1.0),
            default=pending.default,
            meaning=pending.meaning,
        )
        if self._era == "paleolithic":
            self._era_keys.add(pending.key)
        return True

    def list_pending(self) -> list[PendingCapability]:
        return list(self._pending.values())

    def list_definitions(self) -> dict[str, CapabilityDefinition]:
        return dict(self._definitions)

    def to_public_dict(self, era: str | None = None) -> dict[str, dict]:
        keys = self.allowed_keys(era)
        return {
            k: {
                "category": self._definitions[k].category,
                "range": list(self._definitions[k].range),
                "default": self._definitions[k].default,
                "meaning": self._definitions[k].meaning,
            }
            for k in keys
            if k in self._definitions
        }
