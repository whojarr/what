from __future__ import annotations

from civsim.models.entity import Entity
from civsim.models.world import GameState
from civsim.registry.method_registry import MethodDefinition, MethodRegistry


class MethodEngine:
    def __init__(self, registry: MethodRegistry) -> None:
        self.registry = registry

    def seed_starter_methods(self, state: GameState) -> list[str]:
        feedback: list[str] = []
        for defn in self.registry.all_methods():
            if defn.starter and self.learn(state, defn.id):
                feedback.append(f"You know {defn.name} — {defn.description.lower()}")
        return feedback

    def sync_from_world(self, state: GameState) -> None:
        """Backfill starter methods for legacy saves missing the field."""
        if not state.known_methods:
            self.seed_starter_methods(state)

    def learn(self, state: GameState, method_id: str) -> bool:
        if not self.registry.get(method_id):
            return False
        if method_id in state.known_methods:
            return False
        state.known_methods.append(method_id)
        return True

    def unlock_from_entity(self, state: GameState, entity: Entity) -> str | None:
        method_id = self.registry.method_for_entity_type(entity.type)
        if method_id and self.learn(state, method_id):
            defn = self.registry.get(method_id)
            return defn.name if defn else method_id
        return None

    def unlock_from_recipe_type(self, state: GameState, recipe_type: str) -> str | None:
        method_id = self.registry.method_for_recipe_type(recipe_type)
        if method_id and self.learn(state, method_id):
            defn = self.registry.get(method_id)
            return defn.name if defn else method_id
        return None

    def learn_from_invention(
        self, state: GameState, invention_type: str, tags: list[str]
    ) -> str | None:
        if invention_type.startswith("method."):
            method_id = invention_type.split(".", 1)[1]
            if self.learn(state, method_id):
                defn = self.registry.get(method_id)
                return defn.name if defn else method_id
        tag_set = {t.lower() for t in tags}
        for defn in self.registry.all_methods():
            if tag_set & {defn.id} | (tag_set & defn.output_tags):
                if self.learn(state, defn.id):
                    return defn.name
        return None

    def missing_method_message(self, method_id: str) -> str:
        defn = self.registry.get(method_id)
        if not defn:
            return f"Learn {method_id} first."
        hint = defn.hint or f"Invent {defn.name.lower()} on the Invent page."
        return f"You haven't learned {defn.name} — {hint}"

    def validate_recipe_method(self, state: GameState, method_id: str | None) -> list[str]:
        if not method_id:
            return []
        if method_id in state.known_methods:
            return []
        return [self.missing_method_message(method_id)]

    def validate_unknown_combination(self, state: GameState, intent: str) -> list[str]:
        if intent.strip():
            needed = self.registry.methods_for_text(intent)
            missing = [m for m in needed if m not in state.known_methods]
            if missing:
                return [self.missing_method_message(missing[0])]
        return [
            "No known process fits this combination — discover a recipe, combine two "
            "methods you know, or invent a process on the Invent page."
        ]

    def fusion_unknown_message(self) -> str:
        return (
            "These two methods don't combine into a new process — try a different pair "
            "(e.g. Heating with Soaking, or Heating with Knapping)."
        )

    def fusion_already_known_message(self, method_id: str) -> str:
        defn = self.registry.get(method_id)
        name = defn.name if defn else method_id
        return f"You already know {name} — nothing new emerges from this pairing."

    def list_for_ui(self, state: GameState) -> list[dict]:
        known = set(state.known_methods)
        items: list[dict] = []
        for defn in self.registry.all_methods():
            items.append(
                {
                    "id": defn.id,
                    "name": defn.name,
                    "description": defn.description,
                    "known": defn.id in known,
                    "hint": defn.hint if defn.id not in known else "",
                }
            )
        return items
