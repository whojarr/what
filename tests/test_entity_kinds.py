from civsim.models.entity import Entity
from civsim.models.entity_kinds import (
    classify_entity_tags,
    has_machine_io,
    is_component,
    is_object,
    is_portable,
)


def test_softened_hide_is_object_not_machine():
    caps = {"shelter": 0.4, "tool_craft": 0.2}
    tags = classify_entity_tags(["hide", "water"], "object.soft_hide", caps)
    assert "object" in tags
    assert "component" not in tags
    assert not has_machine_io(caps)

    entity = Entity(
        id="x",
        name="Softened hide",
        type="object.soft_hide",
        tags=tags,
        capabilities=caps,
        region_id="cave_chamber",
    )
    assert is_object(entity)
    assert not is_component(entity)


def test_grinder_is_machine_with_output():
    caps = {"tool_craft": 0.5, "food_output": 0.2}
    tags = classify_entity_tags(["flint", "stone"], "tool.grinder", caps)
    assert "component" in tags
    assert has_machine_io(caps)
    entity = Entity(
        id="x",
        name="Grinder",
        type="tool.grinder",
        tags=tags,
        capabilities=caps,
        region_id="cave_chamber",
    )
    assert is_component(entity)
    assert not is_object(entity)


def test_seat_is_object_with_only_passive_stats():
    caps = {"shelter": 0.15, "social_cohesion": 0.15}
    tags = classify_entity_tags(["object", "furniture", "chair"], "object.seat", caps)
    assert "object" in tags
    assert not has_machine_io(caps)


def test_fuel_cake_is_machine_via_warmth_output():
    caps = {"warmth_output": 0.45, "tool_craft": 0.1}
    assert has_machine_io(caps)
    tags = classify_entity_tags(["dung", "fire", "fuel"], "fuel.dung_cake", caps)
    assert "component" in tags


def test_material_demand_makes_machine():
    caps = {"warmth_demand": 0.4, "shelter": 0.5}
    assert has_machine_io(caps)
    tags = classify_entity_tags(["stone"], "component.smoker", caps)
    assert "component" in tags


def test_normalize_tags_splits_comma_joined():
    from civsim.models.entity_kinds import normalize_tags

    assert normalize_tags(["flint,sharp,bone,object"]) == [
        "flint",
        "sharp",
        "bone",
        "object",
    ]
    assert normalize_tags(["hide", "hide,water"]) == ["hide", "water"]


def test_malformed_tags_classify_as_component_when_tool_has_io():
    entity = Entity(
        id="x",
        name="Knapped flint",
        type="tool.flint_knapped",
        tags=["object", "flint", "sharp", "bone", "fire"],
        capabilities={"tool_craft": 0.65, "hunting": 0.35},
        region_id="cave_chamber",
    )
    assert is_component(entity)
    assert not is_object(entity)


def test_object_hints_from_composition():
    from civsim.models.entity_kinds import object_display, component_display

    soft = Entity(
        id="a",
        name="Softened hide",
        type="object.soft_hide",
        tags=["object", "hide", "water"],
        capabilities={"shelter": 0.4},
        region_id="cave_chamber",
    )
    hint = object_display(soft)["hint"]
    assert "hide" in hint.lower()
    assert "water" in hint.lower() or "soaked" in hint.lower()

    flint = Entity(
        id="b",
        name="Knapped flint",
        type="tool.flint_knapped",
        tags=["component", "flint", "sharp", "bone", "fire"],
        capabilities={"tool_craft": 0.65, "hunting": 0.35},
        region_id="cave_chamber",
    )
    tool_hint = component_display(flint)["hint"]
    assert "flint" in tool_hint.lower()
    assert "bone" in tool_hint.lower()


def test_natural_fixtures_not_portable():
    fire = Entity(
        id="natural_fire",
        name="Fire",
        type="component.fire",
        tags=["natural", "component", "fire"],
        capabilities={"warmth_output": 0.35},
        region_id="cave_chamber",
    )
    assert not is_portable(fire)


def test_softened_hide_is_portable():
    soft = Entity(
        id="a",
        name="Softened hide",
        type="object.soft_hide",
        tags=["object", "hide", "water"],
        capabilities={"shelter": 0.4},
        region_id="cave_chamber",
    )
    assert is_portable(soft)


