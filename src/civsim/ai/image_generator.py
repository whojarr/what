import base64
import logging
import os

import httpx
from openai import BadRequestError, OpenAI

logger = logging.getLogger(__name__)

# DALL·E 2/3 are retired on many keys; prefer GPT Image models (see OpenAI image generation docs).
_FALLBACK_MODELS = (
    "gpt-image-1-mini",
    "gpt-image-1",
    "gpt-image-2",
    "dall-e-3",
)


def _model_candidates(preferred: str | None) -> list[str]:
    env_model = os.environ.get("OPENAI_IMAGE_MODEL", "").strip()
    out: list[str] = []
    for m in (env_model, preferred):
        if m and m not in out:
            out.append(m)
    for m in _FALLBACK_MODELS:
        if m not in out:
            out.append(m)
    return out


def _is_gpt_image(model: str) -> bool:
    return model.startswith("gpt-image")


class ImageGenerator:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required for AI graphics")
        self.client = OpenAI(api_key=key)
        self.model = model or os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1-mini")

    def _request_kwargs(self, model: str, prompt: str) -> dict:
        if _is_gpt_image(model):
            return {
                "model": model,
                "prompt": prompt,
                "size": "1024x1024",
                "n": 1,
                "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "low"),
            }
        size = "256x256" if model == "dall-e-2" else "1024x1024"
        return {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }

    def _generate_with_model(self, model: str, prompt: str) -> bytes:
        resp = self.client.images.generate(**self._request_kwargs(model, prompt))
        item = resp.data[0]
        if item.b64_json:
            return base64.b64decode(item.b64_json)
        if item.url:
            r = httpx.get(item.url, timeout=60.0)
            r.raise_for_status()
            return r.content
        raise RuntimeError("No image data from OpenAI")

    def generate_png(self, prompt: str) -> bytes:
        last_error: Exception | None = None
        for model in _model_candidates(self.model):
            try:
                png = self._generate_with_model(model, prompt)
                if model != self.model:
                    logger.info("AI graphics using model %s (preferred %s unavailable)", model, self.model)
                    self.model = model
                return png
            except BadRequestError as err:
                msg = str(err).lower()
                if "does not exist" in msg or "invalid_value" in msg or "invalid" in msg:
                    last_error = err
                    logger.warning("Image model %s rejected: %s", model, err)
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError("No image model available")
