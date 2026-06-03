from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from civsim.models.entity import Entity
from civsim.models.events import EventImpact, GameEvent

DEFAULT_ERA = "paleolithic"

DepositDepth = Literal["surface", "deep"]


class MaterialDeposit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    material_id: str
    abundance: float = Field(ge=0.0, le=1.0)
    depth: DepositDepth = "surface"
    discovered: bool = False
    description: str = ""


class Resources(BaseModel):
    """Survival resource pools (0–1 normalized)."""

    model_config = ConfigDict(extra="forbid")

    warmth: float = 0.15
    water: float = 0.4
    food: float = 0.1
    materials: float = 0.1
    knowledge: float = 0.05


class ClimateState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_index: float = 0.35
    water_stress: float = 0.2
    atmospheric_instability: float = 0.1
    ecosystem_health: float = 0.75


class CompoundProvenance(BaseModel):
    """What was combined when a novel compound was first isolated."""

    model_config = ConfigDict(extra="forbid")

    materials: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    intent: str = ""
    turn: int = 0
    source: Literal["lab", "invent"] = "lab"
    recipe_id: str | None = None


class NovelCompound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provenance: CompoundProvenance = Field(default_factory=CompoundProvenance)


def novel_compound_name(entry: NovelCompound | str) -> str:
    if isinstance(entry, str):
        return entry
    return entry.name


class RegionExit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    target_region_id: str
    description: str = ""
    discovered: bool = False
    accessible: bool = False


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    biome_tags: list[str] = Field(default_factory=list)
    energy_ceiling: float = 0.5
    water_availability: float = 0.5
    absent_materials: list[str] = Field(default_factory=list)
    always_available: list[str] = Field(default_factory=list)
    deposits: list[MaterialDeposit] = Field(default_factory=list)
    exits: list[RegionExit] = Field(default_factory=list)


class TickResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn: int
    resources: Resources
    climate: ClimateState
    events: list[GameEvent] = Field(default_factory=list)
    impacts: list[EventImpact] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    resource_deltas: dict[str, float] = Field(default_factory=dict)
    climate_deltas: dict[str, float] = Field(default_factory=dict)


class GameState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = ""
    turn: int = 0
    rng_seed: int = 42
    era: str = DEFAULT_ERA
    path_divergence: float = 0.0
    invention_count: int = 0
    resources: Resources = Field(default_factory=Resources)
    climate: ClimateState = Field(default_factory=ClimateState)
    regions: list[Region] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    event_log: list[GameEvent] = Field(default_factory=list)
    entity_names: dict[str, str] = Field(default_factory=dict)
    material_stocks: dict[str, float] = Field(default_factory=dict)
    region_material_stocks: dict[str, dict[str, float]] = Field(default_factory=dict)
    novel_compounds: dict[str, NovelCompound] = Field(default_factory=dict)
    surveyed_region_ids: list[str] = Field(default_factory=list)
    known_methods: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_state(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        nc = data.get("novel_compounds")
        if isinstance(nc, dict):
            migrated: dict[str, object] = {}
            for cid, val in nc.items():
                if isinstance(val, str):
                    migrated[cid] = {"name": val}
                else:
                    migrated[cid] = val
            data = {**data, "novel_compounds": migrated}
        if data.get("name") is None:
            data = {**data, "name": ""}
        legacy_stocks = data.get("material_stocks")
        regional = data.get("region_material_stocks")
        if legacy_stocks and not regional:
            regions = data.get("regions") or []
            region_id = regions[0]["id"] if regions else "cave_chamber"
            data = {
                **data,
                "region_material_stocks": {region_id: dict(legacy_stocks)},
            }
        return data
