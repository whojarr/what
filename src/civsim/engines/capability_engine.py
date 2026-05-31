from civsim.models.capabilities import IdeaProposal, NormalizedProposal
from civsim.registry.capability_registry import MODERN_ONLY_KEYS, CapabilityRegistry

# Map common LLM mistakes to paleolithic registry keys
CAPABILITY_ALIASES: dict[str, str] = {
    "warmth": "warmth_output",
    "heat": "warmth_output",
    "water": "water_output",
    "food": "food_output",
    "tools": "tool_craft",
    "crafting": "tool_craft",
    "hunt": "hunting",
    "defense": "hunting",
    "protection": "shelter",
    "shelter_strength": "shelter",
    "storage_capacity": "storage",
    "social": "social_cohesion",
    "innovation": "innovation_rate",
    "charcoal": "warmth_output",
    "fuel": "warmth_output",
    "burning": "warmth_output",
}


class CapabilityEngine:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def normalize(self, proposal: IdeaProposal) -> NormalizedProposal:
        queued_keys: list[str] = []
        dropped_keys: list[str] = []

        for suggestion in proposal.suggested_capabilities:
            pending = self.registry.propose_new_capability(
                suggestion, source=proposal.type
            )
            if pending:
                queued_keys.append(pending.key)

        raw: dict[str, float] = {}
        for key, value in proposal.capabilities.items():
            key = key.strip().lower().replace(" ", "_")
            key = CAPABILITY_ALIASES.get(key, key)
            if key in MODERN_ONLY_KEYS:
                dropped_keys.append(key)
                continue
            raw[key] = float(value)

        normalized, unknown = self.registry.normalize_capabilities(raw)
        for key in unknown:
            if key in MODERN_ONLY_KEYS:
                dropped_keys.append(key)
                continue
            aliased = CAPABILITY_ALIASES.get(key, key)
            if self.registry.has(aliased):
                src_val = raw.get(key, proposal.capabilities.get(key, 0.5))
                normalized[aliased] = self.registry._clamp(aliased, float(src_val))
            else:
                queued_keys.append(key)

        filled = self.registry.fill_defaults(normalized, era=self.registry.era)

        return NormalizedProposal(
            type=proposal.type,
            tags=[t.lower().strip() for t in proposal.tags],
            capabilities=filled,
            queued_capability_keys=queued_keys,
            dropped_capability_keys=dropped_keys,
        )
