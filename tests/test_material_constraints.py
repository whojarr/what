from pathlib import Path

from civsim.engines.constraint_engine import ConstraintEngine
from civsim.engines.material_engine import MaterialEngine
from civsim.models.capabilities import ConstraintStatus, NormalizedProposal
from civsim.registry.material_registry import MaterialRegistry
from civsim.world.generator import WorldGenerator

ROOT = Path(__file__).resolve().parent.parent


def _engine() -> ConstraintEngine:
    mat_reg = MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    return ConstraintEngine(MaterialEngine(mat_reg))


def test_charcoal_needs_tweak_without_wood():
    engine = _engine()
    world = WorldGenerator().generate(1)
    region = world.regions[0]
    proposal = NormalizedProposal(
        type="fuel.charcoal",
        tags=["charcoal", "fuel", "fire"],
        capabilities={"warmth_output": 0.6, "tool_craft": 0.2, "storage": 0.3},
    )
    result = engine.validate_proposal(proposal, region, world)
    assert result.status in (ConstraintStatus.NEEDS_TWEAK, ConstraintStatus.RISKY)
    combined = " ".join(result.hidden_issues + result.warnings).lower()
    assert "wood" in combined or "bone" in combined or "dung" in combined


def test_iron_needs_survey_first():
    engine = _engine()
    world = WorldGenerator().generate(1)
    region = world.regions[0]
    proposal = NormalizedProposal(
        type="tool.iron",
        tags=["metal", "iron", "ore"],
        capabilities={"tool_craft": 0.7, "hunting": 0.2, "uncertainty": 0.3},
    )
    result = engine.validate_proposal(proposal, region, world)
    assert result.status == ConstraintStatus.NEEDS_TWEAK
    assert any("found it yet" in h.lower() or "survey" in h.lower() for h in result.hidden_issues)


def test_bone_tools_valid_in_cave():
    engine = _engine()
    world = WorldGenerator().generate(1)
    region = world.regions[0]
    proposal = NormalizedProposal(
        type="tool.bone",
        tags=["bone", "stone"],
        capabilities={"tool_craft": 0.6, "hunting": 0.3, "shelter": 0.2},
    )
    result = engine.validate_proposal(proposal, region, world)
    assert result.status in (ConstraintStatus.VALID, ConstraintStatus.RISKY)


def test_flint_tools_valid_after_start():
    engine = _engine()
    world = WorldGenerator().generate(1)
    region = world.regions[0]
    proposal = NormalizedProposal(
        type="tool.flint",
        tags=["flint", "sharp", "blade"],
        capabilities={"tool_craft": 0.7, "hunting": 0.4},
    )
    result = engine.validate_proposal(proposal, region, world)
    assert result.status in (ConstraintStatus.VALID, ConstraintStatus.RISKY)


def test_speculative_mode_allows_experimental_leaps():
    engine = _engine()
    world = WorldGenerator().generate(1)
    region = world.regions[0]
    proposal = NormalizedProposal(
        type="material.cave_varnish",
        tags=["chemical", "compound", "varnish"],
        capabilities={"tool_craft": 0.3, "innovation_rate": 0.4, "uncertainty": 0.5},
    )
    loose = engine.validate_proposal(proposal, region, world, speculative=True)
    assert loose.status != ConstraintStatus.BLOCKED
    assert loose.status in (ConstraintStatus.VALID, ConstraintStatus.RISKY)


def test_register_novel_compound():
    from civsim.models.world import CompoundProvenance

    mat_reg = MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    engine = MaterialEngine(mat_reg)
    world = WorldGenerator().generate(3)

    registered = engine.register_novel_compound(
        world,
        "Cave varnish",
        ["chemical", "compound", "varnish"],
        "material.cave_varnish",
        provenance=CompoundProvenance(
            materials=["flint", "bone"],
            components=["natural_fire"],
            intent="mix pigments",
            turn=2,
        ),
    )
    assert registered is not None
    compound_id, feedback = registered
    assert compound_id in world.novel_compounds
    entry = world.novel_compounds[compound_id]
    assert entry.name == "Cave varnish"
    assert entry.provenance.materials == ["flint", "bone"]
    assert entry.provenance.components == ["natural_fire"]
    assert "Cave varnish" in feedback
    assert world.material_stocks[compound_id] > 0
