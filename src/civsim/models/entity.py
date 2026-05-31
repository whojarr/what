from pydantic import BaseModel, ConfigDict, Field


class EntityCore(BaseModel):
    """Simulation-facing entity — no player name."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    tags: list[str] = Field(default_factory=list)
    capabilities: dict[str, float] = Field(default_factory=dict)
    region_id: str
    health: float = 1.0
    operational: bool = True


class EntityDraft(BaseModel):
    """Pre-placement entity from normalized proposal."""

    model_config = ConfigDict(extra="forbid")

    type: str
    tags: list[str] = Field(default_factory=list)
    capabilities: dict[str, float] = Field(default_factory=dict)
    region_id: str
    name: str = "Unnamed"


class Entity(BaseModel):
    """Full entity with display name."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str
    tags: list[str] = Field(default_factory=list)
    capabilities: dict[str, float] = Field(default_factory=dict)
    region_id: str
    health: float = 1.0
    operational: bool = True

    def to_core(self) -> EntityCore:
        return EntityCore(
            id=self.id,
            type=self.type,
            tags=self.tags,
            capabilities=self.capabilities,
            region_id=self.region_id,
            health=self.health,
            operational=self.operational,
        )

    @classmethod
    def from_core(cls, core: EntityCore, name: str) -> "Entity":
        return cls(
            id=core.id,
            name=name,
            type=core.type,
            tags=core.tags,
            capabilities=core.capabilities,
            region_id=core.region_id,
            health=core.health,
            operational=core.operational,
        )
