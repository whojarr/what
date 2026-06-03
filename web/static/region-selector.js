(function () {
  const select = document.getElementById("global-region-select");
  const body = document.body;
  if (!select || !body.dataset.gameId || !window.What) return;

  const { esc, setRegionId, createClient } = window.What;
  const client = createClient({ root: body });
  let regions = [];
  let syncing = false;

  function renderOptions(selectedId) {
    if (!regions.length) {
      select.innerHTML = '<option value="">No regions</option>';
      return;
    }
    select.innerHTML = regions
      .map(
        (r) =>
          `<option value="${esc(r.id)}"${r.id === selectedId ? " selected" : ""}>${esc(r.name)}</option>`
      )
      .join("");
  }

  function syncSelect(regionId) {
    if (!regionId || !regions.some((r) => r.id === regionId)) return;
    syncing = true;
    select.value = regionId;
    syncing = false;
  }

  async function loadRegions() {
    const [game, overview] = await Promise.all([
      client.getGame(),
      client.worldOverview(client.getRegionId() || undefined).catch(() => null),
    ]);
    regions = game.regions || [];
    let activeId = client.getRegionId();
    if (!activeId && overview?.region?.id) {
      activeId = overview.region.id;
    }
    if (!activeId && regions[0]) {
      activeId = regions[0].id;
    }
    if (activeId && !regions.some((r) => r.id === activeId)) {
      activeId = regions[0]?.id || activeId;
    }
    if (activeId) {
      setRegionId(activeId, { notify: false });
    }
    renderOptions(activeId);
  }

  select.addEventListener("change", () => {
    if (syncing || !select.value) return;
    const regionId = select.value;
    if (regionId === client.getRegionId()) {
      window.dispatchEvent(
        new CustomEvent("what-region-change", { detail: { regionId } })
      );
      return;
    }
    setRegionId(regionId);
  });

  document.addEventListener("what-region-change", (event) => {
    syncSelect(event.detail?.regionId);
  });

  loadRegions().catch(() => {
    select.innerHTML = '<option value="">Regions unavailable</option>';
  });
})();
