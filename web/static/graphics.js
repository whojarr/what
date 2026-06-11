(function () {
  const STORAGE_KEY = "what_graphics_level";
  const LEVEL_TEXT = 0;
  const LEVEL_AI = 1;
  const LEVEL_BASIC3D = 2;

  function getGraphicsLevel() {
    const raw = localStorage.getItem(STORAGE_KEY);
    const n = parseInt(raw, 10);
    if (n === LEVEL_AI) return LEVEL_AI;
    if (n === LEVEL_BASIC3D) return LEVEL_BASIC3D;
    return LEVEL_TEXT;
  }

  function setGraphicsLevel(level) {
    let n = LEVEL_TEXT;
    if (level === LEVEL_AI) n = LEVEL_AI;
    else if (level === LEVEL_BASIC3D) n = LEVEL_BASIC3D;
    localStorage.setItem(STORAGE_KEY, String(n));
    applyGraphicsLevel(n);
    window.dispatchEvent(new CustomEvent("what-graphics-change", { detail: { level: n } }));
    return n;
  }

  function applyGraphicsLevel(level) {
    document.body.dataset.graphicsLevel = String(level);
  }

  function isAi() {
    return getGraphicsLevel() === LEVEL_AI;
  }

  function isBasic3d() {
    return getGraphicsLevel() === LEVEL_BASIC3D;
  }

  function descriptor(subjectType, item, extra) {
    const display = item.display || {};
    const name =
      extra?.name ||
      item.name ||
      display.label ||
      item.label ||
      item.id ||
      "Unknown";
    const hint =
      extra?.hint ||
      item.hint ||
      display.hint ||
      item.description ||
      item.uses ||
      "";
    return {
      type: subjectType,
      id: item.id,
      name: String(name),
      hint: String(hint),
    };
  }

  function slotHtml(desc, options) {
    const pathPreview = Boolean(options?.pathPreview);
    if (!desc?.id || !desc?.type) return "";
    if (!isAi() && !(isBasic3d() && pathPreview)) return "";
    if (isBasic3d() && !pathPreview) return "";
    const { esc } = window.What;
    let sizeClass = "";
    if (pathPreview) sizeClass = " visual-slot-path";
    else if (options?.large) sizeClass = " visual-slot-large";
    return `<span class="visual-slot${sizeClass}" data-visual-type="${esc(desc.type)}" data-visual-id="${esc(desc.id)}" data-visual-name="${esc(desc.name)}" aria-hidden="true"></span>`;
  }

  function visualUrl(apiBase, gameId, desc) {
    return `${apiBase.replace(/\/$/, "")}/games/${gameId}/visuals/${encodeURIComponent(desc.type)}/${encodeURIComponent(desc.id)}`;
  }

  function sceneImageUrl(apiBase, gameId, regionId, templateVersion) {
    const base = apiBase.replace(/\/$/, "");
    const params = new URLSearchParams();
    if (regionId) params.set("region_id", regionId);
    if (templateVersion != null) params.set("v", String(templateVersion));
    const qs = params.toString();
    return `${base}/games/${gameId}/world/scene/image${qs ? `?${qs}` : ""}`;
  }

  const sceneImageCache = new Map();

  function sceneCacheKey(ctx, regionId, templateVersion) {
    return `${ctx.gameId}:${regionId || ""}:${templateVersion ?? ""}`;
  }

  async function fetchSceneData(ctx, regionId) {
    const regionQuery = regionId ? `?region_id=${encodeURIComponent(regionId)}` : "";
    const res = await fetch(
      `${ctx.apiBase.replace(/\/$/, "")}/games/${ctx.gameId}/world/scene${regionQuery}`
    );
    if (!res.ok) throw new Error(`scene ${res.status}`);
    return res.json();
  }

  async function ensureSceneImage(ctx, regionId, regionName) {
    const sceneData = await fetchSceneData(ctx, regionId);
    const name = regionName || sceneData.region?.name || "Cave";
    const url = sceneImageUrl(ctx.apiBase, ctx.gameId, regionId, sceneData.template_version);
    const key = sceneCacheKey(ctx, regionId, sceneData.template_version);
    let pending = sceneImageCache.get(key);
    if (!pending) {
      pending = (async () => {
        const res = await fetch(url);
        if (!res.ok) throw new Error("scene image failed");
        const blob = await res.blob();
        const objectUrl = URL.createObjectURL(blob);
        try {
          const img = await new Promise((resolve, reject) => {
            const el = new Image();
            el.alt = `${name} — cave scene`;
            el.onload = () => resolve(el);
            el.onerror = () => reject(new Error("scene image failed"));
            el.src = objectUrl;
          });
          return { sceneData, url, img, objectUrl };
        } catch (err) {
          URL.revokeObjectURL(objectUrl);
          throw err;
        }
      })();
      sceneImageCache.set(key, pending);
      pending.catch(() => sceneImageCache.delete(key));
    }
    return pending;
  }

  function sceneImageElement(entry, className) {
    const img = entry.img.cloneNode(false);
    img.className = className;
    return img;
  }

  async function loadSceneThumb(slot, ctx, regionId, regionName) {
    try {
      const entry = await ensureSceneImage(ctx, regionId, regionName);
      const img = sceneImageElement(entry, "world-scene-thumb");
      img.onerror = () => slot.remove();
      slot.appendChild(img);
    } catch (_err) {
      slot.remove();
    }
  }

  function hydrateSceneSlots(root, ctx) {
    if (!isAi() || !ctx?.apiBase || !ctx?.gameId) return;
    const scope = root || document;
    scope.querySelectorAll(".world-scene-slot:not([data-scene-hydrated])").forEach((slot) => {
      slot.dataset.sceneHydrated = "1";
      const regionId = slot.dataset.regionId || "";
      const regionName = slot.dataset.regionName || "Cave";
      void loadSceneThumb(slot, ctx, regionId, regionName);
    });
  }

  function hydrate(root, ctx) {
    if (!ctx?.apiBase || !ctx?.gameId) return;
    const scope = root || document;
    scope.querySelectorAll(".visual-slot:not([data-visual-hydrated])").forEach((slot) => {
      const isPath = slot.classList.contains("visual-slot-path");
      if (!isAi() && !(isBasic3d() && isPath)) return;
      slot.dataset.visualHydrated = "1";
      const desc = {
        type: slot.dataset.visualType,
        id: slot.dataset.visualId,
        name: slot.dataset.visualName || "",
      };
      const img = document.createElement("img");
      if (slot.classList.contains("visual-slot-path")) {
        img.className = "visual-thumb visual-thumb-path";
      } else if (slot.classList.contains("visual-slot-large")) {
        img.className = "visual-thumb visual-thumb-large";
      } else {
        img.className = "visual-thumb";
      }
      img.alt = desc.name;
      img.loading = "lazy";
      img.decoding = "async";
      img.src = visualUrl(ctx.apiBase, ctx.gameId, desc);
      img.onerror = () => {
        img.remove();
      };
      slot.replaceWith(img);
    });
    hydrateSceneSlots(scope, ctx);
  }

  function syncToggleSelects(level) {
    const value = String(level ?? getGraphicsLevel());
    document.querySelectorAll(".graphics-level-select").forEach((select) => {
      select.value = value;
    });
  }

  function initToggle() {
    syncToggleSelects(getGraphicsLevel());
    document.querySelectorAll(".graphics-level-select").forEach((select) => {
      select.addEventListener("change", () => {
        setGraphicsLevel(parseInt(select.value, 10));
      });
    });
    window.addEventListener("what-graphics-change", (event) => {
      syncToggleSelects(event.detail?.level);
    });
  }

  applyGraphicsLevel(getGraphicsLevel());
  document.addEventListener("DOMContentLoaded", initToggle);

  window.WhatGraphics = {
    LEVEL_TEXT,
    LEVEL_AI,
    LEVEL_BASIC3D,
    getGraphicsLevel,
    setGraphicsLevel,
    isAi,
    isBasic3d,
    descriptor,
    slotHtml,
    visualUrl,
    sceneImageUrl,
    ensureSceneImage,
    sceneImageElement,
    hydrateSceneSlots,
    hydrate,
  };
})();
