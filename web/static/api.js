(function () {
  const REGION_KEY = "what_region_id";

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pct(value) {
    return Math.round(Number(value) * 100);
  }

  function capitalize(value) {
    const s = String(value || "");
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  }

  function fmtFixed(value, digits) {
    return Number(value).toFixed(digits);
  }

  function setStatus(message) {
    const statusBar = document.getElementById("status-bar");
    if (!statusBar) return;
    if (message) {
      statusBar.textContent = message;
      statusBar.classList.add("is-visible");
      document.body.classList.add("has-status-bar");
    } else {
      statusBar.classList.remove("is-visible");
      document.body.classList.remove("has-status-bar");
    }
  }

  function componentBadges(item) {
    const badges = [];
    if (item.kind === "starter") badges.push('<span class="badge">starter</span>');
    if (item.role === "fire") badges.push('<span class="badge">fire</span>');
    else if (item.role === "water") badges.push('<span class="badge">water</span>');
    else if (item.role) badges.push('<span class="badge">machine</span>');
    return badges.join("");
  }

  function objectBadge(role) {
    if (role === "furniture") return '<span class="badge">furniture</span>';
    if (role === "dwelling") return '<span class="badge">dwelling</span>';
    if (role === "material") return '<span class="badge">processed</span>';
    return '<span class="badge">object</span>';
  }

  async function apiGet(apiBase, path) {
    const res = await fetch(`${apiBase}${path}`);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function apiPost(apiBase, path, body) {
    const res = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (_err) {
      data = text;
    }
    if (!res.ok) {
      const err = new Error(typeof data === "string" ? data : `HTTP ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  async function apiDelete(apiBase, path) {
    const res = await fetch(`${apiBase}${path}`, { method: "DELETE" });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (_err) {
      data = text;
    }
    if (!res.ok) {
      const err = new Error(typeof data === "string" ? data : `HTTP ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function apiErrorMessage(err) {
    const detail = err?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      return detail[0]?.msg || String(detail[0]);
    }
    if (detail && typeof detail === "object") {
      return detail.error || detail.errors?.[0] || "Request failed";
    }
    return err?.message || "Request failed";
  }

  function syncRegionDatasets(regionId) {
    document.querySelectorAll("[data-game-id]").forEach((el) => {
      el.dataset.regionId = regionId;
    });
  }

  function getRegionId() {
    return (
      sessionStorage.getItem(REGION_KEY) ||
      document.body?.dataset?.regionId ||
      ""
    );
  }

  function setRegionId(regionId, options) {
    if (!regionId) return;
    const notify = options?.notify !== false;
    const prev = sessionStorage.getItem(REGION_KEY);
    sessionStorage.setItem(REGION_KEY, regionId);
    syncRegionDatasets(regionId);
    if (notify && prev !== regionId) {
      window.dispatchEvent(
        new CustomEvent("what-region-change", { detail: { regionId } })
      );
    }
  }

  function regionQuery(regionId) {
    const rid = regionId || "";
    return rid ? `?region_id=${encodeURIComponent(rid)}` : "";
  }

  function createClient(config) {
    const root = config.root || null;
    const apiBase = (config.apiBase || root?.dataset?.apiBase || "").replace(/\/$/, "");
    const gameId = config.gameId || root?.dataset?.gameId;

    if (root?.dataset?.regionId && !getRegionId()) {
      setRegionId(root.dataset.regionId, { notify: false });
    }

    const gid = () => {
      if (!gameId) throw new Error("Missing game id");
      return gameId;
    };

    return {
      apiBase,
      gameId,
      root,
      get: (path) => apiGet(apiBase, path),
      post: (path, body) => apiPost(apiBase, path, body),
      getRegionId,
      setRegionId,

      listGames() {
        return apiGet(apiBase, "/games");
      },

      deleteGame(id) {
        return apiDelete(apiBase, `/games/${id}`);
      },

      createGame(seed, name) {
        const body = { seed };
        if (name) body.name = name;
        return apiPost(apiBase, "/games", body);
      },

      getGame() {
        return apiGet(apiBase, `/games/${gid()}`);
      },

      worldOverview(regionId) {
        return apiGet(apiBase, `/games/${gid()}/world/overview${regionQuery(regionId)}`);
      },

      worldMaterialsAbsent(regionId) {
        return apiGet(apiBase, `/games/${gid()}/world/materials/absent${regionQuery(regionId)}`);
      },

      worldMaterialsAvailable(regionId) {
        return apiGet(
          apiBase,
          `/games/${gid()}/world/materials/available${regionQuery(regionId)}`
        );
      },

      worldMaterialsStocks(regionId) {
        return apiGet(apiBase, `/games/${gid()}/world/materials/stocks${regionQuery(regionId)}`);
      },

      worldComponents(regionId) {
        return apiGet(apiBase, `/games/${gid()}/world/components${regionQuery(regionId)}`);
      },

      worldObjects(regionId) {
        return apiGet(apiBase, `/games/${gid()}/world/objects${regionQuery(regionId)}`);
      },

      renameRegion(regionId, name) {
        return apiPost(apiBase, `/games/${gid()}/regions/${regionId}/name`, { name });
      },

      renameGame(name) {
        return apiPost(apiBase, `/games/${gid()}/name`, { name });
      },

      travelTo(targetRegionId, fromRegionId) {
        return apiPost(apiBase, `/games/${gid()}/travel`, {
          target_region_id: targetRegionId,
          from_region_id: fromRegionId || null,
        });
      },

      surveyRegion(regionId) {
        return apiPost(apiBase, `/games/${gid()}/regions/${regionId}/survey`);
      },

      tick() {
        return apiPost(apiBase, `/games/${gid()}/tick`);
      },

      labOptions(regionId) {
        return apiGet(apiBase, `/games/${gid()}/lab/options${regionQuery(regionId)}`);
      },

      labCombine(body) {
        return apiPost(apiBase, `/games/${gid()}/lab/combine`, body);
      },

      placeEntity(body) {
        return apiPost(apiBase, `/games/${gid()}/entities`, body);
      },

      getEntity(entityId) {
        return apiGet(apiBase, `/games/${gid()}/entities/${entityId}`);
      },

      interpretIdea(text, regionId) {
        return apiPost(apiBase, "/ideas/interpret", {
          game_id: gid(),
          text,
          region_id: regionId || null,
        });
      },

      searchMemory(query, limit) {
        const q = encodeURIComponent(query || "");
        const lim = limit || 20;
        return apiGet(apiBase, `/games/${gid()}/memory?q=${q}&limit=${lim}`);
      },

      getEvents(limit) {
        const lim = limit || 20;
        return apiGet(apiBase, `/games/${gid()}/events?limit=${lim}`);
      },
    };
  }

  async function setFlaskSession(gameId) {
    const res = await fetch("/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ game_id: gameId }),
    });
    if (!res.ok) throw new Error("Could not start session");
    return res.json();
  }

  async function clearFlaskSession() {
    const res = await fetch("/session", {
      method: "DELETE",
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error("Could not clear session");
    return res.json();
  }

  window.What = {
    esc,
    pct,
    capitalize,
    fmtFixed,
    setStatus,
    componentBadges,
    objectBadge,
    apiGet,
    apiPost,
    apiDelete,
    apiErrorMessage,
    getRegionId,
    setRegionId,
    createClient,
    setFlaskSession,
    clearFlaskSession,
  };
})();
