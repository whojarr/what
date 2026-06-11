(function () {
  const root = document.getElementById("settings-root");
  if (!root || !window.What) return;

  const {
    esc,
    fmtFixed,
    setStatus,
    apiErrorMessage,
    createClient,
    setFlaskSession,
    clearFlaskSession,
  } = window.What;

  const client = createClient({ root });
  const activeGameId = root.dataset.gameId || "";
  const errorEl = document.getElementById("settings-error");
  const savesList = document.getElementById("settings-saves-list");
  const savesEmpty = document.getElementById("settings-saves-empty");
  const currentMeta = document.getElementById("settings-current-meta");
  const renameForm = document.getElementById("settings-rename-world-form");
  const worldNameInput = document.getElementById("settings-world-name");
  const leaveBtn = document.getElementById("settings-leave-journey");
  const historyRecordsEl = document.getElementById("settings-history-records");
  const historyEventsEl = document.getElementById("settings-history-events");
  const historySearchForm = document.getElementById("settings-history-search-form");
  const historyQueryInput = historySearchForm?.querySelector('[name="q"]');

  function showError(message) {
    if (!errorEl) return;
    errorEl.textContent = message;
    errorEl.hidden = !message;
  }

  function formatSavedAt(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  function saveTitle(game) {
    const named = (game.name || "").trim();
    if (named) return esc(named);
    if (game.primary_region) return esc(game.primary_region);
    return "Untitled world";
  }

  function renderSaveRow(game) {
    const title = saveTitle(game);
    const regionLine =
      (game.name || "").trim() && game.primary_region
        ? `<span class="muted save-row-region">${esc(game.primary_region)}</span>`
        : "";
    const when = formatSavedAt(game.saved_at);
    const meta = [
      `Turn ${esc(game.turn)}`,
      `Seed ${esc(game.rng_seed)}`,
      esc(game.era),
      game.invention_count ? `${esc(game.invention_count)} inventions` : null,
    ]
      .filter(Boolean)
      .join(" · ");
    const isActive = game.id === activeGameId;
    return `<li class="save-row${isActive ? " save-row-active" : ""}">
      <div class="save-row-main">
        <strong>${title}${isActive ? ' <span class="badge">current</span>' : ""}</strong>
        ${regionLine}
        <span class="muted save-row-meta">${meta}</span>
        ${when ? `<span class="muted save-row-when">Last played ${esc(when)}</span>` : ""}
      </div>
      <div class="save-row-actions">
        ${
          isActive
            ? `<a href="/world" class="primary">Open cave</a>`
            : `<button type="button" class="primary" data-resume="${esc(game.id)}">Continue</button>`
        }
        <button type="button" class="save-delete" data-delete="${esc(game.id)}" aria-label="Delete saved journey">Delete</button>
      </div>
    </li>`;
  }

  async function resumeGame(gameId, button) {
    showError("");
    setStatus("Loading save…");
    document.body.classList.add("is-waiting");
    if (button) button.disabled = true;
    try {
      await setFlaskSession(gameId);
      window.location.href = "/world";
    } catch (err) {
      showError(apiErrorMessage(err));
      setStatus("");
      document.body.classList.remove("is-waiting");
      if (button) button.disabled = false;
    }
  }

  function bindSaveList() {
    savesList.querySelectorAll("[data-resume]").forEach((btn) => {
      btn.addEventListener("click", () => resumeGame(btn.dataset.resume, btn));
    });
    savesList.querySelectorAll("[data-delete]").forEach((btn) => {
      btn.addEventListener("click", () => deleteGame(btn.dataset.delete, btn));
    });
  }

  async function deleteGame(gameId, button) {
    if (!window.confirm("Delete this saved journey? You cannot undo this.")) {
      return;
    }
    showError("");
    setStatus("Deleting save…");
    if (button) button.disabled = true;
    try {
      await client.deleteGame(gameId);
      if (activeGameId === gameId) {
        await clearFlaskSession();
        window.location.href = "/settings";
        return;
      }
      await loadSavedGames();
      setStatus("");
    } catch (err) {
      showError(apiErrorMessage(err));
      setStatus("");
      if (button) button.disabled = false;
    }
  }

  async function loadSavedGames() {
    if (!savesList) return;
    try {
      const data = await client.listGames();
      const games = data.games || [];
      if (!games.length) {
        savesList.innerHTML = "";
        if (savesEmpty) savesEmpty.hidden = false;
        return;
      }
      if (savesEmpty) savesEmpty.hidden = true;
      savesList.innerHTML = games.map(renderSaveRow).join("");
      bindSaveList();
    } catch (err) {
      savesList.innerHTML = "";
      if (savesEmpty) {
        savesEmpty.textContent = "Could not load saved journeys.";
        savesEmpty.hidden = false;
      }
      showError(apiErrorMessage(err));
    }
  }

  async function loadCurrentJourney() {
    if (!activeGameId) return;
    try {
      const game = await client.getGame();
      if (worldNameInput) {
        worldNameInput.value = (game.name || "").trim() || "Untitled world";
      }
      if (currentMeta) {
        const primaryRegion =
          game.regions && game.regions.length ? game.regions[0].name : "";
        const parts = [`Turn ${game.turn}`, `Seed ${game.rng_seed}`];
        if (primaryRegion) {
          parts.unshift(primaryRegion);
        }
        currentMeta.textContent = parts.join(" · ");
      }
    } catch (err) {
      if (currentMeta) currentMeta.textContent = apiErrorMessage(err);
    }
  }

  if (renameForm) {
    renameForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = (worldNameInput?.value || "").trim();
      if (!name) return;
      showError("");
      setStatus("Saving…");
      const submitBtn = renameForm.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      try {
        await client.renameGame(name);
        await loadCurrentJourney();
        await loadSavedGames();
        setStatus("Saved");
        window.setTimeout(() => setStatus(""), 2000);
      } catch (err) {
        showError(apiErrorMessage(err));
        setStatus("");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  if (leaveBtn) {
    leaveBtn.addEventListener("click", async () => {
      showError("");
      setStatus("Leaving journey…");
      leaveBtn.disabled = true;
      try {
        await clearFlaskSession();
        window.location.href = "/";
      } catch (err) {
        showError(apiErrorMessage(err));
        setStatus("");
        leaveBtn.disabled = false;
      }
    });
  }

  function renderHistoryRecords(records) {
    if (!historyRecordsEl) return;
    if (!records?.length) {
      historyRecordsEl.innerHTML = '<li class="muted">No matching memories.</li>';
      return;
    }
    historyRecordsEl.innerHTML = records
      .map(
        (r) =>
          `<li><span class="badge">${esc(r.kind)}</span> turn ${esc(r.turn)}: ${esc(r.text)}</li>`
      )
      .join("");
  }

  function renderHistoryEvents(events) {
    if (!historyEventsEl) return;
    if (!events?.length) {
      historyEventsEl.innerHTML = '<li class="muted">No events yet.</li>';
      return;
    }
    historyEventsEl.innerHTML = events
      .map(
        (e) =>
          `<li>Turn ${esc(e.turn)}: ${esc(e.type)} (${fmtFixed(e.severity, 2)}) — ${esc(e.description)}</li>`
      )
      .join("");
  }

  async function loadHistory(query) {
    const [memory, eventData] = await Promise.all([
      client.searchMemory(query, 20),
      client.getEvents(20),
    ]);
    renderHistoryRecords(memory.records || []);
    renderHistoryEvents(eventData.events || []);
  }

  function historyUrl(query) {
    if (query) {
      return `${window.location.pathname}?q=${encodeURIComponent(query)}#history`;
    }
    return `${window.location.pathname}#history`;
  }

  if (historySearchForm) {
    historySearchForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const q = historyQueryInput?.value.trim() || "";
      history.replaceState(null, "", historyUrl(q));
      loadHistory(q).catch(() => {
        if (historyRecordsEl) {
          historyRecordsEl.innerHTML =
            '<li class="error">Could not load history from the API.</li>';
        }
        if (historyEventsEl) historyEventsEl.innerHTML = "";
      });
    });
  }

  async function initHistory() {
    if (!historyRecordsEl || !historyEventsEl) return;
    if (!client.apiBase || !client.gameId) return;
    const q = new URLSearchParams(window.location.search).get("q") || "";
    if (historyQueryInput) historyQueryInput.value = q;
    try {
      await loadHistory(q);
    } catch (_err) {
      historyRecordsEl.innerHTML = '<li class="error">Could not load history from the API.</li>';
      historyEventsEl.innerHTML = "";
    }
  }

  loadSavedGames();
  loadCurrentJourney();
  initHistory();
})();
