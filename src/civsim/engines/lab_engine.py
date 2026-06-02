from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from civsim.models.capabilities import IdeaProposal
from civsim.models.entity_kinds import classify_entity_tags
from civsim.models.world import novel_compound_name, Region
from civsim.registry.material_registry import MaterialRegistry

IMPLICIT_MATERIALS = frozenset({"bone", "hide", "dung"})
LAB_COST = 0.1

NATURAL_COMBO_MSG = (
    "Pick a natural combination — two materials, two machines, two objects, "
    "two methods you know, or mix different kinds (e.g. ore with fire, hide with a needle)."
)


@dataclass(frozen=True)
class LabRecipe:
    materials: frozenset[str]
    required_components: frozenset[str]
    proposal: IdeaProposal
    feedback: str
    kind: str = "component"
    object_count: int = 0
    object_tags: frozenset[str] = frozenset()
    component_count: int = 0
    component_tags: frozenset[str] = frozenset()
    method: str | None = None
    unlocks_method: str | None = None


class LabEngine:
    def __init__(
        self,
        material_registry: MaterialRegistry,
        recipes_path: Path | None = None,
    ) -> None:
        self.materials = material_registry
        self.recipes = self._load_recipes(recipes_path)

    def _load_recipes(self, path: Path | None) -> list[LabRecipe]:
        if not path or not path.exists():
            return []
        with path.open() as f:
            raw = yaml.safe_load(f) or {}
        recipes: list[LabRecipe] = []
        for spec in raw.get("recipes") or []:
            mats = frozenset(spec.get("materials") or [])
            requires = spec.get("requires") or {}
            required_components: set[str] = set(requires.get("components") or [])
            near = spec.get("near")
            if near:
                required_components.add(near)
            caps = {k: float(v) for k, v in (spec.get("capabilities") or {}).items()}
            tags = list(spec.get("tags", []))
            kind = spec.get("kind", "component")
            if kind == "object" and "object" not in tags:
                tags.append("object")
            proposal = IdeaProposal(
                type=spec["type"],
                tags=tags,
                capabilities=caps,
                player_name=spec.get("player_name", "Experiment result"),
                reasoning=spec.get("feedback", "Something new from the combination."),
            )
            tags = classify_entity_tags(proposal.tags, proposal.type, caps)
            recipes.append(
                LabRecipe(
                    materials=mats,
                    required_components=frozenset(required_components),
                    proposal=proposal.model_copy(update={"tags": tags}),
                    feedback=spec.get("feedback", "Something happens."),
                    kind=kind,
                    object_count=int(spec.get("object_count", 0)),
                    object_tags=frozenset(spec.get("object_tags") or []),
                    component_count=int(spec.get("component_count", 0)),
                    component_tags=frozenset(spec.get("component_tags") or []),
                    method=spec.get("method"),
                    unlocks_method=spec.get("unlocks_method"),
                )
            )
        return recipes

    @classmethod
    def load_for_era(cls, era: str, data_dir: Path, material_registry: MaterialRegistry) -> LabEngine:
        path = data_dir / f"lab_recipes_{era}.yaml"
        return cls(material_registry, path)

    @staticmethod
    def is_natural_combination(
        material_ids: list[str],
        component_ids: list[str],
        object_ids: list[str],
        method_ids: list[str],
    ) -> bool:
        if len(method_ids) >= 2:
            return True
        if len(material_ids) >= 2:
            return True
        if len(component_ids) >= 2:
            return True
        if len(object_ids) >= 2:
            return True
        if material_ids and component_ids:
            return True
        if material_ids and object_ids:
            return True
        if component_ids and object_ids:
            return True
        if method_ids and material_ids:
            return True
        if method_ids and component_ids:
            return True
        if method_ids and object_ids:
            return True
        return False

    def validate_inputs(
        self,
        material_ids: list[str],
        component_ids: list[str],
        object_ids: list[str],
        region: Region,
        state: GameState,
        method_ids: list[str] | None = None,
        intent: str = "",
    ) -> list[str]:
        errors: list[str] = []
        methods = list(method_ids or [])

        if not self.is_natural_combination(material_ids, component_ids, object_ids, methods):
            errors.append(NATURAL_COMBO_MSG)

        for method_id in methods:
            if method_id not in state.known_methods:
                defn_name = method_id.replace("_", " ")
                errors.append(f"You haven't learned {defn_name} yet — invent or discover it first.")

        for mat_id in material_ids:
            if not self.materials.get(mat_id):
                errors.append(f"Unknown material: {mat_id}")
            elif not self._material_selectable(mat_id, region, state):
                errors.append(
                    f"{self.materials.name_for(mat_id)} is not available — "
                    "survey, gather, or discover it first."
                )
        for eid in component_ids + object_ids:
            entity = next((e for e in state.entities if e.id == eid), None)
            if not entity:
                errors.append(f"Unknown item: {eid}")
            elif not entity.operational:
                errors.append(f"{entity.name} is not usable right now.")
        return errors

    def _material_selectable(self, mat_id: str, region: Region, state: GameState) -> bool:
        if mat_id in state.novel_compounds:
            return state.material_stocks.get(mat_id, 0.0) > 0.02
        if mat_id in IMPLICIT_MATERIALS:
            return True
        if state.material_stocks.get(mat_id, 0.0) > 0.02:
            return True
        for deposit in region.deposits:
            if deposit.material_id == mat_id and deposit.discovered and deposit.abundance > 0.05:
                return True
        return False

    def _count_matching_entities(
        self,
        entity_ids: list[str],
        state: GameState,
        kind_tag: str,
        required_tags: frozenset[str],
        count: int,
    ) -> bool:
        if count < 1:
            return True
        entities = [
            e for e in state.entities if e.id in entity_ids and kind_tag in e.tags
        ]
        if len(entities) < count:
            return False
        if not required_tags:
            return True
        tagged = [
            e
            for e in entities
            if required_tags & {t.lower() for t in e.tags}
        ]
        return len(tagged) >= count

    def _method_satisfied(self, recipe: LabRecipe, method_ids: list[str]) -> bool:
        if not recipe.method:
            return True
        if not method_ids:
            return True
        return recipe.method in method_ids

    def _components_satisfied(self, recipe: LabRecipe, component_set: set[str]) -> bool:
        return recipe.required_components.issubset(component_set)

    def match_recipe(
        self,
        material_ids: list[str],
        component_ids: list[str],
        object_ids: list[str],
        state: GameState,
        method_ids: list[str] | None = None,
    ) -> LabRecipe | None:
        mat_set = frozenset(material_ids)
        component_set = set(component_ids)
        methods = list(method_ids or [])

        for recipe in self.recipes:
            if recipe.object_count >= 1 or recipe.component_count >= 1:
                continue
            if recipe.materials != mat_set:
                continue
            if not self._components_satisfied(recipe, component_set):
                continue
            if not self._method_satisfied(recipe, methods):
                continue
            return recipe

        for recipe in self.recipes:
            if recipe.object_count < 2:
                continue
            if recipe.materials and recipe.materials != mat_set:
                continue
            if recipe.required_components and not self._components_satisfied(recipe, component_set):
                continue
            if not self._count_matching_entities(
                object_ids, state, "object", recipe.object_tags, recipe.object_count
            ):
                continue
            if not self._method_satisfied(recipe, methods):
                continue
            return recipe

        for recipe in self.recipes:
            if recipe.object_count < 1 or recipe.component_count < 1:
                continue
            if recipe.materials != mat_set:
                continue
            if recipe.required_components and not self._components_satisfied(recipe, component_set):
                continue
            if not self._count_matching_entities(
                object_ids, state, "object", recipe.object_tags, recipe.object_count
            ):
                continue
            if not self._count_matching_entities(
                component_ids, state, "component", recipe.component_tags, recipe.component_count
            ):
                continue
            if not self._method_satisfied(recipe, methods):
                continue
            return recipe

        return None

    def build_combination_context(
        self,
        material_ids: list[str],
        component_ids: list[str],
        object_ids: list[str],
        method_ids: list[str],
        state: GameState,
        method_names: dict[str, str],
        intent: str = "",
    ) -> dict:
        materials = [
            {"id": mid, "name": self.materials.name_for(mid)} for mid in material_ids
        ]
        components: list[dict] = []
        objects: list[dict] = []
        for eid in component_ids:
            entity = next((e for e in state.entities if e.id == eid), None)
            if entity:
                components.append(
                    {
                        "id": entity.id,
                        "name": entity.name,
                        "type": entity.type,
                        "tags": entity.tags,
                    }
                )
        for eid in object_ids:
            entity = next((e for e in state.entities if e.id == eid), None)
            if entity:
                objects.append(
                    {
                        "id": entity.id,
                        "name": entity.name,
                        "type": entity.type,
                        "tags": entity.tags,
                    }
                )
        methods = [
            {"id": mid, "name": method_names.get(mid, mid)} for mid in method_ids
        ]
        return {
            "materials": materials,
            "components": components,
            "objects": objects,
            "methods": methods,
            "intent": intent.strip(),
            "summary": self.build_prompt(
                material_ids, component_ids, object_ids, state, intent
            ),
        }

    def build_prompt(
        self,
        material_ids: list[str],
        component_ids: list[str],
        object_ids: list[str],
        state: GameState,
        intent: str,
    ) -> str:
        mat_names = [self.materials.name_for(m) for m in material_ids]
        names: list[str] = []
        for eid in component_ids + object_ids:
            entity = next((e for e in state.entities if e.id == eid), None)
            if entity:
                kind = "object" if "object" in entity.tags else "component"
                names.append(f"{entity.name} ({kind})")
        parts: list[str] = []
        if mat_names:
            parts.append(f"materials: {', '.join(mat_names)}")
        if names:
            parts.append(f"using: {', '.join(names)}")
        body = "Lab experiment — combine " + "; ".join(parts) if parts else "Lab experiment"
        if intent.strip():
            body += f". Intent: {intent.strip()}"
        else:
            body += ". See what inanimate thing or machine emerges."
        return body + "."

    def consume_materials(
        self, state: GameState, material_ids: list[str], region: Region
    ) -> tuple[dict[str, float], list[str]]:
        costs: dict[str, float] = {}
        feedback: list[str] = []
        for mat_id in material_ids:
            if mat_id in IMPLICIT_MATERIALS:
                costs[mat_id] = 0.0
                continue
            cost = LAB_COST
            stock = state.material_stocks.get(mat_id, 0.0)
            if stock >= cost:
                state.material_stocks[mat_id] = stock - cost
                costs[mat_id] = cost
            else:
                for deposit in region.deposits:
                    if (
                        deposit.material_id == mat_id
                        and deposit.discovered
                        and deposit.abundance >= cost
                    ):
                        deposit.abundance = max(0.0, deposit.abundance - cost)
                        costs[mat_id] = cost
                        break
                else:
                    costs[mat_id] = 0.0
            name = self.materials.name_for(mat_id)
            if costs.get(mat_id, 0) > 0:
                feedback.append(f"Used some {name}.")
        return costs, feedback

    def list_selectable_materials(self, region: Region, state: GameState) -> list[dict]:
        items: list[dict] = []
        seen: set[str] = set()
        for mat_id in sorted(IMPLICIT_MATERIALS):
            seen.add(mat_id)
            items.append(
                {
                    "id": mat_id,
                    "name": self.materials.name_for(mat_id),
                    "source": "scavenging",
                    "stock": state.material_stocks.get(mat_id, 0.0),
                }
            )
        for deposit in region.deposits:
            if not deposit.discovered or deposit.material_id in seen:
                continue
            seen.add(deposit.material_id)
            items.append(
                {
                    "id": deposit.material_id,
                    "name": self.materials.name_for(deposit.material_id),
                    "source": "deposit",
                    "stock": state.material_stocks.get(deposit.material_id, 0.0),
                    "abundance": deposit.abundance,
                }
            )
        for compound_id, entry in sorted(state.novel_compounds.items()):
            if compound_id in seen:
                continue
            seen.add(compound_id)
            items.append(
                {
                    "id": compound_id,
                    "name": novel_compound_name(entry),
                    "source": "discovered",
                    "stock": state.material_stocks.get(compound_id, 0.0),
                }
            )
        return items
