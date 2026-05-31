from __future__ import annotations

import re
from dataclasses import dataclass, field

from civsim.models.entity import EntityCore
from civsim.models.world import GameState, MaterialDeposit, Region
from civsim.registry.material_registry import MINING_TAGS, MaterialRegistry, WALL_TAGS

COMPOUND_HINT_TAGS = frozenset(
    {
        "chemical",
        "compound",
        "pigment",
        "mineral",
        "crystal",
        "mix",
        "varnish",
        "resin",
        "powder",
        "metal",
        "ore",
        "novel",
        "substance",
        "reagent",
    }
)


@dataclass
class SurveyResult:
    discoveries: list[MaterialDeposit] = field(default_factory=list)
    feedback: list[str] = field(default_factory=list)


class MaterialEngine:
    def __init__(self, material_registry: MaterialRegistry) -> None:
        self.materials = material_registry

    def survey_region(self, state: GameState, region: Region) -> SurveyResult:
        result = SurveyResult()
        newly: list[MaterialDeposit] = []

        for deposit in region.deposits:
            if deposit.depth == "surface" and not deposit.discovered:
                deposit.discovered = True
                newly.append(deposit)

        result.discoveries = newly

        if region.id not in state.surveyed_region_ids:
            state.surveyed_region_ids.append(region.id)
            if region.absent_materials:
                absent_names = [
                    self.materials.name_for(m) for m in region.absent_materials
                ]
                result.feedback.append(
                    f"Not found here: {', '.join(absent_names)}."
                )

        for deposit in newly:
            result.feedback.append(deposit.description)

        if not newly and region.id in state.surveyed_region_ids:
            result.feedback.append(
                "You scan the cave again — nothing new on the surface."
            )
        elif not result.feedback:
            result.feedback.append(
                "The cave walls are damp limestone. Flint lies underfoot."
            )

        undiscovered_deep = any(
            d.depth == "deep" and not d.discovered for d in region.deposits
        )
        if undiscovered_deep:
            result.feedback.append(
                "Deeper walls may hold more — dig or invent tools to reach them."
            )

        return result

    def discover_from_invention(
        self,
        state: GameState,
        region: Region,
        tags: list[str],
        capabilities: dict[str, float],
    ) -> list[str]:
        tag_set = {t.lower().strip() for t in tags}
        can_mine = bool(tag_set & MINING_TAGS)
        can_dig = (
            capabilities.get("tool_craft", 0.0) > 0.4 and bool(tag_set & WALL_TAGS)
        )
        if not can_mine and not can_dig:
            return []

        feedback: list[str] = []
        for deposit in region.deposits:
            if deposit.depth == "deep" and not deposit.discovered:
                deposit.discovered = True
                feedback.append(
                    f"You found {self.materials.name_for(deposit.material_id)} "
                    f"in the depths — {deposit.description}"
                )
                break
        return feedback

    def discover_from_entities(self, state: GameState) -> list[str]:
        feedback: list[str] = []
        regions = {r.id: r for r in state.regions}
        for entity in state.entities:
            if not entity.operational or "natural" in entity.tags:
                continue
            region = regions.get(entity.region_id)
            if not region:
                continue
            tag_set = {t.lower() for t in entity.tags}
            if not (tag_set & MINING_TAGS):
                continue
            for deposit in region.deposits:
                if deposit.depth == "deep" and not deposit.discovered:
                    deposit.discovered = True
                    feedback.append(
                        f"Working the rock reveals "
                        f"{self.materials.name_for(deposit.material_id)}."
                    )
                    break
        return feedback

    @staticmethod
    def _compound_id(name: str, fallback: str = "compound") -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:32]
        return slug or fallback

    def register_novel_compound(
        self,
        state: GameState,
        name: str,
        tags: list[str],
        entity_type: str = "",
    ) -> tuple[str, str] | None:
        """Record a newly created substance that is not in the era catalog."""
        if entity_type.startswith("material."):
            compound_id = self._compound_id(entity_type.split(".", 1)[1])
        else:
            tag_set = {t.lower().strip() for t in tags}
            if entity_type.startswith("method."):
                return None
            if not (tag_set & COMPOUND_HINT_TAGS):
                return None
            compound_id = self._compound_id(name, fallback=next(iter(tag_set & COMPOUND_HINT_TAGS), "compound"))

        if self.materials.get(compound_id) or compound_id in state.novel_compounds:
            return None

        display = name.strip() or compound_id.replace("_", " ").title()
        state.novel_compounds[compound_id] = display
        state.material_stocks[compound_id] = max(
            0.25, state.material_stocks.get(compound_id, 0.0)
        )
        return compound_id, f"You isolated a new substance: {display}."

    def name_for(self, material_id: str, state: GameState | None = None) -> str:
        if state and material_id in state.novel_compounds:
            return state.novel_compounds[material_id]
        return self.materials.name_for(material_id)

    def is_material_available(
        self,
        material_id: str,
        region: Region,
        state: GameState,
    ) -> bool:
        if self.materials.is_implicit(material_id):
            return True
        if material_id in state.novel_compounds:
            return state.material_stocks.get(material_id, 0.0) > 0.02
        if material_id in region.absent_materials:
            return False
        stock = state.material_stocks.get(material_id, 0.0)
        if stock > 0.05:
            return True
        for deposit in region.deposits:
            if deposit.material_id == material_id and deposit.discovered:
                return deposit.abundance > 0.05
        return False

    def is_material_discovered(self, material_id: str, region: Region, state: GameState | None = None) -> bool:
        if state and material_id in state.novel_compounds:
            return True
        if self.materials.is_implicit(material_id):
            return True
        for deposit in region.deposits:
            if deposit.material_id == material_id:
                return deposit.discovered
        return material_id not in region.absent_materials

    def deposit_abundance(self, material_id: str, region: Region) -> float:
        total = 0.0
        for deposit in region.deposits:
            if deposit.material_id == material_id and deposit.discovered:
                total = max(total, deposit.abundance)
        return total

    def discovered_materials_for_region(
        self, region: Region, state: GameState
    ) -> list[dict]:
        seen: set[str] = set()
        items: list[dict] = []
        for deposit in region.deposits:
            if not deposit.discovered or deposit.material_id in seen:
                continue
            seen.add(deposit.material_id)
            stock = state.material_stocks.get(deposit.material_id, 0.0)
            items.append(
                {
                    "id": deposit.material_id,
                    "name": self.materials.name_for(deposit.material_id),
                    "abundance": deposit.abundance,
                    "stock": stock,
                }
            )
        for compound_id, display in sorted(state.novel_compounds.items()):
            items.append(
                {
                    "id": compound_id,
                    "name": display,
                    "abundance": state.material_stocks.get(compound_id, 0.0),
                    "stock": state.material_stocks.get(compound_id, 0.0),
                    "novel": True,
                }
            )
        return items

    def harvest_tick(
        self, state: GameState, cores: list[EntityCore]
    ) -> list[str]:
        feedback: list[str] = []
        regions = {r.id: r for r in state.regions}

        for core in cores:
            if not core.operational or "natural" in core.tags:
                continue
            tag_set = {t.lower() for t in core.tags}
            is_miner = bool(tag_set & MINING_TAGS) or (
                core.capabilities.get("tool_craft", 0.0) > 0.4
                and bool(tag_set & WALL_TAGS)
            )
            if not is_miner:
                continue

            region = regions.get(core.region_id)
            if not region:
                continue

            harvest_rate = (
                core.capabilities.get("tool_craft", 0.0) * 0.04
                + (0.02 if tag_set & MINING_TAGS else 0.01)
            )

            for deposit in region.deposits:
                if not deposit.discovered or deposit.abundance <= 0.05:
                    continue
                mat_id = deposit.material_id
                taken = min(harvest_rate, deposit.abundance * 0.08)
                deposit.abundance = max(0.0, deposit.abundance - taken * 0.5)
                current = state.material_stocks.get(mat_id, 0.0)
                state.material_stocks[mat_id] = min(1.0, current + taken)

        self._aggregate_materials_meter(state)
        return feedback

    def drain_materials(
        self, state: GameState, cores: list[EntityCore], region: Region
    ) -> None:
        for core in cores:
            if not core.operational or "natural" in core.tags:
                continue
            demand = core.capabilities.get("material_demand", 0.0) * 0.015
            if demand <= 0:
                continue
            required = self.materials.required_materials(core.tags)
            if required:
                for mat_id in required:
                    stock = state.material_stocks.get(mat_id, 0.0)
                    if stock >= demand:
                        state.material_stocks[mat_id] = stock - demand
                        demand = 0.0
                        break
            if demand > 0:
                state.resources.materials = max(0.0, state.resources.materials - demand)

        self._aggregate_materials_meter(state)

    def _aggregate_materials_meter(self, state: GameState) -> None:
        if not state.material_stocks:
            return
        region = state.regions[0] if state.regions else None
        weighted = 0.0
        weight_sum = 0.0
        for mat_id, stock in state.material_stocks.items():
            if stock <= 0:
                continue
            abundance = 1.0
            if region:
                abundance = max(abundance, self.deposit_abundance(mat_id, region))
            weighted += stock * abundance
            weight_sum += abundance
        if weight_sum > 0:
            aggregate = weighted / weight_sum
            state.resources.materials = min(
                1.0, max(state.resources.materials, aggregate * 0.6)
            )
