from pathlib import Path

from civsim.registry.method_registry import MethodRegistry
from civsim.services.game_service import GameService
from civsim.registry.capability_registry import CapabilityRegistry
from civsim.registry.material_registry import MaterialRegistry
from civsim.engines.method_engine import MethodEngine
from civsim.models.entity import EntityDraft
from civsim.models.world import GameState

ROOT = Path(__file__).resolve().parent.parent


def _service(tmp_path) -> GameService:
    cap_reg = CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    mat_reg = MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    method_reg = MethodRegistry.load_for_era("paleolithic", ROOT / "data")
    return GameService(
        cap_reg,
        tmp_path / "saves",
        material_registry=mat_reg,
        method_registry=method_reg,
        data_dir=ROOT / "data",
    )


def test_new_game_starts_with_heating_and_soaking(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    assert "heating" in state.known_methods
    assert "sewing" not in state.known_methods


def test_bone_needle_unlocks_sewing(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    result = service.combine_in_lab(state.id, region.id, ["hide", "bone"])
    assert result is not None
    assert result["recipe_match"] is True
    assert any("sewing" in f.lower() for f in result["feedback"])
    state = service.load_game(state.id)
    assert "sewing" in state.known_methods


def test_raincoat_blocked_without_sewing(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    from civsim.models.entity import Entity

    softened = Entity(
        id="soft_hide_1",
        name="Softened hide",
        type="object.soft_hide",
        tags=["object", "hide", "water"],
        capabilities={"shelter": 0.4},
        region_id=region.id,
    )
    needle = Entity(
        id="bone_needle_1",
        name="Bone needle and sinew",
        type="tool.bone_needle",
        tags=["bone", "hide", "component"],
        capabilities={"tool_craft": 0.55},
        region_id=region.id,
    )
    state.entities.extend([softened, needle])
    service._save(state)

    result = service.combine_in_lab(
        state.id,
        region.id,
        ["hide"],
        component_ids=["bone_needle_1"],
        object_ids=["soft_hide_1"],
    )
    assert result is not None
    assert "error" in result
    assert "sewing" in result["error"].lower()


def test_invent_method_learns_sewing(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    draft = EntityDraft(
        type="method.sewing",
        tags=["method", "sewing"],
        capabilities={"innovation_rate": 0.3},
        region_id=region.id,
        name="Sewing",
    )
    entity, constraint, error, learned = service.place_entity(state.id, draft)
    assert entity is None
    assert error is None
    assert learned == "Sewing"
    state = service.load_game(state.id)
    assert "sewing" in state.known_methods


def test_unknown_lab_combo_rejected(tmp_path, monkeypatch):
    service = _service(tmp_path)
    monkeypatch.setattr(service, "_interpret_lab_with_ai", lambda *a, **k: None)
    state = service.create_game(seed=42)
    region = state.regions[0]
    result = service.combine_in_lab(
        state.id, region.id, ["flint", "hide"], intent="make a spaceship"
    )
    assert result is not None
    assert "error" in result
    assert "process" in result["error"].lower() or "method" in result["error"].lower()


def test_ai_lab_combination_when_no_recipe(tmp_path, monkeypatch):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    service.combine_in_lab(state.id, region.id, ["hide", "bone"])
    state = service.load_game(state.id)
    assert "sewing" in state.known_methods

    def fake_ai(*args, **kwargs):
        return {
            "proposal": {
                "type": "object.hide_wrap",
                "tags": ["object", "hide", "garment"],
                "capabilities": {"shelter": 0.35},
                "player_name": "Stitched hide wrap",
                "reasoning": "Crude stitches hold the hide together.",
            },
            "normalized": {
                "type": "object.hide_wrap",
                "tags": ["object", "hide", "garment"],
                "capabilities": {"shelter": 0.35},
                "queued_capability_keys": [],
                "dropped_capability_keys": [],
            },
            "constraint": {"status": "VALID", "warnings": [], "hidden_issues": [], "suggested_adjustments": []},
            "feedback": ["Sinew pulls hide into a rough wrap.", "An uncertain experiment — results may surprise you."],
            "material_costs": {},
            "recipe_match": False,
            "ai_suggested": True,
            "result_kind": "object",
        }

    monkeypatch.setattr(service, "_interpret_lab_with_ai", fake_ai)
    result = service.combine_in_lab(
        state.id,
        region.id,
        ["hide"],
        method_ids=["sewing"],
    )
    assert result is not None
    assert result.get("error") is None
    assert result["ai_suggested"] is True
    assert result["recipe_match"] is False
    assert "stitched" in result["proposal"]["player_name"].lower()


def test_method_fusion_heating_soaking_learns_sewing(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    assert "sewing" not in state.known_methods

    result = service.combine_in_lab(
        state.id,
        region.id,
        [],
        component_ids=[],
        object_ids=[],
        method_ids=["heating", "soaking"],
    )
    assert result is not None
    assert result.get("error") is None
    assert result["result_kind"] == "method"
    assert result["method_learned"] == "sewing"
    state = service.load_game(state.id)
    assert "sewing" in state.known_methods


def test_method_fusion_requires_exactly_two(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    service.combine_in_lab(
        state.id, region.id, [], method_ids=["heating", "soaking"]
    )
    result = service.combine_in_lab(
        state.id,
        region.id,
        [],
        method_ids=["heating", "soaking", "sewing"],
    )
    assert result is not None
    assert "error" in result
    assert "exactly two" in result["error"].lower()


def test_method_fusion_rejects_unknown_pair(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    service.combine_in_lab(state.id, region.id, ["hide", "bone"])
    state = service.load_game(state.id)
    assert "sewing" in state.known_methods

    result = service.combine_in_lab(
        state.id,
        region.id,
        [],
        method_ids=["heating", "sewing"],
    )
    assert result is not None
    assert "error" in result
    assert "don't combine" in result["error"].lower()


def test_method_fusion_already_known(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    service.combine_in_lab(
        state.id, region.id, [], method_ids=["heating", "soaking"]
    )
    state = service.load_game(state.id)
    assert "sewing" in state.known_methods

    again = service.combine_in_lab(
        state.id, region.id, [], method_ids=["heating", "soaking"]
    )
    assert again is not None
    assert "error" in again
    assert "already know" in again["error"].lower()


def test_legacy_save_gets_starter_methods():
    legacy = {
        "id": "legacy-methods",
        "turn": 0,
        "rng_seed": 1,
        "era": "paleolithic",
        "path_divergence": 0.0,
        "invention_count": 0,
        "resources": {
            "warmth": 0.1,
            "water": 0.4,
            "food": 0.1,
            "materials": 0.1,
            "knowledge": 0.05,
        },
        "climate": {
            "temperature_index": 0.35,
            "water_stress": 0.2,
            "atmospheric_instability": 0.1,
            "ecosystem_health": 0.75,
        },
        "regions": [
            {
                "id": "cave_chamber",
                "name": "The Cave",
                "biome_tags": ["cave"],
                "energy_ceiling": 0.5,
                "water_availability": 0.55,
            }
        ],
        "entities": [],
        "event_log": [],
        "entity_names": {},
    }
    state = GameState.model_validate(legacy)
    assert state.known_methods == []
    engine = MethodEngine(MethodRegistry.load_for_era("paleolithic", ROOT / "data"))
    engine.sync_from_world(state)
    assert "heating" in state.known_methods
