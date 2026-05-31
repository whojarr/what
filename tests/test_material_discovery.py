from pathlib import Path

from civsim.engines.material_engine import MaterialEngine
from civsim.models.entity import EntityDraft
from civsim.registry.material_registry import MaterialRegistry
from civsim.services.game_service import GameService
from civsim.registry.capability_registry import CapabilityRegistry
from civsim.world.generator import WorldGenerator

ROOT = Path(__file__).resolve().parent.parent


def _service(tmp_path) -> GameService:
    cap_reg = CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    mat_reg = MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    return GameService(
        cap_reg, tmp_path / "saves", material_registry=mat_reg, data_dir=ROOT / "data"
    )


def test_survey_reveals_surface_deposits(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    iron = next(d for d in region.deposits if d.material_id == "iron_oxide")
    assert not iron.discovered

    result = service.survey_region(state.id, region.id)
    assert result is not None
    reloaded = service.load_game(state.id)
    iron_after = next(
        d for d in reloaded.regions[0].deposits if d.material_id == "iron_oxide"
    )
    assert iron_after.discovered
    assert any("iron" in f.lower() or "red streaks" in f.lower() for f in result["feedback"])
    assert any("wood" in f.lower() or "not found" in f.lower() for f in result["feedback"])
    assert result["turn"] == 1


def test_mining_invention_reveals_deep_deposit(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    deep_before = [d for d in region.deposits if d.depth == "deep" and not d.discovered]
    if not deep_before:
        return

    draft = EntityDraft(
        type="tool.mining",
        tags=["mining", "excavation", "stone", "cave"],
        capabilities={"tool_craft": 0.6, "shelter": 0.2, "maintenance_complexity": 0.3},
        region_id=region.id,
        name="Wall digger",
    )
    entity, constraint, err = service.place_entity(state.id, draft)
    assert entity is not None
    assert err is None
    reloaded = service.load_game(state.id)
    deep_after = [d for d in reloaded.regions[0].deposits if d.depth == "deep" and d.discovered]
    assert len(deep_after) >= 1


def test_material_engine_survey_idempotent(tmp_path):
    mat_reg = MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    engine = MaterialEngine(mat_reg)
    state = WorldGenerator().generate(42)
    region = state.regions[0]
    first = engine.survey_region(state, region)
    assert len(first.discoveries) >= 1
    second = engine.survey_region(state, region)
    assert len(second.discoveries) == 0
