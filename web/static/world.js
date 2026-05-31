(function () {
  const root = document.getElementById("world-root");
  if (!root) return;

  const apiBase = (root.dataset.apiBase || "").replace(/\/$/, "");
  const gameId = root.dataset.gameId;
  const previewLimit = parseInt(root.dataset.previewLimit, 10) || 3;

  const appEl = document.getElementById("world-app");
  const actionsEl = document.getElementById("world-actions");
  const feedbackEl = document.getElementById("world-feedback");
  const panel = document.getElementById("world-side-panel");
  const backdrop = panel.querySelector(".world-side-panel-backdrop");
  const closeBtn = panel.querySelector(".world-side-panel-close");
  const titleEl = panel.querySelector(".world-side-panel-title");
  const bodyEl = panel.querySelector(".world-side-panel-body");
  const statusBar = document.getElementById("status-bar");

  const SECTIONS = {
    overview: () => `/games/${gameId}/world/overview`,
    materialsAbsent: () => `/games/${gameId}/world/materials/absent`,
    materialsAvailable: () => `/games/${gameId}/world/materials/available`,
    materialsStocks: () => `/games/${gameId}/world/materials/stocks`,
    components: () => `/games/${gameId}/world/components`,
    objects: () => `/games/${gameId}/world/objects`,
  };

  const PANELS = {
    "materials-available": { title: "Available to use", section: "materialsAvailable" },
    "materials-stocks": { title: "Gathered stocks", section: "materialsStocks" },
    components: { title: "Components", section: "components" },
    objects: { title: "Objects", section: "objects" },
  };

  const sectionCache = {};

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function capitalize(value) {
    const s = String(value || "");
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  }

  function pct(value) {
    return Math.round(Number(value) * 100);
  }

  function setStatus(message) {
    if (!statusBar) return;
    if (message) {
      statusBar.textContent = message;
      statusBar.classList.add("is-visible");
      document.body.classList.add("has-status-bar");
    } else {
      statusBar.classList.remove("is-visible");
      document.body.classList.remove("has-status-bar");
    }
  }

  function componentBadges(display) {
    const badges = [];
    if (display.kind === "starter") badges.push('<span class="badge">starter</span>');
    if (display.role === "fire") badges.push('<span class="badge">fire</span>');
    else if (display.role === "water") badges.push('<span class="badge">water</span>');
    else badges.push('<span class="badge">machine</span>');
    return badges.join("");
  }

  function objectBadge(role) {
    if (role === "furniture") return '<span class="badge">furniture</span>';
    if (role === "dwelling") return '<span class="badge">dwelling</span>';
    if (role === "material") return '<span class="badge">processed</span>';
    return '<span class="badge">object</span>';
  }

  function renderStat(name, value) {
    return `
      <div class="stat">
        <span>${esc(name)}</span>
        <meter value="${esc(value)}" max="1"></meter> ${pct(value)}%
      </div>`;
  }

  function sectionMore(count) {
    if (count > previewLimit) return `<p class="section-more">View all ${count} →</p>`;
    if (count > 0) return `<p class="section-more">View details →</p>`;
    return "";
  }

  function renderHeader(overview) {
    const region = overview.region || {};
    const res = overview.resources || {};
    return `
      <section class="panel world-header">
        <div class="world-header-row">
          <div class="world-name">
            <h2>The cave</h2>
            <form class="rename-form" data-action="rename">
              <input type="hidden" name="region_id" value="${esc(region.id)}">
              <input type="text" name="name" value="${esc(region.name)}" class="name-input">
              <button type="submit" class="small">Rename</button>
            </form>
            <p class="meta">${esc((region.biome_tags || []).join(", "))}</p>
          </div>
          <div class="world-turn">
            <h2>Turn ${esc(overview.turn)} · ${esc(capitalize(overview.era))}</h2>
            <p class="meta">Path divergence: ${pct(overview.path_divergence || 0)}% · Inventions: ${esc(overview.invention_count || 0)}</p>
            <div class="stats-grid">
              ${renderStat("Warmth", res.warmth)}
              ${renderStat("Water", res.water)}
              ${renderStat("Food", res.food)}
              ${renderStat("Materials", res.materials)}
              ${renderStat("Knowledge", res.knowledge)}
            </div>
          </div>
        </div>
      </section>`;
  }

  function renderMaterialsPanel(absent, available, stocks) {
    const absentItems = (absent.items || [])
      .map((m) => `<li><span class="badge warn">${esc(m.name)}</span></li>`)
      .join("");
    const availItems = (available.items || [])
      .slice(0, previewLimit)
      .map((m) => {
        const meter =
          m.source === "deposit"
            ? `<meter value="${esc(m.abundance)}" max="1"></meter> ${pct(m.abundance)}%`
            : "";
        const badge = m.badge ? `<span class="badge">${esc(m.badge)}</span>` : "";
        return `<li><strong>${esc(m.name)}</strong> ${badge} ${meter}</li>`;
      })
      .join("");
    const stockItems = (stocks.stocks || [])
      .slice(0, previewLimit)
      .map((s) => `<li>${esc(s.name)}: ${pct(s.stock)}%</li>`)
      .join("");

    return `
      <section class="panel materials-panel">
        <h2>What the cave offers</h2>
        <div class="materials-columns">
          <div class="materials-col">
            <h3>Not here</h3>
            <ul class="entity-list">${
              absentItems || '<li class="muted">Nothing ruled out yet.</li>'
            }</ul>
          </div>
          <a href="#materials-available" class="materials-col materials-col-link" data-world-panel="materials-available">
            <h3>Available to use <span class="section-count">${(available.items || []).length}</span></h3>
            <ul class="entity-list">${
              availItems || '<li class="muted">Nothing available yet.</li>'
            }</ul>
            ${sectionMore((available.items || []).length)}
          </a>
          <a href="#materials-stocks" class="materials-col materials-col-link" data-world-panel="materials-stocks">
            <h3>Gathered stocks <span class="section-count">${(stocks.stocks || []).length}</span></h3>
            <ul class="entity-list">${
              stockItems || '<li class="muted">None gathered yet.</li>'
            }</ul>
            ${sectionMore((stocks.stocks || []).length)}
          </a>
        </div>
      </section>`;
  }

  function renderEntityPreview(item, kind) {
    const display = item.display || {};
    if (kind === "component") {
      return `
        <li>
          ${componentBadges(display)}
          <strong>${esc(display.label || item.name)}</strong>
          <span class="health">health ${pct(item.health)}%</span>
          ${item.operational ? "" : '<span class="badge warn">offline</span>'}
        </li>`;
    }
    return `
      <li>
        ${objectBadge(display.role)}
        <strong>${esc(display.label || item.name)}</strong>
        <span class="health">health ${pct(item.health)}%</span>
        ${item.operational ? "" : '<span class="badge warn">broken</span>'}
      </li>`;
  }

  function renderEntitiesRow(components, objects) {
    const compItems = (components.items || [])
      .slice(0, previewLimit)
      .map((e) => renderEntityPreview(e, "component"))
      .join("");
    const objItems = (objects.items || [])
      .slice(0, previewLimit)
      .map((e) => renderEntityPreview(e, "object"))
      .join("");

    return `
      <div class="world-entities-row">
        <a href="#components" class="panel section-link-panel" data-world-panel="components">
          <h2>Components <span class="section-count">${(components.items || []).length}</span></h2>
          <p class="muted">Machines — fire, water, tools. Used at Discover.</p>
          <ul class="entity-grid">${
            compItems || '<li class="muted">No components yet.</li>'
          }</ul>
          ${sectionMore((components.items || []).length)}
        </a>
        <a href="#objects" class="panel section-link-panel" data-world-panel="objects">
          <h2>Objects <span class="section-count">${(objects.items || []).length}</span></h2>
          <p class="muted">Inanimate things — furniture, shelters, houses.</p>
          <ul class="entity-grid">${
            objItems || '<li class="muted">None yet.</li>'
          }</ul>
          ${sectionMore((objects.items || []).length)}
        </a>
      </div>`;
  }

  function renderActions(overview) {
    const regionId = overview.region?.id || "";
    return `
      <a href="/invent" class="button primary">Invent something</a>
      <a href="/lab" class="button">Discover</a>
      <button type="button" class="button" data-action="survey" data-region-id="${esc(regionId)}">Survey the cave</button>
      <button type="button" class="button" data-action="tick">Advance turn</button>`;
  }

  function renderWorldPage(sections) {
    appEl.innerHTML =
      renderHeader(sections.overview) +
      renderMaterialsPanel(
        sections.materialsAbsent,
        sections.materialsAvailable,
        sections.materialsStocks
      ) +
      renderEntitiesRow(sections.components, sections.objects);
    actionsEl.innerHTML = renderActions(sections.overview);
  }

  function renderCapabilities(caps) {
    if (!caps || !Object.keys(caps).length) return "";
    const rows = Object.entries(caps)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(
        ([key, val]) => `
        <div class="cap-row">
          <dt>${esc(key.replace(/_/g, " "))}</dt>
          <dd><meter value="${esc(val)}" max="1"></meter></dd>
          <dd>${pct(val)}%</dd>
        </div>`
      )
      .join("");
    return `<dl class="cap-list">${rows}</dl>`;
  }

  function renderMaterialsAvailableDetail(data) {
    const cards = (data.items || [])
      .map((m) => {
        if (m.source === "deposit") {
          return `
          <li class="detail-card">
            <div class="detail-card-head">
              <strong>${esc(m.name)}</strong>
              <span class="badge">deposit</span>
            </div>
            <p class="detail-line">
              <meter value="${esc(m.abundance)}" max="1"></meter>
              ${pct(m.abundance)}% abundant · ${esc(capitalize(m.depth))} depth
            </p>
            ${m.description ? `<p class="muted detail-desc">${esc(m.description)}</p>` : ""}
          </li>`;
        }
        return `
        <li class="detail-card">
          <div class="detail-card-head">
            <strong>${esc(m.name)}</strong>
            <span class="badge">${esc(m.badge)}</span>
          </div>
          <p class="muted detail-desc">Always available through ${esc(m.badge)}.</p>
        </li>`;
      })
      .join("");

    return `
      <p class="muted">Materials you can gather or combine at the discovery bench.</p>
      <ul class="detail-list">${cards || '<li class="muted">Nothing available yet.</li>'}</ul>
      ${data.undiscovered_hint ? `<p class="muted detail-footnote">${esc(data.undiscovered_hint)}</p>` : ""}`;
  }

  function renderMaterialsStocksDetail(data) {
    const stockCards = (data.stocks || [])
      .map(
        (s) => `
        <li class="detail-card">
          <div class="detail-card-head">
            <strong>${esc(s.name)}</strong>
            <span class="badge">${pct(s.stock)}%</span>
          </div>
          <p class="detail-line">
            <meter value="${esc(s.stock)}" max="1"></meter>
            ${pct(s.stock)}% of storage
          </p>
        </li>`
      )
      .join("");

    const compoundBlock = (data.compounds || []).length
      ? `
      <h3>Novel compounds</h3>
      <ul class="detail-list">
        ${data.compounds
          .map(
            (c) => `
          <li class="detail-card">
            <div class="detail-card-head">
              <strong>${esc(c.name)}</strong>
              <span class="badge">compound</span>
            </div>
            <p class="muted detail-desc">Discovered through experimentation.</p>
          </li>`
          )
          .join("")}
      </ul>`
      : "";

    return `
      <p class="muted">Material you have already collected and stored.</p>
      <ul class="detail-list">${
        stockCards ||
        '<li class="muted">None gathered yet — survey, scavenge, or combine materials to build stocks.</li>'
      }</ul>
      ${compoundBlock}`;
  }

  function renderEntityDetailCard(item, kind) {
    const display = item.display || {};
    const tags = (item.tags || [])
      .map((tag) => `<span class="badge">${esc(tag)}</span>`)
      .join("");
    const warn =
      kind === "component"
        ? item.operational
          ? ""
          : '<span class="badge warn">offline</span>'
        : item.operational
          ? ""
          : '<span class="badge warn">broken</span>';

    return `
      <li class="detail-card">
        <div class="detail-card-head">
          ${kind === "component" ? componentBadges(display) : objectBadge(display.role)}
          <strong>${esc(display.label || item.name)}</strong>
          ${warn}
        </div>
        <p class="muted detail-desc">${esc(display.hint || "")}</p>
        <p class="detail-line">Health ${pct(item.health)}% · ${esc(item.region_name || item.region_id)}</p>
        <p class="detail-line muted">${esc(item.type)}</p>
        ${tags ? `<p class="detail-tags">${tags}</p>` : ""}
        ${renderCapabilities(item.capabilities)}
      </li>`;
  }

  function renderComponentsDetail(data) {
    const cards = (data.items || [])
      .map((e) => renderEntityDetailCard(e, "component"))
      .join("");
    return `
      <p class="muted">Machines — fire, water, tools. Used at <a href="/lab">Discover</a>.</p>
      <ul class="detail-list">${cards || '<li class="muted">No components yet.</li>'}</ul>`;
  }

  function renderObjectsDetail(data) {
    const cards = (data.items || []).map((e) => renderEntityDetailCard(e, "object")).join("");
    return `
      <p class="muted">Inanimate things — furniture, shelters, houses. Combine at <a href="/lab">Discover</a>.</p>
      <ul class="detail-list">${
        cards || '<li class="muted">None yet — combine materials into seats, tables, or shelters.</li>'
      }</ul>`;
  }

  const DETAIL_RENDERERS = {
    materialsAvailable: renderMaterialsAvailableDetail,
    materialsStocks: renderMaterialsStocksDetail,
    components: renderComponentsDetail,
    objects: renderObjectsDetail,
  };

  function renderFeedback(title, bodyHtml) {
    feedbackEl.innerHTML = `
      <section class="panel feedback-recent">
        <h2>${esc(title)}</h2>
        ${bodyHtml}
        <button type="button" class="button small" data-action="dismiss-feedback">Dismiss</button>
      </section>`;
    feedbackEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderSurveyFeedback(result) {
    const discoveries = (result.discoveries || [])
      .map(
        (d) =>
          `<li><strong>${esc(d.name)}</strong> <span class="muted">${esc(d.description || "")}</span></li>`
      )
      .join("");
    const feedback = (result.feedback || []).map((f) => `<li>${esc(f)}</li>`).join("");
    renderFeedback(
      `Cave survey — Turn ${result.turn}`,
      `${discoveries ? `<h3>New discoveries</h3><ul class="entity-list">${discoveries}</ul>` : ""}
       <h3>What you learned</h3>
       <ul class="feedback">${feedback || "<li>Nothing new this time.</li>"}</ul>`
    );
  }

  function renderTickFeedback(result) {
    const resources = Object.entries(result.resource_deltas || {})
      .map(([k, v]) => `<li>${esc(k)}: ${v >= 0 ? "+" : ""}${Number(v).toFixed(3)}</li>`)
      .join("");
    const climate = Object.entries(result.climate_deltas || {})
      .map(([k, v]) => `<li>${esc(k)}: ${v >= 0 ? "+" : ""}${Number(v).toFixed(3)}</li>`)
      .join("");
    const feedback = (result.feedback || []).map((f) => `<li>${esc(f)}</li>`).join("");
    const events = (result.events || [])
      .map(
        (e) =>
          `<div class="event-card"><strong>${esc(e.type)}</strong> severity ${Number(e.severity).toFixed(2)}${
            e.region_name || e.region_id ? ` in ${esc(e.region_name || e.region_id)}` : ""
          }</div>`
      )
      .join("");
    const impacts = (result.impacts || [])
      .map(
        (i) =>
          `<li><strong>${esc(i.entity_name || i.entity_id)}</strong>: damage ${Number(i.damage).toFixed(2)}, health ${pct(i.health_after)}%${
            i.operational ? "" : ' <span class="badge warn">offline</span>'
          }</li>`
      )
      .join("");

    renderFeedback(
      `Turn ${result.turn} complete`,
      `<h3>Resource changes</h3><ul>${resources || "<li>None</li>"}</ul>
       <h3>Climate changes</h3><ul>${climate || "<li>None</li>"}</ul>
       <h3>Feedback</h3><ul class="feedback">${feedback || "<li>Quiet turn.</li>"}</ul>
       ${events ? `<h3>Events</h3>${events}` : ""}
       ${impacts ? `<h3>Impacts</h3><ul>${impacts}</ul>` : ""}`
    );
  }

  function invalidateSections() {
    Object.keys(sectionCache).forEach((key) => delete sectionCache[key]);
  }

  async function fetchSection(key, forceRefresh) {
    if (!forceRefresh && sectionCache[key]) return sectionCache[key];
    const path = SECTIONS[key]?.();
    if (!path) throw new Error(`Unknown section: ${key}`);
    const res = await fetch(`${apiBase}${path}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    sectionCache[key] = await res.json();
    return sectionCache[key];
  }

  async function fetchAllSections(forceRefresh) {
    const keys = Object.keys(SECTIONS);
    const results = await Promise.all(keys.map((key) => fetchSection(key, forceRefresh)));
    return Object.fromEntries(keys.map((key, i) => [key, results[i]]));
  }

  function setHash(id) {
    history.replaceState(null, "", id ? `#${id}` : window.location.pathname);
  }

  function closePanel() {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    document.body.classList.remove("world-panel-open");
    setHash("");
  }

  async function refreshWorld(forceRefresh) {
    const sections = await fetchAllSections(forceRefresh);
    renderWorldPage(sections);
    if (panel.classList.contains("is-open")) {
      const panelId = window.location.hash.replace(/^#/, "");
      const config = PANELS[panelId];
      const render = config ? DETAIL_RENDERERS[config.section] : null;
      if (render && sections[config.section]) {
        bodyEl.innerHTML = render(sections[config.section]);
      }
    }
    return sections;
  }

  async function openPanel(panelId) {
    const config = PANELS[panelId];
    const render = config ? DETAIL_RENDERERS[config.section] : null;
    if (!config || !render) return;

    titleEl.textContent = config.title;
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    document.body.classList.add("world-panel-open");
    setHash(panelId);
    bodyEl.innerHTML = '<p class="muted world-panel-loading">Loading…</p>';

    try {
      const data = await fetchSection(config.section, false);
      bodyEl.innerHTML = render(data);
    } catch (_err) {
      bodyEl.innerHTML = '<p class="error">Could not load details from the API. Try again.</p>';
    }
  }

  async function apiPost(path, body) {
    const res = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function handleRename(form) {
    const regionId = form.querySelector('[name="region_id"]').value;
    const name = form.querySelector('[name="name"]').value.trim();
    if (!name) return;
    setStatus("Saving…");
    try {
      await apiPost(`/games/${gameId}/regions/${regionId}/name`, { name });
      invalidateSections();
      await refreshWorld(true);
      setStatus("Saved");
      window.setTimeout(() => setStatus(""), 2000);
    } catch (_err) {
      setStatus("Could not save name");
    }
  }

  async function handleSurvey(regionId) {
    setStatus("Surveying…");
    document.body.classList.add("is-waiting");
    try {
      const result = await apiPost(`/games/${gameId}/regions/${regionId}/survey`);
      invalidateSections();
      await refreshWorld(true);
      renderSurveyFeedback(result);
      setStatus("Survey complete");
      window.setTimeout(() => setStatus(""), 2500);
    } catch (_err) {
      setStatus("Survey failed");
    } finally {
      document.body.classList.remove("is-waiting");
    }
  }

  async function handleTick() {
    setStatus("Advancing turn…");
    document.body.classList.add("is-waiting");
    try {
      const result = await apiPost(`/games/${gameId}/tick`);
      invalidateSections();
      await refreshWorld(true);
      renderTickFeedback(result);
      setStatus("Turn advanced");
      window.setTimeout(() => setStatus(""), 2500);
    } catch (_err) {
      setStatus("Could not advance turn");
    } finally {
      document.body.classList.remove("is-waiting");
    }
  }

  root.addEventListener("click", (event) => {
    const panelTrigger = event.target.closest("[data-world-panel]");
    if (panelTrigger) {
      event.preventDefault();
      openPanel(panelTrigger.dataset.worldPanel);
      return;
    }

    const actionEl = event.target.closest("[data-action]");
    if (!actionEl) return;

    if (actionEl.dataset.action === "survey") {
      handleSurvey(actionEl.dataset.regionId);
    } else if (actionEl.dataset.action === "tick") {
      handleTick();
    } else if (actionEl.dataset.action === "dismiss-feedback") {
      feedbackEl.innerHTML = "";
    }
  });

  root.addEventListener("submit", (event) => {
    const form = event.target.closest('[data-action="rename"]');
    if (!form) return;
    event.preventDefault();
    handleRename(form);
  });

  closeBtn.addEventListener("click", closePanel);
  backdrop.addEventListener("click", closePanel);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panel.classList.contains("is-open")) {
      closePanel();
    }
  });

  async function init() {
    if (!apiBase || !gameId) {
      appEl.innerHTML = '<p class="error">Missing game session.</p>';
      return;
    }
    try {
      await refreshWorld(true);
      const hashId = window.location.hash.replace(/^#/, "");
      if (hashId && PANELS[hashId]) openPanel(hashId);
    } catch (_err) {
      appEl.innerHTML =
        '<p class="error">Could not load the cave from the API. Is the backend running?</p>';
    }
  }

  init();
})();
