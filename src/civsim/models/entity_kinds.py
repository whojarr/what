"""Entity kinds: materials (stocks), components (machines), objects (inanimate things)."""

from __future__ import annotations

from civsim.models.entity import Entity

STARTER_COMPONENT_IDS = frozenset({"natural_fire", "natural_spring"})

IO_THRESHOLD = 0.25

# Capabilities that mean the thing actively inputs or outputs — it is a machine.
MACHINE_OUTPUTS = (
    "warmth_output",
    "water_output",
    "food_output",
    "light",
    "hunting",
    "innovation_rate",
)
MACHINE_INPUTS = (
    "warmth_demand",
    "food_demand",
    "material_demand",
)
# tool_craft counts only at/above threshold — passive quality of an object does not.
MACHINE_PROCESS = ("tool_craft",)

# Passive stats — shelter, storage, social_cohesion alone do not make a machine.
PASSIVE_CAPS = frozenset({"shelter", "storage", "social_cohesion", "maintenance_complexity"})

OBJECT_TAGS = frozenset(
    {
        "object",
        "furniture",
        "structure",
        "shelter",
        "house",
        "table",
        "chair",
        "seat",
        "bed",
        "wall",
        "dwelling",
    }
)
OBJECT_TYPE_PREFIXES = ("object.", "structure.", "furniture.", "dwelling.")
MACHINE_TYPE_PREFIXES = ("tool.", "component.", "fuel.")


def has_machine_io(capabilities: dict[str, float], threshold: float = IO_THRESHOLD) -> bool:
    """True when the entity actively takes in or puts out something — a machine, not inanimate."""
    for key in MACHINE_OUTPUTS + MACHINE_INPUTS:
        if capabilities.get(key, 0.0) >= threshold:
            return True
    for key in MACHINE_PROCESS:
        if capabilities.get(key, 0.0) >= threshold:
            return True
    return False


COMPOSITION_TAGS = frozenset(
    {
        "hide",
        "leather",
        "bone",
        "flint",
        "limestone",
        "stone",
        "water",
        "dung",
        "iron",
        "metal",
        "ore",
        "garment",
        "pigment",
        "chemical",
        "sulfur",
        "manganese",
        "fire",
    }
)
MATERIAL_LABELS = {
    "hide": "hide",
    "leather": "leather",
    "bone": "bone",
    "flint": "flint",
    "limestone": "limestone",
    "stone": "stone",
    "water": "water",
    "dung": "dung",
    "iron": "iron",
    "metal": "metal",
    "ore": "ore",
    "garment": "garment",
    "pigment": "pigment",
    "chemical": "minerals",
    "sulfur": "sulfur",
    "manganese": "manganese",
    "fire": "fire",
}


def _material_phrase(tag_set: set[str]) -> str:
    parts = [
        MATERIAL_LABELS[t]
        for t in (
            "limestone",
            "stone",
            "flint",
            "bone",
            "hide",
            "leather",
            "water",
            "dung",
            "iron",
            "metal",
            "ore",
            "sulfur",
            "manganese",
            "pigment",
            "garment",
        )
        if t in tag_set
    ]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0].capitalize()
    if len(parts) == 2:
        return f"{parts[0].capitalize()} and {parts[1]}"
    return f"{', '.join(p.capitalize() for p in parts[:-1])}, and {parts[-1]}"


def _object_composition_hint(entity: Entity, tag_set: set[str], role: str) -> str:
    by_type = {
        "object.soft_hide": "Hide soaked in water — soft and pliable",
        "object.raincoat": "Stitched hide — a garment for rain",
        "object.seat": "Stone and hide — a place to sit",
        "object.table": "Stone, hide, and bone — a flat surface",
        "object.shelter": "Stone and hide — stretched cover",
        "object.house": "Stone, hide, bone, and flint — walled dwelling",
        "object.furnished_corner": "Seat and table together — a lived-in corner",
        "material.cave_pigment": "Sulfur and manganese — colored dust",
    }
    if entity.type in by_type:
        return by_type[entity.type]

    materials = _material_phrase(tag_set)
    if role == "dwelling":
        return f"{materials or 'Built materials'} — shelter, no moving parts"
    if role == "furniture":
        return f"{materials or 'Lashed materials'} — furnishing"
    if "garment" in tag_set:
        return f"{materials or 'Hide'} — clothing to wear"
    if "hide" in tag_set and "water" in tag_set:
        return "Hide and water — softened, ready to work"
    if "hide" in tag_set:
        return "Worked hide — material for sewing or cover"
    if tag_set & {"pigment", "chemical"}:
        return f"{materials or 'Minerals'} — powder for color or mixing"
    if materials:
        return f"{materials} — processed, inanimate"
    return "Built from cave materials — inanimate"


def _tool_composition_hint(entity: Entity, tag_set: set[str]) -> str | None:
    by_type = {
        "tool.flint_knapped": "Flint and bone — knapped sharp edge",
        "tool.bone_needle": "Bone and hide — needle and sinew for sewing",
        "tool.grinder": "Flint on limestone — grinding surface",
        "tool.flint_clean": "Flint washed in water — clean stone",
        "fuel.dung_cake": "Dung and bone char — fuel that smolders",
        "material.roasted_ore": "Iron ore and fire — roasted red stone",
    }
    if entity.type in by_type:
        return by_type[entity.type]
    materials = _material_phrase(tag_set)
    if materials and has_machine_io(entity.capabilities):
        return f"{materials} — tool with active use"
    return None


