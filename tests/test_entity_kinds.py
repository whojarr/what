from civsim.models.entity import Entity
from civsim.models.entity_kinds import (
    classify_entity_tags,
    has_machine_io,
    is_component,
    is_object,
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


def test_stale_object_tag_on_tool_still_component():
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
