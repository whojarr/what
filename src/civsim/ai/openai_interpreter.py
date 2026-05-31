import json
import logging
import os

from openai import APIError, OpenAI

from civsim.ai.text_normalize import normalize_invention_text
from civsim.models.capabilities import IdeaProposal, LabCombinationVerdict
from civsim.models.world import GameState
from civsim.registry.capability_registry import CapabilityRegistry

logger = logging.getLogger(__name__)

PALEO_SYSTEM_PROMPT = """You interpret invention ideas for a paleolithic cave survival game.

CORE DESIGN: This world rewards things that SEEM like they would work — even if they do not exist in our history yet.
Players fork alternate timelines. New minerals, compounds, and processes can emerge as they experiment.
Judge plausibility in-world (could a clever cave-dweller believe this might work?), not strict real-world archaeology.

The world has four kinds of things:
1. MATERIALS — raw stuff (flint, bone, hide, ore) — not entities you create directly.
2. COMPONENTS — machines that DO something (fire, water, tools, knapped flint).
3. OBJECTS — inanimate things that just ARE (seats, tables, shelters, houses) — tag with "object" plus furniture/structure/shelter/house as appropriate.
4. METHODS — processes you learn (sewing, smelting, cooking/heating, soaking, knapping, chemical mixing). Use type method.* (e.g. method.sewing), tags ["method", "sewing"], minimal capabilities. Methods are knowledge, not physical things.

When inventing a new substance, use type material.* and tags like chemical, compound, mineral, pigment as appropriate.
The player starts with Fire and Water components plus cave materials; heating and soaking are known from the start.
The cave has NO wood, plant fiber, or clay — substitutes or novel compounds are fine if the idea supports them.
Respond with a single JSON object (no markdown) with these fields:
- type: string — use method.* for processes, object.* for inanimate things, tool.* or component.* for machines
- tags: string array — include "method" for processes; "object" OR "component"/tool tags for things, never both
- capabilities: object mapping ONLY allowed capability keys to floats 0.0-1.0
- suggested_capabilities: array of {key, category, meaning, default} for new concepts
- player_name: short display name for THIS THING ONLY — never the game title
- reasoning: one sentence in plain language

Objects: high shelter/social_cohesion/storage only — NO machine unless there is real input/output.
Components (machines): must have meaningful input OR output — warmth/food/water/material demand,
  warmth/food/water/light/hunting output, or tool_craft >= 0.25. Passive shelter alone is an object.
Methods: innovation_rate or tool_craft at low values is fine; focus tags on the process name.
Prefer allowing creative leaps with uncertainty over rejecting ideas that feel plausible in the fiction.
Use ONLY allowed capability keys in capabilities."""


LAB_COMBINE_PROMPT = """You judge discovery-bench experiments in a paleolithic cave survival game.

CORE DESIGN: Reward combinations that SEEM like they would work in fiction — even if no exact recipe exists and even if the result is unknown to our real world.
New minerals and compounds can emerge from successful experiments. Path divergence means history bends.

The player selected materials, machines (components), objects, and/or methods to combine.

Your job: decide if something plausible could emerge, including creative stretches and novel substances (type material.* with chemical/compound/mineral tags when appropriate).

Respond with a single JSON object (no markdown):
- reasonable: boolean — false only when the combo is absurd or self-contradictory
- verdict: "works" | "risky" | "blocked" — risky = plausible-but-uncertain; blocked with reasonable false when it cannot work at all
- feedback: 1-2 sentences in plain language — what happens at the bench, or why it fails
- When reasonable is true, also include:
  - player_name: short name for what emerges
  - type: object.* for inanimate things, tool.* or component.* for machines, material.* for new substances
  - tags: string array (include "object" for inanimate things; chemical/compound for novel substances)
  - capabilities: allowed keys only, floats 0.0-1.0
  - reasoning: one sentence
  - result_kind: "object" or "component"

Rules:
- Honor methods the player selected; require sewing for stitching, heating for heat work, etc.
- Missing an ideal tool can still yield a risky partial result if close (e.g. sewing hide → crude stitched wrap)
- Cave has NO wood, plant fiber, or clay — substitutes and novel compounds are OK
- Reject only truly impossible ideas (spaceships, electricity) — not things that merely haven't been invented yet in OUR world
Use ONLY allowed capability keys in capabilities when proposing a result."""


