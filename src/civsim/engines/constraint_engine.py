from civsim.models.capabilities import ConstraintResult, ConstraintStatus, NormalizedProposal
from civsim.models.entity import EntityCore
from civsim.models.world import DEFAULT_ERA, GameState, Region

ANACHRONISM_TAGS = frozenset({"metal", "electric", "digital", "industrial", "computer"})


class ConstraintEngine:
    """Validates proposals using capabilities, tags, and world context only."""

    def __init__(self, material_engine=None) -> None:
        self._material_engine = material_engine

    def validate_proposal(
        self,
        proposal: NormalizedProposal,
        region: Region,
        world: GameState,
        speculative: bool = False,
    ) -> ConstraintResult:
        if world.era == "paleolithic":
            result = self._validate_paleolithic(proposal, region, world, speculative)
        else:
            result = self._validate_modern(proposal, region, world)
        if speculative and result.status == ConstraintStatus.BLOCKED:
            warnings = list(result.warnings)
            warnings.append("Speculative build — the world bends to let you try.")
            return result.model_copy(
                update={"status": ConstraintStatus.RISKY, "warnings": warnings}
            )
        if speculative and result.status == ConstraintStatus.NEEDS_TWEAK:
            warnings = list(result.warnings)
            warnings.append("Rough but worth attempting — refine as you learn.")
            return result.model_copy(
                update={"status": ConstraintStatus.RISKY, "warnings": warnings}
            )
        return result

    def _validate_paleolithic(
        self,
        proposal: NormalizedProposal,
        region: Region,
        world: GameState,
        speculative: bool = False,
    ) -> ConstraintResult:
        caps = proposal.capabilities
        tags = set(proposal.tags)
        warnings: list[str] = []
        hidden: list[str] = []
        adjustments: list[dict] = []
        status = ConstraintStatus.VALID

        if proposal.dropped_capability_keys:
            warnings.append(
                f"Simplified for this age (ignored): {', '.join(proposal.dropped_capability_keys)}"
            )
            if status == ConstraintStatus.VALID:
                status = ConstraintStatus.RISKY

        if proposal.queued_capability_keys:
            warnings.append(
                f"New concepts pending: {', '.join(proposal.queued_capability_keys)} — "
                "you can still try to build this."
            )
            if status == ConstraintStatus.VALID:
                status = ConstraintStatus.RISKY

        meaningful = sum(1 for v in caps.values() if v > 0.05)
        if meaningful < 2 and not speculative:
            hidden.append("Too few workable strengths — try a clearer, concrete idea.")
            status = ConstraintStatus.NEEDS_TWEAK
        elif meaningful < 2 and speculative:
            warnings.append("A vague experiment — results may be unpredictable.")
            status = ConstraintStatus.RISKY

        uncertainty = caps.get("uncertainty", 0.0)
        if uncertainty > 0.7:
            warnings.append("A wild idea — outcomes may fork history in unexpected ways.")
            if status == ConstraintStatus.VALID:
                status = ConstraintStatus.RISKY

        # Only count non-default modern leakage (fill_defaults may add zeros)
        modern_signal = sum(
            caps.get(k, 0.0)
            for k in ("compute_output", "compute_demand", "energy_output", "cooling")
            if caps.get(k, 0.0) > 0.05
        )
        if modern_signal > 0.25 and uncertainty < 0.6 and not speculative:
            warnings.append("This sounds far beyond your era — the cave may not understand it yet.")
            status = ConstraintStatus.NEEDS_TWEAK
            adjustments.append(
                {"capability": "uncertainty", "suggestion": "raise above 0.6 for a bold leap"}
            )
        elif modern_signal > 0.25 and uncertainty < 0.6 and speculative:
            warnings.append("Far-fetched — but your timeline is already diverging.")
            status = ConstraintStatus.RISKY
        elif modern_signal > 0.25:
            warnings.append("An impossible-seeming leap — history might bend.")
            status = ConstraintStatus.RISKY

        if tags & ANACHRONISM_TAGS and world.path_divergence < 0.1:
            warnings.append("Ideas from another age — you are inventing a different future.")
            status = ConstraintStatus.RISKY

        if caps.get("water_dependency", 0.0) > 0.7 and "spring" not in region.biome_tags:
            if "damp" in region.biome_tags or region.water_availability > 0.4:
                warnings.append("Heavy water needs — the spring helps, but watch droughts.")
            else:
                warnings.append("High water dependency in a dry cave.")
                status = ConstraintStatus.RISKY

        mat_status, mat_warnings, mat_hidden, mat_adjustments = self._validate_materials(
            proposal.tags, region, world, uncertainty, speculative
        )
        warnings.extend(mat_warnings)
        hidden.extend(mat_hidden)
        adjustments.extend(mat_adjustments)
        if mat_status == ConstraintStatus.BLOCKED and not speculative:
            status = ConstraintStatus.BLOCKED
        elif mat_status == ConstraintStatus.NEEDS_TWEAK and status != ConstraintStatus.BLOCKED:
            if speculative or world.path_divergence > 0.08:
                status = ConstraintStatus.RISKY
            else:
                status = ConstraintStatus.NEEDS_TWEAK
        elif mat_status == ConstraintStatus.RISKY and status == ConstraintStatus.VALID:
            status = ConstraintStatus.RISKY

        if status == ConstraintStatus.VALID and warnings:
            status = ConstraintStatus.RISKY

        return ConstraintResult(
            status=status,
            warnings=warnings,
            hidden_issues=hidden,
            suggested_adjustments=adjustments,
        )

    def _validate_materials(
        self,
        tags: list[str],
        region: Region,
        world: GameState,
        uncertainty: float,
        speculative: bool = False,
    ) -> tuple[ConstraintStatus, list[str], list[str], list[dict]]:
        if not self._material_engine:
            return ConstraintStatus.VALID, [], [], []

        engine = self._material_engine
        registry = engine.materials
        warnings: list[str] = []
        hidden: list[str] = []
        adjustments: list[dict] = []
        status = ConstraintStatus.VALID

        required = registry.required_materials(tags)
        for mat_id in required:
            defn = registry.get(mat_id)
            if not defn:
                continue
            name = defn.name

            if mat_id in region.absent_materials:
                subs = [
                    s
                    for s in defn.substitutes
                    if engine.is_material_available(s, region, world)
                ]
                if subs:
                    sub_names = ", ".join(registry.name_for(s) for s in subs)
                    warnings.append(
                        f"No {name} in this cave — try {sub_names} instead."
                    )
                    adjustments.append(
                        {
                            "material": mat_id,
                            "suggestion": f"Use {sub_names} as a local substitute.",
                        }
                    )
                    if status == ConstraintStatus.VALID:
                        status = ConstraintStatus.RISKY
                elif uncertainty < 0.6 and not speculative and world.path_divergence < 0.1:
                    hidden.append(f"No {name} here — timber and plants do not grow in this cave.")
                    status = ConstraintStatus.NEEDS_TWEAK
                    adjustments.append(
                        {
                            "material": mat_id,
                            "suggestion": f"Rework the idea using stone, bone, or wall minerals.",
                        }
                    )
                else:
                    warnings.append(
                        f"No {name} in this cave — you may be inventing a substitute or a new path."
                    )
                    if status == ConstraintStatus.VALID:
                        status = ConstraintStatus.RISKY
                continue

            if not engine.is_material_discovered(mat_id, region, world):
                has_deposit = any(d.material_id == mat_id for d in region.deposits)
                if has_deposit and not speculative:
                    hidden.append(
                        f"{name} may be in the walls, but you haven't found it yet — "
                        "survey or dig deeper."
                    )
                    status = ConstraintStatus.NEEDS_TWEAK
                elif has_deposit:
                    warnings.append(
                        f"{name} might lurk in the walls — you're experimenting ahead of proof."
                    )
                    if status == ConstraintStatus.VALID:
                        status = ConstraintStatus.RISKY
                continue

            abundance = engine.deposit_abundance(mat_id, region)
            if 0 < abundance <= 0.25:
                warnings.append(f"{name} is scarce here.")
                if status == ConstraintStatus.VALID:
                    status = ConstraintStatus.RISKY

        return status, warnings, hidden, adjustments

    def _validate_modern(
        self,
        proposal: NormalizedProposal,
        region: Region,
        world: GameState,
    ) -> ConstraintResult:
        caps = proposal.capabilities
        tags = set(proposal.tags)
        warnings: list[str] = []
        hidden: list[str] = []
        adjustments: list[dict] = []
        status = ConstraintStatus.VALID

        if proposal.queued_capability_keys:
            hidden.append(
                f"Unknown capabilities queued for approval: {', '.join(proposal.queued_capability_keys)}"
            )
            status = ConstraintStatus.NEEDS_TWEAK

        water_dep = caps.get("water_dependency", 0.0)
        if water_dep > 0.7 and "arid" in region.biome_tags:
            warnings.append("High water dependency in arid region.")
            status = ConstraintStatus.RISKY

        if "storm_exposed" in tags and caps.get("storm_resistance", 0.3) < 0.4:
            warnings.append("Storm-exposed placement with low storm resistance.")
            status = ConstraintStatus.RISKY

        energy_demand = caps.get("energy_demand", 0.0)
        if energy_demand > region.energy_ceiling:
            hidden.append("Energy demand exceeds regional energy ceiling.")
            status = ConstraintStatus.BLOCKED

        if status == ConstraintStatus.VALID and warnings:
            status = ConstraintStatus.RISKY

        return ConstraintResult(
            status=status,
            warnings=warnings,
            hidden_issues=hidden,
            suggested_adjustments=adjustments,
        )

    def validate_entity_core(self, core: EntityCore, region: Region, world: GameState) -> ConstraintResult:
        from civsim.models.capabilities import NormalizedProposal

        proposal = NormalizedProposal(
            type=core.type,
            tags=core.tags,
            capabilities=core.capabilities,
        )
        return self.validate_proposal(proposal, region, world)
