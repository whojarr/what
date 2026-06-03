(function () {
  const root = document.getElementById("lab-root");
  if (!root || !window.What || !window.WhatDisplay || !window.WhatItemDetail || !window.WhatSidePanel) return;

  const { esc, pct, setStatus, apiErrorMessage, createClient } = window.What;
  const { componentBadges, objectBadge } = window.WhatDisplay;
  const {
    renderMaterialDetail,
    renderLabMaterialDetail,
    renderStockDetail,
    renderCompoundDetail,
    renderEntityFullDetail,
    renderEntityGroupDetail,
    renderMethodDetail,
  } = window.WhatItemDetail;

  const client = createClient({ root });
  const sidePanel = window.WhatSidePanel.createSidePanel(root, "#lab-side-panel");
  const gfx = () => window.WhatGraphics;

  function gSlot(subjectType, item) {
    if (!gfx() || !item) return "";
    return gfx().slotHtml(gfx().descriptor(subjectType, item));
  }

  function hydrateGfx(node) {
    if (!gfx()) return;
    gfx().hydrate(node || document, { apiBase: client.apiBase, gameId: client.gameId });
  }

  const workspaceEl = document.getElementById("lab-workspace");
  const resultSlot = document.getElementById("lab-result-slot");

  let options = null;
  let lastResult = null;
  let labRefreshGen = 0;
  const selection = {
    material_ids: [],
    component_ids: [],
    object_ids: [],
    method_ids: [],
    intent: "",
  };

  function materialMeta(m) {
    if (m.stock > 0.01) return `stock ${pct(m.stock)}%`;
    if (m.source === "scavenging" || m.source === "hunting" || m.source === "fuel") return "nearby";
    if (m.source === "foraging" || m.source === "gathering" || m.source === "earth") return "nearby";
    if (m.source === "nearby") return "nearby";
    if (m.source === "carried" || m.source === "hauled") return "hauled in";
    if (m.source === "stored") return "stored here";
    if (m.source === "discovered") return "discovered";
    if (m.source === "deposit") return "deposit";
    if (m.abundance != null) return `${pct(m.abundance)}%`;
    return "";
  }

  function renderMethods(methods) {
    if (!methods?.length) return "";
    const pills = methods
      .map((m) => {
        if (m.known) {
          const checked = selection.method_ids.includes(m.id) ? " checked" : "";
          return `
            <label class="method-pill method-known method-pick" title="${esc(m.description || "")}">
              <input type="checkbox" name="method_ids" value="${esc(m.id)}"${checked}>
              ${esc(m.name)}
              <button type="button" class="method-detail-btn" data-lab-detail="method" data-item-id="${esc(m.id)}" aria-label="Details for ${esc(m.name)}">›</button>
            </label>`;
        }
        return `
          <span class="method-pill method-unknown" title="${esc(m.hint || "")}">
            ${esc(m.name)} · ?
            <button type="button" class="method-detail-btn" data-lab-detail="method" data-item-id="${esc(m.id)}" aria-label="Details for ${esc(m.name)}">›</button>
          </span>`;
      })
      .join("");
    return `
      <div class="lab-methods">
        <h3 class="lab-section-title">Methods</h3>
        <p class="muted lab-methods-hint">Select one or two processes — pick exactly two alone to fuse into a new method, or use with materials and machines.</p>
        <div class="method-bar">${pills}</div>
      </div>`;
  }

  function componentsEmptyText() {
    const name = options?.region_name || "this region";
    return `No machines here in ${name}. Fire and water stay in the cave — open a path there, switch Region above, or bring portable tools in a pack.`;
  }

  function renderPickColumn(title, lede, items, kind, emptyText) {
    const nameKey = `${kind}_ids`;
    const inputName =
      kind === "material" ? "material_ids" : kind === "component" ? "component_ids" : "object_ids";

    const rows = (items || [])
      .map((item) => {
        const checked = selection[nameKey].includes(item.id) ? " checked" : "";
        const countBadge = item.count > 1 ? ` <span class="badge">×${item.count}</span>` : "";
        if (kind === "material") {
          const meta = materialMeta(item);
          return `
            <div class="pick-item">
              <label class="pick-item-check" title="Select for experiment">
                <input type="checkbox" name="${inputName}" value="${esc(item.id)}"${checked}>
              </label>
              <button type="button" class="pick-item-info" data-lab-detail="material" data-item-id="${esc(item.id)}">
                ${gSlot("material", item)}
                <span class="pick-item-body"><span>${esc(item.name)}</span>
                ${meta ? `<span class="muted pick-meta">${esc(meta)}</span>` : ""}</span>
              </button>
            </div>`;
        }
        const badge = kind === "component" ? componentBadges(item) : objectBadge(item.role);
        const label = esc(item.label || item.name);
        const hint = esc(item.hint || "");
        const visualType = kind === "component" ? "component" : "object";
        return `
          <div class="pick-item pick-item-tall">
            <label class="pick-item-check" title="Select for experiment">
              <input type="checkbox" name="${inputName}" value="${esc(item.id)}"${checked}>
            </label>
            <button type="button" class="pick-item-info" data-lab-detail="${esc(kind)}" data-item-id="${esc(item.id)}">
              ${gSlot(visualType, item)}
              <div class="pick-item-body">
                <div>${badge} <strong>${label}</strong>${countBadge}</div>
                <span class="muted pick-hint">${hint}</span>
              </div>
            </button>
          </div>`;
      })
      .join("");

    return `
      <div class="lab-column">
        <h3>${esc(title)}</h3>
        <p class="muted">${esc(lede)}</p>
        <div class="pick-grid pick-grid-stack">
          ${rows || `<p class="muted lab-empty">${esc(emptyText)}</p>`}
        </div>
      </div>`;
  }

  function renderWorkspace(error) {
    if (!options) return;
    workspaceEl.innerHTML = `
      <form class="lab-form" id="lab-form">
        ${renderMethods(options.methods)}
        <div class="lab-columns">
          ${renderPickColumn("Materials", "Flint, bone, hide, ore.", options.materials, "material", "Nothing available.")}
          ${renderPickColumn(
            "Components",
            "Machines — fire, water, tools.",
            options.components,
            "component",
            componentsEmptyText()
          )}
          ${renderPickColumn("Objects (Learnt)", "Things you built and kept.", options.objects, "object", "None learnt yet — build from materials.")}
        </div>
        <div class="lab-actions">
          <label class="lab-intent">What are you trying?
            <input type="text" name="intent" autocomplete="off"
                   placeholder="e.g. stitch a raincoat"
                   value="${esc(selection.intent)}">
          </label>
          <button type="submit" class="primary">Try combination</button>
        </div>
      </form>
      ${error ? `<p class="error lab-error feedback-recent">${esc(error)}</p>` : ""}`;
    hydrateGfx(workspaceEl);
  }

  function renderResult(result) {
    if (!result) {
      resultSlot.innerHTML = "";
      return;
    }

    const feedback = (result.feedback || [])
      .map(
        (f, i) =>
          `<p class="${i === 0 && result.recipe_match ? "warn" : "muted"} result-line">${esc(f)}</p>`
      )
      .join("");
    const aiLine = result.ai_suggested
      ? '<p class="muted result-line">Experimental combination — not a known recipe.</p>'
      : "";

    let proposalBlock = "";
    if (result.proposal && result.normalized) {
      const kindLabel = result.result_kind === "object" ? "Object" : "Component";
      const keepLabel = result.result_kind === "object" ? "Keep object" : "Keep component";
      const blocked = result.constraint?.status === "BLOCKED";
      proposalBlock = `
        <h3 class="result-name">${esc(result.proposal.player_name)}</h3>
        <p class="muted">${kindLabel} — ${esc(result.proposal.reasoning || "")}</p>
        ${
          blocked
            ? ""
            : `
        <div class="place-form">
          <label>Name
            <input type="text" id="lab-invention-name" autocomplete="off"
                   value="${esc(result.proposal.player_name)}">
          </label>
          <button type="button" class="primary" data-action="keep">${keepLabel}</button>
        </div>`
        }`;
    }

    resultSlot.innerHTML = `
      <aside class="panel lab-result feedback-recent">
        <h3>What happened</h3>
        ${feedback}
        ${aiLine}
        ${proposalBlock}
      </aside>`;
  }

  function readSelectionFromForm(form) {
    selection.material_ids = [...form.querySelectorAll('[name="material_ids"]:checked')].map(
      (el) => el.value
    );
    selection.component_ids = [...form.querySelectorAll('[name="component_ids"]:checked')].map(
      (el) => el.value
    );
    selection.object_ids = [...form.querySelectorAll('[name="object_ids"]:checked')].map(
      (el) => el.value
    );
    selection.method_ids = [...form.querySelectorAll('[name="method_ids"]:checked')].map(
      (el) => el.value
    );
    selection.intent = form.querySelector('[name="intent"]')?.value || "";
  }

  async function loadOptions(regionId) {
    const requestedRegion = regionId || client.getRegionId();
    options = await client.labOptions(requestedRegion || undefined);
    if (!requestedRegion && options?.region_id) {
      client.setRegionId(options.region_id, { notify: false });
    }
  }

  function clearSelection() {
    selection.material_ids = [];
    selection.component_ids = [];
    selection.object_ids = [];
    selection.method_ids = [];
  }

  function findLabItem(kind, id) {
    if (!options) return null;
    if (kind === "material") return (options.materials || []).find((m) => m.id === id);
    if (kind === "component") return (options.components || []).find((c) => c.id === id);
    if (kind === "object") return (options.objects || []).find((o) => o.id === id);
    if (kind === "method") return (options.methods || []).find((m) => m.id === id);
    return null;
  }

  async function loadMaterialDetailHtml(materialId) {
    const regionId = client.getRegionId();
    try {
      const [available, stocks] = await Promise.all([
        client.worldMaterialsAvailable(regionId),
        client.worldMaterialsStocks(regionId),
      ]);
      const stock = (stocks.stocks || []).find((s) => s.id === materialId);
      if (stock) return renderStockDetail(stock);
      const compound = (stocks.compounds || []).find((c) => c.id === materialId);
      if (compound) return renderCompoundDetail(compound);
      const material = (available.items || []).find((m) => m.id === materialId);
      if (material) return renderMaterialDetail(material);
    } catch (_err) {
      /* fall back to lab cache */
    }
    return renderLabMaterialDetail(findLabItem("material", materialId));
  }

  async function loadEntityDetailHtml(kind, entityId, { groupView = true } = {}) {
    const cached = findLabItem(kind, entityId);
    try {
      const entity = await client.getEntity(entityId);
      const entityKind = entity.kind === "component" ? "component" : "object";
      if (groupView && cached?.count > 1 && cached.id === entityId) {
        return renderEntityGroupDetail(
          { ...cached, ...entity, display: entity.display || cached },
          entityKind,
          null,
          true
        );
      }
      return renderEntityFullDetail(entity, entityKind);
    } catch (_err) {
      if (cached) {
        if (groupView && cached.count > 1) {
          return renderEntityGroupDetail(cached, kind, null, true);
        }
        return renderEntityFullDetail(cached, kind);
      }
      return '<p class="error">Could not load item details.</p>';
    }
  }

  async function openItemDetail(kind, id, { groupView = true } = {}) {
    const cached = findLabItem(kind, id);
    const title = cached?.name || cached?.label || "Details";
    sidePanel.setLoading(title);

    let html = '<p class="error">Item not found.</p>';
    let detailTitle = title;

    try {
      if (kind === "material") {
        html = await loadMaterialDetailHtml(id);
        detailTitle = findLabItem("material", id)?.name || title;
      } else if (kind === "component" || kind === "object") {
        html = await loadEntityDetailHtml(kind, id, { groupView });
        if (!groupView) {
          try {
            const entity = await client.getEntity(id);
            detailTitle = entity.display?.label || entity.name || title;
          } catch (_err) {
            detailTitle = title;
          }
        } else {
          const entity = findLabItem(kind, id);
          detailTitle = entity?.label || entity?.name || title;
        }
      } else if (kind === "method") {
        const method = findLabItem("method", id);
        html = renderMethodDetail(method);
        detailTitle = method?.name || title;
      }
    } catch (_err) {
      html = '<p class="error">Could not load item details.</p>';
    }

    await sidePanel.open({
      title: detailTitle,
      html,
      hydrate: hydrateGfx,
    });
  }

  async function refreshWorkspace(error, regionId) {
    const gen = ++labRefreshGen;
    workspaceEl.innerHTML = '<p class="muted world-panel-loading">Loading bench…</p>';
    await loadOptions(regionId);
    if (gen !== labRefreshGen) return;
    renderWorkspace(error || "");
    if (lastResult) renderResult(lastResult);
  }

  async function handleCombine(form) {
    readSelectionFromForm(form);
    setStatus("Trying combination…");
    document.body.classList.add("is-waiting");
    try {
      lastResult = await client.labCombine({
        region_id: client.getRegionId(),
        material_ids: selection.material_ids,
        component_ids: selection.component_ids,
        object_ids: selection.object_ids,
        method_ids: selection.method_ids,
        intent: selection.intent,
      });
      renderResult(lastResult);
      await refreshWorkspace("");
      setStatus("Combination complete");
      window.setTimeout(() => setStatus(""), 2500);
    } catch (err) {
      lastResult = null;
      renderResult(null);
      renderWorkspace(apiErrorMessage(err));
      setStatus("Combination failed");
      window.setTimeout(() => setStatus(""), 2500);
    } finally {
      document.body.classList.remove("is-waiting");
    }
  }

  async function handleKeep() {
    if (!lastResult?.proposal || !lastResult?.normalized) return;
    const name =
      document.getElementById("lab-invention-name")?.value ||
      lastResult.proposal.player_name ||
      "Unnamed";
    setStatus("Saving…");
    document.body.classList.add("is-waiting");
    try {
      await client.placeEntity({
        type: lastResult.normalized.type,
        tags: lastResult.normalized.tags || [],
        capabilities: lastResult.normalized.capabilities || {},
        region_id: client.getRegionId(),
        name,
      });
      lastResult = null;
      renderResult(null);
      await refreshWorkspace("");
      setStatus("Saved");
      window.setTimeout(() => setStatus(""), 2500);
    } catch (err) {
      renderWorkspace(apiErrorMessage(err));
      setStatus("Could not save");
      window.setTimeout(() => setStatus(""), 2500);
    } finally {
      document.body.classList.remove("is-waiting");
    }
  }

  root.addEventListener("submit", (event) => {
    const form = event.target.closest("#lab-form");
    if (!form) return;
    event.preventDefault();
    handleCombine(form);
  });

  root.addEventListener("click", (event) => {
    if (event.target.closest('[data-action="keep"]')) {
      event.preventDefault();
      handleKeep();
      return;
    }

    const instanceBtn = event.target.closest("[data-lab-detail-instance]");
    if (instanceBtn) {
      event.preventDefault();
      event.stopPropagation();
      const kind = instanceBtn.dataset.labDetailKind || "component";
      openItemDetail(kind, instanceBtn.dataset.labDetailInstance, { groupView: false });
      return;
    }

    const detailBtn = event.target.closest("[data-lab-detail]");
    if (detailBtn) {
      event.preventDefault();
      event.stopPropagation();
      openItemDetail(detailBtn.dataset.labDetail, detailBtn.dataset.itemId);
    }
  });

  async function init() {
    if (!client.apiBase || !client.gameId) {
      workspaceEl.innerHTML = '<p class="error">Missing game session.</p>';
      return;
    }
    try {
      if (!client.getRegionId()) {
        const overview = await client.worldOverview();
        if (overview?.region?.id) {
          client.setRegionId(overview.region.id, { notify: false });
        }
      }
      await refreshWorkspace("", client.getRegionId());
    } catch (_err) {
      workspaceEl.innerHTML =
        '<p class="error">Could not load the bench from the API. Is the backend running?</p>';
    }
  }

  document.addEventListener("what-region-change", (event) => {
    const regionId = event.detail?.regionId;
    if (!regionId) return;
    lastResult = null;
    renderResult(null);
    clearSelection();
    refreshWorkspace("", regionId).catch(() => {
      workspaceEl.innerHTML =
        '<p class="error">Could not load the bench for this region.</p>';
    });
  });

  init();
})();
