"""Entity kinds: materials (stocks), components (machines), objects (inanimate things)."""

from __future__ import annotations

from __future__ import annotations

from civsim.models.entity import Entity
from civsim.models.world import Region

STARTER_COMPONENT_IDS = frozenset({"natural_fire", "natural_spring"})

# Fixed in place — too large or tied to the landscape.
FIXED_STRUCTURE_TAGS = frozenset(
    {"structure", "shelter", "house", "dwelling", "wall", "furniture"}
)

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
        "object.carry_pack": "Hide and fiber — lashed pack for hauling between places",
        "object.woven_basket": "Fiber and wood — a basket for goods on the move",
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


def normalize_tags(raw: list[str]) -> list[str]:
    """Split comma-joined tag strings and dedupe."""
    out: list[str] = []
    for tag in raw:
        t = tag.strip().lower()
        if not t:
            continue
        if "," in t:
            out.extend(p.strip() for p in t.split(",") if p.strip())
        else:
            out.append(t)
    seen: set[str] = set()
    deduped: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


def entity_kind(entity: Entity) -> str:
    if is_component(entity):
        return "component"
    if is_object(entity):
        return "object"
    return "other"


def is_portable(entity: Entity) -> bool:
    """True when the player can bring this entity when traveling between regions."""
    if entity.id in STARTER_COMPONENT_IDS or "natural" in entity.tags:
        return False
    tag_set = {t.lower() for t in entity.tags}
    if tag_set & FIXED_STRUCTURE_TAGS:
        return False
    caps = entity.capabilities or {}
    if caps.get("shelter", 0.0) >= 0.55:
        return False
    return is_object(entity) or is_component(entity)


def lab_accessible_region_ids(region: Region) -> set[str]:
    """Regions whose fixed fixtures (e.g. cave fire) can be used at this bench."""
    ids = {region.id}
    for passage in region.exits:
        if passage.discovered and passage.accessible:
            ids.add(passage.target_region_id)
    return ids


def entity_available_at_lab(
    entity: Entity, region: Region, accessible: set[str] | None = None
) -> bool:
    """True when an entity can be used at the lab — here, carried, or a nearby natural fixture."""
    if not entity.operational:
        return False
    reachable = accessible if accessible is not None else lab_accessible_region_ids(region)
    if entity.region_id == region.id:
        return True
    if entity.region_id not in reachable:
        return False
    return "natural" in entity.tags


def travel_carry_capacity(entities: list[Entity], from_region_id: str) -> int:
    """How many portable entities can leave a region — packs and baskets add slots."""
    portables = [
        e for e in entities if e.region_id == from_region_id and is_portable(e)
    ]
    capacity = 1
    for entity in portables:
        storage = entity.capabilities.get("storage", 0.0)
        if storage >= 0.1:
            capacity += max(1, int(round(storage * 6)))
    return capacity


def partition_for_travel(
    entities: list[Entity], from_region_id: str
) -> tuple[list[Entity], list[Entity]]:
    """Split portables into (carried, left_behind) by carry capacity."""
    portables = [
        e for e in entities if e.region_id == from_region_id and is_portable(e)
    ]
    capacity = travel_carry_capacity(entities, from_region_id)

    def sort_key(entity: Entity) -> tuple:
        storage = entity.capabilities.get("storage", 0.0)
        return (
            -storage,
            -entity.capabilities.get("tool_craft", 0.0),
            0 if is_component(entity) else 1,
            entity.name.lower(),
        )

    portables.sort(key=sort_key)
    return portables[:capacity], portables[capacity:]


def material_travel_capacity(entities: list[Entity], from_region_id: str) -> float:
    """Bulk material volume that can move when traveling — needs a pack or basket."""
    portables = [
        e for e in entities if e.region_id == from_region_id and is_portable(e)
    ]
    capacity = 0.0
    for entity in portables:
        storage = entity.capabilities.get("storage", 0.0)
        if storage >= 0.1:
            capacity += storage * 0.85
    return min(1.0, capacity)


def transfer_materials_on_travel(
    region_stocks: dict[str, dict[str, float]],
    from_region_id: str,
    to_region_id: str,
    to_absent_materials: set[str],
    entities: list[Entity],
) -> list[tuple[str, float]]:
    """Move stored materials between regions up to pack capacity."""
    capacity = material_travel_capacity(entities, from_region_id)
    if capacity <= 0.001:
        return []

    from_stocks = region_stocks.setdefault(from_region_id, {})
    to_stocks = region_stocks.setdefault(to_region_id, {})
    if not from_stocks:
        return []

    moved: list[tuple[str, float]] = []
    remaining = capacity
    candidates = [(mid, amt) for mid, amt in from_stocks.items() if amt > 0.01]
    candidates.sort(key=lambda item: (0 if item[0] in to_absent_materials else 1, -item[1], item[0]))

    for mat_id, amount in candidates:
        if remaining <= 0.001:
            break
        haul = min(amount, remaining)
        if haul <= 0.001:
            continue
        from_stocks[mat_id] = amount - haul
        if from_stocks[mat_id] <= 0.001:
            del from_stocks[mat_id]
        to_stocks[mat_id] = min(1.0, to_stocks.get(mat_id, 0.0) + haul)
        remaining -= haul
        moved.append((mat_id, haul))

    return moved


def classify_entity_tags(
    tags: list[str],
    entity_type: str,
    capabilities: dict[str, float],
) -> list[str]:
    normalized = normalize_tags(tags)
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
