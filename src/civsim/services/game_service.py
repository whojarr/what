import json
import os
import uuid
from pathlib import Path

from civsim.ai.openai_interpreter import OpenAIInterpreter
from civsim.ai.text_normalize import normalize_invention_text
from civsim.engines.capability_engine import CapabilityEngine
from civsim.engines.constraint_engine import ANACHRONISM_TAGS, ConstraintEngine
from civsim.engines.event_system import EventSystem
from civsim.engines.lab_engine import LabEngine
from civsim.engines.material_engine import MaterialEngine
from civsim.engines.method_engine import MethodEngine
from civsim.engines.simulation import SimulationEngine
from civsim.memory.in_memory import InMemoryMemory
from civsim.models.capabilities import (
    ConstraintResult,
    ConstraintStatus,
    IdeaProposal,
    NormalizedProposal,
)
from civsim.models.entity_kinds import (
    classify_entity_tags,
    component_display,
    is_component,
    is_object,
    object_display,
)
from civsim.models.entity import Entity, EntityDraft
from civsim.models.world import DEFAULT_ERA, GameState, Region, TickResult
from civsim.registry.capability_registry import CapabilityRegistry
from civsim.registry.material_registry import MaterialRegistry
from civsim.registry.method_registry import MethodRegistry
from civsim.world.generator import WorldGenerator


