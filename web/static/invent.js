(function () {
  const root = document.getElementById("invent-root");
  if (!root || !window.What || !window.WhatDisplay) return;

  const { esc, setStatus, apiErrorMessage, createClient } = window.What;
  const { renderMaterialsPanel, renderConstraintBlock, renderPlaceSuccess } = window.WhatDisplay;

  const client = createClient({ root });
  const materialsEl = document.getElementById("invent-materials");
  const resultEl = document.getElementById("invent-result");
  const errorEl = document.getElementById("invent-error");
  let lastResult = null;

  function renderPlaceForm(result) {
    const status = result.constraint?.status;
    if (status === "BLOCKED") return "";

    const isMethod = (result.proposal?.type || "").startsWith("method.");
    const btnLabel =
      isMethod ? "Learn this method" : status === "NEEDS_TWEAK" ? "Try building anyway" : "Build it";
    const nameLabel = isMethod ? "Method name" : "Invention name";

    return `
      <div class="place-form" id="invent-place-form">
        <label>${nameLabel}
          <input type="text" id="invent-place-name" autocomplete="off"
                 value="${esc(result.proposal?.player_name || "")}">
        </label>
        <button type="button" class="primary" data-action="place">${esc(btnLabel)}</button>
      </div>`;
  }

  function renderResult(result) {
    if (!result) {
      resultEl.innerHTML = "";
      return;
    }
    resultEl.innerHTML = `
      <section class="panel feedback-recent">
        <h3>${esc(result.proposal?.player_name || "Proposal")}</h3>
        ${renderConstraintBlock(result)}
        ${renderPlaceForm(result)}
      </section>`;
  }

  async function loadMaterials(regionId) {
    const rid = regionId || client.getRegionId();
    const [absent, available, stocks] = await Promise.all([
      client.worldMaterialsAbsent(rid),
      client.worldMaterialsAvailable(rid),
      client.worldMaterialsStocks(rid),
    ]);
    materialsEl.innerHTML = renderMaterialsPanel(absent, available, stocks, {
      heading: "What you have to work with",
      linkPanels: false,
    });
  }

  async function handleInterpret(form) {
    const idea = form.querySelector('[name="idea"]').value.trim();
    const regionId = client.getRegionId();
    if (!idea) return;
    errorEl.innerHTML = "";
    setStatus("Interpreting…");
    document.body.classList.add("is-waiting");
    try {
      lastResult = await client.interpretIdea(idea, regionId);
      renderResult(lastResult);
      setStatus("Interpretation complete");
      window.setTimeout(() => setStatus(""), 2500);
    } catch (err) {
      lastResult = null;
      renderResult(null);
      errorEl.innerHTML = `<p class="error feedback-recent">${esc(apiErrorMessage(err))}</p>`;
      setStatus("Interpretation failed");
      window.setTimeout(() => setStatus(""), 2500);
    } finally {
      document.body.classList.remove("is-waiting");
    }
  }

  async function handlePlace() {
    if (!lastResult?.normalized) return;
    const regionId = client.getRegionId();
    const name =
      document.getElementById("invent-place-name")?.value ||
      lastResult.proposal?.player_name ||
      "Unnamed";

    setStatus("Building…");
    document.body.classList.add("is-waiting");
    try {
      const detail = await client.placeEntity({
        type: lastResult.normalized.type,
        tags: lastResult.normalized.tags || [],
        capabilities: lastResult.normalized.capabilities || {},
        region_id: regionId,
        name,
      });
      lastResult = null;
      resultEl.innerHTML = `
        <section class="panel feedback-recent">
          ${renderPlaceSuccess(detail)}
          ${detail.constraint ? `<p>Status: ${esc(detail.constraint.status)}</p>` : ""}
          <p class="actions-inline">
            <a href="/world" class="button">Back to cave</a>
            <a href="/lab" class="button">Discovery bench</a>
          </p>
        </section>`;
      await loadMaterials();
      setStatus("Saved");
      window.setTimeout(() => setStatus(""), 2500);
    } catch (err) {
      errorEl.innerHTML = `<p class="error feedback-recent">${esc(apiErrorMessage(err))}</p>`;
      setStatus("Could not build");
      window.setTimeout(() => setStatus(""), 2500);
    } finally {
      document.body.classList.remove("is-waiting");
    }
  }

  root.addEventListener("submit", (event) => {
    const form = event.target.closest("#invent-form");
    if (!form) return;
    event.preventDefault();
    handleInterpret(form);
  });

  root.addEventListener("click", (event) => {
    if (event.target.closest('[data-action="place"]')) {
      event.preventDefault();
      handlePlace();
    }
  });

  document.addEventListener("what-region-change", (event) => {
    const regionId = event.detail?.regionId;
    if (!regionId) return;
    lastResult = null;
    renderResult(null);
    loadMaterials(regionId);
  });

  async function init() {
    if (!client.apiBase || !client.gameId) {
      materialsEl.innerHTML = '<p class="error">Missing game session.</p>';
      return;
    }
    try {
      await loadMaterials();
    } catch (_err) {
      materialsEl.innerHTML =
        '<p class="error">Could not load from the API. Is the backend running?</p>';
    }
  }

  init();
})();
