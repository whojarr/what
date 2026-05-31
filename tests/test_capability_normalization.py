from pathlib import Path

from civsim.engines.capability_engine import CapabilityEngine
from civsim.models.capabilities import IdeaProposal, SuggestedCapability
from civsim.registry.capability_registry import CapabilityRegistry

ROOT = Path(__file__).resolve().parent.parent


def test_normalize_clamps_and_fills_defaults():
    registry = CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    engine = CapabilityEngine(registry)
    proposal = IdeaProposal(
        type="tool.bone",
        tags=["stone"],
        capabilities={"tool_craft": 1.5, "hunting": -0.2},
    )
    result = engine.normalize(proposal)
    assert result.capabilities["tool_craft"] == 1.0
    assert result.capabilities["hunting"] == 0.0
    assert "shelter" in result.capabilities


def test_modern_keys_dropped_not_needs_tweak():
    registry = CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    engine = CapabilityEngine(registry)
    proposal = IdeaProposal(
        type="tool.test",
        tags=["stone"],
        capabilities={"tool_craft": 0.6, "compute_output": 0.9, "cooling": 0.5},
    )
    result = engine.normalize(proposal)
    assert "compute_output" in result.dropped_capability_keys
    assert "compute_output" not in result.capabilities or result.capabilities.get("compute_output", 0) <= 0.05
    assert "tool_craft" in result.capabilities


def test_alias_maps_warmth():
    registry = CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    engine = CapabilityEngine(registry)
    proposal = IdeaProposal(type="tool.fire", capabilities={"warmth": 0.7})
    result = engine.normalize(proposal)
    assert result.capabilities.get("warmth_output", 0) == 0.7


def test_unknown_capability_queued():
    registry = CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    engine = CapabilityEngine(registry)
    proposal = IdeaProposal(
        type="test.unit",
        capabilities={"tool_craft": 0.5, "quantum_flux": 0.8},
        suggested_capabilities=[
            SuggestedCapability(
                key="quantum_flux",
                category="meta",
                meaning="Quantum flux coupling",
            )
        ],
    )
    result = engine.normalize(proposal)
    assert "quantum_flux" not in result.capabilities or result.capabilities.get("quantum_flux", 0) < 0.1
