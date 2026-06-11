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
    api_module.IMAGES_PATH = tmp_path / "images"
    api_module.visual_service = __import__(
        "civsim.services.visual_service", fromlist=["VisualService"]
    ).VisualService(api_module.IMAGES_PATH, api_module.game_service)
    return TestClient(api_module.app)


def test_visual_endpoint_serves_cached_image(client, tmp_path, monkeypatch):
    import api.main as api_module

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    r = client.post("/games", json={"seed": 2})
    game_id = r.json()["id"]
    state = api_module.game_service.load_game(game_id)
    fire = next(e for e in state.entities if e.id == "natural_fire")
    png_path = tmp_path / "images" / "cached.png"
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    png_path.write_bytes(png_bytes)

    def fake_get_or_create(gid, subject_type, subject_id, **kwargs):
        subject = api_module.game_service.resolve_visual_subject(gid, subject_type, subject_id)
        assert subject is not None
        return png_path

    api_module.visual_service.get_or_create_image = fake_get_or_create
    resp = client.get(f"/games/{game_id}/visuals/component/{fire.id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == png_bytes


def test_list_games_includes_saves(client):
    r1 = client.post("/games", json={"seed": 3})
    r2 = client.post("/games", json={"seed": 5})
    assert r1.status_code == 200
    assert r2.status_code == 200
    listed = client.get("/games")
    assert listed.status_code == 200
    games = listed.json()["games"]
    assert len(games) == 2
    ids = {g["id"] for g in games}
    assert r1.json()["id"] in ids
    assert r2.json()["id"] in ids
    for g in games:
        assert "turn" in g
        assert "rng_seed" in g
        assert "saved_at" in g


def test_create_game_accepts_world_name(client):
    r = client.post("/games", json={"seed": 12, "name": "  Misty Hollow  "})
    assert r.status_code == 200
    game = r.json()
    assert game["name"] == "Misty Hollow"
    listed = client.get("/games")
    row = next(g for g in listed.json()["games"] if g["id"] == game["id"])
    assert row["name"] == "Misty Hollow"


def test_rename_game_updates_world_name(client):
    created = client.post("/games", json={"seed": 9, "name": "Old Name"})
    assert created.status_code == 200
    game_id = created.json()["id"]
    renamed = client.post(f"/games/{game_id}/name", json={"name": "  New Hollow  "})
    assert renamed.status_code == 200
    assert renamed.json() == {"id": game_id, "name": "New Hollow"}
    loaded = client.get(f"/games/{game_id}")
    assert loaded.json()["name"] == "New Hollow"
    listed = client.get("/games")
    row = next(g for g in listed.json()["games"] if g["id"] == game_id)
    assert row["name"] == "New Hollow"


def test_delete_game_removes_save(client):
    created = client.post("/games", json={"seed": 4})
    assert created.status_code == 200
    game_id = created.json()["id"]
    deleted = client.delete(f"/games/{game_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    listed = client.get("/games")
    ids = {g["id"] for g in listed.json()["games"]}
    assert game_id not in ids
    assert client.get(f"/games/{game_id}").status_code == 404
    assert client.delete(f"/games/{game_id}").status_code == 404


def test_create_and_get_game(client):
    r = client.post("/games", json={"seed": 7})
    assert r.status_code == 200
    game = r.json()
    assert game["era"] == "paleolithic"
    assert len(game["regions"]) == 2
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
    assert "exits" in body
    assert any(e["id"] == "passage_out" for e in body["exits"])

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


def test_world_scene_api(client):
    r = client.post("/games", json={"seed": 7})
    game_id = r.json()["id"]
    region_id = r.json()["regions"][0]["id"]

    scene = client.get(f"/games/{game_id}/world/scene")
    assert scene.status_code == 200
    body = scene.json()
    assert body["region"]["id"] == region_id
    assert body["template_id"] == "cave_enclosure"
    assert body["template_version"] >= 25
    assert body.get("scene_mode") == "single_scene"
    assert body["surfaces"] == []
    assert set(body.get("panorama_crops", {})) == {"back", "left", "right", "floor"}
    slot_ids = {e["id"] for e in body["slot_entities"]}
    assert "natural_fire" in slot_ids
    assert "natural_spring" in slot_ids


def test_world_scene_image(client, tmp_path, monkeypatch):
    import api.main as api_module

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    r = client.post("/games", json={"seed": 7})
    game_id = r.json()["id"]
    region_id = r.json()["regions"][0]["id"]

    master = tmp_path / "master.png"
    master.write_bytes(_mini_png_with_regions())
    api_module.visual_service.get_or_create_panorama_master = lambda *args, **kwargs: master

    resp = client.get(f"/games/{game_id}/world/scene/image?region_id={region_id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 50


def test_world_scene_panorama_surface(client, tmp_path, monkeypatch):
    import api.main as api_module

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    r = client.post("/games", json={"seed": 7})
    game_id = r.json()["id"]
    region_id = r.json()["regions"][0]["id"]

    master = tmp_path / "master.png"
    master.write_bytes(_mini_png_with_regions())

    def fake_master(gid, template_id, rid):
        return master

    def fake_crop(gid, template_id, rid, surface_id):
        from civsim.services.scene_panorama import crop_normalized, load_png, png_bytes

        crops = api_module.scene_registry.panorama_crops(template_id)
        img = load_png(master.read_bytes())
        cropped = crop_normalized(img, crops[surface_id])
        out = tmp_path / f"{surface_id}.png"
        out.write_bytes(png_bytes(cropped))
        return out

    api_module.visual_service.get_or_create_panorama_master = fake_master
    api_module.visual_service.get_scene_panorama_surface = fake_crop

    resp = client.get(
        f"/games/{game_id}/world/scene/panorama/left?region_id={region_id}"
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 50


def _mini_png_with_regions():
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (900, 600), (100, 90, 70))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_survey_discovers_passage(client):
    r = client.post("/games", json={"seed": 11})
    game_id = r.json()["id"]
    region_id = r.json()["regions"][0]["id"]
    survey = client.post(f"/games/{game_id}/regions/{region_id}/survey")
    assert survey.status_code == 200
    assert any("daylight passage" in f.lower() for f in survey.json()["feedback"])

    overview = client.get(f"/games/{game_id}/world/overview")
    passage = next(e for e in overview.json()["exits"] if e["id"] == "passage_out")
    assert passage["discovered"] is True
    assert passage["status"] == "found"


def test_travel_to_outside(client):
    r = client.post("/games", json={"seed": 11})
    game_id = r.json()["id"]
    cave_id = r.json()["regions"][0]["id"]
    outside_id = r.json()["regions"][1]["id"]

    blocked = client.post(
        f"/games/{game_id}/travel",
        json={"target_region_id": outside_id, "from_region_id": cave_id},
    )
    assert blocked.status_code == 400

    client.post(f"/games/{game_id}/regions/{cave_id}/survey")
    travel = client.post(
        f"/games/{game_id}/travel",
        json={"target_region_id": outside_id, "from_region_id": cave_id},
    )
    assert travel.status_code == 200
    assert travel.json()["region_id"] == outside_id

    outside_avail = client.get(
        f"/games/{game_id}/world/materials/available",
        params={"region_id": outside_id},
    )
    avail_ids = {i["id"] for i in outside_avail.json()["items"]}
    assert "wood" in avail_ids
    assert "clay" in avail_ids


def test_travel_carries_portable_items(client):
    import api.main as api_module
    from civsim.models.entity import Entity

    r = client.post("/games", json={"seed": 11})
    game_id = r.json()["id"]
    cave_id = r.json()["regions"][0]["id"]
    outside_id = r.json()["regions"][1]["id"]

    state = api_module.game_service.load_game(game_id)
    state.entities.append(
        Entity(
            id="portable_hide",
            name="Softened hide",
            type="object.soft_hide",
            tags=["object", "hide"],
            capabilities={"shelter": 0.3},
            region_id=cave_id,
        )
    )
    api_module.game_service._save(state)

    client.post(f"/games/{game_id}/regions/{cave_id}/survey")
    travel = client.post(
        f"/games/{game_id}/travel",
        json={"target_region_id": outside_id, "from_region_id": cave_id},
    )
    assert travel.status_code == 200
    body = travel.json()
    assert "Softened hide" in body["carried"]
    assert any("Softened hide" in f for f in body["feedback"])

    outside_objects = client.get(
        f"/games/{game_id}/world/objects",
        params={"region_id": outside_id},
    )
    names = {i["name"] for i in outside_objects.json()["items"]}
    assert "Softened hide" in names

    cave_components = client.get(
        f"/games/{game_id}/world/components",
        params={"region_id": cave_id},
    )
    comp_ids = {i["id"] for i in cave_components.json()["items"]}
    assert "natural_fire" in comp_ids
    assert "natural_spring" in comp_ids


def test_travel_leaves_excess_without_pack(client):
    import api.main as api_module
    from civsim.models.entity import Entity

    r = client.post("/games", json={"seed": 11})
    game_id = r.json()["id"]
    cave_id = r.json()["regions"][0]["id"]
    outside_id = r.json()["regions"][1]["id"]

    state = api_module.game_service.load_game(game_id)
    state.entities.extend(
        [
            Entity(
                id="tool_a",
                name="Knapped flint",
                type="tool.flint_knapped",
                tags=["component", "flint"],
                capabilities={"tool_craft": 0.65},
                region_id=cave_id,
            ),
            Entity(
                id="tool_b",
                name="Bone needle",
                type="tool.bone_needle",
                tags=["component", "bone"],
                capabilities={"tool_craft": 0.55},
                region_id=cave_id,
            ),
        ]
    )
    api_module.game_service._save(state)

    client.post(f"/games/{game_id}/regions/{cave_id}/survey")
    travel = client.post(
        f"/games/{game_id}/travel",
        json={"target_region_id": outside_id, "from_region_id": cave_id},
    )
    assert travel.status_code == 200
    body = travel.json()
    assert len(body["carried"]) == 1
    assert len(body["left_behind"]) == 1

    outside_components = client.get(
        f"/games/{game_id}/world/components",
        params={"region_id": outside_id},
    )
    names = {i["name"] for i in outside_components.json()["items"]}
    assert len(names & {"Knapped flint", "Bone needle"}) == 1


def test_travel_carried_materials_show_in_lab(client):
    import api.main as api_module
    from civsim.models.entity import Entity

    r = client.post("/games", json={"seed": 11})
    game_id = r.json()["id"]
    cave_id = r.json()["regions"][0]["id"]
    outside_id = r.json()["regions"][1]["id"]

    state = api_module.game_service.load_game(game_id)
    state.region_material_stocks[cave_id] = {"flint": 0.5}
    state.entities.append(
        Entity(
            id="carry_pack",
            name="Hide carry pack",
            type="object.carry_pack",
            tags=["object", "hide"],
            capabilities={"storage": 0.35},
            region_id=cave_id,
        )
    )
    api_module.game_service._save(state)

    client.post(f"/games/{game_id}/regions/{cave_id}/survey")
    client.post(
        f"/games/{game_id}/travel",
        json={"target_region_id": outside_id, "from_region_id": cave_id},
    )

    lab = client.get(
        f"/games/{game_id}/lab/options",
        params={"region_id": outside_id},
    )
    mat_ids = {m["id"] for m in lab.json()["materials"]}
    assert "flint" in mat_ids
    assert "wood" in mat_ids
    assert "clay" in mat_ids
    assert "bone" not in mat_ids
    assert "hide" not in mat_ids
    flint = next(m for m in lab.json()["materials"] if m["id"] == "flint")
    assert flint["source"] == "hauled"


def test_travel_materials_stay_without_pack(client):
    import api.main as api_module

    r = client.post("/games", json={"seed": 11})
    game_id = r.json()["id"]
    cave_id = r.json()["regions"][0]["id"]
    outside_id = r.json()["regions"][1]["id"]

    state = api_module.game_service.load_game(game_id)
    state.region_material_stocks[cave_id] = {"flint": 0.5}
    api_module.game_service._save(state)

    client.post(f"/games/{game_id}/regions/{cave_id}/survey")
    travel = client.post(
        f"/games/{game_id}/travel",
        json={"target_region_id": outside_id, "from_region_id": cave_id},
    )
    assert travel.status_code == 200
    assert "flint" not in (travel.json().get("materials_hauled") or [])
    assert any("stay behind" in f.lower() for f in travel.json()["feedback"])

    lab = client.get(
        f"/games/{game_id}/lab/options",
        params={"region_id": outside_id},
    )
    mat_ids = {m["id"] for m in lab.json()["materials"]}
    assert "flint" not in mat_ids


def test_lab_materials_match_cave_region(client):
    r = client.post("/games", json={"seed": 11})
    game_id = r.json()["id"]
    cave_id = r.json()["regions"][0]["id"]

    lab = client.get(
        f"/games/{game_id}/lab/options",
        params={"region_id": cave_id},
    )
    mat_ids = {m["id"] for m in lab.json()["materials"]}
    assert "bone" in mat_ids
    assert "hide" in mat_ids
    assert "flint" in mat_ids
    assert "wood" not in mat_ids


def test_get_entity_api(client):
    r = client.post("/games", json={"seed": 3})
    game_id = r.json()["id"]
    fire_id = "natural_fire"
    detail = client.get(f"/games/{game_id}/entities/{fire_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == fire_id
    assert body["kind"] == "component"
    assert body["display"]["label"] == "Fire"
    assert body["classification"]
    assert "active_capabilities" in body


def test_compound_provenance_in_stocks(client):
    import api.main as api_module

    r = client.post("/games", json={"seed": 9})
    game_id = r.json()["id"]
    state = api_module.game_service.load_game(game_id)
    api_module.game_service._register_novel_compound(
        state,
        "Cement Shovel",
        ["compound", "chemical"],
        "material.cement_shovel",
        region_id=state.regions[0].id,
        provenance=api_module.game_service._build_compound_provenance(
            state,
            source="lab",
            material_ids=["clay", "flint"],
            component_ids=["natural_fire"],
            intent="bind cement",
        ),
    )
    api_module.game_service._save(state)

    stocks = client.get(f"/games/{game_id}/world/materials/stocks")
    assert stocks.status_code == 200
    compound = next(c for c in stocks.json()["compounds"] if c["id"] == "cement_shovel")
    assert "Clay" in compound["made_from"]
    assert "Flint" in compound["made_from"]
    assert "Fire" in compound["made_from"]
    assert compound["provenance"]["intent"] == "bind cement"


def test_place_entity_skips_duplicate_name(client):
    r = client.post("/games", json={"seed": 7})
    game_id = r.json()["id"]
    region_id = r.json()["regions"][0]["id"]
    payload = {
        "type": "object.pouch",
        "tags": ["object", "hide"],
        "capabilities": {},
        "region_id": region_id,
        "name": "Rudimentary Pouch",
    }
    first = client.post(f"/games/{game_id}/entities", json=payload)
    second = client.post(f"/games/{game_id}/entities", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["entity"]["id"] == second.json()["entity"]["id"]

    listed = client.get(f"/games/{game_id}/world/objects")
    names = [i["name"] for i in listed.json()["items"]]
    assert names.count("Rudimentary Pouch") == 1


def test_world_objects_collapse_same_name(client, tmp_path, monkeypatch):
    monkeypatch.setenv("SAVES_PATH", str(tmp_path / "saves"))
    import api.main as api_module

    api_module.SAVES_PATH = tmp_path / "saves"
    service = api_module.game_service
    state = service.create_game(7)
    service.auto_approve_pending()
    from civsim.models.entity import Entity
    from civsim.models.entity_kinds import classify_entity_tags

    tags = classify_entity_tags(["object", "hide"], "object.pouch", {})
    state.entities.extend([
        Entity(
            id="infra_a",
            name="Rudimentary Pouch",
            type="object.pouch",
            tags=tags,
            capabilities={},
            region_id=state.regions[0].id,
        ),
        Entity(
            id="infra_b",
            name="Rudimentary Pouch",
            type="object.other",
            tags=tags,
            capabilities={},
            region_id=state.regions[0].id,
        ),
    ])
    service._save(state)
    items = service.get_world_objects(state.id)["items"]
    pouch = next(i for i in items if i["name"] == "Rudimentary Pouch")
    assert pouch["count"] == 2


def test_lab_options_collapse_duplicate_names(client, tmp_path, monkeypatch):
    monkeypatch.setenv("SAVES_PATH", str(tmp_path / "saves"))
    import api.main as api_module

    api_module.SAVES_PATH = tmp_path / "saves"
    service = api_module.game_service
    state = service.create_game(7)
    service.auto_approve_pending()
    from civsim.models.entity import Entity
    from civsim.models.entity_kinds import classify_entity_tags

    tags = classify_entity_tags(["object", "hide"], "object.pouch", {})
    state.entities.extend([
        Entity(
            id="infra_a",
            name="Rudimentary Pouch",
            type="object.pouch",
            tags=tags,
            capabilities={},
            region_id=state.regions[0].id,
        ),
        Entity(
            id="infra_b",
            name="Rudimentary Pouch",
            type="object.other",
            tags=tags,
            capabilities={},
            region_id=state.regions[0].id,
        ),
    ])
    service._save(state)
    opts = service.get_lab_options(state.id)
    pouch = next(o for o in opts["objects"] if o["name"] == "Rudimentary Pouch")
    assert pouch["count"] == 2
    assert len(opts["objects"]) == len({o["name"].lower() for o in opts["objects"]})