def test_grinder_tool_is_portable():
    entity = Entity(
        id="x",
        name="Grinder",
        type="tool.grinder",
        tags=["component", "flint", "stone"],
        capabilities={"tool_craft": 0.5, "food_output": 0.2},
        region_id="cave_chamber",
    )
    assert is_portable(entity)


def test_shelter_structure_not_portable():
    shelter = Entity(
        id="s",
        name="Lean-to",
        type="object.shelter",
        tags=["object", "shelter", "structure"],
        capabilities={"shelter": 0.7},
        region_id="cave_chamber",
    )
    assert not is_portable(shelter)


def test_travel_carry_capacity_without_pack():
    from civsim.models.entity_kinds import partition_for_travel, travel_carry_capacity
    from civsim.models.world import Region, RegionExit

    cave = Region(id="cave", name="Cave", exits=[])
    entities = [
        Entity(
            id="a",
            name="Knapped flint",
            type="tool.flint_knapped",
            tags=["component", "flint"],
            capabilities={"tool_craft": 0.65},
            region_id="cave",
        ),
        Entity(
            id="b",
            name="Bone needle",
            type="tool.bone_needle",
            tags=["component", "bone"],
            capabilities={"tool_craft": 0.55},
            region_id="cave",
        ),
    ]
    assert travel_carry_capacity(entities, "cave") == 1
    carried, left = partition_for_travel(entities, "cave")
    assert len(carried) == 1
    assert len(left) == 1


def test_travel_carry_capacity_with_pack():
    from civsim.models.entity_kinds import partition_for_travel, travel_carry_capacity

    entities = [
        Entity(
            id="pack",
            name="Hide carry pack",
            type="object.carry_pack",
            tags=["object", "hide"],
            capabilities={"storage": 0.35},
            region_id="cave",
        ),
        Entity(
            id="a",
            name="Knapped flint",
            type="tool.flint_knapped",
            tags=["component", "flint"],
            capabilities={"tool_craft": 0.65},
            region_id="cave",
        ),
        Entity(
            id="b",
            name="Bone needle",
            type="tool.bone_needle",
            tags=["component", "bone"],
            capabilities={"tool_craft": 0.55},
            region_id="cave",
        ),
    ]
    assert travel_carry_capacity(entities, "cave") == 3
    carried, left = partition_for_travel(entities, "cave")
    assert len(carried) == 3
    assert len(left) == 0
    assert carried[0].id == "pack"


def test_material_travel_capacity():
    from civsim.models.entity_kinds import material_travel_capacity, transfer_materials_on_travel
    from civsim.models.entity import Entity

    pack = Entity(
        id="pack",
        name="Hide carry pack",
        type="object.carry_pack",
        tags=["object", "hide"],
        capabilities={"storage": 0.35},
        region_id="cave",
    )
    assert abs(material_travel_capacity([pack], "cave") - 0.2975) < 0.001
    assert material_travel_capacity([], "cave") == 0.0

    region_stocks = {"cave": {"flint": 0.5, "bone": 0.2}, "outside": {}}
    moved = transfer_materials_on_travel(
        region_stocks,
        "cave",
        "outside",
        {"flint", "limestone"},
        [pack],
    )
    assert moved
    assert region_stocks["outside"].get("flint", 0) > 0
    assert region_stocks["cave"].get("flint", 0) < 0.5


def test_entity_available_at_lab_natural_in_connected_region():
    from civsim.models.entity_kinds import entity_available_at_lab
    from civsim.models.world import Region, RegionExit

    cave = Region(id="cave", name="Cave", exits=[])
    outside = Region(
        id="outside",
        name="Outside",
        exits=[
            RegionExit(
                id="mouth",
                name="Cave mouth",
                target_region_id="cave",
                discovered=True,
                accessible=True,
            )
        ],
    )
    fire = Entity(
        id="natural_fire",
        name="Fire",
        type="component.fire",
        tags=["natural", "component", "fire"],
        capabilities={"warmth_output": 0.35},
        region_id="cave",
    )
    tool = Entity(
        id="grinder",
        name="Grinder",
        type="tool.grinder",
        tags=["component", "flint"],
        capabilities={"tool_craft": 0.5},
        region_id="cave",
    )
    assert entity_available_at_lab(fire, outside)
    assert not entity_available_at_lab(tool, outside)
