from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class SceneRegistry:
    def __init__(self, version: int, templates: dict[str, dict]) -> None:
        self.version = version
        self._templates = templates
        self._default_id = "default" if "default" in templates else next(iter(templates))

    @classmethod
    def load_for_era(cls, era: str, data_dir: Path) -> SceneRegistry:
        path = data_dir / f"scenes_{era}.yaml"
        if not path.exists():
            return cls(1, {"default": _FALLBACK_TEMPLATE})
        with path.open() as f:
            raw = yaml.safe_load(f) or {}
        version = int(raw.get("version") or 1)
        templates = raw.get("templates") or {}
        if "default" not in templates:
            templates["default"] = _FALLBACK_TEMPLATE
        return cls(version, templates)

    def resolve(self, region_id: str, biome_tags: list[str]) -> tuple[str, dict]:
        tag_set = {t.lower().strip() for t in biome_tags}
        best_id: str | None = None
        best_score = -1
        for template_id, template in self._templates.items():
            if template_id == "default":
                continue
            match = template.get("match") or {}
            region_ids = match.get("region_ids") or []
            if region_id in region_ids:
                return template_id, template
            required_any = {t.lower().strip() for t in (match.get("biome_tags_any") or [])}
            if required_any and tag_set.intersection(required_any):
                score = len(tag_set.intersection(required_any))
                if score > best_score:
                    best_score = score
                    best_id = template_id
        if best_id:
            return best_id, self._templates[best_id]
        return self._default_id, self._templates[self._default_id]

    def get_template(self, template_id: str) -> dict | None:
        return self._templates.get(template_id)

    def surface_prompt(
        self,
        template_id: str,
        surface_id: str,
        name: str,
        hint: str,
        scene_brief: str = "",
    ) -> str | None:
        template = self.get_template(template_id)
        if not template:
            return None
        assets = template.get("assets") or {}
        surfaces = assets.get("surfaces") or {}
        spec = surfaces.get(surface_id)
        if not spec:
            backdrop = assets.get("backdrop") or {}
            if surface_id == "back" and backdrop.get("prompt"):
                spec = backdrop
        if not spec:
            return None
        prompt_template = spec.get("prompt")
        if not prompt_template:
            return None
        return " ".join(
            prompt_template.format(
                name=name,
                hint=hint,
                scene_brief=scene_brief.strip(),
            ).split()
        )

    def backdrop_prompt(self, template_id: str, name: str, hint: str) -> str | None:
        return self.surface_prompt(template_id, "back", name, hint)

    def panorama_config(self, template_id: str) -> dict[str, Any] | None:
        template = self.get_template(template_id)
        if not template:
            return None
        cfg = (template.get("assets") or {}).get("panorama")
        return cfg if isinstance(cfg, dict) else None

    def panorama_prompt(
        self,
        template_id: str,
        name: str,
        hint: str,
        exit_name: str = "",
        exit_hint: str = "",
    ) -> str | None:
        cfg = self.panorama_config(template_id)
        if not cfg:
            return None
        prompt_template = cfg.get("expand_prompt") or cfg.get("prompt")
        if not prompt_template:
            return None
        return " ".join(
            prompt_template.format(
                name=name,
                hint=hint,
                exit_name=exit_name or name,
                exit_hint=exit_hint or hint,
                scene_brief="",
            ).split()
        )

    def panorama_crops(self, template_id: str) -> dict[str, dict[str, float]]:
        cfg = self.panorama_config(template_id) or {}
        crops = cfg.get("crops") or {}
        return {k: dict(v) for k, v in crops.items() if isinstance(v, dict)}

    def panorama_wall_crops(self, template_id: str) -> dict[str, dict[str, float]]:
        return {
            k: v for k, v in self.panorama_crops(template_id).items() if k != "floor"
        }

    def panorama_floor_prompt(
        self, template_id: str, name: str, hint: str
    ) -> str | None:
        cfg = self.panorama_config(template_id) or {}
        floor = cfg.get("floor")
        if not isinstance(floor, dict):
            return None
        prompt_template = floor.get("prompt")
        if not prompt_template:
            return None
        return " ".join(
            prompt_template.format(name=name, hint=hint, scene_brief="").split()
        )

    def panorama_floor_strip(self, template_id: str) -> dict[str, float] | None:
        cfg = self.panorama_config(template_id) or {}
        strip = cfg.get("floor_strip")
        if isinstance(strip, dict):
            return dict(strip)
        return None

    def panorama_exit_rect(self, template_id: str) -> dict[str, float] | None:
        cfg = self.panorama_config(template_id) or {}
        opening = cfg.get("source_opening") or cfg.get("exit_opening")
        if isinstance(opening, dict):
            return dict(opening)
        composite_surface = cfg.get("exit_composite")
        if composite_surface:
            return self.panorama_crops(template_id).get(composite_surface)
        return None

    def panorama_mode(self, template_id: str) -> str:
        cfg = self.panorama_config(template_id) or {}
        return str(cfg.get("mode") or "sliced")

    def panorama_canvas_size(self, template_id: str) -> tuple[int, int]:
        cfg = self.panorama_config(template_id) or {}
        canvas = cfg.get("canvas")
        if isinstance(canvas, dict):
            return int(canvas.get("width", 1536)), int(canvas.get("height", 1024))
        size = cfg.get("size")
        if isinstance(size, str) and "x" in size:
            w, h = size.split("x", 1)
            return int(w), int(h)
        return 1536, 1024


_FALLBACK_TEMPLATE = {
    "match": {},
    "camera": {"position": [0, 1.8, 5], "look_at": [0, 0.5, 0], "fov": 50},
    "environment": {"mesh": "open_ground", "ambient": 0.45, "background": "#1a2332"},
    "assets": {
        "backdrop": {
            "visual_type": "region",
            "prompt": "Paleolithic region: {name}. {hint} Wide view, painterly, no text.",
        }
    },
    "slots": {},
    "exits": {},
}
