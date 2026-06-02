(function () {
  const STORAGE_KEY = "what_graphics_level";
  const LEVEL_TEXT = 0;
  const LEVEL_AI = 1;

  function getGraphicsLevel() {
    const raw = localStorage.getItem(STORAGE_KEY);
    const n = parseInt(raw, 10);
    return n === LEVEL_AI ? LEVEL_AI : LEVEL_TEXT;
  }

  function setGraphicsLevel(level) {
    const n = level === LEVEL_AI ? LEVEL_AI : LEVEL_TEXT;
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
    if (!isAi() || !desc?.id || !desc?.type) return "";
    const { esc } = window.What;
    const large = options?.large ? " visual-slot-large" : "";
    return `<span class="visual-slot${large}" data-visual-type="${esc(desc.type)}" data-visual-id="${esc(desc.id)}" data-visual-name="${esc(desc.name)}" aria-hidden="true"></span>`;
  }

  function visualUrl(apiBase, gameId, desc) {
    return `${apiBase.replace(/\/$/, "")}/games/${gameId}/visuals/${encodeURIComponent(desc.type)}/${encodeURIComponent(desc.id)}`;
  }

  function hydrate(root, ctx) {
    if (!isAi() || !ctx?.apiBase || !ctx?.gameId) return;
    const scope = root || document;
    scope.querySelectorAll(".visual-slot:not([data-visual-hydrated])").forEach((slot) => {
      slot.dataset.visualHydrated = "1";
      const desc = {
        type: slot.dataset.visualType,
        id: slot.dataset.visualId,
        name: slot.dataset.visualName || "",
      };
      const img = document.createElement("img");
      img.className = slot.classList.contains("visual-slot-large")
        ? "visual-thumb visual-thumb-large"
        : "visual-thumb";
      img.alt = desc.name;
      img.loading = "lazy";
      img.decoding = "async";
      img.src = visualUrl(ctx.apiBase, ctx.gameId, desc);
      img.onerror = () => {
        img.remove();
      };
      slot.replaceWith(img);
    });
  }

  function initToggle() {
    const select = document.getElementById("graphics-level");
    if (!select) return;
    select.value = String(getGraphicsLevel());
    select.addEventListener("change", () => {
      setGraphicsLevel(parseInt(select.value, 10));
    });
  }

  applyGraphicsLevel(getGraphicsLevel());
  document.addEventListener("DOMContentLoaded", initToggle);

  window.WhatGraphics = {
    LEVEL_TEXT,
    LEVEL_AI,
    getGraphicsLevel,
    setGraphicsLevel,
    isAi,
    descriptor,
    slotHtml,
    visualUrl,
    hydrate,
  };
})();
