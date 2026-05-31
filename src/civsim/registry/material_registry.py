from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

MINING_TAGS = frozenset({"mining", "excavation", "digging", "prospecting", "extraction"})
WALL_TAGS = frozenset({"stone", "wall", "cave"})


@dataclass(frozen=True)
class MaterialDefinition:
    id: str
    name: str
    tags: frozenset[str]
    substitutes: tuple[str, ...]
    implicit: bool = False


class MaterialRegistry:
    def __init__(self) -> None:
        self._materials: dict[str, MaterialDefinition] = {}
        self._tag_to_material: dict[str, str] = {}

    @classmethod
    def from_yaml(cls, path: Path) -> MaterialRegistry:
        registry = cls()
        with path.open() as f:
            raw = yaml.safe_load(f) or {}
        for mat_id, spec in (raw.get("materials") or {}).items():
            tags = frozenset(t.lower().strip() for t in spec.get("tags", []))
            subs = tuple(s.lower().strip() for s in spec.get("substitutes", []))
            defn = MaterialDefinition(
                id=mat_id,
                name=spec.get("name", mat_id),
                tags=tags,
                substitutes=subs,
                implicit=bool(spec.get("implicit", False)),
            )
            registry._materials[mat_id] = defn
            for tag in tags:
                registry._tag_to_material[tag] = mat_id
        return registry

    @classmethod
    def load_for_era(cls, era: str, data_dir: Path) -> MaterialRegistry:
        path = data_dir / f"materials_{era}.yaml"
        if path.exists():
            return cls.from_yaml(path)
        fallback = data_dir / "materials_paleolithic.yaml"
        if fallback.exists():
            return cls.from_yaml(fallback)
        return cls()

    def get(self, material_id: str) -> MaterialDefinition | None:
        return self._materials.get(material_id)

    def name_for(self, material_id: str) -> str:
        defn = self._materials.get(material_id)
        return defn.name if defn else material_id

    def required_materials(self, tags: list[str]) -> list[str]:
        tag_set = {t.lower().strip() for t in tags}
        seen: set[str] = set()
        required: list[str] = []
        for mat_id, defn in self._materials.items():
            if tag_set & defn.tags and mat_id not in seen:
                seen.add(mat_id)
                required.append(mat_id)
        return required

    def substitute_names(self, material_id: str) -> list[str]:
        defn = self._materials.get(material_id)
        if not defn:
            return []
        return [self.name_for(s) for s in defn.substitutes if s in self._materials]

    def is_implicit(self, material_id: str) -> bool:
        defn = self._materials.get(material_id)
        return bool(defn and defn.implicit)

    def all_material_ids(self) -> list[str]:
        return sorted(self._materials.keys())
