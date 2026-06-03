(function () {
  const form = document.getElementById("home-form");
  if (!form || !window.What) return;

  const {
    esc,
    setStatus,
    apiErrorMessage,
    createClient,
    setFlaskSession,
    clearFlaskSession,
  } = window.What;
  const activeGameId = document.body.dataset.gameId || "";
  const errorEl = document.getElementById("home-error");
  const savesPanel = document.getElementById("saved-games-panel");
  const savesList = document.getElementById("saved-games-list");
  const client = createClient({ apiBase: form.dataset.apiBase });

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
    return `<li class="save-row">
      <div class="save-row-main">
        <strong>${title}</strong>
        ${regionLine}
        <span class="muted save-row-meta">${meta}</span>
        ${when ? `<span class="muted save-row-when">Last played ${esc(when)}</span>` : ""}
      </div>
      <div class="save-row-actions">
        <button type="button" class="primary" data-resume="${esc(game.id)}">Continue</button>
        <button type="button" class="save-delete" data-delete="${esc(game.id)}" aria-label="Delete saved journey">Delete</button>
      </div>
    </li>`;
  }

  async function resumeGame(gameId, button) {
    errorEl.hidden = true;
    setStatus("Loading save…");
    document.body.classList.add("is-waiting");
    if (button) button.disabled = true;
    try {
      await setFlaskSession(gameId);
      window.location.href = "/world";
    } catch (err) {
      errorEl.textContent = apiErrorMessage(err);
      errorEl.hidden = false;
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
    if (
      !window.confirm(
        "Delete this saved journey? You cannot undo this."
      )
    ) {
      return;
    }
    errorEl.hidden = true;
    setStatus("Deleting save…");
    if (button) button.disabled = true;
    try {
      await client.deleteGame(gameId);
      if (activeGameId === gameId) {
        await clearFlaskSession();
      }
      const data = await client.listGames();
      const games = data.games || [];
      if (!games.length) {
        savesPanel.hidden = true;
        savesList.innerHTML = "";
      } else {
        savesPanel.hidden = false;
        savesList.innerHTML = games.map(renderSaveRow).join("");
        bindSaveList();
      }
      setStatus("");
    } catch (err) {
      errorEl.textContent = apiErrorMessage(err);
      errorEl.hidden = false;
      setStatus("");
      if (button) button.disabled = false;
    }
  }

  async function loadSavedGames() {
    if (!savesPanel || !savesList) return;
    try {
      const data = await client.listGames();
      const games = data.games || [];
      if (!games.length) return;
      savesPanel.hidden = false;
      savesList.innerHTML = games.map(renderSaveRow).join("");
      bindSaveList();
    } catch (_err) {
      /* API may be down; new game still works */
    }
  }

  loadSavedGames();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const worldName = (form.querySelector('[name="world_name"]').value || "").trim();
    const seed = parseInt(form.querySelector('[name="seed"]').value, 10) || 42;
    errorEl.hidden = true;
    setStatus("Entering…");
    document.body.classList.add("is-waiting");
    try {
      const game = await client.createGame(seed, worldName);
      await setFlaskSession(game.id);
      window.location.href = "/world";
    } catch (err) {
      errorEl.textContent = apiErrorMessage(err);
      errorEl.hidden = false;
      setStatus("");
      document.body.classList.remove("is-waiting");
    }
  });
})();
