from __future__ import annotations

import re
from dataclasses import dataclass, field

from civsim.models.entity import EntityCore
from civsim.models.world import CompoundProvenance, GameState, NovelCompound, novel_compound_name, MaterialDeposit, Region
from civsim.registry.material_registry import MINING_TAGS, MaterialRegistry, WALL_TAGS

# Minimum deposit abundance to experiment at the bench (lab_engine.LAB_COST).
MIN_DEPOSIT_USE = 0.1

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

    @staticmethod
    def region_stocks(state: GameState, region_id: str) -> dict[str, float]:
        if region_id not in state.region_material_stocks:
            state.region_material_stocks[region_id] = {}
        return state.region_material_stocks[region_id]

    @classmethod
    def stock_at(cls, state: GameState, region_id: str, material_id: str) -> float:
        return cls.region_stocks(state, region_id).get(material_id, 0.0)

    @classmethod
    def set_stock(
        cls, state: GameState, region_id: str, material_id: str, amount: float
    ) -> None:
        stocks = cls.region_stocks(state, region_id)
        if amount <= 0.001:
            stocks.pop(material_id, None)
        else:
            stocks[material_id] = min(1.0, amount)

    @classmethod
    def add_stock(
        cls, state: GameState, region_id: str, material_id: str, delta: float
    ) -> None:
        cls.set_stock(
            state,
            region_id,
            material_id,
            cls.stock_at(state, region_id, material_id) + delta,
        )

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
        *,
        region_id: str,
        provenance: CompoundProvenance | None = None,
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
        state.novel_compounds[compound_id] = NovelCompound(
            name=display,
            provenance=provenance or CompoundProvenance(),
        )
        self.set_stock(
            state,
            region_id,
            compound_id,
            max(0.25, self.stock_at(state, region_id, compound_id)),
        )
        return compound_id, f"You isolated a new substance: {display}."

    def name_for(self, material_id: str, state: GameState | None = None) -> str:
        if state and material_id in state.novel_compounds:
            return novel_compound_name(state.novel_compounds[material_id])
        return self.materials.name_for(material_id)

    def is_material_available(
        self,
        material_id: str,
        region: Region,
        state: GameState,
    ) -> bool:
        stock = self.stock_at(state, region.id, material_id)
        if material_id in region.always_available:
            return True
        if material_id in region.absent_materials:
            return stock > 0.02
        if material_id in state.novel_compounds:
            return stock > 0.02
        if stock > 0.02:
            return True
        for deposit in region.deposits:
            if deposit.material_id == material_id and deposit.discovered:
                return deposit.abundance >= MIN_DEPOSIT_USE or stock > 0.02
        return False

    _BASELINE_LAB_SOURCES: dict[str, str] = {
        "bone": "scavenging",
        "hide": "hunting",
        "dung": "fuel",
        "wood": "foraging",
        "plant_fiber": "gathering",
        "clay": "earth",
    }

    def list_lab_materials(self, region: Region, state: GameState) -> list[dict]:
        """Materials the discovery bench can offer in this region."""
        items: list[dict] = []
        seen: set[str] = set()
        regional = self.region_stocks(state, region.id)

        for mat_id in region.always_available:
            seen.add(mat_id)
            items.append(
                {
                    "id": mat_id,
                    "name": self.materials.name_for(mat_id),
                    "source": self._BASELINE_LAB_SOURCES.get(mat_id, "nearby"),
                    "stock": regional.get(mat_id, 0.0),
                }
            )

        for deposit in region.deposits:
            if not deposit.discovered or deposit.material_id in seen:
                continue
            if not self.is_material_available(deposit.material_id, region, state):
                continue
            stock = regional.get(deposit.material_id, 0.0)
            seen.add(deposit.material_id)
            items.append(
                {
                    "id": deposit.material_id,
                    "name": self.materials.name_for(deposit.material_id),
                    "source": "deposit",
                    "stock": stock,
                    "abundance": deposit.abundance,
                }
            )

        for compound_id, entry in sorted(state.novel_compounds.items()):
            if compound_id in seen:
                continue
            stock = regional.get(compound_id, 0.0)
            if stock <= 0.02:
                continue
            seen.add(compound_id)
            items.append(
                {
                    "id": compound_id,
                    "name": novel_compound_name(entry),
                    "source": "discovered",
                    "stock": stock,
                }
            )

        for mat_id, stock in sorted(regional.items()):
            if mat_id in seen or stock <= 0.02:
                continue
            if not self.is_material_available(mat_id, region, state):
                continue
            seen.add(mat_id)
            source = "hauled" if mat_id in region.absent_materials else "stored"
            items.append(
                {
                    "id": mat_id,
                    "name": self.materials.name_for(mat_id),
                    "source": source,
                    "stock": stock,
                }
            )

        items.sort(key=lambda item: item["name"].lower())
        return items

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
            stock = self.stock_at(state, region.id, deposit.material_id)
            items.append(
                {
                    "id": deposit.material_id,
                    "name": self.materials.name_for(deposit.material_id),
                    "abundance": deposit.abundance,
                    "stock": stock,
                }
            )
        for compound_id, entry in sorted(state.novel_compounds.items()):
            stock = self.stock_at(state, region.id, compound_id)
            items.append(
                {
                    "id": compound_id,
                    "name": novel_compound_name(entry),
                    "abundance": stock,
                    "stock": stock,
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
                self.add_stock(state, core.region_id, mat_id, taken)

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
                    stock = self.stock_at(state, core.region_id, mat_id)
                    if stock >= demand:
                        self.set_stock(state, core.region_id, mat_id, stock - demand)
                        demand = 0.0
                        break
            if demand > 0:
                state.resources.materials = max(0.0, state.resources.materials - demand)

        self._aggregate_materials_meter(state)

    def _aggregate_materials_meter(self, state: GameState) -> None:
        combined: dict[str, float] = {}
        for stocks in state.region_material_stocks.values():
            for mat_id, stock in stocks.items():
                if stock > 0:
                    combined[mat_id] = combined.get(mat_id, 0.0) + stock
        if not combined:
            return
        region = state.regions[0] if state.regions else None
        weighted = 0.0
        weight_sum = 0.0
        for mat_id, stock in combined.items():
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
