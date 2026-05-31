"""Re-exports — prefer civsim.models.entity_kinds."""

from civsim.models.entity_kinds import (
    component_display,
    is_component,
    is_object,
    classify_entity_tags,
    with_component_tag,
)

__all__ = [
    "component_display",
    "is_component",
    "is_object",
    "classify_entity_tags",
    "with_component_tag",
]
