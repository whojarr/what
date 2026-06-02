import hashlib
import logging
from pathlib import Path

from civsim.ai.image_generator import ImageGenerator

logger = logging.getLogger(__name__)

_PROMPT_BY_TYPE = {
    "material": (
        "Small game icon of a paleolithic raw material: {name}. {hint} "
        "Stone-age cave setting, painterly, centered object, dark muted background, no text, no people."
    ),
    "stock": (
        "Small game icon of gathered paleolithic material stockpile: {name}. {hint} "
        "Stone-age, painterly, no text, no people."
    ),
    "compound": (
        "Small game icon of a novel paleolithic substance: {name}. {hint} "
        "Mysterious compound, painterly, no text, no people."
    ),
    "component": (
        "Small game icon of a paleolithic machine or tool: {name}. {hint} "
        "Fire, water, or hand-made device, painterly, no text."
    ),
    "object": (
        "Small game icon of a paleolithic crafted object: {name}. {hint} "
        "Furniture, shelter, or artifact, painterly, no text, no people."
    ),
}


def build_visual_prompt(subject: dict) -> str:
    template = _PROMPT_BY_TYPE.get(
        subject["type"],
        "Small game icon for a paleolithic survival item: {name}. {hint} Painterly, no text.",
    )
    hint = (subject.get("hint") or "").strip()
    return template.format(name=subject["name"], hint=hint)


class VisualService:
    def __init__(self, images_path: Path, game_service: object) -> None:
        self.images_path = images_path
        self.images_path.mkdir(parents=True, exist_ok=True)
        self.game_service = game_service
        self._generator: ImageGenerator | None = None

    def _get_generator(self) -> ImageGenerator:
        if self._generator is None:
            self._generator = ImageGenerator()
        return self._generator

    def _cache_path(self, subject: dict) -> Path:
        key = f"{subject['type']}:{subject['id']}:{subject['name']}"
        digest = hashlib.sha256(key.encode()).hexdigest()[:32]
        return self.images_path / f"{digest}.png"

    def get_or_create_image(
        self, game_id: str, subject_type: str, subject_id: str
    ) -> Path | None:
        subject = self.game_service.resolve_visual_subject(game_id, subject_type, subject_id)
        if not subject:
            return None
        path = self._cache_path(subject)
        if path.exists():
            return path
        try:
            png = self._get_generator().generate_png(build_visual_prompt(subject))
        except ValueError:
            return None
        except Exception:
            logger.exception("Failed to generate visual for %s/%s", subject_type, subject_id)
            return None
        path.write_bytes(png)
        return path
