from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SAVES_PATH", str(tmp_path / "saves"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import api.main as api_module

    api_module.SAVES_PATH = tmp_path / "saves"
    api_module.registry = __import__(
        "civsim.registry.capability_registry", fromlist=["CapabilityRegistry"]
    ).CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    api_module.material_registry = __import__(
        "civsim.registry.material_registry", fromlist=["MaterialRegistry"]
    ).MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    api_module.game_service = __import__(
        "civsim.services.game_service", fromlist=["GameService"]
    ).GameService(
        api_module.registry,
        tmp_path / "saves",
        material_registry=api_module.material_registry,
        method_registry=__import__(
            "civsim.registry.method_registry", fromlist=["MethodRegistry"]
        ).MethodRegistry.load_for_era("paleolithic", ROOT / "data"),
        data_dir=ROOT / "data",
    )
    return TestClient(api_module.app)


def test_create_and_get_game(client):
    r = client.post("/games", json={"seed": 7})
    assert r.status_code == 200
    game = r.json()
    assert game["era"] == "paleolithic"
    assert len(game["regions"]) == 1
    game_id = game["id"]
    r2 = client.get(f"/games/{game_id}")
    assert r2.status_code == 200
    assert r2.json()["turn"] == 0
    assert "warmth" in r2.json()["resources"]


def test_place_entity_and_tick(client):
    r = client.post("/games", json={"seed": 7})
    game_id = r.json()["id"]
    region_id = r.json()["regions"][0]["id"]
    place = client.post(
        f"/games/{game_id}/entities",
        json={
            "type": "tool.bone",
            "tags": ["stone"],
            "capabilities": {"tool_craft": 0.6, "hunting": 0.2},
            "region_id": region_id,
            "name": "Bone Tools",
        },
    )
    assert place.status_code == 200
    tick = client.post(f"/games/{game_id}/tick")
    assert tick.status_code == 200
    assert tick.json()["turn"] == 1


def test_lab_combine_api(client):
    r = client.post("/games", json={"seed": 7})
    game_id = r.json()["id"]
    region_id = r.json()["regions"][0]["id"]
    opts = client.get(f"/games/{game_id}/lab/options", params={"region_id": region_id})
    assert opts.status_code == 200
    combine = client.post(
        f"/games/{game_id}/lab/combine",
        json={
            "region_id": region_id,
            "material_ids": ["flint", "bone"],
            "component_ids": ["natural_fire"],
            "object_ids": [],
            "intent": "",
        },
    )
    assert combine.status_code == 200
    body = combine.json()
    assert body["recipe_match"] is True
    assert "proposal" in body


def test_survey_region(client):
    r = client.post("/games", json={"seed": 7})
    game_id = r.json()["id"]
    region_id = r.json()["regions"][0]["id"]
    survey = client.post(f"/games/{game_id}/regions/{region_id}/survey")
    assert survey.status_code == 200
    body = survey.json()
    assert body["turn"] == 1
    assert "feedback" in body
    assert "iron_oxide" in {
        d["material_id"] for d in body["discoveries"]
    } or any("iron" in f.lower() for f in body["feedback"])


def test_interpret_requires_api_key(client):
    r = client.post("/games", json={"seed": 1})
    game_id = r.json()["id"]
    r2 = client.post("/ideas/interpret", json={"game_id": game_id, "text": "bone needles"})
    assert r2.status_code == 503


def test_world_section_apis(client):
    r = client.post("/games", json={"seed": 7})
    game_id = r.json()["id"]
    region_id = r.json()["regions"][0]["id"]

    overview = client.get(f"/games/{game_id}/world/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["turn"] == 0
    assert body["region"]["id"] == region_id
    assert "warmth" in body["resources"]

    absent = client.get(f"/games/{game_id}/world/materials/absent")
    assert absent.status_code == 200
    assert "wood" in {i["id"] for i in absent.json()["items"]}

    available = client.get(f"/games/{game_id}/world/materials/available")
    assert available.status_code == 200
    avail = available.json()
    assert len(avail["items"]) >= 3
    assert any(i["id"] == "bone" for i in avail["items"])

    stocks = client.get(f"/games/{game_id}/world/materials/stocks")
    assert stocks.status_code == 200
    assert "stocks" in stocks.json()

    components = client.get(f"/games/{game_id}/world/components")
    assert components.status_code == 200
    comp_ids = {i["id"] for i in components.json()["items"]}
    assert "natural_fire" in comp_ids
    assert all("display" in i for i in components.json()["items"])

    objects = client.get(f"/games/{game_id}/world/objects")
    assert objects.status_code == 200
    assert "items" in objects.json()
