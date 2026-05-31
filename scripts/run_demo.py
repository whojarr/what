#!/usr/bin/env python3
"""Scripted 5-turn cave gameplay demo without browser or LLM."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from civsim.models.capabilities import IdeaProposal
from civsim.models.entity import EntityDraft
from civsim.registry.capability_registry import CapabilityRegistry
from civsim.registry.material_registry import MaterialRegistry
from civsim.services.game_service import GameService


def main() -> None:
    data_dir = PROJECT_ROOT / "data"
    saves_path = PROJECT_ROOT / "data" / "saves"
    registry = CapabilityRegistry.load_for_era("paleolithic", data_dir)
    material_registry = MaterialRegistry.load_for_era("paleolithic", data_dir)
    service = GameService(registry, saves_path, material_registry=material_registry, data_dir=data_dir)

    print("=== WHAT — Paleolithic Demo ===\n")

    state = service.create_game(seed=42)
    print(f"Created game {state.id}")
    print(f"Era: {state.era}")
    print(f"Cave: {state.regions[0].name}")
    print(f"Fixtures: {[e.name for e in state.entities if 'natural' in e.tags]}")
    print("Initial resources:", state.resources.model_dump())
    print()

    cave_id = state.regions[0].id
    proposal = IdeaProposal(
        type="tool.bone_tools",
        tags=["stone", "bone"],
        capabilities={
            "tool_craft": 0.55,
            "hunting": 0.35,
            "food_output": 0.2,
            "material_demand": 0.15,
        },
        player_name="Bone Tools",
        reasoning="Sharp bone flakes and stones for cutting and scraping.",
    )

    print('Inventing: "bone tools"')
    result = service.interpret_idea_direct(state.id, proposal, cave_id)
    print("Constraint:", result["constraint"]["status"])
    for w in result["constraint"].get("warnings", []):
        print(f"  Warning: {w}")
    print()

    draft = EntityDraft(
        type=result["normalized"]["type"],
        tags=result["normalized"]["tags"],
        capabilities=result["normalized"]["capabilities"],
        region_id=cave_id,
        name=proposal.player_name,
    )
    entity, constraint, err = service.place_entity(state.id, draft)
    if err:
        print(f"Placement failed: {err}")
        sys.exit(1)
    print(f"Crafted: {entity.name} in {state.regions[0].name}")
    print(f"Path divergence: {service.load_game(state.id).path_divergence:.2f}\n")

    print("=== Simulating 5 turns ===\n")
    for _ in range(5):
        tick = service.tick(state.id)
        print(f"--- Turn {tick.turn} ---")
        print(f"  Resources: {json.dumps(tick.resources.model_dump())}")
        if tick.events:
            for e in tick.events:
                print(f"  Event: {e.type.value} severity={e.severity:.2f}")
        if tick.impacts:
            for imp in tick.impacts:
                name = imp.entity_name or imp.entity_id
                print(f"  Impact: {name} damage={imp.damage:.2f} health={imp.health_after:.2f}")
        for fb in tick.feedback:
            print(f"  >> {fb}")
        print()

    final = service.load_game(state.id)
    if final:
        print(f"Inventions: {final.invention_count}, divergence: {final.path_divergence:.2f}")
    print("Demo complete.")


if __name__ == "__main__":
    main()
