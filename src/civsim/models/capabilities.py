from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConstraintStatus(str, Enum):
    VALID = "VALID"
    RISKY = "RISKY"
    NEEDS_TWEAK = "NEEDS_TWEAK"
    BLOCKED = "BLOCKED"


class CapabilityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    range: tuple[float, float] = (0.0, 1.0)
    default: float = 0.0
    meaning: str


class SuggestedCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    category: str
    meaning: str
    default: float = 0.0


class IdeaProposal(BaseModel):
    """Raw LLM output before normalization."""

    model_config = ConfigDict(extra="forbid")

    type: str
    tags: list[str] = Field(default_factory=list)
    capabilities: dict[str, float] = Field(default_factory=dict)
    suggested_capabilities: list[SuggestedCapability] = Field(default_factory=list)
    player_name: str = "Unnamed Project"
    reasoning: str = ""


class LabCombinationVerdict(BaseModel):
    """AI judgment of a discovery-bench combination."""

    model_config = ConfigDict(extra="forbid")

    reasonable: bool
    verdict: str = "blocked"
    feedback: str = ""
    player_name: str = ""
    type: str = ""
    tags: list[str] = Field(default_factory=list)
    capabilities: dict[str, float] = Field(default_factory=dict)
    reasoning: str = ""
    result_kind: str = "component"


class PendingCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    key: str
    category: str
    meaning: str
    default: float = 0.0
    proposed_from: str = ""


class ConstraintResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ConstraintStatus
    warnings: list[str] = Field(default_factory=list)
    hidden_issues: list[str] = Field(default_factory=list)
    suggested_adjustments: list[dict[str, Any]] = Field(default_factory=list)


class NormalizedProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    tags: list[str]
    capabilities: dict[str, float]
    queued_capability_keys: list[str] = Field(default_factory=list)
    dropped_capability_keys: list[str] = Field(default_factory=list)
