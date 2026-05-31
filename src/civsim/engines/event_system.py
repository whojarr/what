import random
import uuid

from civsim.models.entity import EntityCore
from civsim.models.events import EventImpact, EventType, GameEvent
from civsim.models.world import ClimateState, DEFAULT_ERA, Region
from civsim.registry.capability_registry import CapabilityRegistry


PALEO_RESISTANCE_MAP = {
    EventType.COLD_SNAP: "warmth_output",
    EventType.CAVE_IN: "shelter",
    EventType.PREDATOR: "hunting",
    EventType.FIRE_FADES: "warmth_output",
    EventType.DROUGHT: "water_output",
}

PALEO_TAG_BOOST = {
    EventType.COLD_SNAP: {"cave": -0.05, "damp": 0.05},
    EventType.PREDATOR: {"sheltered": -0.1},
    EventType.FIRE_FADES: {"fire": 0.2},
    EventType.CAVE_IN: {"cave": 0.15},
}

MODERN_RESISTANCE_MAP = {
    EventType.FLOOD: "flood_resistance",
    EventType.HEATWAVE: "heat_resistance",
    EventType.STORM: "storm_resistance",
    EventType.SUPPLY_DISRUPTION: "supply_chain_resilience",
}

MODERN_TAG_BOOST = {
    EventType.STORM: {"marine": 0.15, "storm_exposed": 0.2},
    EventType.FLOOD: {"coastal": 0.2, "low_elevation": 0.15},
    EventType.HEATWAVE: {"arid": 0.1},
}


class EventSystem:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def roll_events(
        self,
        rng: random.Random,
        turn: int,
        climate: ClimateState,
        regions: list[Region],
        era: str = DEFAULT_ERA,
    ) -> list[GameEvent]:
        if era == "paleolithic":
            return self._roll_paleolithic(rng, turn, climate, regions)
        return self._roll_modern(rng, turn, climate, regions)

    def _roll_paleolithic(
        self,
        rng: random.Random,
        turn: int,
        climate: ClimateState,
        regions: list[Region],
    ) -> list[GameEvent]:
        events: list[GameEvent] = []
        weights = {
            EventType.COLD_SNAP: 0.2 + climate.temperature_index * 0.35,
            EventType.CAVE_IN: 0.08,
            EventType.PREDATOR: 0.12,
            EventType.FIRE_FADES: 0.1,
            EventType.DROUGHT: 0.1 + climate.water_stress * 0.25,
        }
        if rng.random() < 0.5:
            event_type = rng.choices(
                list(weights.keys()),
                weights=[weights[t] for t in weights],
                k=1,
            )[0]
            region = rng.choice(regions) if regions else None
            base_severity = 0.25 + rng.random() * 0.45
            climate_boost = {
                EventType.COLD_SNAP: climate.temperature_index * 0.2,
                EventType.DROUGHT: climate.water_stress * 0.2,
                EventType.FIRE_FADES: 0.1,
                EventType.PREDATOR: 0.1,
                EventType.CAVE_IN: 0.05,
            }.get(event_type, 0.0)
            severity = min(1.0, base_severity + climate_boost)
            events.append(
                GameEvent(
                    id=str(uuid.uuid4())[:8],
                    type=event_type,
                    severity=severity,
                    turn=turn,
                    region_id=region.id if region else None,
                    description=f"{event_type.value} severity {severity:.2f}",
                )
            )
        return events

    def _roll_modern(
        self,
        rng: random.Random,
        turn: int,
        climate: ClimateState,
        regions: list[Region],
    ) -> list[GameEvent]:
        events: list[GameEvent] = []
        weights = {
            EventType.FLOOD: 0.15 + climate.water_stress * 0.3,
            EventType.HEATWAVE: 0.15 + climate.temperature_index * 0.35,
            EventType.STORM: 0.12 + climate.atmospheric_instability * 0.4,
            EventType.SUPPLY_DISRUPTION: 0.1 + (1 - climate.ecosystem_health) * 0.2,
        }
        if rng.random() < 0.45:
            event_type = rng.choices(
                list(weights.keys()),
                weights=[weights[t] for t in weights],
                k=1,
            )[0]
            region = rng.choice(regions) if regions else None
            base_severity = 0.3 + rng.random() * 0.5
            climate_boost = {
                EventType.FLOOD: climate.water_stress * 0.2,
                EventType.HEATWAVE: climate.temperature_index * 0.25,
                EventType.STORM: climate.atmospheric_instability * 0.25,
                EventType.SUPPLY_DISRUPTION: (1 - climate.ecosystem_health) * 0.15,
            }[event_type]
            severity = min(1.0, base_severity + climate_boost)
            events.append(
                GameEvent(
                    id=str(uuid.uuid4())[:8],
                    type=event_type,
                    severity=severity,
                    turn=turn,
                    region_id=region.id if region else None,
                    description=f"{event_type.value} severity {severity:.2f}",
                )
            )
        return events

    def apply_event(
        self,
        event: GameEvent,
        entities: list[EntityCore],
        regions: dict[str, Region],
        era: str = DEFAULT_ERA,
    ) -> list[EventImpact]:
        resistance_map = (
            PALEO_RESISTANCE_MAP if era == "paleolithic" else MODERN_RESISTANCE_MAP
        )
        tag_boost = PALEO_TAG_BOOST if era == "paleolithic" else MODERN_TAG_BOOST
        resistance_key = resistance_map.get(event.type)
        if not resistance_key:
            return []

        default_def = self.registry.get(resistance_key)
        default_val = default_def.default if default_def else 0.2
        impacts: list[EventImpact] = []

        for entity in entities:
            if not entity.operational:
                continue
            if event.region_id and entity.region_id != event.region_id:
                continue
            if event.type == EventType.FIRE_FADES and "fire" not in entity.tags:
                continue
            if event.type == EventType.PREDATOR and "natural" in entity.tags:
                continue

            resistance = entity.capabilities.get(resistance_key, default_val)
            if event.type == EventType.COLD_SNAP:
                resistance = max(
                    resistance,
                    entity.capabilities.get("shelter", 0.2),
                )
            if event.type == EventType.PREDATOR:
                resistance = max(
                    resistance,
                    entity.capabilities.get("social_cohesion", 0.2) * 0.5,
                )

            severity = event.severity
            for tag in entity.tags:
                severity += tag_boost.get(event.type, {}).get(tag, 0.0)
            severity = min(1.0, max(0.0, severity))

            damage = max(0.0, severity - resistance)
            if damage <= 0:
                continue

            new_health = max(0.0, entity.health - damage * 0.5)
            entity.health = new_health
            if new_health < 0.25:
                entity.operational = False

            impacts.append(
                EventImpact(
                    entity_id=entity.id,
                    damage=damage,
                    health_after=new_health,
                    operational=entity.operational,
                )
            )
        return impacts
