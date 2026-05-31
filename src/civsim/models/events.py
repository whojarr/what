from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    # Paleolithic
    COLD_SNAP = "cold_snap"
    CAVE_IN = "cave_in"
    PREDATOR = "predator"
    FIRE_FADES = "fire_fades"
    DROUGHT = "drought"
    # Future eras (retained)
    FLOOD = "flood"
    HEATWAVE = "heatwave"
    STORM = "storm"
    SUPPLY_DISRUPTION = "supply_disruption"


class GameEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: EventType
    severity: float
    turn: int
    region_id: str | None = None
    description: str = ""
    region_name: str = ""


class EventImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    damage: float
    health_after: float
    operational: bool
    entity_name: str = ""
