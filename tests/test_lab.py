from pathlib import Path

from civsim.engines.lab_engine import LabEngine
from civsim.registry.capability_registry import CapabilityRegistry
from civsim.registry.material_registry import MaterialRegistry
from civsim.registry.method_registry import MethodRegistry
from civsim.services.game_service import GameService
from civsim.world.generator import WorldGenerator

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


def test_lab_recipe_match():
    mat_reg = MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    lab = LabEngine.load_for_era("paleolithic", ROOT / "data", mat_reg)
    state = WorldGenerator().generate(42)
    recipe = lab.match_recipe(["flint", "bone"], ["natural_fire"], [], state)
    assert recipe is not None
    assert recipe.proposal.player_name == "Knapped flint"


def test_lab_combine_known_recipe(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    result = service.combine_in_lab(
        state.id,
        region.id,
        ["flint", "bone"],
        component_ids=["natural_fire"],
    )
    assert result is not None
    assert result["recipe_match"] is True
    assert "flint" in result["proposal"]["player_name"].lower() or "knapped" in result["proposal"]["player_name"].lower()
    assert any("flint" in f.lower() for f in result["feedback"])


def test_lab_rejects_too_few_inputs(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    result = service.combine_in_lab(state.id, region.id, ["flint"], [])
    assert result is not None
    assert "error" in result
    assert "natural combination" in result["error"].lower()


def test_natural_combination_rules():
    assert LabEngine.is_natural_combination(["a", "b"], [], [], [])
    assert LabEngine.is_natural_combination([], ["fire", "water"], [], [])
    assert LabEngine.is_natural_combination([], [], ["o1", "o2"], [])
    assert LabEngine.is_natural_combination([], [], [], ["heating", "soaking"])
    assert LabEngine.is_natural_combination(["ore"], ["fire"], [], [])
    assert not LabEngine.is_natural_combination(["flint"], [], [], [])
    assert not LabEngine.is_natural_combination([], ["fire"], [], [])


def test_roasted_ore_needs_fire_not_flint(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    for deposit in region.deposits:
        if deposit.material_id == "iron_oxide":
            deposit.discovered = True
    service._save(state)

    without_fire = service.combine_in_lab(
        state.id, region.id, ["iron_oxide"], component_ids=[], method_ids=["heating"]
    )
    assert without_fire is not None
    assert "error" in without_fire

    with_fire = service.combine_in_lab(
        state.id,
        region.id,
        ["iron_oxide"],
        component_ids=["natural_fire"],
        method_ids=["heating"],
    )
    assert with_fire is not None
    assert with_fire.get("error") is None
    assert with_fire["recipe_match"] is True
    assert "roasted" in with_fire["proposal"]["player_name"].lower()


def test_lab_options_includes_cave_natural_from_connected_region(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=11)
    cave_id = state.regions[0].id
    outside_id = state.regions[1].id
    service.survey_region(state.id, cave_id)
    service.travel_to_region(state.id, outside_id, cave_id)

    options = service.get_lab_options(state.id, outside_id)
    assert options is not None
    ids = {c["id"] for c in options["components"]}
    assert "natural_fire" in ids
    assert "natural_spring" in ids


def test_lab_options_lists_materials(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    options = service.get_lab_options(state.id)
    assert options is not None
    ids = {m["id"] for m in options["materials"]}
    assert "bone" in ids
    assert "flint" in ids
    assert len(options["components"]) >= 2
    fire = next(c for c in options["components"] if c["id"] == "natural_fire")
    water = next(c for c in options["components"] if c["id"] == "natural_spring")
    assert fire["role"] == "fire"
    assert fire["label"] == "Fire"
    assert water["role"] == "water"
    assert water["label"] == "Water"


def test_lab_object_recipe(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    result = service.combine_in_lab(
        state.id,
        region.id,
        ["limestone", "hide"],
        component_ids=[],
        object_ids=[],
    )
    assert result is not None
    assert result["recipe_match"] is True
    assert result["result_kind"] == "object"
    assert "object" in result["normalized"]["tags"]


def test_classify_shelter_as_object():
    from civsim.models.entity_kinds import classify_entity_tags, is_object
    from civsim.models.entity import Entity

    tags = classify_entity_tags(
        ["stone", "hide", "shelter"],
        "object.shelter",
        {"shelter": 0.6, "tool_craft": 0.1},
    )
    assert "object" in tags
    assert "component" not in tags
    e = Entity(
        id="x",
        name="Shelter",
        type="object.shelter",
        tags=tags,
        capabilities={"shelter": 0.6},
        region_id="cave_chamber",
    )
    assert is_object(e)


def test_lab_raincoat_recipe_match():
    mat_reg = MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    lab = LabEngine.load_for_era("paleolithic", ROOT / "data", mat_reg)
    state = WorldGenerator().generate(42)
    region_id = state.regions[0].id
    from civsim.models.entity import Entity

    softened = Entity(
        id="soft_hide_1",
        name="Softened hide",
        type="object.soft_hide",
        tags=["object", "hide", "water"],
        capabilities={"shelter": 0.4},
        region_id=region_id,
    )
    needle = Entity(
        id="bone_needle_1",
        name="Bone needle and sinew",
        type="tool.bone_needle",
        tags=["bone", "hide", "component"],
        capabilities={"tool_craft": 0.55, "shelter": 0.25},
        region_id=region_id,
    )
    state.entities.extend([softened, needle])
    recipe = lab.match_recipe(
        ["hide"], ["bone_needle_1"], ["soft_hide_1"], state
    )
    assert recipe is not None
    assert recipe.proposal.player_name == "Hide raincoat"
    assert recipe.kind == "object"


def test_lab_raincoat_requires_needle_and_sinew(tmp_path):
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

    only_hide = service.combine_in_lab(
        state.id, region.id, [], [], object_ids=["soft_hide_1"], intent="make a raincoat"
    )
    assert only_hide is not None
    assert "error" in only_hide

    service.combine_in_lab(state.id, region.id, ["hide", "bone"])
    state = service.load_game(state.id)
    assert "sewing" in state.known_methods

    raincoat = service.combine_in_lab(
        state.id,
        region.id,
        ["hide"],
        component_ids=["bone_needle_1"],
        object_ids=["soft_hide_1"],
    )
    assert raincoat is not None
    assert raincoat.get("error") is None
    assert raincoat["recipe_match"] is True
    assert "raincoat" in raincoat["proposal"]["player_name"].lower()


def test_placed_invention_becomes_component(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    from civsim.models.entity import EntityDraft

    draft = EntityDraft(
        type="tool.grinder",
        tags=["flint", "stone"],
        capabilities={"tool_craft": 0.5, "food_output": 0.2},
        region_id=region.id,
        name="Grinder",
    )
    entity, _, err, _ = service.place_entity(state.id, draft)
    assert entity is not None
    assert "component" in entity.tags
    assert "object" not in entity.tags
    options = service.get_lab_options(state.id)
    ids = {c["id"] for c in options["components"]}
    assert entity.id in ids


def test_lab_rejects_component_left_in_other_region(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=11)
    cave_id = state.regions[0].id
    outside_id = state.regions[1].id
    from civsim.models.entity import Entity

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
                id="grinder_1",
                name="Grinding stone",
                type="tool.grinder",
                tags=["component", "flint", "stone"],
                capabilities={"tool_craft": 0.5, "food_output": 0.2},
                region_id=cave_id,
            ),
        ]
    )
    service._save(state)
    service.survey_region(state.id, cave_id)
    service.travel_to_region(state.id, outside_id, cave_id)

    result = service.combine_in_lab(
        state.id,
        outside_id,
        ["wood"],
        component_ids=["grinder_1"],
    )
    assert result is not None
    assert "error" in result
    assert "Grinding stone" in result["error"]


def test_lab_carry_pack_recipe(tmp_path):
    service = _service(tmp_path)
    state = service.create_game(seed=11)
    cave_id = state.regions[0].id
    state.region_material_stocks[cave_id] = {"plant_fiber": 0.4}
    service._save(state)

    result = service.combine_in_lab(
        state.id,
        cave_id,
        ["hide", "plant_fiber"],
    )
    assert result is not None
    assert result.get("error") is None
    assert result["recipe_match"] is True
    assert "pack" in result["proposal"]["player_name"].lower()
    service = _service(tmp_path)
    state = service.create_game(seed=42)
    region = state.regions[0]
    service._register_novel_compound(
        state,
        "Metal Bar",
        ["metal", "compound"],
        "material.metal_bar",
        region_id=region.id,
    )
    service._save(state)

    options = service.get_lab_options(state.id)
    mat_ids = {m["id"] for m in options["materials"]}
    assert "metal_bar" in mat_ids

    result = service.combine_in_lab(
        state.id,
        region.id,
        ["metal_bar", "bone"],
        component_ids=["natural_fire"],
        intent="pick axe",
    )
    assert result is not None
    assert "error" not in result or "Unknown material" not in result.get("error", "")
    assert "Unknown material: metal_bar" not in (result.get("errors") or [])
