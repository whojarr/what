import random

from civsim.engines.event_system import EventSystem
from civsim.engines.material_engine import MaterialEngine
from civsim.models.entity import EntityCore
from civsim.models.world import ClimateState, DEFAULT_ERA, GameState, Resources, TickResult
from civsim.registry.capability_registry import CapabilityRegistry


class SimulationEngine:
    def __init__(
        self,
        registry: CapabilityRegistry,
        event_system: EventSystem,
        material_engine: MaterialEngine | None = None,
    ) -> None:
        self.registry = registry
        self.event_system = event_system
        self.material_engine = material_engine

    def tick(self, state: GameState) -> TickResult:
        if state.era == "paleolithic":
            return self._tick_paleolithic(state)
        return self._tick_modern(state)

    def _tick_paleolithic(self, state: GameState) -> TickResult:
        rng = random.Random(state.rng_seed + state.turn)
        prev_resources = state.resources.model_copy()
        prev_climate = state.climate.model_copy()

        cores = [e.to_core() for e in state.entities]
        regions = {r.id: r for r in state.regions}

        self._apply_survival_costs(state, cores)
        if self.material_engine and state.regions:
            region = state.regions[0]
            self.material_engine.drain_materials(state, cores, region)
            discovery_fb = self.material_engine.discover_from_entities(state)
            self.material_engine.harvest_tick(state, cores)
        else:
            discovery_fb = []
        self._update_survival_resources(state, cores)
        self._drift_paleolithic_climate(state, cores)
        state.turn += 1

        events = self.event_system.roll_events(
            rng, state.turn, state.climate, state.regions, era=state.era
        )
        impacts = []
        for event in events:
            event_impacts = self.event_system.apply_event(
                event, cores, regions, era=state.era
            )
            impacts.extend(event_impacts)
            state.event_log.append(event)

        self._sync_entities(state, cores)
        self._apply_drift(state, cores, rng, skip_natural=True)

        feedback = self._paleolithic_feedback(
            state, events, impacts, prev_resources, prev_climate
        )
        feedback.extend(discovery_fb)
        resource_deltas = {
            k: getattr(state.resources, k) - getattr(prev_resources, k)
            for k in ("warmth", "water", "food", "materials", "knowledge")
        }
        climate_deltas = {
            "temperature_index": state.climate.temperature_index
            - prev_climate.temperature_index,
            "water_stress": state.climate.water_stress - prev_climate.water_stress,
            "atmospheric_instability": state.climate.atmospheric_instability
            - prev_climate.atmospheric_instability,
            "ecosystem_health": state.climate.ecosystem_health
            - prev_climate.ecosystem_health,
        }

        return TickResult(
            turn=state.turn,
            resources=state.resources.model_copy(),
            climate=state.climate.model_copy(),
            events=events,
            impacts=impacts,
            feedback=feedback,
            resource_deltas=resource_deltas,
            climate_deltas=climate_deltas,
        )

    def _apply_survival_costs(self, state: GameState, cores: list[EntityCore]) -> None:
        base_warmth_drain = 0.012 + state.climate.temperature_index * 0.008
        state.resources.warmth = max(0.0, state.resources.warmth - base_warmth_drain)
        state.resources.food = max(0.0, state.resources.food - 0.015)

        for core in cores:
            if not core.operational or "natural" in core.tags:
                continue
            maint = core.capabilities.get("maintenance_complexity", 0.3)
            state.resources.warmth = max(
                0.0,
                state.resources.warmth
                - core.capabilities.get("warmth_demand", 0.0) * 0.025
                - maint * 0.008,
            )
            state.resources.water = max(
                0.0,
                state.resources.water - core.capabilities.get("water_dependency", 0.0) * 0.01,
            )
            state.resources.food = max(
                0.0,
                state.resources.food - core.capabilities.get("food_demand", 0.0) * 0.02,
            )
            if not self.material_engine:
                state.resources.materials = max(
                    0.0,
                    state.resources.materials
                    - core.capabilities.get("material_demand", 0.0) * 0.015
                    - maint * 0.006,
                )
            elif maint > 0:
                state.resources.materials = max(
                    0.0,
                    state.resources.materials - maint * 0.006,
                )

    def _update_survival_resources(self, state: GameState, cores: list[EntityCore]) -> None:
        for core in cores:
            if not core.operational:
                continue
            state.resources.warmth = min(
                1.0,
                state.resources.warmth
                + core.capabilities.get("warmth_output", 0.0) * 0.05,
            )
            state.resources.water = min(
                1.0,
                state.resources.water + core.capabilities.get("water_output", 0.0) * 0.04,
            )
            state.resources.food = min(
                1.0,
                state.resources.food + core.capabilities.get("food_output", 0.0) * 0.04,
            )
            state.resources.materials = min(
                1.0,
                state.resources.materials + core.capabilities.get("tool_craft", 0.0) * 0.015,
            )
            state.resources.knowledge = min(
                1.0,
                state.resources.knowledge
                + core.capabilities.get("innovation_rate", 0.0) * 0.01,
            )

    def _drift_paleolithic_climate(self, state: GameState, cores: list[EntityCore]) -> None:
        smoke = sum(
            c.capabilities.get("warmth_output", 0.0)
            for c in cores
            if c.operational and "fire" in c.tags
        )
        state.climate.temperature_index = min(
            1.0, state.climate.temperature_index + 0.002 + smoke * 0.003
        )
        state.climate.water_stress = min(
            1.0, state.climate.water_stress + 0.001
        )
        state.climate.atmospheric_instability = min(
            1.0, state.climate.atmospheric_instability + smoke * 0.002
        )

    def _paleolithic_feedback(
        self,
        state: GameState,
        events,
        impacts,
        prev_resources: Resources,
        prev_climate: ClimateState,
    ) -> list[str]:
        feedback: list[str] = []
        if state.resources.warmth < prev_resources.warmth - 0.02:
            feedback.append("The cold creeps in — warmth is fading.")
        if state.resources.food < prev_resources.food - 0.02:
            feedback.append("Bellies rumble; food stores are thin.")
        if state.resources.water < prev_resources.water - 0.02:
            feedback.append("Water feels scarce this cycle.")
        if state.path_divergence > 0.15:
            feedback.append("Your inventions are carving a strange path through time.")
        if events:
            feedback.append(f"{len(events)} hardship(s) struck the cave this cycle.")
        if impacts:
            feedback.append("Something you rely on was damaged — check the cave.")
        if not feedback:
            feedback.append("Another cycle passes in the damp dark — you endure.")
        return feedback

    def _sync_entities(self, state: GameState, cores: list[EntityCore]) -> None:
        for core in cores:
            for entity in state.entities:
                if entity.id == core.id:
                    entity.health = core.health
                    entity.operational = core.operational
                    break

    def _apply_drift(
        self,
        state: GameState,
        cores: list[EntityCore],
        rng: random.Random,
        skip_natural: bool = False,
    ) -> None:
        for core in cores:
            if not core.operational:
                continue
            if skip_natural and "natural" in core.tags:
                continue
            stability = core.capabilities.get("scaling_stability", 0.7)
            if rng.random() > stability:
                drift = 0.01 * (1 - stability)
                for key in list(core.capabilities.keys()):
                    if key == "uncertainty":
                        continue
                    core.capabilities[key] = max(0.0, core.capabilities[key] - drift)
            for entity in state.entities:
                if entity.id == core.id:
                    entity.capabilities = dict(core.capabilities)

    def _tick_modern(self, state: GameState) -> TickResult:
        """Legacy modern-era tick (unused in v1 default game)."""
        rng = random.Random(state.rng_seed + state.turn)
        prev_climate = state.climate.model_copy()
        cores = [e.to_core() for e in state.entities]
        regions = {r.id: r for r in state.regions}
        state.turn += 1
        events = self.event_system.roll_events(
            rng, state.turn, state.climate, state.regions, era="modern"
        )
        impacts = []
        for event in events:
            impacts.extend(
                self.event_system.apply_event(event, cores, regions, era="modern")
            )
            state.event_log.append(event)
        self._sync_entities(state, cores)
        return TickResult(
            turn=state.turn,
            resources=state.resources.model_copy(),
            climate=state.climate.model_copy(),
            events=events,
            impacts=impacts,
            feedback=["Modern-era simulation stub."],
            resource_deltas={},
            climate_deltas={
                "temperature_index": state.climate.temperature_index
                - prev_climate.temperature_index,
            },
        )
