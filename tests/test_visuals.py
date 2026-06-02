from pathlib import Path

import pytest

from civsim.registry.capability_registry import CapabilityRegistry
from civsim.registry.material_registry import MaterialRegistry
from civsim.registry.method_registry import MethodRegistry
from civsim.services.game_service import GameService
from civsim.services.visual_service import VisualService, build_visual_prompt

ROOT = Path(__file__).resolve().parent.parent

MINI_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def service(tmp_path):
    reg = CapabilityRegistry.load_for_era("paleolithic", ROOT / "data")
    mat_reg = MaterialRegistry.load_for_era("paleolithic", ROOT / "data")
    method_reg = MethodRegistry.load_for_era("paleolithic", ROOT / "data")
    return GameService(
        reg,
        tmp_path / "saves",
        material_registry=mat_reg,
        method_registry=method_reg,
        data_dir=ROOT / "data",
    )


def test_resolve_visual_subject_material(service):
    state = service.create_game(3)
    subject = service.resolve_visual_subject(state.id, "material", "flint")
    assert subject is not None
    assert subject["name"] == "Flint"
    assert subject["type"] == "material"


def test_model_candidates_respects_env_first(monkeypatch):
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    from civsim.ai.image_generator import _model_candidates

    assert _model_candidates("dall-e-2")[0] == "gpt-image-1"


def test_gpt_image_request_uses_low_quality():
    from civsim.ai.image_generator import ImageGenerator

    gen = ImageGenerator(api_key="sk-test", model="gpt-image-1-mini")
    kwargs = gen._request_kwargs("gpt-image-1-mini", "a flint tool")
    assert kwargs["model"] == "gpt-image-1-mini"
    assert kwargs["size"] == "1024x1024"
    assert kwargs["quality"] == "low"
    assert "response_format" not in kwargs


def test_build_visual_prompt_includes_name():
    prompt = build_visual_prompt(
        {"type": "object", "name": "Stone seat", "hint": "A simple seat"}
    )
    assert "Stone seat" in prompt
    assert "seat" in prompt.lower()


def test_visual_service_uses_cache(tmp_path, service):
    state = service.create_game(5)
    fire = next(e for e in state.entities if e.id == "natural_fire")
    visual = VisualService(tmp_path / "images", service)

    class FakeGen:
        def __init__(self) -> None:
            self.calls = 0

        def generate_png(self, prompt: str) -> bytes:
            self.calls += 1
            return MINI_PNG

    gen = FakeGen()
    visual._generator = gen

    path1 = visual.get_or_create_image(state.id, "component", fire.id)
    path2 = visual.get_or_create_image(state.id, "component", fire.id)
    assert path1 is not None
    assert path1 == path2
    assert path1.exists()
    assert gen.calls == 1