class GameService:
    def __init__(
        self,
        registry: CapabilityRegistry,
        saves_path: Path,
        memory: InMemoryMemory | None = None,
        material_registry: MaterialRegistry | None = None,
        method_registry: MethodRegistry | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.registry = registry
        self.saves_path = saves_path
        self.saves_path.mkdir(parents=True, exist_ok=True)
        self.memory = memory or InMemoryMemory()
        self.material_registry = material_registry or MaterialRegistry()
        self.data_dir = data_dir or Path()
        if method_registry is None and self.data_dir:
            method_registry = MethodRegistry.load_for_era(DEFAULT_ERA, self.data_dir)
        self.method_registry = method_registry or MethodRegistry()
        self.material_engine = MaterialEngine(self.material_registry)
        self.method_engine = MethodEngine(self.method_registry)
        self.lab_engine = LabEngine.load_for_era(
            DEFAULT_ERA, self.data_dir, self.material_registry
        )
        self.capability_engine = CapabilityEngine(registry)
        self.constraint_engine = ConstraintEngine(self.material_engine)
        self.event_system = EventSystem(registry)
        self.simulation = SimulationEngine(registry, self.event_system, self.material_engine)
        self.world_gen = WorldGenerator()
        self._interpreter: OpenAIInterpreter | None = None

    def _get_interpreter(self) -> OpenAIInterpreter:
        if self._interpreter is None:
            self._interpreter = OpenAIInterpreter()
        return self._interpreter

    def create_game(self, seed: int = 42) -> GameState:
        state = self.world_gen.generate(seed)
        self.method_engine.seed_starter_methods(state)
        self._save(state)
        return state

    def load_game(self, game_id: str) -> GameState | None:
        path = self.saves_path / f"{game_id}.json"
        if not path.exists():
            return None
        with path.open() as f:
            data = json.load(f)
        state = GameState.model_validate(data)
        self.method_engine.sync_from_world(state)
        return state

    def _save(self, state: GameState) -> None:
        path = self.saves_path / f"{state.id}.json"
        with path.open("w") as f:
            json.dump(state.model_dump(), f, indent=2)

    def rename_region(self, game_id: str, region_id: str, name: str) -> GameState | None:
        state = self.load_game(game_id)
        if not state:
            return None
        for region in state.regions:
            if region.id == region_id:
                region.name = name
                break
        self._save(state)
        return state

    def interpret_idea(
        self, game_id: str, player_text: str, region_id: str | None = None
    ) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        try:
            interpreter = self._get_interpreter()
        except ValueError as e:
            raise RuntimeError(str(e)) from e

        similar = self.memory.search_similar(player_text, game_id, limit=3)
        memory_context = [r.text for r in similar]
        mat_ctx = self.get_material_context(state, region_id)
        proposal = interpreter.interpret(
            player_text, state, self.registry, memory_context, mat_ctx
        )
        _, typo_note = normalize_invention_text(player_text)
        normalized = self.capability_engine.normalize(proposal)
        self.auto_approve_pending()
        normalized = self._refresh_queued_keys(normalized)
        region = next(
            (r for r in state.regions if r.id == region_id),
            state.regions[0] if state.regions else None,
        )
        constraint = None
        if region:
            constraint = self.constraint_engine.validate_proposal(
                normalized, region, state, speculative=True
            )
        return {
            "proposal": proposal.model_dump(),
            "normalized": normalized.model_dump(),
            "constraint": constraint.model_dump() if constraint else None,
            "memory_hints": memory_context,
            "typo_note": typo_note,
        }

    def interpret_idea_direct(
        self, game_id: str, proposal: IdeaProposal, region_id: str | None = None
    ) -> dict | None:
        """For demo/testing without LLM."""
        state = self.load_game(game_id)
        if not state:
            return None
        normalized = self.capability_engine.normalize(proposal)
        region = next(
            (r for r in state.regions if r.id == region_id),
            state.regions[0] if state.regions else None,
        )
        constraint = None
        if region:
            constraint = self.constraint_engine.validate_proposal(
                normalized, region, state, speculative=False
            )
        return {
            "proposal": proposal.model_dump(),
            "normalized": normalized.model_dump(),
            "constraint": constraint.model_dump() if constraint else None,
        }

    def place_entity(
        self,
        game_id: str,
        draft: EntityDraft,
    ) -> tuple[Entity | None, ConstraintResult | None, str | None, str | None]:
        state = self.load_game(game_id)
        if not state:
            return None, None, "Game not found", None
        region = next((r for r in state.regions if r.id == draft.region_id), None)
        if not region:
            return None, None, "Region not found", None

        normalized = NormalizedProposal(
            type=draft.type,
            tags=draft.tags,
            capabilities=draft.capabilities,
        )
        result = self.constraint_engine.validate_proposal(normalized, region, state)
        if result.status == ConstraintStatus.BLOCKED:
            return None, result, "Entity blocked by constraints", None

        if draft.type.startswith("method."):
            method_id = draft.type.split(".", 1)[1]
            defn = self.method_registry.get(method_id)
            newly_learned = self.method_engine.learn(state, method_id)
            learned_name = defn.name if defn else draft.name
            state.invention_count += 1
            self._bump_path_divergence(state, draft.capabilities, draft.tags)
            self._save(state)
            self.memory.record_idea(
                draft.name, draft.type, result.status.value, state.turn, game_id
            )
            if newly_learned:
                self.memory.record_event(
                    "method_learned",
                    f"You learned {learned_name}.",
                    [],
                    state.turn,
                    game_id,
                )
            return None, result, None, learned_name

        entity_id = f"infra_{uuid.uuid4().hex[:8]}"
        entity = Entity(
            id=entity_id,
            name=draft.name,
            type=draft.type,
            tags=classify_entity_tags(draft.tags, draft.type, draft.capabilities),
            capabilities=draft.capabilities,
            region_id=draft.region_id,
        )
        state.entities.append(entity)
        state.entity_names[entity_id] = draft.name
        state.invention_count += 1
        self._bump_path_divergence(state, draft.capabilities, draft.tags)
        learned_method = self.method_engine.unlock_from_entity(state, entity)
        if learned_method:
            self.memory.record_event(
                "method_learned",
                f"You learned {learned_method}.",
                [],
                state.turn,
                game_id,
            )
        discovery_fb = self.material_engine.discover_from_invention(
            state, region, draft.tags, draft.capabilities
        )
        compound_fb = self._register_novel_compound(
            state, draft.name, entity.tags, entity.type
        )
        if compound_fb:
            discovery_fb = discovery_fb + [compound_fb]
        if discovery_fb:
            self.memory.record_event(
                "material_discovery",
                "; ".join(discovery_fb),
                [],
                state.turn,
                game_id,
            )
        self._save(state)
        self.memory.record_idea(
            draft.name, entity_id, result.status.value, state.turn, game_id
        )
        return entity, result, None, learned_method

    def _refresh_queued_keys(self, normalized: NormalizedProposal) -> NormalizedProposal:
        """Drop queued keys that were approved or are now in the registry."""
        still_queued = [
            k for k in normalized.queued_capability_keys if not self.registry.has(k)
        ]
        return normalized.model_copy(update={"queued_capability_keys": still_queued})

    def _bump_path_divergence(
        self, state: GameState, capabilities: dict[str, float], tags: list[str]
    ) -> None:
        tag_set = set(tags)
        bump = capabilities.get("uncertainty", 0.0) * 0.1
        if tag_set & ANACHRONISM_TAGS:
            bump += 0.06
        modern = (
            capabilities.get("compute_output", 0.0)
            + capabilities.get("compute_demand", 0.0)
            + capabilities.get("energy_output", 0.0)
        )
        if modern > 0.2:
            bump += 0.08
        state.path_divergence = min(1.0, state.path_divergence + bump)

    def _enrich_tick_result(self, state: GameState, result: TickResult) -> TickResult:
        """Attach player-facing names for API/UI (not used in simulation)."""
        entity_names = {e.id: e.name for e in state.entities}
        region_names = {r.id: r.name for r in state.regions}
        impacts = [
            imp.model_copy(
                update={"entity_name": entity_names.get(imp.entity_id, imp.entity_id)}
            )
            for imp in result.impacts
        ]
        events = [
            ev.model_copy(
                update={
                    "region_name": region_names.get(ev.region_id, ev.region_id or "")
                    if ev.region_id
                    else ""
                }
            )
            for ev in result.events
        ]
        return result.model_copy(update={"impacts": impacts, "events": events})

    def survey_region(
        self, game_id: str, region_id: str
    ) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        region = next((r for r in state.regions if r.id == region_id), None)
        if not region:
            return None

        survey = self.material_engine.survey_region(state, region)
        tick_result = self.simulation.tick(state)
        feedback = survey.feedback + tick_result.feedback
        self._save(state)

        discoveries = [
            {
                "id": d.id,
                "material_id": d.material_id,
                "name": self.material_registry.name_for(d.material_id),
                "description": d.description,
                "abundance": d.abundance,
            }
            for d in survey.discoveries
        ]
        return {
            "discoveries": discoveries,
            "feedback": feedback,
            "game_state": state.model_dump(),
            "turn": state.turn,
        }

    def get_material_context(self, state: GameState, region_id: str | None = None) -> dict:
        region = next(
            (r for r in state.regions if r.id == region_id),
            state.regions[0] if state.regions else None,
        )
        if not region:
            return {}
        discovered = self.material_engine.discovered_materials_for_region(region, state)
        undiscovered_deep = any(
            d.depth == "deep" and not d.discovered for d in region.deposits
        )
        undiscovered_surface = any(
            d.depth == "surface" and not d.discovered for d in region.deposits
        )
        hint_parts: list[str] = []
        if undiscovered_surface:
            hint_parts.append("Survey the cave to learn what the walls hold.")
        if undiscovered_deep:
            hint_parts.append("Deeper walls may hold more — survey or dig.")
        return {
            "absent_materials": [
                {"id": m, "name": self.material_registry.name_for(m)}
                for m in region.absent_materials
            ],
            "discovered_materials": discovered,
            "novel_compounds": [
                {"id": cid, "name": name}
                for cid, name in sorted(state.novel_compounds.items())
            ],
            "undiscovered_hint": " ".join(hint_parts) if hint_parts else "",
            "region_surveyed": region.id in state.surveyed_region_ids,
        }

    def get_lab_options(self, game_id: str, region_id: str | None = None) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        region = next(
            (r for r in state.regions if r.id == region_id),
            state.regions[0] if state.regions else None,
        )
        if not region:
            return None
        materials = self.lab_engine.list_selectable_materials(region, state)
        components = []
        objects = []
        for e in state.entities:
            if not e.operational:
                continue
            if is_component(e):
                components.append(
                    {"id": e.id, "name": e.name, "type": e.type, "tags": e.tags, **component_display(e)}
                )
            elif is_object(e):
                objects.append(
                    {"id": e.id, "name": e.name, "type": e.type, "tags": e.tags, **object_display(e)}
                )
        return {
            "region_id": region.id,
            "materials": materials,
            "components": components,
            "objects": objects,
            "methods": self.method_engine.list_for_ui(state),
        }

    def combine_in_lab(
        self,
        game_id: str,
        region_id: str,
        material_ids: list[str],
        component_ids: list[str] | None = None,
        object_ids: list[str] | None = None,
        entity_ids: list[str] | None = None,
        method_ids: list[str] | None = None,
        intent: str = "",
    ) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        region = next((r for r in state.regions if r.id == region_id), None)
        if not region:
            return None

        components = list(component_ids or entity_ids or [])
        objects = list(object_ids or [])
        methods = list(method_ids or [])

        errors = self.lab_engine.validate_inputs(
            material_ids, components, objects, region, state, method_ids=methods
        )
        if errors:
            return {"error": errors[0], "errors": errors}

        if (
            not material_ids
            and not components
            and not objects
            and len(methods) >= 2
        ):
            if len(methods) != 2:
                return {
                    "error": "Pick exactly two methods to combine into a new process.",
                    "errors": ["Pick exactly two methods to combine into a new process."],
                }
            fusion = self.method_registry.match_fusion(methods)
            if fusion:
                unlock_defn = self.method_registry.get(fusion.unlocks)
                unlock_name = unlock_defn.name if unlock_defn else fusion.unlocks
                if fusion.unlocks in state.known_methods:
                    msg = self.method_engine.fusion_already_known_message(fusion.unlocks)
                    return {"error": msg, "errors": [msg]}
                feedback = [fusion.feedback]
                if self.method_engine.learn(state, fusion.unlocks):
                    feedback.append(f"You learned {unlock_name}.")
                    self._save(state)
                    self.memory.record_event(
                        "method_learned",
                        f"Combined methods to learn {unlock_name}.",
                        [],
                        state.turn,
                        game_id,
                    )
                return {
                    "feedback": feedback,
                    "recipe_match": True,
                    "result_kind": "method",
                    "method_learned": fusion.unlocks,
                    "proposal": None,
                }
            msg = self.method_engine.fusion_unknown_message()
            return {"error": msg, "errors": [msg]}

        recipe = self.lab_engine.match_recipe(
            material_ids, components, objects, state, method_ids=methods
        )
        if recipe:
            if recipe.method and methods and recipe.method not in methods:
                defn = self.method_registry.get(recipe.method)
                name = defn.name if defn else recipe.method
                return {
                    "error": f"Select {name} under Methods for this combination.",
                    "errors": [f"Select {name} under Methods for this combination."],
                }
            method_errors = self.method_engine.validate_recipe_method(state, recipe.method)
            if method_errors:
                return {"error": method_errors[0], "errors": method_errors}
        elif not recipe:
            ai_result = self._interpret_lab_with_ai(
                game_id,
                region_id,
                state,
                region,
                material_ids,
                components,
                objects,
                methods,
                intent,
            )
            if ai_result is not None:
                if ai_result.get("error"):
                    return ai_result
                return ai_result
            unknown_errors = self.method_engine.validate_unknown_combination(state, intent)
            return {"error": unknown_errors[0], "errors": unknown_errors}

        costs, cost_feedback = self.lab_engine.consume_materials(
            state, material_ids, region
        )
        self.material_engine._aggregate_materials_meter(state)
        self._save(state)

        experiment_feedback = list(cost_feedback)
        recipe_match = False
        result_kind = "component"

        if recipe:
            recipe_match = True
            result_kind = recipe.kind
            experiment_feedback.append(recipe.feedback)
            interpret = self.interpret_idea_direct(
                game_id, recipe.proposal, region_id
            )
            if not interpret:
                return None
            state = self.load_game(game_id)
            if state:
                if recipe.unlocks_method:
                    learned = self.method_registry.get(recipe.unlocks_method)
                    if self.method_engine.learn(state, recipe.unlocks_method) and learned:
                        experiment_feedback.append(f"You learned {learned.name}.")
                unlocked = self.method_engine.unlock_from_recipe_type(
                    state, recipe.proposal.type
                )
                if unlocked:
                    experiment_feedback.append(f"You learned {unlocked}.")
                self._save(state)
            return {
                **interpret,
                "feedback": experiment_feedback,
                "material_costs": costs,
                "recipe_match": recipe_match,
                "result_kind": result_kind,
                "prompt": None,
            }

        return None

    def _register_novel_compound(
        self, state: GameState, name: str, tags: list[str], entity_type: str
    ) -> str | None:
        registered = self.material_engine.register_novel_compound(
            state, name, tags, entity_type
        )
        if not registered:
            return None
        _compound_id, feedback = registered
        return feedback

    def _interpret_lab_with_ai(
        self,
        game_id: str,
        region_id: str,
        state: GameState,
        region: Region,
        material_ids: list[str],
        component_ids: list[str],
        object_ids: list[str],
        method_ids: list[str],
        intent: str,
    ) -> dict | None:
        if os.environ.get("LAB_AI_FALLBACK", "true").lower() not in ("1", "true", "yes"):
            return None
        try:
            interpreter = self._get_interpreter()
        except ValueError:
            return None

        method_names = {m.id: m.name for m in self.method_registry.all_methods()}
        combination = self.lab_engine.build_combination_context(
            material_ids,
            component_ids,
            object_ids,
            method_ids,
            state,
            method_names,
            intent,
        )
        mat_ctx = self.get_material_context(state, region_id)
        try:
            verdict = interpreter.interpret_lab_combination(
                combination, state, self.registry, mat_ctx
            )
        except RuntimeError:
            return None

        if not verdict.reasonable or verdict.verdict == "blocked":
            msg = verdict.feedback or "That combination cannot work in this cave."
            return {"error": msg, "errors": [msg]}

        if not verdict.type or not verdict.player_name:
            return None

        proposal = IdeaProposal(
            type=verdict.type,
            tags=verdict.tags,
            capabilities=verdict.capabilities,
            player_name=verdict.player_name,
            reasoning=verdict.reasoning or verdict.feedback,
        )
        normalized = self.capability_engine.normalize(proposal)
        self.auto_approve_pending()
        normalized = self._refresh_queued_keys(normalized)
        constraint = self.constraint_engine.validate_proposal(
            normalized, region, state, speculative=True
        )

        if constraint.status == ConstraintStatus.BLOCKED:
            parts = [verdict.feedback] if verdict.feedback else []
            parts.extend(constraint.hidden_issues)
            parts.extend(constraint.warnings)
            msg = parts[0] if parts else "Blocked by world constraints."
            return {"error": msg, "errors": parts}

        costs, cost_feedback = self.lab_engine.consume_materials(
            state, material_ids, region
        )
        self.material_engine._aggregate_materials_meter(state)
        self._bump_path_divergence(state, proposal.capabilities, proposal.tags)
        compound_fb = self._register_novel_compound(
            state, proposal.player_name, proposal.tags, proposal.type
        )
        self._save(state)

        feedback = list(cost_feedback)
        if verdict.feedback:
            feedback.append(verdict.feedback)
        if compound_fb:
            feedback.append(compound_fb)
        if verdict.verdict == "risky":
            feedback.append("An uncertain experiment — results may surprise you.")
        if constraint.status == ConstraintStatus.NEEDS_TWEAK:
            feedback.append("A rough result — you could refine this idea.")
        for warning in constraint.warnings:
            if warning not in feedback:
                feedback.append(warning)

        tags = classify_entity_tags(
            normalized.tags, normalized.type, normalized.capabilities
        )
        if verdict.result_kind in ("object", "component"):
            result_kind = verdict.result_kind
        elif "object" in tags:
            result_kind = "object"
        else:
            result_kind = "component"

        return {
            "proposal": proposal.model_dump(),
            "normalized": normalized.model_dump(),
            "constraint": constraint.model_dump(),
            "feedback": feedback,
            "material_costs": costs,
            "recipe_match": False,
            "ai_suggested": True,
            "result_kind": result_kind,
            "prompt": combination.get("summary"),
        }

    def tick(self, game_id: str) -> TickResult | None:
        state = self.load_game(game_id)
        if not state:
            return None
        result = self._enrich_tick_result(state, self.simulation.tick(state))
        for event in result.events:
            self.memory.record_event(
                event.type.value,
                event.description,
                [i.model_dump() for i in result.impacts],
                result.turn,
                game_id,
            )
        self._save(state)
        return result

    def get_events(self, game_id: str, limit: int = 20) -> list:
        state = self.load_game(game_id)
        if not state:
            return []
        return [e.model_dump() for e in state.event_log[-limit:]]

    def auto_approve_pending(self) -> int:
        if os.environ.get("AUTO_APPROVE_CAPABILITIES", "false").lower() != "true":
            return 0
        count = 0
        for pending in list(self.registry.list_pending()):
            if self.registry.approve_pending(pending.id):
                count += 1
        return count
