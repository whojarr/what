from pathlib import Path

from civsim.registry.scene_registry import SceneRegistry

ROOT = Path(__file__).resolve().parent.parent


def test_scene_registry_matches_region_id():
    reg = SceneRegistry.load_for_era("paleolithic", ROOT / "data")
    template_id, template = reg.resolve("cave_chamber", ["cave", "sheltered"])
    assert template_id == "cave_enclosure"
    assert template["environment"]["mesh"] == "cave_shell"


def test_scene_registry_matches_biome_tags():
    reg = SceneRegistry.load_for_era("paleolithic", ROOT / "data")
    template_id, _template = reg.resolve("outside_slope", ["grassland", "wind"])
    assert template_id == "open_slope"


def test_scene_registry_backdrop_prompt():
    reg = SceneRegistry.load_for_era("paleolithic", ROOT / "data")
    prompt = reg.backdrop_prompt("open_slope", "Outside", "grassland")
    assert prompt is not None
    assert "Outside" in prompt


def test_scene_registry_single_scene_mode():
    reg = SceneRegistry.load_for_era("paleolithic", ROOT / "data")
    assert reg.panorama_mode("cave_enclosure") == "single_scene"
    assert reg.panorama_canvas_size("cave_enclosure") == (1536, 1024)
    prompt = reg.panorama_prompt(
        "cave_enclosure",
        "The Cave",
        "cave, damp",
        exit_name="Outside the cave",
        exit_hint="grassland",
    )
    assert prompt is not None
    assert "pulled back" in prompt.lower()
    assert "visual cue" in prompt.lower()
    assert "Outside the cave" in prompt
    assert "foreground" in prompt.lower()
    assert set(reg.panorama_wall_crops("cave_enclosure")) == {"back", "left", "right"}
    assert "floor" in reg.panorama_crops("cave_enclosure")
    opening = reg.panorama_exit_rect("cave_enclosure")
    assert opening is not None
    assert opening["w"] <= 0.08
    assert opening["y"] <= 0.22


def test_scene_registry_fallback():
    reg = SceneRegistry.load_for_era("paleolithic", ROOT / "data")
    template_id, template = reg.resolve("unknown_region", [])
    assert template_id == "default"
    assert "camera" in template
