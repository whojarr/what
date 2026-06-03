(function () {
  const { esc, pct, capitalize, fmtFixed, componentBadges, objectBadge } = window.What;
  const gfx = () => window.WhatGraphics;

  function gSlot(subjectType, item) {
    if (!gfx() || !item) return "";
    return gfx().slotHtml(gfx().descriptor(subjectType, item));
  }

  function sectionMore(count, previewLimit) {
    if (count > previewLimit) return `<p class="section-more">View all ${count} →</p>`;
    if (count > 0) return `<p class="section-more">View details →</p>`;
    return "";
  }

  function renderMaterialsPanel(absent, available, stocks, options) {
    const heading = options?.heading || "What the cave offers";
    const previewLimit = options?.previewLimit || 8;
    const linkPanels = options?.linkPanels !== false;

    const absentItems = (absent?.items || [])
      .map((m) => `<li><span class="badge warn">${esc(m.name)}</span></li>`)
      .join("");

    const availItems = (available?.items || [])
      .slice(0, previewLimit)
      .map((m) => {
        const meter =
          m.source === "deposit"
            ? `<meter value="${esc(m.abundance)}" max="1"></meter> ${pct(m.abundance)}%`
            : "";
        const badge = m.badge ? `<span class="badge">${esc(m.badge)}</span>` : "";
        return `<li>${gSlot("material", m)}<strong>${esc(m.name)}</strong> ${badge} ${meter}</li>`;
      })
      .join("");

    const stockItems = (stocks?.stocks || [])
      .slice(0, previewLimit)
      .map((s) => `<li>${gSlot("stock", s)}${esc(s.name)}: ${pct(s.stock)}%</li>`)
      .join("");

    const availCount = (available?.items || []).length;
    const stockCount = (stocks?.stocks || []).length;

    const availCol = linkPanels
      ? `<a href="/world#materials-available" class="materials-col materials-col-link">
          <h3>Available to use <span class="section-count">${availCount}</span></h3>
          <ul class="entity-list">${availItems || '<li class="muted">Nothing available yet.</li>'}</ul>
          ${sectionMore(availCount, previewLimit)}
        </a>`
      : `<div class="materials-col">
          <h3>Available to use <span class="section-count">${availCount}</span></h3>
          <ul class="entity-list">${availItems || '<li class="muted">Nothing available yet.</li>'}</ul>
        </div>`;

    const stockCol = linkPanels
      ? `<a href="/world#materials-stocks" class="materials-col materials-col-link">
          <h3>Materials (In stock) <span class="section-count">${stockCount}</span></h3>
          <ul class="entity-list">${stockItems || '<li class="muted">Nothing in stock yet.</li>'}</ul>
          ${sectionMore(stockCount, previewLimit)}
        </a>`
      : `<div class="materials-col">
          <h3>Materials (In stock) <span class="section-count">${stockCount}</span></h3>
          <ul class="entity-list">${stockItems || '<li class="muted">Nothing in stock yet.</li>'}</ul>
        </div>`;

    return `
      <section class="panel materials-panel">
        <h2>${esc(heading)}</h2>
        <div class="materials-columns">
          <div class="materials-col">
            <h3>Not here</h3>
            <ul class="entity-list">${
              absentItems || '<li class="muted">Nothing ruled out yet.</li>'
            }</ul>
          </div>
          ${availCol}
          ${stockCol}
        </div>
      </section>`;
  }

  function constraintHeading(status) {
    if (status === "VALID") return "Ready to build";
    if (status === "RISKY") return "Risky but possible";
    if (status === "NEEDS_TWEAK") return "Needs a clearer idea";
    return "Blocked";
  }

  function renderCapabilityBars(capabilities, threshold) {
    const min = threshold ?? 0.05;
    const rows = Object.entries(capabilities || {})
      .filter(([, val]) => val > min)
      .map(
        ([key, val]) => `
        <div class="cap-row">
          <span>${esc(key)}</span>
          <meter value="${esc(val)}" max="1"></meter>
          <span>${fmtFixed(val, 2)}</span>
        </div>`
      )
      .join("");
    if (!rows) return "";
    return `<h4>Strengths</h4><div class="cap-bars">${rows}</div>`;
  }

  function renderConstraintBlock(result) {
    const status = result.constraint?.status || "BLOCKED";
    const warnings = (result.constraint?.warnings || [])
      .map((w) => `<p class="warn">${esc(w)}</p>`)
      .join("");
    const hidden = (result.constraint?.hidden_issues || [])
      .map((h) => `<p class="error">${esc(h)}</p>`)
      .join("");
    const hints = (result.constraint?.suggested_adjustments || [])
      .map((adj) => `<p class="muted">Hint: ${esc(adj.suggestion)}</p>`)
      .join("");
    const dropped = (result.normalized?.dropped_capability_keys || []).length
      ? `<p class="muted">Mapped away from this era: ${esc(result.normalized.dropped_capability_keys.join(", "))}</p>`
      : "";
    const memory = (result.memory_hints || []).length
      ? `<h4>Memory</h4><ul>${result.memory_hints.map((h) => `<li>${esc(h)}</li>`).join("")}</ul>`
      : "";

    return `
      ${result.typo_note ? `<p class="warn">${esc(result.typo_note)}</p>` : ""}
      <p class="muted">${esc(result.proposal?.reasoning || "")}</p>
      <p><strong>Type:</strong> ${esc(result.proposal?.type || "")}</p>
      <p><strong>Tags:</strong> ${esc((result.proposal?.tags || []).join(", "))}</p>
      <h4>${constraintHeading(status)} <span class="status-${esc(status)}">(${esc(status)})</span></h4>
      ${warnings}
      ${hidden}
      ${hints}
      ${dropped}
      ${renderCapabilityBars(result.normalized?.capabilities)}
      ${memory}`;
  }

  function renderPlaceSuccess(detail) {
    if (detail.method_learned && detail.entity) {
      return `
        <h3>Deployed</h3>
        <p><strong>${esc(detail.entity.name)}</strong> is now active.</p>
        <p class="muted">You also learned <strong>${esc(detail.method_learned)}</strong>.</p>`;
    }
    if (detail.method_learned) {
      return `
        <h3>Method learned</h3>
        <p>You now know <strong>${esc(detail.method_learned)}</strong>.</p>`;
    }
    if (detail.entity) {
      return `
        <h3>Deployed</h3>
        <p><strong>${esc(detail.entity.name)}</strong> is now active in ${esc(detail.entity.region_id)}.</p>`;
    }
    return "<h3>Done</h3>";
  }

  window.WhatDisplay = {
    renderMaterialsPanel,
    renderConstraintBlock,
    renderCapabilityBars,
    renderPlaceSuccess,
    constraintHeading,
    sectionMore,
    componentBadges,
    objectBadge,
    capitalize,
  };
})();