class OpenAIInterpreter:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required for idea interpretation")
        self.client = OpenAI(api_key=key)
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def interpret(
        self,
        player_text: str,
        world: GameState,
        registry: CapabilityRegistry,
        memory_context: list[str] | None = None,
        material_context: dict | None = None,
    ) -> IdeaProposal:
        fixtures = [
            {
                "type": e.type,
                "tags": e.tags,
                "capabilities": {
                    k: v for k, v in e.capabilities.items() if v > 0.05
                },
            }
            for e in world.entities
            if "component" in e.tags or e.id in ("natural_fire", "natural_spring")
        ]
        context = {
            "era": world.era,
            "path_divergence": world.path_divergence,
            "invention_count": world.invention_count,
            "resources": world.resources.model_dump(),
            "climate": world.climate.model_dump(),
            "turn": world.turn,
            "regions": [
                {
                    "id": r.id,
                    "biome_tags": r.biome_tags,
                    "water_availability": r.water_availability,
                }
                for r in world.regions
            ],
            "components": fixtures,
            "fixtures": fixtures,
            "known_methods": world.known_methods,
            "novel_compounds": world.novel_compounds,
            "materials": material_context or {},
            "allowed_capabilities": registry.allowed_keys(world.era),
            "memory": memory_context or [],
        }
        system = PALEO_SYSTEM_PROMPT if world.era == "paleolithic" else PALEO_SYSTEM_PROMPT
        idea_for_llm, typo_note = normalize_invention_text(player_text)
        user_content = f"Player idea: {idea_for_llm}\n\n"
        if typo_note:
            user_content += f"Typo note: {typo_note}\n\n"
        user_content += f"World context:\n{json.dumps(context, indent=2)}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
            )
        except APIError as e:
            logger.exception("OpenAI API error during idea interpretation")
            raise RuntimeError(f"Idea interpretation failed: {e}") from e

        raw = json.loads(response.choices[0].message.content or "{}")
        caps = {k: float(v) for k, v in raw.get("capabilities", {}).items()}
        try:
            return IdeaProposal(
                type=raw["type"],
                tags=raw.get("tags", []),
                capabilities=caps,
                suggested_capabilities=raw.get("suggested_capabilities", []),
                player_name=raw.get("player_name", "Unnamed Project"),
                reasoning=raw.get("reasoning", ""),
            )
        except Exception as e:
            raise RuntimeError(f"Invalid idea proposal from model: {e}") from e

    def interpret_lab_combination(
        self,
        combination: dict,
        world: GameState,
        registry: CapabilityRegistry,
        material_context: dict | None = None,
    ) -> LabCombinationVerdict:
        context = {
            "era": world.era,
            "turn": world.turn,
            "path_divergence": world.path_divergence,
            "known_methods": world.known_methods,
            "novel_compounds": world.novel_compounds,
            "combination": combination,
            "materials_context": material_context or {},
            "allowed_capabilities": registry.allowed_keys(world.era),
        }
        user_content = (
            "Discovery bench experiment:\n"
            f"{json.dumps(context, indent=2)}"
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": LAB_COMBINE_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
            )
        except APIError as e:
            logger.exception("OpenAI API error during lab combination")
            raise RuntimeError(f"Lab combination interpretation failed: {e}") from e

        raw = json.loads(response.choices[0].message.content or "{}")
        caps = {k: float(v) for k, v in raw.get("capabilities", {}).items()}
        try:
            return LabCombinationVerdict(
                reasonable=bool(raw.get("reasonable", False)),
                verdict=str(raw.get("verdict", "blocked")),
                feedback=str(raw.get("feedback", "")),
                player_name=str(raw.get("player_name", "")),
                type=str(raw.get("type", "")),
                tags=list(raw.get("tags") or []),
                capabilities=caps,
                reasoning=str(raw.get("reasoning", "")),
                result_kind=str(raw.get("result_kind", "component")),
            )
        except Exception as e:
            raise RuntimeError(f"Invalid lab verdict from model: {e}") from e
