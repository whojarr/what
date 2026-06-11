import hashlib
import json
import logging
from pathlib import Path

from openai import BadRequestError

from civsim.ai.image_generator import ImageGenerator, _scene_size_candidates, parse_scene_size
from civsim.services.scene_panorama import (
    build_expansion_mask,
    build_panorama_seed,
    crop_normalized,
    load_png,
    mask_png_bytes,
    png_bytes,
)

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
    "region": (
        "Wide landscape scene of a paleolithic region: {name}. {hint} "
        "Atmospheric environment view, painterly, muted earth tones, no text, no people."
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
    def __init__(
        self,
        images_path: Path,
        game_service: object,
        scene_registry: object | None = None,
    ) -> None:
        self.images_path = images_path
        self.images_path.mkdir(parents=True, exist_ok=True)
        self.panoramas_path = images_path / "panoramas"
        self.panoramas_path.mkdir(parents=True, exist_ok=True)
        self.game_service = game_service
        self.scene_registry = scene_registry
        self._generator: ImageGenerator | None = None

    def _get_generator(self) -> ImageGenerator:
        if self._generator is None:
            self._generator = ImageGenerator()
        return self._generator

    def _cache_path(self, subject: dict, *, scene_context: str | None = None) -> Path:
        key = f"{subject['type']}:{subject['id']}:{subject['name']}"
        if scene_context:
            key = f"{scene_context}:{key}"
        digest = hashlib.sha256(key.encode()).hexdigest()[:32]
        return self.images_path / f"{digest}.png"

    def _scene_prompt(
        self,
        template_id: str,
        surface_id: str,
        name: str,
        hint: str,
        scene_brief: str = "",
    ) -> str | None:
        if not self.scene_registry:
            return None
        if surface_id == "floor":
            floor_prompt = self.scene_registry.panorama_floor_prompt(
                template_id, name, hint
            )
            if floor_prompt:
                return floor_prompt
        return self.scene_registry.surface_prompt(
            template_id, surface_id, name, hint, scene_brief=scene_brief
        )

    def get_or_create_image(
        self,
        game_id: str,
        subject_type: str,
        subject_id: str,
        *,
        context: str | None = None,
        template_id: str | None = None,
        surface: str | None = None,
        region_id: str | None = None,
    ) -> Path | None:
        subject = self.game_service.resolve_visual_subject(game_id, subject_type, subject_id)
        if not subject:
            return None
        scene_context: str | None = None
        prompt = build_visual_prompt(subject)
        if context == "scene" and template_id and self.scene_registry:
            surface_id = (surface or "back").strip().lower()
            scene_context = (
                f"scene:v{self.scene_registry.version}:{template_id}:{surface_id}"
            )
            scene_prompt = self._scene_prompt(
                template_id,
                surface_id,
                subject["name"],
                subject.get("hint") or "",
            )
            if scene_prompt:
                prompt = scene_prompt
        path = self._cache_path(subject, scene_context=scene_context)
        if path.exists():
            return path
        try:
            png = self._get_generator().generate_png(prompt)
        except ValueError:
            return None
        except Exception:
            logger.exception("Failed to generate visual for %s/%s", subject_type, subject_id)
            return None
        path.write_bytes(png)
        return path

    def get_or_create_scene_floor(
        self, game_id: str, template_id: str, region_id: str | None
    ) -> Path | None:
        state = self.game_service.load_game(game_id)
        region = self.game_service._world_region(state, region_id) if state else None
        if not region:
            return None
        return self.get_or_create_image(
            game_id,
            "region",
            region.id,
            context="scene",
            template_id=template_id,
            surface="floor",
            region_id=region_id,
        )

    def _panorama_layout_digest(self, template_id: str) -> str:
        if not self.scene_registry:
            return "0"
        cfg = self.scene_registry.panorama_config(template_id) or {}
        floor_cfg = cfg.get("floor") if isinstance(cfg.get("floor"), dict) else {}
        payload = {
            "v": self.scene_registry.version,
            "mode": cfg.get("mode"),
            "canvas": cfg.get("canvas"),
            "crops": cfg.get("crops"),
            "exit_opening": cfg.get("exit_opening"),
            "source_opening": cfg.get("source_opening"),
            "expand_prompt": cfg.get("expand_prompt"),
            "floor_prompt": floor_cfg.get("prompt"),
            "floor_strip": cfg.get("floor_strip"),
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def _panorama_master_path(self, cache_key: str) -> Path:
        digest = hashlib.sha256(cache_key.encode()).hexdigest()[:32]
        return self.panoramas_path / f"{digest}.png"

    def _resolve_exit_subject(
        self, game_id: str, region_id: str | None, template_id: str
    ) -> dict | None:
        state = self.game_service.load_game(game_id)
        if not state:
            return None
        region = self.game_service._world_region(state, region_id)
        if not region:
            return None
        scene = self.game_service.get_world_scene(game_id, region_id)
        exit_id = self.game_service._exit_target_region_id(
            scene.get("exits") if scene else None, region
        )
        if not exit_id:
            return None
        return self.game_service.resolve_visual_subject(game_id, "region", exit_id)

    def get_or_create_panorama_master(
        self,
        game_id: str,
        template_id: str,
        region_id: str | None,
    ) -> Path | None:
        if hasattr(self.game_service, "ensure_scene_registry"):
            self.game_service.ensure_scene_registry()
            self.scene_registry = self.game_service.scene_registry
        if not self.scene_registry:
            return None
        cfg = self.scene_registry.panorama_config(template_id)
        if not cfg:
            return None
        state = self.game_service.load_game(game_id)
        region = self.game_service._world_region(state, region_id) if state else None
        if not region:
            return None
        region_subject = self.game_service.resolve_visual_subject(
            game_id, "region", region.id
        )
        if not region_subject:
            return None
        exit_subject = self._resolve_exit_subject(game_id, region_id, template_id)
        exit_name = (exit_subject or {}).get("name") or region_subject["name"]
        exit_hint = (exit_subject or {}).get("hint") or region_subject.get("hint") or ""
        exit_path = (
            self.get_or_create_image(game_id, "region", exit_subject["id"])
            if exit_subject
            else None
        )
        mode = self.scene_registry.panorama_mode(template_id)
        floor_path = (
            None
            if mode == "single_scene"
            else self.get_or_create_scene_floor(game_id, template_id, region_id)
        )
        exit_digest = (
            hashlib.sha256(exit_path.read_bytes()).hexdigest()[:12]
            if exit_path and exit_path.exists()
            else "none"
        )
        floor_digest = (
            hashlib.sha256(floor_path.read_bytes()).hexdigest()[:12]
            if floor_path and floor_path.exists()
            else "none"
        )
        layout = self._panorama_layout_digest(template_id)
        cache_key = (
            f"panorama:{layout}:{template_id}:{region_id}:"
            f"{exit_digest}:{floor_digest}"
        )
        master_path = self._panorama_master_path(cache_key)
        if master_path.exists():
            return master_path
        prompt = self.scene_registry.panorama_prompt(
            template_id,
            region_subject["name"],
            region_subject.get("hint") or "",
            exit_name=exit_name,
            exit_hint=exit_hint,
        )
        if not prompt:
            return None
        if not exit_path or not exit_path.exists():
            logger.warning("Panorama requires exit region image for %s", template_id)
            return None
        source_rect = self.scene_registry.panorama_exit_rect(template_id)
        if not source_rect:
            return None
        if mode != "single_scene":
            if not floor_path or not floor_path.exists():
                logger.warning("Panorama requires scene floor texture for %s", template_id)
                return None
            floor_strip = self.scene_registry.panorama_floor_strip(template_id)
            if not floor_strip:
                return None
        try:
            exit_img = load_png(exit_path.read_bytes())
            canvas_size = self.scene_registry.panorama_canvas_size(template_id)
            preferred = f"{canvas_size[0]}x{canvas_size[1]}"
            png: bytes | None = None
            for size_str in _scene_size_candidates(preferred):
                w, h = parse_scene_size(size_str)
                if mode == "single_scene":
                    seed = build_panorama_seed(exit_img, (w, h), source_rect)
                    mask = build_expansion_mask((w, h), source_rect)
                else:
                    floor_img = load_png(floor_path.read_bytes())
                    seed = build_panorama_seed(
                        exit_img,
                        (w, h),
                        source_rect,
                        floor_img=floor_img,
                        floor_rect=floor_strip,
                    )
                    mask = build_expansion_mask((w, h), [source_rect, floor_strip])
                try:
                    png = self._get_generator().expand_png(
                        prompt,
                        png_bytes(seed),
                        mask_png_bytes(mask),
                        size=size_str,
                    )
                    break
                except BadRequestError:
                    continue
            if png is None:
                raise RuntimeError("No supported scene size for expand")
        except ValueError:
            return None
        except Exception:
            logger.exception("Failed to expand scene panorama for %s", template_id)
            return None
        master_path.write_bytes(png)
        return master_path

    def get_scene_panorama_surface(
        self,
        game_id: str,
        template_id: str,
        region_id: str | None,
        surface_id: str,
    ) -> Path | None:
        if not self.scene_registry:
            return None
        crops = self.scene_registry.panorama_wall_crops(template_id)
        rect = crops.get(surface_id)
        if not rect:
            return None
        master = self.get_or_create_panorama_master(game_id, template_id, region_id)
        if not master:
            return None
        img = load_png(master.read_bytes())
        cropped = crop_normalized(img, rect)
        rect_key = hashlib.sha256(
            json.dumps(rect, sort_keys=True).encode()
        ).hexdigest()[:8]
        layout = self._panorama_layout_digest(template_id)
        cache_key = f"{layout}:{master.name}:{surface_id}:{rect_key}"
        digest = hashlib.sha256(cache_key.encode()).hexdigest()[:32]
        out = self.panoramas_path / f"crop_{digest}.png"
        if not out.exists():
            out.write_bytes(png_bytes(cropped))
        return out
