(function () {
  const form = document.getElementById("home-form");
  if (!form || !window.What) return;

  const { esc, setStatus, apiErrorMessage, createClient, setFlaskSession } = window.What;
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

  function renderSaveRow(game) {
    const region = game.primary_region ? esc(game.primary_region) : "Unknown region";
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
        <strong>${region}</strong>
        <span class="muted save-row-meta">${meta}</span>
        ${when ? `<span class="muted save-row-when">Last played ${esc(when)}</span>` : ""}
      </div>
      <button type="button" class="primary" data-resume="${esc(game.id)}">Continue</button>
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

  async function loadSavedGames() {
    if (!savesPanel || !savesList) return;
    try {
      const data = await client.listGames();
      const games = data.games || [];
      if (!games.length) return;
      savesPanel.hidden = false;
      savesList.innerHTML = games.map(renderSaveRow).join("");
      savesList.querySelectorAll("[data-resume]").forEach((btn) => {
        btn.addEventListener("click", () => resumeGame(btn.dataset.resume, btn));
      });
    } catch (_err) {
      /* API may be down; new game still works */
    }
  }

  loadSavedGames();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const seed = parseInt(form.querySelector('[name="seed"]').value, 10) || 42;
    errorEl.hidden = true;
    setStatus("Entering…");
    document.body.classList.add("is-waiting");
    try {
      const game = await client.createGame(seed);
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
