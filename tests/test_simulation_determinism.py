import hashlib
import json
from pathlib import Path

from civsim.engines.event_system import EventSystem
from civsim.engines.simulation import SimulationEngine
from civsim.models.entity import Entity
from civsim.registry.capability_registry import CapabilityRegistry
from civsim.world.generator import WorldGenerator

ROOT = Path(__file__).resolve().parent.parent


def _world_hash(state) -> str:
    data = {
        "turn": state.turn,
        "resources": state.resources.model_dump(),
        "climate": state.climate.model_dump(),
        "path_divergence": state.path_divergence,
        "entities": [
            {
                "id": e.id,
                "health": e.health,
                "operational": e.operational,
                "capabilities": e.capabilities,
            }
            for e in state.entities
        ],
        "event_count": len(state.event_log),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def test_deterministic_replay():
    registry = CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    event_system = EventSystem(registry)
    sim = SimulationEngine(registry, event_system)

    def run():
        state = WorldGenerator().generate(seed=99)
        cave_id = state.regions[0].id
        state.entities.append(
            Entity(
                id="e1",
                name="Bone Tools",
                type="tool.bone",
                tags=["stone"],
                capabilities={
                    "tool_craft": 0.5,
                    "hunting": 0.3,
                    "food_demand": 0.1,
                    "warmth_demand": 0.05,
                },
                region_id=cave_id,
            )
        )
        for _ in range(10):
            sim.tick(state)
        return _world_hash(state)

    assert run() == run()
