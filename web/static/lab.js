(function () {
  const root = document.getElementById("lab-root");
  if (!root || !window.What || !window.WhatDisplay) return;

  const { esc, pct, setStatus, apiErrorMessage, createClient } = window.What;
  const { componentBadges, objectBadge } = window.WhatDisplay;

  const client = createClient({ root });
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
  const selection = {
    material_ids: [],
    component_ids: [],
    object_ids: [],
    method_ids: [],
    intent: "",
  };

  function materialMeta(m) {
    if (m.stock > 0.01) return `stock ${pct(m.stock)}%`;
    if (m.source === "scavenging") return "nearby";
    if (m.source === "discovered") return "discovered";
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
            </label>`;
        }
        return `
          <span class="method-pill method-unknown" title="${esc(m.hint || "")}">
            ${esc(m.name)} · ?
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
            <label class="pick-item">
              <input type="checkbox" name="${inputName}" value="${esc(item.id)}"${checked}>
              ${gSlot("material", item)}
              <span class="pick-item-body"><span>${esc(item.name)}</span>
              ${meta ? `<span class="muted pick-meta">${esc(meta)}</span>` : ""}</span>
            </label>`;
        }
        const badge = kind === "component" ? componentBadges(item) : objectBadge(item.role);
        const label = esc(item.label || item.name);
        const hint = esc(item.hint || "");
        const visualType = kind === "component" ? "component" : "object";
        return `
          <label class="pick-item pick-item-tall">
            <input type="checkbox" name="${inputName}" value="${esc(item.id)}"${checked}>
            ${gSlot(visualType, item)}
            <div class="pick-item-body">
              <div>${badge} <strong>${label}</strong>${countBadge}</div>
              <span class="muted pick-hint">${hint}</span>
            </div>
          </label>`;
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
        <input type="hidden" name="region_id" value="${esc(options.region_id)}">
        ${renderMethods(options.methods)}
        <div class="lab-columns">
          ${renderPickColumn("Materials", "Flint, bone, hide, ore.", options.materials, "material", "Nothing available.")}
          ${renderPickColumn("Components", "Machines — fire, water, tools.", options.components, "component", "No components yet.")}
          ${renderPickColumn("Objects", "Furniture, structures, processed stuff.", options.objects, "object", "None yet — build from materials.")}
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

  async function loadOptions() {
    options = await client.labOptions(client.getRegionId());
    client.setRegionId(options.region_id);
  }

  async function refreshWorkspace(error) {
    await loadOptions();
    renderWorkspace(error || "");
    if (lastResult) renderResult(lastResult);
  }

  async function handleCombine(form) {
    readSelectionFromForm(form);
    setStatus("Trying combination…");
    document.body.classList.add("is-waiting");
    try {
      lastResult = await client.labCombine({
        region_id: options.region_id,
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
        region_id: options.region_id,
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
    }
  });

  async function init() {
    if (!client.apiBase || !client.gameId) {
      workspaceEl.innerHTML = '<p class="error">Missing game session.</p>';
      return;
    }
    try {
      await refreshWorkspace("");
    } catch (_err) {
      workspaceEl.innerHTML =
        '<p class="error">Could not load the bench from the API. Is the backend running?</p>';
    }
  }

  init();
})();
