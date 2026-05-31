from pathlib import Path

from civsim.engines.constraint_engine import ConstraintEngine
from civsim.models.capabilities import ConstraintStatus, NormalizedProposal
from civsim.world.generator import WorldGenerator

ROOT = Path(__file__).resolve().parent.parent


def test_modern_tech_needs_tweak_in_paleolithic():
    engine = ConstraintEngine()
    world = WorldGenerator().generate(1)
    region = world.regions[0]
    proposal = NormalizedProposal(
        type="tech.computer",
        tags=["digital"],
        capabilities={"tool_craft": 0.3, "compute_output": 0.8, "uncertainty": 0.2},
    )
    result = engine.validate_proposal(proposal, region, world)
    assert result.status in (ConstraintStatus.NEEDS_TWEAK, ConstraintStatus.RISKY)


def test_bone_tools_valid_in_cave():
    engine = ConstraintEngine()
    world = WorldGenerator().generate(1)
    region = world.regions[0]
    proposal = NormalizedProposal(
        type="tool.bone",
        tags=["bone", "stone"],
        capabilities={"tool_craft": 0.6, "hunting": 0.3, "shelter": 0.2},
    )
    result = engine.validate_proposal(proposal, region, world)
    assert result.status in (ConstraintStatus.VALID, ConstraintStatus.RISKY)


def test_dropped_modern_is_risky_not_needs_tweak():
    engine = ConstraintEngine()
    world = WorldGenerator().generate(1)
    proposal = NormalizedProposal(
        type="tool.stone",
        tags=["stone"],
        capabilities={"tool_craft": 0.7, "hunting": 0.4, "shelter": 0.2},
        dropped_capability_keys=["compute_output"],
    )
    result = engine.validate_proposal(proposal, world.regions[0], world)
    assert result.status == ConstraintStatus.RISKY
    assert result.status != ConstraintStatus.NEEDS_TWEAK
