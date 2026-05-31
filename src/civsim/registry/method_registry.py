from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class MethodDefinition:
    id: str
    name: str
    description: str
    output_tags: frozenset[str]
    starter: bool = False
    unlock_entity_types: frozenset[str] = frozenset()
    unlock_recipe_types: frozenset[str] = frozenset()
    hint: str = ""


@dataclass(frozen=True)
class MethodFusion:
    methods: frozenset[str]
    unlocks: str
    feedback: str


class MethodRegistry:
    def __init__(self) -> None:
        self._methods: dict[str, MethodDefinition] = {}
        self._entity_type_to_method: dict[str, str] = {}
        self._recipe_type_to_method: dict[str, str] = {}
        self._fusions: list[MethodFusion] = []

    @classmethod
    def from_yaml(cls, path: Path) -> MethodRegistry:
        registry = cls()
        with path.open() as f:
            raw = yaml.safe_load(f) or {}
        for method_id, spec in (raw.get("methods") or {}).items():
            unlock_entity = frozenset(spec.get("unlock_entity_types") or [])
            unlock_recipe = frozenset(spec.get("unlock_recipe_types") or [])
            defn = MethodDefinition(
                id=method_id,
                name=spec.get("name", method_id),
                description=spec.get("description", ""),
                output_tags=frozenset(
                    t.lower().strip() for t in spec.get("output_tags") or []
                ),
                starter=bool(spec.get("starter", False)),
                unlock_entity_types=unlock_entity,
                unlock_recipe_types=unlock_recipe,
                hint=spec.get("hint", ""),
            )
            registry._methods[method_id] = defn
            for entity_type in unlock_entity:
                registry._entity_type_to_method[entity_type] = method_id
            for recipe_type in unlock_recipe:
                registry._recipe_type_to_method[recipe_type] = method_id
        for spec in raw.get("method_fusions") or []:
            pair = frozenset(spec.get("methods") or [])
            if len(pair) != 2 or not spec.get("unlocks"):
                continue
            registry._fusions.append(
                MethodFusion(
                    methods=pair,
                    unlocks=spec["unlocks"],
                    feedback=spec.get(
                        "feedback",
                        "Two processes merge in your mind — something new clicks.",
                    ),
                )
            )
        return registry

    @classmethod
    def load_for_era(cls, era: str, data_dir: Path) -> MethodRegistry:
        path = data_dir / f"methods_{era}.yaml"
        if path.exists():
            return cls.from_yaml(path)
        fallback = data_dir / "methods_paleolithic.yaml"
        if fallback.exists():
            return cls.from_yaml(fallback)
        return cls()

    def get(self, method_id: str) -> MethodDefinition | None:
        return self._methods.get(method_id)

    def all_methods(self) -> list[MethodDefinition]:
        return [self._methods[k] for k in sorted(self._methods.keys())]

    def method_for_entity_type(self, entity_type: str) -> str | None:
        return self._entity_type_to_method.get(entity_type)

    def method_for_recipe_type(self, recipe_type: str) -> str | None:
        return self._recipe_type_to_method.get(recipe_type)

    def methods_for_text(self, text: str) -> list[str]:
        words = {w.lower().strip(".,!?") for w in text.split()}
        matched: list[str] = []
        for method_id, defn in self._methods.items():
            if words & defn.output_tags:
                matched.append(method_id)
        return matched

    def match_fusion(self, method_ids: list[str]) -> MethodFusion | None:
        pair = frozenset(method_ids)
        if len(pair) != 2:
            return None
        for fusion in self._fusions:
            if fusion.methods == pair:
                return fusion
        return None
