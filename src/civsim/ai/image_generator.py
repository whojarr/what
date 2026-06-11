import base64
import io
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

# GPT Image edit API supported sizes (see OpenAI image generation docs).
_EDIT_SUPPORTED_SIZES = frozenset({
    "1024x1024",
    "1024x1536",
    "1536x1024",
})

_SCENE_SIZE_CANDIDATES = (
    "1536x1024",
    "1024x1024",
    "1024x1536",
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


def _edit_model_candidates(preferred: str | None) -> list[str]:
    return [m for m in _model_candidates(preferred) if _is_gpt_image(m)]


def parse_scene_size(size: str) -> tuple[int, int]:
    w, h = size.lower().split("x", 1)
    return int(w), int(h)


def normalize_scene_edit_size(size: str | None) -> str | None:
    """Map template canvas sizes to a supported images.edit size."""
    if not size:
        return None
    if size in _EDIT_SUPPORTED_SIZES:
        return size
    try:
        w, h = parse_scene_size(size)
    except ValueError:
        return None
    if w > h * 1.05:
        return "1536x1024"
    if h > w * 1.05:
        return "1024x1536"
    return "1024x1024"


def _scene_size_candidates(preferred: str | None) -> list[str]:
    env_size = os.environ.get("OPENAI_SCENE_SIZE", "").strip()
    out: list[str] = []
    for s in (preferred, env_size):
        normalized = normalize_scene_edit_size(s)
        if normalized and normalized not in out:
            out.append(normalized)
    for s in _SCENE_SIZE_CANDIDATES:
        if s not in out:
            out.append(s)
    return out


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

    def _edit_kwargs(
        self,
        model: str,
        prompt: str,
        image_bytes: bytes,
        mask_bytes: bytes,
        size: str,
    ) -> dict:
        if _is_gpt_image(model):
            return {
                "model": model,
                "prompt": prompt,
                "image": ("seed.png", io.BytesIO(image_bytes), "image/png"),
                "mask": ("mask.png", io.BytesIO(mask_bytes), "image/png"),
                "size": size,
                "n": 1,
                "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "low"),
            }
        return {
            "model": model,
            "prompt": prompt,
            "image": ("seed.png", io.BytesIO(image_bytes), "image/png"),
            "mask": ("mask.png", io.BytesIO(mask_bytes), "image/png"),
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }

    def _edit_with_model(
        self,
        model: str,
        prompt: str,
        image_bytes: bytes,
        mask_bytes: bytes,
        size: str,
    ) -> bytes:
        resp = self.client.images.edit(
            **self._edit_kwargs(model, prompt, image_bytes, mask_bytes, size)
        )
        item = resp.data[0]
        if item.b64_json:
            return base64.b64decode(item.b64_json)
        if item.url:
            r = httpx.get(item.url, timeout=60.0)
            r.raise_for_status()
            return r.content
        raise RuntimeError("No image data from OpenAI edit")

    def expand_png(
        self,
        prompt: str,
        image_bytes: bytes,
        mask_bytes: bytes,
        *,
        size: str | None = None,
    ) -> bytes:
        """Outpaint from a seed image, preserving masked (opaque) regions."""
        last_error: Exception | None = None
        for image_size in _scene_size_candidates(size):
            for model in _edit_model_candidates(self.model):
                try:
                    png = self._edit_with_model(
                        model, prompt, image_bytes, mask_bytes, image_size
                    )
                    if model != self.model:
                        logger.info(
                            "AI expand using model %s (preferred %s unavailable)",
                            model,
                            self.model,
                        )
                        self.model = model
                    if image_size != size:
                        logger.info("AI expand using size %s", image_size)
                    return png
                except BadRequestError as err:
                    msg = str(err).lower()
                    if "invalid" in msg and "size" in msg:
                        last_error = err
                        logger.warning(
                            "Image edit size %s rejected by %s: %s",
                            image_size,
                            model,
                            err,
                        )
                        break
                    if "does not exist" in msg or "invalid_value" in msg:
                        last_error = err
                        logger.warning("Image edit model %s rejected: %s", model, err)
                        continue
                    raise
        if last_error:
            raise last_error
        raise RuntimeError("No image model/size available for edit")

    def generate_png(self, prompt: str) -> bytes:
        last_error: Exception | None = None
        for model in _model_candidates(self.model):
            try:
                png = self._generate_with_model(model, prompt)
                if model != self.model:
                    logger.info(
                        "AI graphics using model %s (preferred %s unavailable)",
                        model,
                        self.model,
                    )
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
