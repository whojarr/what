import base64
import hashlib
import logging
from pathlib import Path

from openai import OpenAI

logger = logging.getLogger(__name__)

_BRIEF_VERSION = 2

_BRIEF_PROMPT = """Analyze this game environment image for generating matching interior room panels (side walls, floor).

Focus ONLY on tones at the FRAME EDGES and bottom: rock/stone wall colors beside the opening, floor/ground tones, shadow depth, and overall brightness/exposure. Ignore distant sky or far landscape detail.

Write max 90 words: exact color palette (muted/earthy), rock texture, lighting direction, shadow level, and overall brightness. State if the scene is dim or bright. No people or text."""


class SceneBriefAnalyzer:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        import os

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required for scene brief analysis")
        self.client = OpenAI(api_key=key)
        self.model = model or os.environ.get("OPENAI_SCENE_BRIEF_MODEL", "gpt-4o-mini")

    def get_or_create_brief(self, image_path: Path, cache_dir: Path) -> str:
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()[:32]
        cache_file = cache_dir / f"brief_v{_BRIEF_VERSION}_{digest}.txt"
        if cache_file.exists():
            return cache_file.read_text().strip()
        brief = self._analyze(image_path)
        cache_file.write_text(brief)
        return brief

    def _analyze(self, image_path: Path) -> str:
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _BRIEF_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=220,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise RuntimeError("Empty scene brief from vision model")
        return text
