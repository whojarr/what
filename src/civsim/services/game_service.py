import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

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
    classification_reason,
    component_display,
    entity_available_at_lab,
    entity_kind,
    is_component,
    is_object,
    lab_accessible_region_ids,
    material_travel_capacity,
    object_display,
    partition_for_travel,
    transfer_materials_on_travel,
)
from civsim.models.entity import Entity, EntityDraft
from civsim.models.world import (
    CompoundProvenance,
    DEFAULT_ERA,
    GameState,
    NovelCompound,
    Region,
    TickResult,
    novel_compound_name,
)
from civsim.registry.capability_registry import CapabilityRegistry
from civsim.registry.material_registry import MaterialRegistry
from civsim.registry.method_registry import MethodRegistry
from civsim.registry.scene_registry import SceneRegistry
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
        self.lab_engine.material_engine = self.material_engine
        self.capability_engine = CapabilityEngine(registry)
        self.constraint_engine = ConstraintEngine(self.material_engine)
        self.event_system = EventSystem(registry)
        self.simulation = SimulationEngine(registry, self.event_system, self.material_engine)
        self.world_gen = WorldGenerator()
        self._interpreter: OpenAIInterpreter | None = None
        if self.data_dir:
            self.scene_registry = SceneRegistry.load_for_era(DEFAULT_ERA, self.data_dir)
            scenes_path = self.data_dir / f"scenes_{DEFAULT_ERA}.yaml"
            try:
                self._scenes_mtime = scenes_path.stat().st_mtime
            except OSError:
                self._scenes_mtime = None
        else:
            self.scene_registry = SceneRegistry(1, {"default": {}})
            self._scenes_mtime = None

    def ensure_scene_registry(self) -> None:
        """Reload scene templates when scenes YAML changes (dev-friendly)."""
        if not self.data_dir:
            return
        path = self.data_dir / f"scenes_{DEFAULT_ERA}.yaml"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if self._scenes_mtime is not None and mtime == self._scenes_mtime:
            return
        self.scene_registry = SceneRegistry.load_for_era(DEFAULT_ERA, self.data_dir)
        self._scenes_mtime = mtime
        if self._interpreter is None:
            self._interpreter = OpenAIInterpreter()
        return self._interpreter

    @staticmethod
    def normalize_world_name(name: str | None) -> str:
        cleaned = (name or "").strip()
        if not cleaned:
            return "Untitled world"
        return cleaned[:80]

    def create_game(self, seed: int = 42, name: str | None = None) -> GameState:
        state = self.world_gen.generate(seed)
        state.name = self.normalize_world_name(name)
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

    def list_saves(self) -> list[dict]:
        summaries: list[dict] = []
        for path in self.saves_path.glob("*.json"):
            try:
                mtime = path.stat().st_mtime
                with path.open() as f:
                    data = json.load(f)
                state = GameState.model_validate(data)
            except (OSError, json.JSONDecodeError, ValidationError):
                continue
            primary_region = state.regions[0].name if state.regions else ""
            summaries.append(
                {
                    "id": state.id,
                    "name": state.name,
                    "turn": state.turn,
                    "rng_seed": state.rng_seed,
                    "era": state.era,
                    "invention_count": state.invention_count,
                    "primary_region": primary_region,
                    "saved_at": datetime.fromtimestamp(mtime, tz=UTC).isoformat(),
                }
            )
        summaries.sort(key=lambda s: s["saved_at"], reverse=True)
        return summaries

    def delete_game(self, game_id: str) -> bool:
        path = self.saves_path / f"{game_id}.json"
        if not path.exists():
            return False
        path.unlink()
        records = getattr(self.memory, "_records", None)
        if records is not None:
            records.pop(game_id, None)
        return True

    def resolve_visual_subject(
        self, game_id: str, subject_type: str, subject_id: str
    ) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        era = state.era
        st = subject_type.lower().strip()
        if st in ("material", "stock"):
            name = self.material_registry.name_for(subject_id)
            blurb = self._BASELINE_MATERIAL_BLURBS.get(subject_id, "")
            uses = self._BASELINE_MATERIAL_USES.get(subject_id, "")
            hint = blurb or uses or "Raw material for crafting."
            return {
                "type": st,
                "id": subject_id,
                "name": name,
                "hint": hint,
                "era": era,
            }
        if st == "compound":
            entry = state.novel_compounds.get(subject_id)
            if not entry:
                return None
            return {
                "type": "compound",
                "id": subject_id,
                "name": novel_compound_name(entry),
                "hint": "A novel compound discovered at the discovery bench.",
                "era": era,
            }
        if st in ("component", "object"):
            entity = next((e for e in state.entities if e.id == subject_id), None)
            if not entity:
                return None
            display = component_display(entity) if st == "component" else object_display(entity)
            return {
                "type": st,
                "id": subject_id,
                "name": display["label"],
                "hint": display.get("hint") or "",
                "era": era,
            }
        if st == "region":
            region = next((r for r in state.regions if r.id == subject_id), None)
            if not region:
                return None
            return {
                "type": "region",
                "id": region.id,
                "name": region.name,
                "hint": ", ".join(region.biome_tags) or "Paleolithic landscape.",
                "era": era,
            }
        return None

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

    def rename_game(self, game_id: str, name: str) -> GameState | None:
        state = self.load_game(game_id)
        if not state:
            return None
        state.name = self.normalize_world_name(name)
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
        classified_tags = classify_entity_tags(draft.tags, draft.type, draft.capabilities)
        preview = Entity(
            id="__preview__",
            name=draft.name,
            type=draft.type,
            tags=classified_tags,
            capabilities=draft.capabilities,
            region_id=draft.region_id,
        )
        kind = entity_kind(preview)
        name_key = draft.name.lower().strip()
        for existing in state.entities:
            if existing.region_id != draft.region_id:
                continue
            if existing.name.lower().strip() != name_key:
                continue
            if entity_kind(existing) != kind:
                continue
            self.memory.record_idea(
                draft.name, existing.id, result.status.value, state.turn, game_id
            )
            return existing, result, None, None

        entity = Entity(
            id=entity_id,
            name=draft.name,
            type=draft.type,
            tags=classified_tags,
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
            state,
            draft.name,
            entity.tags,
            entity.type,
            region_id=draft.region_id,
            provenance=self._build_compound_provenance(state, source="invent"),
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
        exit_feedback: list[str] = []
        for passage in region.exits:
            if not passage.discovered:
                passage.discovered = True
                exit_feedback.append(
                    f"You find {passage.name.lower()}: {passage.description}"
                )
        tick_result = self.simulation.tick(state)
        feedback = exit_feedback + survey.feedback + tick_result.feedback
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
                {"id": cid, "name": novel_compound_name(entry)}
                for cid, entry in sorted(state.novel_compounds.items())
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
        materials = self.material_engine.list_lab_materials(region, state)
        accessible = lab_accessible_region_ids(region)
        region_names = {r.id: r.name for r in state.regions}
        components = []
        objects = []
        for e in state.entities:
            if not entity_available_at_lab(e, region, accessible):
                continue
            if is_component(e):
                item = {
                    "id": e.id,
                    "name": e.name,
                    "type": e.type,
                    "tags": e.tags,
                    **component_display(e),
                }
                if e.region_id != region.id:
                    item["region_id"] = e.region_id
                    item["region_name"] = region_names.get(e.region_id, e.region_id)
                    item["hint"] = (
                        f"{item.get('hint', '')} · In {item['region_name']}"
                    ).strip(" · ")
                components.append(item)
            elif is_object(e):
                item = {
                    "id": e.id,
                    "name": e.name,
                    "type": e.type,
                    "tags": e.tags,
                    **object_display(e),
                }
                if e.region_id != region.id:
                    item["region_id"] = e.region_id
                    item["region_name"] = region_names.get(e.region_id, e.region_id)
                    item["hint"] = (
                        f"{item.get('hint', '')} · In {item['region_name']}"
                    ).strip(" · ")
                objects.append(item)
        return {
            "region_id": region.id,
            "region_name": region.name,
            "materials": materials,
            "components": self._collapse_named_items(components),
            "objects": self._collapse_named_items(objects),
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
        self,
        state: GameState,
        name: str,
        tags: list[str],
        entity_type: str,
        *,
        region_id: str,
        provenance: CompoundProvenance | None = None,
    ) -> str | None:
        registered = self.material_engine.register_novel_compound(
            state,
            name,
            tags,
            entity_type,
            region_id=region_id,
            provenance=provenance,
        )
        if not registered:
            return None
        _compound_id, feedback = registered
        return feedback

    def _build_compound_provenance(
        self,
        state: GameState,
        *,
        source: str,
        material_ids: list[str] | None = None,
        component_ids: list[str] | None = None,
        object_ids: list[str] | None = None,
        method_ids: list[str] | None = None,
        intent: str = "",
        recipe_id: str | None = None,
    ) -> CompoundProvenance:
        return CompoundProvenance(
            materials=list(material_ids or []),
            components=list(component_ids or []),
            objects=list(object_ids or []),
            methods=list(method_ids or []),
            intent=intent or "",
            turn=state.turn,
            source=source,  # type: ignore[arg-type]
            recipe_id=recipe_id,
        )

    def _provenance_public(self, state: GameState, prov: CompoundProvenance) -> dict:
        entity_names = {e.id: e.name for e in state.entities}
        method_names = {m.id: m.name for m in self.method_registry.all_methods()}

        def names(ids: list[str], lookup: dict[str, str], fallback_prefix: str) -> list[dict]:
            return [{"id": i, "name": lookup.get(i, i.replace("_", " ").title())} for i in ids]

        materials = names(
            prov.materials,
            {mid: self.material_engine.name_for(mid, state) for mid in prov.materials},
            "material",
        )
        components = names(prov.components, entity_names, "component")
        objects = names(prov.objects, entity_names, "object")
        methods = names(prov.methods, method_names, "method")

        parts: list[str] = []
        parts.extend(m["name"] for m in materials)
        parts.extend(c["name"] for c in components)
        parts.extend(o["name"] for o in objects)
        if methods:
            parts.append("via " + " + ".join(m["name"] for m in methods))
        if prov.intent:
            parts.append(f'("{prov.intent}")')

        return {
            "source": prov.source,
            "turn": prov.turn,
            "intent": prov.intent,
            "recipe_id": prov.recipe_id,
            "materials": materials,
            "components": components,
            "objects": objects,
            "methods": methods,
            "summary": " + ".join(parts) if parts else "",
        }

    def _compound_public(self, state: GameState, compound_id: str, entry: NovelCompound) -> dict:
        prov = entry.provenance
        public_prov = self._provenance_public(state, prov)
        has_inputs = bool(
            prov.materials or prov.components or prov.objects or prov.methods or prov.intent
        )
        return {
            "id": compound_id,
            "name": entry.name,
            "description": "A novel compound you discovered by combining materials at the bench.",
            "uses": "Use as an ingredient in further experiments.",
            "provenance": public_prov,
            "made_from": public_prov["summary"],
            "has_provenance": has_inputs,
        }

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
            state,
            proposal.player_name,
            proposal.tags,
            proposal.type,
            region_id=region.id,
            provenance=self._build_compound_provenance(
                state,
                source="lab",
                material_ids=material_ids,
                component_ids=component_ids,
                object_ids=object_ids,
                method_ids=method_ids,
                intent=intent,
            ),
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

    def travel_to_region(
        self, game_id: str, target_region_id: str, from_region_id: str | None = None
    ) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        from_region = self._world_region(state, from_region_id)
        target = next((r for r in state.regions if r.id == target_region_id), None)
        if not from_region or not target:
            return None

        passage = next(
            (e for e in from_region.exits if e.target_region_id == target_region_id),
            None,
        )
        if not passage or not passage.discovered:
            return {
                "error": "You have not found a way there yet.",
                "errors": ["You have not found a way there yet. Survey the area first."],
            }

        passage.accessible = True
        return_passage = next(
            (e for e in target.exits if e.target_region_id == from_region.id),
            None,
        )
        if return_passage:
            return_passage.discovered = True
            return_passage.accessible = True

        carried_entities, left_behind = partition_for_travel(state.entities, from_region.id)
        had_stored_materials = any(
            amt > 0.02
            for amt in state.region_material_stocks.get(from_region.id, {}).values()
        )
        moved_materials = transfer_materials_on_travel(
            state.region_material_stocks,
            from_region.id,
            target.id,
            set(target.absent_materials),
            carried_entities,
        )
        materials_hauled: list[str] = []
        for mat_id, _amount in moved_materials:
            materials_hauled.append(self.material_registry.name_for(mat_id))

        carried: list[str] = []
        for entity in carried_entities:
            entity.region_id = target.id
            carried.append(entity.name)

        feedback = [f"You reach {target.name} through {passage.name.lower()}."]
        if carried:
            if len(carried) == 1:
                feedback.append(f"You bring {carried[0]} with you.")
            elif len(carried) <= 4:
                feedback.append(f"You bring {', '.join(carried)} with you.")
            else:
                feedback.append(
                    f"You bring {', '.join(carried[:3])}, and {len(carried) - 3} more with you."
                )
        if left_behind:
            if len(left_behind) == 1:
                feedback.append(f"You leave {left_behind[0].name} behind — no room to carry more.")
            elif len(left_behind) <= 3:
                feedback.append(
                    f"You leave {', '.join(e.name for e in left_behind)} behind — pack full."
                )
            else:
                feedback.append(
                    f"You leave {left_behind[0].name}, {left_behind[1].name}, "
                    f"and {len(left_behind) - 2} more behind — pack full."
                )
        if materials_hauled:
            if len(materials_hauled) == 1:
                feedback.append(f"You haul {materials_hauled[0]} in your pack.")
            elif len(materials_hauled) <= 3:
                feedback.append(f"You haul {', '.join(materials_hauled)} in your pack.")
            else:
                feedback.append(
                    f"You haul {', '.join(materials_hauled[:2])}, "
                    f"and {len(materials_hauled) - 2} more in your pack."
                )
        elif had_stored_materials and material_travel_capacity(carried_entities, from_region.id) <= 0.001:
            feedback.append(
                "Bulk materials stay behind — craft a pack or basket to haul them."
            )

        self._save(state)
        return {
            "region_id": target.id,
            "region_name": target.name,
            "from_region_id": from_region.id,
            "from_region_name": from_region.name,
            "carried": carried,
            "left_behind": [e.name for e in left_behind],
            "materials_hauled": materials_hauled,
            "feedback": feedback,
        }

    _BASELINE_MATERIAL_META: dict[str, dict[str, str]] = {
        "bone": {"name": "Bone", "badge": "scavenging"},
        "hide": {"name": "Hide", "badge": "hunting"},
        "dung": {"name": "Dried dung", "badge": "fuel"},
        "wood": {"name": "Wood", "badge": "foraging"},
        "plant_fiber": {"name": "Plant fiber", "badge": "gathering"},
        "clay": {"name": "Clay", "badge": "earth"},
    }

    _BASELINE_MATERIAL_BLURBS = {
        "bone": "Scavenged from carcasses — sharp fragments, needles, and awls.",
        "hide": "From hunting — leather, cordage, and weatherproof layers.",
        "dung": "Collected as slow-burning fuel for fire and heat.",
        "wood": "Branches and deadfall from the open slope — fuel and structure.",
        "plant_fiber": "Grasses and bark strips — cordage and weaving.",
        "clay": "Soft earth at the surface — pottery and binding when fired.",
    }

    _BASELINE_MATERIAL_USES = {
        "bone": "Tools, needles, points, and structural bits.",
        "hide": "Cordage, garments, shelter skins, and binding.",
        "dung": "Fuel for cooking, warmth, and firing clay.",
        "wood": "Handles, fuel, frames, and digging tools.",
        "plant_fiber": "Twine, weaving, binding, and soft layers.",
        "clay": "Pottery, cement-like mixes, and molded forms.",
    }

    def _baseline_items_for_region(self, region: Region) -> list[dict]:
        items: list[dict] = []
        for mid in region.always_available:
            meta = self._BASELINE_MATERIAL_META.get(mid, {})
            items.append(
                self._material_registry_detail(
                    mid,
                    name=meta.get("name") or self.material_registry.name_for(mid),
                    badge=meta.get("badge", "nearby"),
                    source="baseline",
                    description=self._BASELINE_MATERIAL_BLURBS.get(mid, ""),
                    uses=self._BASELINE_MATERIAL_USES.get(mid, ""),
                    obtain=f"Always available — {meta.get('badge', 'nearby')}",
                )
            )
        return items

    def _region_public(self, region: Region) -> dict:
        return {
            "id": region.id,
            "name": region.name,
            "biome_tags": region.biome_tags,
        }

    def _exits_public(self, state: GameState, region: Region) -> list[dict]:
        region_names = {r.id: r.name for r in state.regions}
        exits: list[dict] = []
        for passage in region.exits:
            status = "hidden"
            if passage.discovered and passage.accessible:
                status = "open"
            elif passage.discovered:
                status = "found"
            exits.append(
                {
                    "id": passage.id,
                    "name": passage.name,
                    "target_region_id": passage.target_region_id,
                    "target_region_name": region_names.get(
                        passage.target_region_id, passage.target_region_id
                    ),
                    "description": passage.description,
                    "discovered": passage.discovered,
                    "accessible": passage.accessible,
                    "status": status,
                }
            )
        return exits

    def _material_registry_detail(self, material_id: str, **extra: object) -> dict:
        defn = self.material_registry.get(material_id)
        item = {
            "id": material_id,
            "name": self.material_registry.name_for(material_id),
            "tags": sorted(defn.tags) if defn else [],
            "substitutes": self.material_registry.substitute_names(material_id),
            "implicit": self.material_registry.is_implicit(material_id) if defn else False,
        }
        item.update(extra)
        return item

    def _world_region(self, state: GameState, region_id: str | None) -> Region | None:
        if region_id:
            return next((r for r in state.regions if r.id == region_id), None)
        return state.regions[0] if state.regions else None

    def get_world_overview(self, game_id: str, region_id: str | None = None) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        region = self._world_region(state, region_id)
        if not region:
            return None
        return {
            "game_id": state.id,
            "turn": state.turn,
            "era": state.era,
            "path_divergence": state.path_divergence,
            "invention_count": state.invention_count,
            "resources": state.resources.model_dump(),
            "region": self._region_public(region),
            "regions": [self._region_public(r) for r in state.regions],
            "exits": self._exits_public(state, region),
        }

    def get_world_scene(self, game_id: str, region_id: str | None = None) -> dict | None:
        self.ensure_scene_registry()
        state = self.load_game(game_id)
        if not state:
            return None
        region = self._world_region(state, region_id)
        if not region:
            return None
        template_id, template = self.scene_registry.resolve(region.id, region.biome_tags)
        components = self.get_world_components(game_id, region.id) or {"items": []}
        objects = self.get_world_objects(game_id, region.id) or {"items": []}
        slot_entities = self._bind_scene_slot_entities(template, components, objects)
        exits = self._exits_public(state, region)
        panorama_crops: dict[str, dict[str, float]] = {}
        if (template.get("assets") or {}).get("panorama"):
            scene_mode = self.scene_registry.panorama_mode(template_id)
            if scene_mode == "single_scene":
                surfaces = []
                panorama_crops = self.scene_registry.panorama_crops(template_id)
            else:
                surfaces = self._scene_surfaces_panorama(
                    template_id, template, region
                )
        else:
            scene_mode = "legacy"
            surfaces = self._scene_surfaces(template_id, template, region, exits)
        return {
            "game_id": state.id,
            "template_id": template_id,
            "template_version": self.scene_registry.version,
            "scene_mode": scene_mode,
            "region": self._region_public(region),
            "camera": template.get("camera") or {},
            "environment": template.get("environment") or {},
            "slots": template.get("slots") or {},
            "exit_layout": template.get("exits") or {},
            "slot_entities": slot_entities,
            "exits": exits,
            "surfaces": surfaces,
            "panorama_crops": panorama_crops,
        }

    def _exit_target_region_id(
        self, exits: list[dict] | None, region: Region
    ) -> str | None:
        if exits:
            for status in ("open", "found"):
                for passage in exits:
                    if passage.get("status") == status:
                        target = passage.get("target_region_id")
                        if target:
                            return target
        if region.exits:
            return region.exits[0].target_region_id
        return None

    def _scene_surfaces_panorama(
        self, template_id: str, template: dict, region: Region
    ) -> list[dict]:
        env = template.get("environment") or {}
        layouts = env.get("surfaces") or []
        wall_crops = self.scene_registry.panorama_wall_crops(template_id)
        hint = ", ".join(region.biome_tags) or "Paleolithic landscape."
        has_fixed_floor = bool(
            self.scene_registry.panorama_floor_prompt(template_id, region.name, hint)
        )
        template_version = self.scene_registry.version
        result: list[dict] = []
        for layout in layouts:
            surface_id = layout.get("id")
            if not surface_id:
                continue
            if surface_id == "floor" and has_fixed_floor:
                result.append(
                    {
                        "id": "floor",
                        "panorama": False,
                        "visual_type": "region",
                        "visual_id": region.id,
                        "params": {
                            "context": "scene",
                            "template_id": template_id,
                            "surface": "floor",
                            "region_id": region.id,
                            "template_version": template_version,
                        },
                    }
                )
                continue
            if surface_id not in wall_crops:
                continue
            result.append(
                {
                    "id": surface_id,
                    "panorama": True,
                    "params": {
                        "template_id": template_id,
                        "region_id": region.id,
                        "surface": surface_id,
                        "template_version": template_version,
                    },
                }
            )
        return result

    def _scene_surfaces(
        self,
        template_id: str,
        template: dict,
        region: Region,
        exits: list[dict] | None = None,
    ) -> list[dict]:
        region_id = region.id
        env = template.get("environment") or {}
        layouts = env.get("surfaces") or []
        asset_surfaces = (template.get("assets") or {}).get("surfaces") or {}
        backdrop = (template.get("assets") or {}).get("backdrop")
        if not layouts and backdrop:
            layouts = [{"id": "back", "size": [12, 5], "position": [0, 2.5, -4], "rotation": [0, 0, 0]}]
        result: list[dict] = []
        for layout in layouts:
            surface_id = layout.get("id")
            if not surface_id:
                continue
            spec = asset_surfaces.get(surface_id)
            if not spec and surface_id == "back" and backdrop:
                spec = backdrop
            if not spec:
                continue
            standard_visual = bool(spec.get("standard_visual"))
            source = spec.get("source")
            if source == "exit_target":
                visual_id = self._exit_target_region_id(exits, region) or region_id
                standard_visual = True
            else:
                visual_id = region_id
            if not standard_visual and not spec.get("prompt"):
                continue
            derived_from = spec.get("derived_from")
            entry: dict = {
                "id": surface_id,
                "size": layout.get("size") or [10, 5],
                "position": layout.get("position") or [0, 0, 0],
                "rotation": layout.get("rotation") or [0, 0, 0],
                "visual_type": "region",
                "visual_id": visual_id,
                "standard_visual": standard_visual,
            }
            if derived_from:
                entry["derived_from"] = derived_from
            if standard_visual:
                entry["params"] = {"region_id": region_id}
            else:
                params: dict = {
                    "context": "scene",
                    "template_id": template_id,
                    "surface": surface_id,
                    "region_id": region_id,
                }
                if derived_from:
                    params["derived_from"] = derived_from
                entry["params"] = params
            result.append(entry)
        return result

    def _bind_scene_slot_entities(
        self, template: dict, components: dict, objects: dict
    ) -> list[dict]:
        slots = template.get("slots") or {}
        comp_items = components.get("items") or []
        obj_items = objects.get("items") or []
        bound: list[dict] = []
        for slot_name, slot_def in slots.items():
            bind = slot_def.get("bind") or {}
            kind = bind.get("kind")
            role = bind.get("role")
            pool: list[dict] = []
            if kind == "component":
                pool = comp_items
            elif kind == "object":
                pool = obj_items
            else:
                pool = comp_items + obj_items
            match = None
            for item in pool:
                display = item.get("display") or {}
                item_role = display.get("role") or item.get("role")
                if role and item_role == role:
                    match = item
                    break
            if not match:
                continue
            entity_kind = kind
            if not entity_kind:
                entity_kind = "component" if match in comp_items else "object"
            bound.append(
                {
                    "slot": slot_name,
                    "id": match["id"],
                    "name": match["name"],
                    "kind": entity_kind,
                    "primitive": slot_def.get("primitive") or "default",
                    "position": slot_def.get("position") or [0, 0, 0],
                }
            )
        return bound

    def get_world_materials_absent(self, game_id: str, region_id: str | None = None) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        region = self._world_region(state, region_id)
        if not region:
            return None
        return {
            "region_id": region.id,
            "items": [
                {"id": m, "name": self.material_registry.name_for(m)}
                for m in region.absent_materials
            ],
        }

    def get_world_materials_available(
        self, game_id: str, region_id: str | None = None
    ) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        region = self._world_region(state, region_id)
        if not region:
            return None
        items = self._baseline_items_for_region(region)
        for deposit in region.deposits:
            if not deposit.discovered:
                continue
            mid = deposit.material_id
            if not self.material_engine.is_material_available(mid, region, state):
                continue
            depth_hint = (
                "Survey found this in the cave walls."
                if deposit.depth == "surface"
                else "Deep deposit — mining or excavation tools help."
            )
            items.append(
                self._material_registry_detail(
                    mid,
                    source="deposit",
                    abundance=deposit.abundance,
                    depth=deposit.depth,
                    description=deposit.description or depth_hint,
                    obtain=depth_hint,
                )
            )
        hidden_surface = any(
            d.depth == "surface" and not d.discovered for d in region.deposits
        )
        hidden_deep = any(d.depth == "deep" and not d.discovered for d in region.deposits)
        hints: list[str] = []
        if hidden_surface:
            hints.append("Survey the cave to find more in the walls.")
        if hidden_deep:
            hints.append("Dig or invent mining tools to reach deeper deposits.")
        return {
            "region_id": region.id,
            "items": items,
            "undiscovered_hint": " ".join(hints),
        }

    def get_world_materials_stocks(
        self, game_id: str, region_id: str | None = None
    ) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        region = self._world_region(state, region_id)
        if not region:
            return None
        regional = self.material_engine.region_stocks(state, region.id)
        stocks = [
            self._material_registry_detail(
                mat_id,
                stock=stock,
                storage_note=(
                    "Running low — survey, scavenge, or combine to refill."
                    if stock < 0.25
                    else "Moderate supply — keep gathering or experimenting."
                    if stock < 0.6
                    else "Well stocked for discovery bench work."
                ),
            )
            for mat_id, stock in sorted(regional.items())
            if stock > 0.01
        ]
        compounds = [
            self._compound_public(state, cid, entry)
            for cid, entry in sorted(state.novel_compounds.items())
            if self.material_engine.stock_at(state, region.id, cid) > 0.01
        ]
        return {
            "region_id": region.id,
            "stocks": stocks,
            "compounds": compounds,
        }

    def _world_entity_item(self, entity: Entity, state: GameState, display: dict) -> dict:
        region_names = {r.id: r.name for r in state.regions}
        caps = entity.capabilities or {}
        active_caps = {
            k: round(v, 3)
            for k, v in sorted(caps.items())
            if v > 0.05
        }
        kind = entity_kind(entity)
        return {
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "tags": entity.tags,
            "health": entity.health,
            "operational": entity.operational,
            "region_id": entity.region_id,
            "region_name": region_names.get(entity.region_id, entity.region_id),
            "capabilities": entity.capabilities,
            "active_capabilities": active_caps,
            "classification": classification_reason(caps),
            "entity_kind": kind,
            "display": display,
            "status_note": (
                "Working normally."
                if entity.operational
                else "Offline or damaged — repair or rebuild may be needed."
            ),
        }

    def _collapse_named_items(self, items: list[dict]) -> list[dict]:
        """Merge same-name entries (e.g. repeated lab results)."""
        grouped: dict[str, dict] = {}
        for item in items:
            key = item["name"].lower().strip()
            if key not in grouped:
                grouped[key] = {**item, "count": 1, "instance_ids": [item["id"]]}
                continue
            entry = grouped[key]
            entry["count"] += 1
            entry["instance_ids"].append(item["id"])
            if "health" in entry and "health" in item:
                entry["health"] = max(entry["health"], item["health"])
            if "operational" in entry and "operational" in item:
                entry["operational"] = entry["operational"] and item["operational"]
            if entry.get("type", "").endswith(".*") and not item.get("type", "").endswith(".*"):
                for field in (
                    "type",
                    "id",
                    "tags",
                    "capabilities",
                    "display",
                    "role",
                    "label",
                    "hint",
                    "kind",
                ):
                    if field in item:
                        entry[field] = item[field]
        return list(grouped.values())

    def _collapse_world_items(self, items: list[dict]) -> list[dict]:
        return self._collapse_named_items(items)

    def get_world_components(self, game_id: str, region_id: str | None = None) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        region = self._world_region(state, region_id)
        if not region:
            return None
        items = self._collapse_world_items([
            self._world_entity_item(e, state, component_display(e))
            for e in state.entities
            if is_component(e) and e.region_id == region.id
        ])
        return {"region_id": region.id, "items": items}

    def get_world_objects(self, game_id: str, region_id: str | None = None) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        region = self._world_region(state, region_id)
        if not region:
            return None
        items = self._collapse_world_items([
            self._world_entity_item(e, state, object_display(e))
            for e in state.entities
            if is_object(e) and e.region_id == region.id
        ])
        return {"region_id": region.id, "items": items}

    def get_entity(self, game_id: str, entity_id: str) -> dict | None:
        state = self.load_game(game_id)
        if not state:
            return None
        entity = next((e for e in state.entities if e.id == entity_id), None)
        if not entity:
            return None
        if is_component(entity):
            kind = "component"
            display = component_display(entity)
        elif is_object(entity):
            kind = "object"
            display = object_display(entity)
        else:
            kind = "entity"
            display = {"label": entity.name, "hint": "", "role": None, "kind": None}
        item = self._world_entity_item(entity, state, display)
        item["kind"] = kind
        return item

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
