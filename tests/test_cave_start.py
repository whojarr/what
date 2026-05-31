from pathlib import Path

from civsim.registry.capability_registry import CapabilityRegistry
from civsim.registry.material_registry import MaterialRegistry
from civsim.world.generator import WorldGenerator

ROOT = Path(__file__).resolve().parent.parent


def test_cave_start_state():
    state = WorldGenerator().generate(seed=42)
    assert state.era == "paleolithic"
    assert len(state.regions) == 1
    region = state.regions[0]
    assert region.id == "cave_chamber"
    assert state.resources.food < 0.2
    assert state.resources.warmth < 0.25
    assert state.invention_count == 0
    assert state.path_divergence == 0.0

    natural = [e for e in state.entities if "natural" in e.tags]
    assert len(natural) == 2
    ids = {e.id for e in natural}
    assert "natural_fire" in ids
    assert "natural_spring" in ids

    assert "wood" in region.absent_materials
    assert "clay" in region.absent_materials
    assert any(d.material_id == "iron_oxide" for d in region.deposits)
    pre_discovered = {d.material_id for d in region.deposits if d.discovered}
    assert "flint" in pre_discovered
    assert "limestone" in pre_discovered
    assert "iron_oxide" not in pre_discovered


def test_paleolithic_allowed_keys_exclude_modern():
    registry = CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    allowed = set(registry.allowed_keys("paleolithic"))
    assert "warmth_output" in allowed
    assert "tool_craft" in allowed
    assert "compute_output" not in allowed
    assert "cooling" not in allowed


def test_material_registry_loads():
    registry = MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    assert registry.get("wood") is not None
    assert "wood" in registry.required_materials(["charcoal", "fuel"])
    assert registry.is_implicit("bone")
