from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    turn: int = 0


class MemoryStore(ABC):
    """Weaviate-compatible interface for game memory."""

    @abstractmethod
    def record_idea(
        self,
        text: str,
        entity_id: str | None,
        outcome: str,
        turn: int,
        game_id: str,
    ) -> MemoryRecord:
        ...

    @abstractmethod
    def record_event(
        self,
        event_type: str,
        description: str,
        impacts: list[dict],
        turn: int,
        game_id: str,
    ) -> MemoryRecord:
        ...

    @abstractmethod
    def search_similar(self, query: str, game_id: str, limit: int = 5) -> list[MemoryRecord]:
        ...
