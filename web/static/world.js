(function () {
  const root = document.getElementById("world-root");
  if (!root || !window.What || !window.WhatDisplay) return;

  const { esc, pct, capitalize, fmtFixed, setStatus, createClient } = window.What;
  const { componentBadges, objectBadge } = window.WhatDisplay;

  const client = createClient({ root });
  const previewLimit = parseInt(root.dataset.previewLimit, 10) || 8;
  const gfx = () => window.WhatGraphics;

  function gSlot(subjectType, item, options) {
    if (!gfx() || !item) return "";
    return gfx().slotHtml(gfx().descriptor(subjectType, item), options);
  }

  function hydrateGfx(node) {
    if (!gfx()) return;
    gfx().hydrate(node || document, { apiBase: client.apiBase, gameId: client.gameId });
  }

  const appEl = document.getElementById("world-app");
  const actionsEl = document.getElementById("world-actions");
  const feedbackEl = document.getElementById("world-feedback");
  const panel = document.getElementById("world-side-panel");
  const backdrop = panel.querySelector(".world-side-panel-backdrop");
  const closeBtn = panel.querySelector(".world-side-panel-close");
  const backBtn = panel.querySelector(".world-side-panel-back");
  const titleEl = panel.querySelector(".world-side-panel-title");
  const bodyEl = panel.querySelector(".world-side-panel-body");
  const statusBar = document.getElementById("status-bar");

  let panelState = { panelId: null, itemRef: null };

  const SECTIONS = {
    overview: () => client.worldOverview(client.getRegionId()),
    materialsAbsent: () => client.worldMaterialsAbsent(client.getRegionId()),
    materialsAvailable: () => client.worldMaterialsAvailable(client.getRegionId()),
    materialsStocks: () => client.worldMaterialsStocks(client.getRegionId()),
    components: () => client.worldComponents(client.getRegionId()),
    objects: () => client.worldObjects(client.getRegionId()),
  };

  const PANELS = {
    "materials-available": { title: "Available to use", section: "materialsAvailable" },
    "materials-stocks": { title: "Gathered stocks", section: "materialsStocks" },
    components: { title: "Components", section: "components" },
    objects: { title: "Objects", section: "objects" },
  };

  const sectionCache = {};

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
        <div class="world-top-row">
          <div class="world-name">
            <h2>${esc(region.name || "The cave")}</h2>
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
          <div class="world-paths">${renderExitsBlock(overview)}</div>
        </div>
      </section>`;
  }

  function renderExitsBlock(overview) {
    const exits = overview.exits || [];
    const hidden = exits.filter((e) => e.status === "hidden");
    const found = exits.filter((e) => e.status === "found");
    const open = exits.filter((e) => e.status === "open");
    const regionId = overview.region?.id || "";

    if (!exits.length) {
      return `
        <h2>Paths</h2>
        <p class="muted">No exits known from here yet.</p>`;
    }

    const openRows = open
      .map(
        (e) => `
        <li class="exit-row exit-open">
          <div>
            <strong>${esc(e.name)}</strong>
            <span class="muted"> → ${esc(e.target_region_name)}</span>
            <p class="muted exit-desc">${esc(e.description)}</p>
          </div>
          <button type="button" class="button small" data-action="travel"
                  data-target-region="${esc(e.target_region_id)}"
                  data-from-region="${esc(regionId)}">
            Go
          </button>
        </li>`
      )
      .join("");

    const foundRows = found
      .map(
        (e) => `
        <li class="exit-row exit-found">
          <div>
            <strong>${esc(e.name)}</strong>
            <span class="muted"> → ${esc(e.target_region_name)}</span>
            <p class="muted exit-desc">${esc(e.description)}</p>
          </div>
          <button type="button" class="button primary small" data-action="travel"
                  data-target-region="${esc(e.target_region_id)}"
                  data-from-region="${esc(regionId)}">
            Venture out
          </button>
        </li>`
      )
      .join("");

    const hiddenHint =
      hidden.length && !found.length && !open.length
        ? `<p class="muted">Survey this area to search for a way out.</p>`
        : "";

    return `
      <h2>Paths</h2>
      ${hiddenHint}
      <ul class="exit-list">${openRows}${foundRows}</ul>`;
  }

  function materialsPanelTitle(regionId) {
    if (regionId === "outside_slope") return "What the open slope offers";
    return "What the cave offers";
  }

  function renderEntityColumnLink(panelId, title, lede, items, kind, emptyText) {
    const rows = (items || [])
      .slice(0, previewLimit)
      .map((item) => renderEntityPreview(item, kind, panelId))
      .join("");
    const count = (items || []).length;
    return `
      <a href="#${panelId}" class="materials-col materials-col-link" data-world-panel="${panelId}">
        <h3>${esc(title)} <span class="section-count">${count}</span></h3>
        <p class="muted materials-col-lede" title="${esc(lede)}">${esc(lede)}</p>
        <ul class="entity-list entity-list-compact">${rows || `<li class="muted">${esc(emptyText)}</li>`}</ul>
        ${sectionMore(count)}
      </a>`;
  }

  function renderMaterialsPanel(absent, available, stocks, components, objects, regionId) {
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
        return `<li class="world-preview-item world-preview-chip" data-world-preview data-world-panel="materials-available" data-world-item="material" data-item-id="${esc(m.id)}">${gSlot("material", m)}<span class="world-preview-text"><strong>${esc(m.name)}</strong> ${badge} ${meter}</span></li>`;
      })
      .join("");
    const stockItems = (stocks.stocks || [])
      .slice(0, previewLimit)
      .map((s) => `<li class="world-preview-item world-preview-chip" data-world-preview data-world-panel="materials-stocks" data-world-item="stock" data-item-id="${esc(s.id)}">${gSlot("stock", s)}<span class="world-preview-text"><strong>${esc(s.name)}</strong> ${pct(s.stock)}%</span></li>`)
      .join("");

    return `
      <section class="panel materials-panel">
        <h2>${esc(materialsPanelTitle(regionId))}</h2>
        <div class="materials-columns materials-columns-all">
          <div class="materials-col">
            <h3>Not here</h3>
            <ul class="entity-list entity-list-compact">${
              absentItems || '<li class="muted">Nothing ruled out yet.</li>'
            }</ul>
          </div>
          <a href="#materials-available" class="materials-col materials-col-link" data-world-panel="materials-available">
            <h3>Available to use <span class="section-count">${(available.items || []).length}</span></h3>
            <ul class="entity-list entity-list-compact">${
              availItems || '<li class="muted">Nothing available yet.</li>'
            }</ul>
            ${sectionMore((available.items || []).length)}
          </a>
          <a href="#materials-stocks" class="materials-col materials-col-link" data-world-panel="materials-stocks">
            <h3>Gathered stocks <span class="section-count">${(stocks.stocks || []).length}</span></h3>
            <ul class="entity-list entity-list-compact">${
              stockItems || '<li class="muted">None gathered yet.</li>'
            }</ul>
            ${sectionMore((stocks.stocks || []).length)}
          </a>
          ${renderEntityColumnLink(
            "components",
            "Components",
            "Machines — fire, water, tools.",
            components.items,
            "component",
            "No components yet."
          )}
          ${renderEntityColumnLink(
            "objects",
            "Objects",
            "Furniture, shelters, houses.",
            objects.items,
            "object",
            "None yet."
          )}
        </div>
      </section>`;
  }

  function renderEntityPreview(item, kind, panelId) {
    const display = item.display || {};
    const countBadge = item.count > 1 ? `<span class="badge">×${item.count}</span>` : "";
    const itemType = item.count > 1 ? "entity-group" : "entity";
    const attrs = `class="world-preview-item world-preview-chip" data-world-preview data-world-panel="${panelId}" data-world-item="${itemType}" data-item-id="${esc(item.id)}"`;
    const warn =
      kind === "component"
        ? item.operational
          ? ""
          : '<span class="badge warn">offline</span>'
        : item.operational
          ? ""
          : '<span class="badge warn">broken</span>';
    const badges = kind === "component" ? componentBadges(display) : objectBadge(display.role);
    return `
      <li ${attrs}>
        ${gSlot(kind, item)}
        <span class="world-preview-text">${badges}<strong>${esc(display.label || item.name)}</strong>${countBadge}${warn}</span>
      </li>`;
  }

  function renderActions(overview) {
    const regionId = overview.region?.id || "";
    const surveyLabel = regionId === "outside_slope" ? "Survey the slope" : "Survey the cave";
    return `
      <a href="/invent" class="button primary">Invent something</a>
      <a href="/lab" class="button">Discover</a>
      <button type="button" class="button" data-action="survey" data-region-id="${esc(regionId)}">${surveyLabel}</button>
      <button type="button" class="button" data-action="tick">Advance turn</button>`;
  }

  function renderWorldPage(sections) {
    const regionId = sections.overview?.region?.id || "";
    appEl.innerHTML =
      renderHeader(sections.overview) +
      renderMaterialsPanel(
        sections.materialsAbsent,
        sections.materialsAvailable,
        sections.materialsStocks,
        sections.components,
        sections.objects,
        regionId
      );
    actionsEl.innerHTML = renderActions(sections.overview);
    hydrateGfx(appEl);
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

  function renderDetailFields(fields) {
    const rows = fields
      .filter((f) => f.value != null && f.value !== "")
      .map(
        (f) => `
        <div class="detail-field">
          <dt>${esc(f.label)}</dt>
          <dd>${f.html != null ? f.html : esc(String(f.value))}</dd>
        </div>`
      )
      .join("");
    return rows ? `<dl class="detail-fields">${rows}</dl>` : "";
  }

  function renderTagPills(tags) {
    if (!tags?.length) return "";
    return `<span class="detail-tags">${tags.map((t) => `<span class="badge">${esc(t)}</span>`).join(" ")}</span>`;
  }

  function healthMeter(value) {
    return `<meter value="${esc(value)}" max="1"></meter> ${pct(value)}%`;
  }

  function roleLabel(display, kind) {
    if (kind === "component") {
      if (display.role === "fire") return "Fire source";
      if (display.role === "water") return "Water source";
      if (display.kind === "starter") return "Starter machine";
      return "Machine / tool";
    }
    if (display.role === "furniture") return "Furniture";
    if (display.role === "dwelling") return "Shelter";
    if (display.role === "material") return "Processed material";
    return "Object";
  }

  function panelListRow(type, id, panelId, mainHtml, meta, item, visualType) {
    const slot = item && visualType ? gSlot(visualType, item) : "";
    return `
      <li class="panel-item-row" role="button" tabindex="0"
          data-world-item="${esc(type)}" data-item-id="${esc(id)}" data-world-panel="${esc(panelId)}">
        <div class="panel-item-main">${slot}${mainHtml}</div>
        ${meta ? `<span class="panel-item-meta">${meta}</span>` : ""}
        <span class="panel-item-chevron" aria-hidden="true">›</span>
      </li>`;
  }

  function renderMaterialsAvailableList(data) {
    const rows = (data.items || [])
      .map((m) => {
        const meta =
          m.source === "deposit"
            ? `${pct(m.abundance)}% · ${capitalize(m.depth)}`
            : esc(m.badge || "");
        const badge =
          m.source === "deposit"
            ? '<span class="badge">deposit</span>'
            : m.badge
              ? `<span class="badge">${esc(m.badge)}</span>`
              : "";
        return panelListRow(
          "material",
          m.id,
          "materials-available",
          `<span class="panel-item-name">${esc(m.name)}</span> ${badge}`,
          meta,
          m,
          "material"
        );
      })
      .join("");

    return `
      <p class="muted">Materials you can gather or combine at the discovery bench.</p>
      <ul class="panel-item-list">${rows || '<li class="muted">Nothing available yet.</li>'}</ul>
      ${data.undiscovered_hint ? `<p class="muted detail-footnote">${esc(data.undiscovered_hint)}</p>` : ""}`;
  }

  function renderMaterialsStocksList(data) {
    const stockRows = (data.stocks || [])
      .map((s) =>
        panelListRow(
          "stock",
          s.id,
          "materials-stocks",
          `<span class="panel-item-name">${esc(s.name)}</span>`,
          `${pct(s.stock)}%`,
          s,
          "stock"
        )
      )
      .join("");

    const compoundRows = (data.compounds || [])
      .map((c) =>
        panelListRow(
          "compound",
          c.id,
          "materials-stocks",
          `<span class="panel-item-name">${esc(c.name)}</span> <span class="badge">compound</span>`,
          "discovered",
          c,
          "compound"
        )
      )
      .join("");

    return `
      <p class="muted">Material you have already collected and stored.</p>
      <ul class="panel-item-list">${
        stockRows ||
        '<li class="muted">None gathered yet — survey, scavenge, or combine materials to build stocks.</li>'
      }</ul>
      ${compoundRows ? `<h3>Novel compounds</h3><ul class="panel-item-list">${compoundRows}</ul>` : ""}`;
  }

  function renderEntityList(data, kind, panelId) {
    const rows = (data.items || [])
      .map((item) => {
        const display = item.display || {};
        const countBadge = item.count > 1 ? `<span class="badge">×${item.count}</span>` : "";
        const itemType = item.count > 1 ? "entity-group" : "entity";
        const badge =
          kind === "component" ? componentBadges(display) : objectBadge(display.role);
        const warn =
          kind === "component"
            ? item.operational
              ? ""
              : '<span class="badge warn">offline</span>'
            : item.operational
              ? ""
              : '<span class="badge warn">broken</span>';
        return panelListRow(
          itemType,
          item.id,
          panelId,
          `${badge} <span class="panel-item-name">${esc(display.label || item.name)}</span> ${countBadge} ${warn}`,
          `health ${pct(item.health)}%`,
          item,
          kind
        );
      })
      .join("");

    const lede =
      kind === "component"
        ? 'Machines — fire, water, tools. Used at <a href="/lab">Discover</a>.'
        : "Inanimate things — furniture, shelters, houses. Combine at <a href=\"/lab\">Discover</a>.";

    return `
      <p class="muted">${lede}</p>
      <ul class="panel-item-list">${rows || `<li class="muted">No ${kind === "component" ? "components" : "objects"} yet.</li>`}</ul>`;
  }

  function renderComponentsList(data) {
    return renderEntityList(data, "component", "components");
  }

  function renderObjectsList(data) {
    return renderEntityList(data, "object", "objects");
  }

  const LIST_RENDERERS = {
    materialsAvailable: renderMaterialsAvailableList,
    materialsStocks: renderMaterialsStocksList,
    components: renderComponentsList,
    objects: renderObjectsList,
  };

  function renderEntityFullDetail(item, kind) {
    const display = item.display || {};
    const countBadge = item.count > 1 ? `<span class="badge">×${item.count}</span>` : "";
    const warn =
      kind === "component"
        ? item.operational
          ? ""
          : '<span class="badge warn">offline</span>'
        : item.operational
          ? ""
          : '<span class="badge warn">broken</span>';
    const caps = item.active_capabilities || item.capabilities || {};
    const fields = [
      { label: "Role", value: roleLabel(display, kind) },
      { label: "Status", value: item.status_note || (item.operational ? "Working normally." : "Needs attention.") },
      { label: "Health", html: healthMeter(item.health) },
      { label: "Location", value: item.region_name || item.region_id },
      { label: "Type", value: item.type },
      { label: "Classification", value: item.classification },
      {
        label: "Tags",
        html: renderTagPills(item.tags) || null,
      },
    ];

    return `
      <div class="panel-item-detail">
        <div class="detail-card">
          <div class="detail-card-head">
            ${gSlot(kind, item, { large: true })}
            <div class="detail-card-head-text">
              ${kind === "component" ? componentBadges(display) : objectBadge(display.role)}
              <strong>${esc(display.label || item.name)}</strong>
              ${countBadge}
              ${warn}
            </div>
          </div>
          ${display.hint ? `<p class="detail-desc">${esc(display.hint)}</p>` : ""}
          ${renderDetailFields(fields)}
          ${Object.keys(caps).length ? `<h4 class="detail-subhead">Capabilities</h4>${renderCapabilities(caps)}` : ""}
          <p class="detail-footnote muted">Use at <a href="/lab">Discover</a> as a component or ingredient.</p>
        </div>
      </div>`;
  }

  function renderMaterialDetail(m) {
    const fields = [
      {
        label: "Source",
        value: m.source === "deposit" ? "Cave deposit" : "Always nearby",
      },
      { label: "How to get", value: m.obtain },
      { label: "Uses", value: m.uses },
      { label: "Description", value: m.description },
    ];
    if (m.source === "deposit") {
      fields.splice(2, 0, {
        label: "Abundance",
        html: `${healthMeter(m.abundance)} · ${capitalize(m.depth)} depth`,
      });
    }
    if (m.substitutes?.length) {
      fields.push({ label: "Substitutes", value: m.substitutes.join(", ") });
    }
    if (m.tags?.length) {
      fields.push({ label: "Material tags", html: renderTagPills(m.tags) });
    }

    const badge =
      m.source === "deposit"
        ? '<span class="badge">deposit</span>'
        : `<span class="badge">${esc(m.badge || "nearby")}</span>`;

    return `
      <div class="panel-item-detail">
        <div class="detail-card">
          <div class="detail-card-head">
            ${gSlot("material", m, { large: true })}
            <div class="detail-card-head-text"><strong>${esc(m.name)}</strong> ${badge}</div>
          </div>
          ${renderDetailFields(fields)}
          <p class="detail-footnote muted">Select at <a href="/lab">Discover</a> when combining materials.</p>
        </div>
      </div>`;
  }

  function renderStockDetail(s) {
    const fields = [
      { label: "Stored amount", html: `${healthMeter(s.stock)} of storage capacity` },
      { label: "Supply", value: s.storage_note },
      { label: "Uses", value: s.uses },
    ];
    if (s.substitutes?.length) {
      fields.push({ label: "Substitutes", value: s.substitutes.join(", ") });
    }
    if (s.tags?.length) {
      fields.push({ label: "Material tags", html: renderTagPills(s.tags) });
    }

    return `
      <div class="panel-item-detail">
        <div class="detail-card">
          <div class="detail-card-head">
            ${gSlot("stock", s, { large: true })}
            <div class="detail-card-head-text">
              <strong>${esc(s.name)}</strong>
              <span class="badge">${pct(s.stock)}% stored</span>
            </div>
          </div>
          ${renderDetailFields(fields)}
          <p class="detail-footnote muted">Gathered stock is consumed when you experiment at the bench.</p>
        </div>
      </div>`;
  }

  function renderProvenanceList(label, items) {
    if (!items?.length) return "";
    return `
      <div class="detail-field">
        <dt>${esc(label)}</dt>
        <dd>${items.map((i) => `<span class="badge">${esc(i.name)}</span>`).join(" ")}</dd>
      </div>`;
  }

  function renderCompoundDetail(c) {
    const prov = c.provenance || {};
    const madeFromFields = [];
    if (c.made_from) {
      madeFromFields.push({ label: "Made from", value: c.made_from });
    } else if (c.has_provenance === false) {
      madeFromFields.push({
        label: "Made from",
        value: "Not recorded — discovered before recipe tracking was added.",
      });
    }
    if (prov.intent) {
      madeFromFields.push({ label: "Intent", value: prov.intent });
    }
    if (prov.turn != null) {
      madeFromFields.push({ label: "Discovered", value: `Turn ${prov.turn}` });
    }
    if (prov.recipe_id) {
      madeFromFields.push({ label: "Recipe", value: prov.recipe_id });
    }

    const inputLists =
      renderProvenanceList("Materials", prov.materials) +
      renderProvenanceList("Components", prov.components) +
      renderProvenanceList("Objects", prov.objects) +
      renderProvenanceList("Methods", prov.methods);

    return `
      <div class="panel-item-detail">
        <div class="detail-card">
          <div class="detail-card-head">
            ${gSlot("compound", c, { large: true })}
            <div class="detail-card-head-text">
              <strong>${esc(c.name)}</strong>
              <span class="badge">compound</span>
            </div>
          </div>
          ${renderDetailFields([
            ...madeFromFields,
            { label: "Origin", value: prov.source === "invent" ? "Invention" : "Discovery bench experiment" },
            { label: "Description", value: c.description },
            { label: "Uses", value: c.uses },
            { label: "Compound id", value: c.id },
          ])}
          ${inputLists ? `<dl class="detail-fields">${inputLists}</dl>` : ""}
        </div>
      </div>`;
  }

  function renderEntityGroupDetail(item, kind) {
    const instances = (item.instance_ids || [item.id])
      .map(
        (id, i) => `
        <li>
          <button type="button" class="panel-instance-row"
                  data-world-item="entity" data-item-id="${esc(id)}" data-world-panel="${esc(panelState.panelId)}">
            Instance ${i + 1} · health ${pct(item.health)}% · ${esc(id.slice(0, 8))}…
          </button>
        </li>`
      )
      .join("");

    return `
      ${renderEntityFullDetail(item, kind)}
      <h3 class="detail-subhead">${item.count} identical instances</h3>
      <p class="muted">Each instance can be inspected separately — useful when health or status differs.</p>
      <ul class="panel-instance-list">${instances}</ul>`;
  }

  function findCachedItem(itemRef) {
    const config = PANELS[itemRef.panelId];
    if (!config) return null;
    const data = sectionCache[config.section];
    if (!data) return null;

    if (itemRef.type === "material") {
      return (data.items || []).find((m) => m.id === itemRef.id);
    }
    if (itemRef.type === "stock") {
      return (data.stocks || []).find((s) => s.id === itemRef.id);
    }
    if (itemRef.type === "compound") {
      return (data.compounds || []).find((c) => c.id === itemRef.id);
    }
    if (itemRef.type === "entity" || itemRef.type === "entity-group") {
      return (data.items || []).find((e) => e.id === itemRef.id);
    }
    return null;
  }

  async function renderItemDetail(itemRef) {
    const config = PANELS[itemRef.panelId];
    const kind = config?.section === "components" ? "component" : "object";

    if (itemRef.type === "material") {
      const m = findCachedItem(itemRef);
      return m ? renderMaterialDetail(m) : '<p class="error">Material not found.</p>';
    }
    if (itemRef.type === "stock") {
      const s = findCachedItem(itemRef);
      return s ? renderStockDetail(s) : '<p class="error">Stock not found.</p>';
    }
    if (itemRef.type === "compound") {
      const c = findCachedItem(itemRef);
      return c ? renderCompoundDetail(c) : '<p class="error">Compound not found.</p>';
    }
    if (itemRef.type === "entity-group") {
      const item = findCachedItem(itemRef);
      return item
        ? renderEntityGroupDetail(item, kind)
        : '<p class="error">Item not found.</p>';
    }
    if (itemRef.type === "entity") {
      try {
        const entity = await client.getEntity(itemRef.id);
        const entityKind = entity.kind === "component" ? "component" : "object";
        return renderEntityFullDetail(entity, entityKind);
      } catch (_err) {
        const cached = findCachedItem(itemRef);
        if (cached) return renderEntityFullDetail(cached, kind);
        return '<p class="error">Could not load entity details.</p>';
      }
    }
    return '<p class="error">Unknown item type.</p>';
  }

  async function itemDetailTitle(itemRef) {
    const cached = findCachedItem(itemRef);
    if (cached) return cached.name || cached.display?.label || "Details";
    if (itemRef.type === "entity") {
      try {
        const entity = await client.getEntity(itemRef.id);
        return entity.display?.label || entity.name || "Details";
      } catch (_err) {
        return "Details";
      }
    }
    return "Details";
  }

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
    const fetcher = SECTIONS[key];
    if (!fetcher) throw new Error(`Unknown section: ${key}`);
    const data = await fetcher();
    if (key === "overview" && data?.region?.id) {
      client.setRegionId(data.region.id);
    }
    sectionCache[key] = data;
    return data;
  }

  async function fetchAllSections(forceRefresh) {
    const keys = Object.keys(SECTIONS);
    const results = await Promise.all(keys.map((key) => fetchSection(key, forceRefresh)));
    return Object.fromEntries(keys.map((key, i) => [key, results[i]]));
  }

  function parsePanelHash() {
    const raw = window.location.hash.replace(/^#/, "");
    if (!raw || !PANELS[raw.split("/")[0]]) return null;
    const slash = raw.indexOf("/");
    if (slash === -1) return { panelId: raw, itemRef: null };
    const panelId = raw.slice(0, slash);
    const rest = decodeURIComponent(raw.slice(slash + 1));
    const colon = rest.indexOf(":");
    if (colon === -1) return { panelId, itemRef: null };
    return {
      panelId,
      itemRef: {
        type: rest.slice(0, colon),
        id: rest.slice(colon + 1),
        panelId,
      },
    };
  }

  function setPanelHash(panelId, itemRef) {
    if (!panelId) {
      history.replaceState(null, "", window.location.pathname);
      return;
    }
    if (itemRef) {
      history.replaceState(
        null,
        "",
        `#${panelId}/${itemRef.type}:${encodeURIComponent(itemRef.id)}`
      );
    } else {
      history.replaceState(null, "", `#${panelId}`);
    }
  }

  function closePanel() {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    document.body.classList.remove("world-panel-open");
    panelState = { panelId: null, itemRef: null };
    backBtn.hidden = true;
    setPanelHash(null);
  }

  async function renderPanelContent() {
    const { panelId, itemRef } = panelState;
    const config = PANELS[panelId];
    if (!config) return;

    backBtn.hidden = !itemRef;

    if (!itemRef) {
      titleEl.textContent = config.title;
      bodyEl.innerHTML = '<p class="muted world-panel-loading">Loading…</p>';
      try {
        const data = await fetchSection(config.section, false);
        const render = LIST_RENDERERS[config.section];
        bodyEl.innerHTML = render ? render(data) : "";
        bodyEl.scrollTop = 0;
        hydrateGfx(bodyEl);
      } catch (_err) {
        bodyEl.innerHTML = '<p class="error">Could not load details from the API. Try again.</p>';
      }
      return;
    }

    bodyEl.innerHTML = '<p class="muted world-panel-loading">Loading…</p>';
    titleEl.textContent = "…";
    try {
      const [title, html] = await Promise.all([
        itemDetailTitle(itemRef),
        renderItemDetail(itemRef),
      ]);
      titleEl.textContent = title;
      bodyEl.innerHTML = html;
      bodyEl.scrollTop = 0;
      hydrateGfx(bodyEl);
    } catch (_err) {
      bodyEl.innerHTML = '<p class="error">Could not load item details.</p>';
    }
  }

  async function openPanel(panelId, itemRef) {
    const config = PANELS[panelId];
    if (!config) return;

    panelState = { panelId, itemRef: itemRef || null };
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    document.body.classList.add("world-panel-open");
    setPanelHash(panelId, itemRef || null);
    await renderPanelContent();
  }

  function openPanelItem(panelId, type, id) {
    openPanel(panelId, { type, id, panelId });
  }

  async function refreshWorld(forceRefresh) {
    const sections = await fetchAllSections(forceRefresh);
    renderWorldPage(sections);
    if (panel.classList.contains("is-open") && panelState.panelId) {
      await renderPanelContent();
    }
    return sections;
  }

  async function handleRename(form) {
    const regionId = form.querySelector('[name="region_id"]').value;
    const name = form.querySelector('[name="name"]').value.trim();
    if (!name) return;
    setStatus("Saving…");
    try {
      await client.renameRegion(regionId, name);
      invalidateSections();
      await refreshWorld(true);
      setStatus("Saved");
      window.setTimeout(() => setStatus(""), 2000);
    } catch (_err) {
      setStatus("Could not save name");
    }
  }

  async function handleTravel(targetRegionId, fromRegionId) {
    setStatus("Traveling…");
    document.body.classList.add("is-waiting");
    try {
      const result = await client.travelTo(targetRegionId, fromRegionId);
      client.setRegionId(result.region_id);
      invalidateSections();
      await refreshWorld(true);
      renderFeedback(
        `Arrived — ${result.region_name}`,
        `<ul class="feedback">${(result.feedback || []).map((f) => `<li>${esc(f)}</li>`).join("")}</ul>`
      );
      setStatus("Arrived");
      window.setTimeout(() => setStatus(""), 2500);
    } catch (_err) {
      setStatus("Could not travel");
    } finally {
      document.body.classList.remove("is-waiting");
    }
  }

  async function handleSurvey(regionId) {
    setStatus("Surveying…");
    document.body.classList.add("is-waiting");
    try {
      const result = await client.surveyRegion(regionId);
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
      const result = await client.tick();
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
    const previewItem = event.target.closest("[data-world-preview]");
    if (previewItem) {
      event.preventDefault();
      event.stopPropagation();
      openPanelItem(
        previewItem.dataset.worldPanel,
        previewItem.dataset.worldItem,
        previewItem.dataset.itemId
      );
      return;
    }

    const panelItem = event.target.closest("[data-world-item]");
    if (panelItem && panel.contains(panelItem)) {
      event.preventDefault();
      openPanelItem(
        panelItem.dataset.worldPanel,
        panelItem.dataset.worldItem,
        panelItem.dataset.itemId
      );
      return;
    }

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
    } else if (actionEl.dataset.action === "travel") {
      handleTravel(actionEl.dataset.targetRegion, actionEl.dataset.fromRegion);
    } else if (actionEl.dataset.action === "tick") {
      handleTick();
    } else if (actionEl.dataset.action === "dismiss-feedback") {
      feedbackEl.innerHTML = "";
    }
  });

  root.addEventListener("keydown", (event) => {
    const row = event.target.closest(".panel-item-row");
    if (row && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      openPanelItem(row.dataset.worldPanel, row.dataset.worldItem, row.dataset.itemId);
    }
  });

  backBtn.addEventListener("click", () => {
    if (panelState.panelId) {
      openPanel(panelState.panelId);
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
    if (!client.apiBase || !client.gameId) {
      appEl.innerHTML = '<p class="error">Missing game session.</p>';
      return;
    }
    try {
      await refreshWorld(true);
      const parsed = parsePanelHash();
      if (parsed?.panelId) {
        openPanel(parsed.panelId, parsed.itemRef);
      }
    } catch (_err) {
      appEl.innerHTML =
        '<p class="error">Could not load the cave from the API. Is the backend running?</p>';
    }
  }

  init();
})();
