(function () {
  const { esc, pct, capitalize, componentBadges, objectBadge } = window.What;
  const gfx = () => window.WhatGraphics;

  function gSlot(subjectType, item, options) {
    if (!gfx() || !item) return "";
    return gfx().slotHtml(gfx().descriptor(subjectType, item), options);
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

  function renderLabMaterialDetail(m) {
    if (!m) return '<p class="error">Material not found.</p>';
    const fields = [
      { label: "Source", value: m.source === "discovered" ? "Novel compound" : m.source || "Available" },
    ];
    if (m.stock > 0.01) {
      fields.push({ label: "In stock", html: healthMeter(m.stock) });
    }
    if (m.abundance != null) {
      fields.push({ label: "Deposit abundance", html: healthMeter(m.abundance) });
    }
    const meta =
      m.stock > 0.01
        ? `<span class="badge">${pct(m.stock)}% in stock</span>`
        : m.source === "scavenging"
          ? '<span class="badge">nearby</span>'
          : m.source === "discovered"
            ? '<span class="badge">compound</span>'
            : m.abundance != null
              ? `<span class="badge">${pct(m.abundance)}% deposit</span>`
              : "";

    return `
      <div class="panel-item-detail">
        <div class="detail-card">
          <div class="detail-card-head">
            ${gSlot("material", m, { large: true })}
            <div class="detail-card-head-text"><strong>${esc(m.name)}</strong> ${meta}</div>
          </div>
          ${renderDetailFields(fields)}
          <p class="detail-footnote muted">Bulk material — consumed when you experiment at the bench.</p>
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
          <p class="detail-footnote muted">In-stock material is consumed when you experiment at the bench.</p>
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

  function renderAbsentMaterialDetail(m) {
    return `
      <div class="panel-item-detail">
        <div class="detail-card">
          <div class="detail-card-head">
            ${gSlot("material", m, { large: true })}
            <div class="detail-card-head-text">
              <strong>${esc(m.name)}</strong>
              <span class="badge warn">not here</span>
            </div>
          </div>
          <p class="detail-desc">This material is not available in the current region. Survey, travel, or invent substitutes if you need it.</p>
        </div>
      </div>`;
  }

  function renderEntityFullDetail(item, kind, options) {
    const footnote = options?.footnote;
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
      {
        label: "Status",
        value: item.status_note || (item.operational ? "Working normally." : "Needs attention."),
      },
      { label: "Health", html: healthMeter(item.health ?? 1) },
      { label: "Location", value: item.region_name || item.region_id },
      { label: "Type", value: item.type },
      { label: "Classification", value: item.classification },
      {
        label: "Tags",
        html: renderTagPills(item.tags) || null,
      },
    ];

    const defaultFootnote =
      kind === "object"
        ? 'Learnt and kept — combine again at <a href="/lab">Discover</a>.'
        : 'Use at <a href="/lab">Discover</a> as a component or ingredient.';
    const hint = display.hint || item.hint || "";

    return `
      <div class="panel-item-detail">
        <div class="detail-card">
          <div class="detail-card-head">
            ${gSlot(kind, item, { large: true })}
            <div class="detail-card-head-text">
              ${kind === "component" ? componentBadges(display) : objectBadge(display.role || item.role)}
              <strong>${esc(display.label || item.label || item.name)}</strong>
              ${countBadge}
              ${warn}
            </div>
          </div>
          ${hint ? `<p class="detail-desc">${esc(hint)}</p>` : ""}
          ${renderDetailFields(fields)}
          ${Object.keys(caps).length ? `<h4 class="detail-subhead">Capabilities</h4>${renderCapabilities(caps)}` : ""}
          <p class="detail-footnote muted">${footnote || defaultFootnote}</p>
        </div>
      </div>`;
  }

  function renderEntityGroupDetail(item, kind, panelId, labMode) {
    const instances = (item.instance_ids || [item.id])
      .map(
        (id, i) => `
        <li>
          <button type="button" class="panel-instance-row"
            ${
              labMode
                ? `data-lab-detail-instance="${esc(id)}" data-lab-detail-kind="${esc(kind)}"`
                : `data-world-item="entity" data-item-id="${esc(id)}" data-world-panel="${esc(panelId)}"`
            }>
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

  function renderMethodDetail(method) {
    if (!method) return '<p class="error">Method not found.</p>';
    const fields = [
      { label: "Status", value: method.known ? "Known — you can use this process" : "Unknown — not learned yet" },
      { label: "Description", value: method.description },
    ];
    if (!method.known && method.hint) {
      fields.push({ label: "How to learn", value: method.hint });
    }

    return `
      <div class="panel-item-detail">
        <div class="detail-card">
          <div class="detail-card-head">
            <div class="detail-card-head-text">
              <strong>${esc(method.name)}</strong>
              ${method.known ? '<span class="badge">known</span>' : '<span class="badge warn">unknown</span>'}
            </div>
          </div>
          ${renderDetailFields(fields)}
          <p class="detail-footnote muted">${
            method.known
              ? "Select at Discover — pick two methods alone to fuse into a new process, or combine with materials and machines."
              : "Invent or discover this process before you can select it at the bench."
          }</p>
        </div>
      </div>`;
  }

  window.WhatItemDetail = {
    gSlot,
    renderCapabilities,
    renderDetailFields,
    renderTagPills,
    healthMeter,
    roleLabel,
    renderMaterialDetail,
    renderLabMaterialDetail,
    renderStockDetail,
    renderCompoundDetail,
    renderAbsentMaterialDetail,
    renderEntityFullDetail,
    renderEntityGroupDetail,
    renderMethodDetail,
    renderProvenanceList,
  };
})();
