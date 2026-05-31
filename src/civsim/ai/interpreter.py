from typing import Protocol

from civsim.models.capabilities import IdeaProposal
from civsim.models.world import GameState
from civsim.registry.capability_registry import CapabilityRegistry


class IdeaInterpreter(Protocol):
    def interpret(
        self,
        player_text: str,
        world: GameState,
        registry: CapabilityRegistry,
        memory_context: list[str] | None = None,
    ) -> IdeaProposal:
        ...
