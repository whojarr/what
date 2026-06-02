(function () {
  const root = document.getElementById("history-root");
  if (!root || !window.What) return;

  const { esc, fmtFixed, createClient } = window.What;
  const client = createClient({ root });
  const recordsEl = document.getElementById("history-records");
  const eventsEl = document.getElementById("history-events");
  const searchForm = document.getElementById("history-search-form");
  const queryInput = searchForm.querySelector('[name="q"]');

  function renderRecords(records) {
    if (!records?.length) {
      recordsEl.innerHTML = '<li class="muted">No matching memories.</li>';
      return;
    }
    recordsEl.innerHTML = records
      .map(
        (r) =>
          `<li><span class="badge">${esc(r.kind)}</span> turn ${esc(r.turn)}: ${esc(r.text)}</li>`
      )
      .join("");
  }

  function renderEvents(events) {
    if (!events?.length) {
      eventsEl.innerHTML = '<li class="muted">No events yet.</li>';
      return;
    }
    eventsEl.innerHTML = events
      .map(
        (e) =>
          `<li>Turn ${esc(e.turn)}: ${esc(e.type)} (${fmtFixed(e.severity, 2)}) — ${esc(e.description)}</li>`
      )
      .join("");
  }

  async function load(query) {
    const [memory, eventData] = await Promise.all([
      client.searchMemory(query, 20),
      client.getEvents(20),
    ]);
    renderRecords(memory.records || []);
    renderEvents(eventData.events || []);
  }

  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const q = queryInput.value.trim();
    history.replaceState(null, "", q ? `?q=${encodeURIComponent(q)}` : window.location.pathname);
    load(q);
  });

  async function init() {
    if (!client.apiBase || !client.gameId) {
      recordsEl.innerHTML = '<li class="error">Missing game session.</li>';
      eventsEl.innerHTML = "";
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q") || "";
    queryInput.value = q;
    try {
      await load(q);
    } catch (_err) {
      recordsEl.innerHTML = '<li class="error">Could not load history from the API.</li>';
      eventsEl.innerHTML = "";
    }
  }

  init();
})();
