import json
from pathlib import Path

from civsim.models.world import GameState

ROOT = Path(__file__).resolve().parent.parent


def test_legacy_save_loads_without_geology_fields():
    legacy = {
        "id": "legacy-test",
        "turn": 3,
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
    assert state.material_stocks == {}
    assert state.novel_compounds == {}
    assert state.known_methods == []
    assert state.surveyed_region_ids == []
    assert state.regions[0].absent_materials == []
    assert state.regions[0].deposits == []


def test_existing_save_file_still_loads():
    saves = ROOT / "data" / "saves"
    if not saves.exists():
        return
    files = list(saves.glob("*.json"))
    if not files:
        return
    with files[0].open() as f:
        data = json.load(f)
    state = GameState.model_validate(data)
    assert state.id
