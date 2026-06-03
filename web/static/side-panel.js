(function () {
  function createSidePanel(rootEl, panelSelector) {
    const panel = rootEl.querySelector(panelSelector || ".world-side-panel");
    if (!panel) {
      throw new Error("Side panel element not found");
    }

    const backdrop = panel.querySelector(".world-side-panel-backdrop");
    const closeBtn = panel.querySelector(".world-side-panel-close");
    const backBtn = panel.querySelector(".world-side-panel-back");
    const titleEl = panel.querySelector(".world-side-panel-title");
    const bodyEl = panel.querySelector(".world-side-panel-body");

    let backHandler = null;

    function close() {
      panel.classList.remove("is-open");
      panel.setAttribute("aria-hidden", "true");
      document.body.classList.remove("world-panel-open");
      if (backBtn) backBtn.hidden = true;
      backHandler = null;
    }

    function setLoading(title) {
      panel.classList.add("is-open");
      panel.setAttribute("aria-hidden", "false");
      document.body.classList.add("world-panel-open");
      if (titleEl) titleEl.textContent = title || "…";
      if (bodyEl) bodyEl.innerHTML = '<p class="muted world-panel-loading">Loading…</p>';
    }

    async function open({ title, html, showBack, onBack, hydrate }) {
      panel.classList.add("is-open");
      panel.setAttribute("aria-hidden", "false");
      document.body.classList.add("world-panel-open");
      if (titleEl) titleEl.textContent = title || "Details";
      if (bodyEl) {
        bodyEl.innerHTML = html || "";
        bodyEl.scrollTop = 0;
      }
      if (backBtn) {
        backBtn.hidden = !showBack;
        backHandler = onBack || null;
      }
      if (hydrate) hydrate(bodyEl);
    }

    if (closeBtn) closeBtn.addEventListener("click", close);
    if (backdrop) backdrop.addEventListener("click", close);
    if (backBtn) {
      backBtn.addEventListener("click", () => {
        if (backHandler) backHandler();
      });
    }

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && panel.classList.contains("is-open")) {
        close();
      }
    });

    return {
      panel,
      bodyEl,
      titleEl,
      close,
      setLoading,
      open,
      isOpen: () => panel.classList.contains("is-open"),
    };
  }

  window.WhatSidePanel = { createSidePanel };
})();