def is_object(entity: Entity) -> bool:
    if entity.id in STARTER_COMPONENT_IDS:
        return False
    if "natural" in entity.tags:
        return False
    if entity.type.startswith(MACHINE_TYPE_PREFIXES) and has_machine_io(entity.capabilities):
        return False
    if "component" in entity.tags and has_machine_io(entity.capabilities):
        return False
    if "object" in entity.tags:
        return True
    if entity.type.startswith(OBJECT_TYPE_PREFIXES):
        return True
    if OBJECT_TAGS & {t.lower() for t in entity.tags}:
        return True
    return not has_machine_io(entity.capabilities)


def is_component(entity: Entity) -> bool:
    if is_object(entity):
        return False
    if entity.id in STARTER_COMPONENT_IDS:
        return True
    if "component" in entity.tags:
        return True
    if "natural" in entity.tags:
        return False
    return has_machine_io(entity.capabilities)


def classify_entity_tags(
    tags: list[str],
    entity_type: str,
    capabilities: dict[str, float],
) -> list[str]:
    normalized = [t.lower().strip() for t in tags]
    tag_set = set(normalized)

    if "object" in tag_set or entity_type.startswith(OBJECT_TYPE_PREFIXES):
        return _with_object_tag(normalized)

    if tag_set & OBJECT_TAGS:
        return _with_object_tag(normalized)

    if entity_type.startswith(MACHINE_TYPE_PREFIXES) and has_machine_io(capabilities):
        return _with_component_tag(normalized)

    if tag_set & {"fire", "fuel", "mining"}:
        return _with_component_tag(normalized)

    # Water tag alone on a processed thing is not a machine — only starter Water component.
    if tag_set & {"tool"} and has_machine_io(capabilities):
        return _with_component_tag(normalized)

    if has_machine_io(capabilities):
        return _with_component_tag(normalized)

    return _with_object_tag(normalized)


def _with_component_tag(tags: list[str]) -> list[str]:
    result = [t for t in tags if t != "object"]
    if "component" not in result:
        result.append("component")
    if "machine" not in result:
        result.append("machine")
    return result


def _with_object_tag(tags: list[str]) -> list[str]:
    result = [t for t in tags if t not in ("component", "machine")]
    if "object" not in result:
        result.append("object")
    return result


# Backward-compatible alias
with_component_tag = classify_entity_tags


COMPONENT_DISPLAY: dict[str, dict[str, str]] = {
    "natural_fire": {
        "role": "fire",
        "label": "Fire",
        "hint": "A machine of heat — dries, cooks, and hardens what you combine with it",
    },
    "natural_spring": {
        "role": "water",
        "label": "Water",
        "hint": "A machine of flow — soaks, rinses, and softens what you combine with it",
    },
}


def component_display(entity: Entity) -> dict[str, str]:
    tag_set = {t.lower() for t in entity.tags}
    if entity.id in COMPONENT_DISPLAY:
        return {**COMPONENT_DISPLAY[entity.id], "kind": "starter"}
    tool_hint = _tool_composition_hint(entity, tag_set)
    if tool_hint:
        role = "fire" if "fire" in tag_set else "water" if "water" in tag_set else "machine"
        return {
            "role": role,
            "label": entity.name,
            "hint": tool_hint,
            "kind": "built",
        }
    if "fire" in tag_set:
        return {
            "role": "fire",
            "label": entity.name,
            "hint": "Fire and fuel — heat for cooking and hardening",
            "kind": "built",
        }
    if "water" in tag_set and entity.id in STARTER_COMPONENT_IDS:
        return {
            "role": "water",
            "label": entity.name,
            "hint": "Provides water — combine with materials, objects, or other components",
            "kind": "built",
        }
    materials = _material_phrase(tag_set)
    hint = f"{materials} — active machine" if materials else "Has inputs or outputs — a working machine"
    return {
        "role": "machine",
        "label": entity.name,
        "hint": hint,
        "kind": "built",
    }


def object_display(entity: Entity) -> dict[str, str]:
    tag_set = {t.lower() for t in entity.tags}
    role = "structure"
    if tag_set & {"furniture", "table", "chair", "seat", "bed"}:
        role = "furniture"
    elif tag_set & {"house", "dwelling", "shelter"} or entity.type.startswith("object.house"):
        role = "dwelling"
    elif tag_set & {"hide", "leather", "garment", "pigment", "chemical"} or entity.type.startswith(
        ("object.", "material.")
    ):
        role = "material"
    return {
        "role": role,
        "label": entity.name,
        "hint": _object_composition_hint(entity, tag_set, role),
        "kind": "built",
    }


def classification_reason(capabilities: dict[str, float]) -> str:
    """Short explanation for UI/debug."""
    if has_machine_io(capabilities):
        active = [
            k
            for k in MACHINE_OUTPUTS + MACHINE_INPUTS + MACHINE_PROCESS
            if capabilities.get(k, 0.0) >= IO_THRESHOLD
        ]
        return f"Machine — active: {', '.join(active)}"
    passive = [k for k in PASSIVE_CAPS if capabilities.get(k, 0.0) >= IO_THRESHOLD]
    if passive:
        return f"Object — passive only ({', '.join(passive)}); no inputs or outputs"
    return "Object — nothing active; inanimate"
