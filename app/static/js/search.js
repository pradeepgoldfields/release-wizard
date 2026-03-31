/* ── System-wide Search ─────────────────────────────────────────────────────
 *
 *  openSearch()   — open the spotlight overlay (also bound to Ctrl+K / /)
 *  closeSearch()  — close it
 *
 *  On open the module fetches all products, pipelines, applications, pipeline
 *  runs and users once, caches them for the session, then filters client-side
 *  as the user types.
 */

(function () {

  // ── DOM references ──────────────────────────────────────────────────────────
  let _overlay = null;
  let _input   = null;
  let _list    = null;
  let _selIdx  = -1;

  // ── Data cache ──────────────────────────────────────────────────────────────
  let _cache = null;           // null = not yet loaded
  let _loading = false;

  // ── Public API ──────────────────────────────────────────────────────────────
  window.openSearch = function () {
    _build();
    _overlay.style.display = "flex";
    _input.value = "";
    _input.focus();
    _render("");
    // Kick off data load in background if not already done
    if (!_cache && !_loading) _loadData();
  };

  window.closeSearch = function () {
    if (_overlay) _overlay.style.display = "none";
  };

  // ── Build overlay DOM (once) ─────────────────────────────────────────────────
  function _build() {
    if (_overlay) return;

    _overlay = document.createElement("div");
    _overlay.id = "search-overlay";
    _overlay.className = "search-overlay";
    _overlay.innerHTML = `
      <div class="search-modal" role="dialog" aria-modal="true" aria-label="Search">
        <div class="search-input-row">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input id="search-input" class="search-input" placeholder="Search products, pipelines, runs, users…" autocomplete="off" spellcheck="false">
          <kbd class="search-esc-hint">Esc</kbd>
        </div>
        <div id="search-results" class="search-results"></div>
        <div class="search-footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span><kbd>↵</kbd> open</span>
          <span><kbd>Esc</kbd> close</span>
        </div>
      </div>`;

    document.body.appendChild(_overlay);

    _input = document.getElementById("search-input");
    _list  = document.getElementById("search-results");

    // Close on backdrop click
    _overlay.addEventListener("click", e => {
      if (e.target === _overlay) closeSearch();
    });

    _input.addEventListener("input", () => {
      _selIdx = -1;
      _render(_input.value);
    });

    _input.addEventListener("keydown", e => {
      const items = _list.querySelectorAll(".search-item");
      if (e.key === "ArrowDown") {
        e.preventDefault();
        _selIdx = Math.min(_selIdx + 1, items.length - 1);
        _highlight(items);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        _selIdx = Math.max(_selIdx - 1, 0);
        _highlight(items);
      } else if (e.key === "Enter") {
        e.preventDefault();
        const active = _list.querySelector(".search-item.selected");
        if (active) active.click();
      } else if (e.key === "Escape") {
        closeSearch();
      }
    });
  }

  function _highlight(items) {
    items.forEach((el, i) => el.classList.toggle("selected", i === _selIdx));
    const sel = items[_selIdx];
    if (sel) sel.scrollIntoView({ block: "nearest" });
  }

  // ── Data loading ─────────────────────────────────────────────────────────────
  async function _loadData() {
    _loading = true;
    try {
      // Load everything in parallel; silently ignore failures on individual calls
      const [products, users] = await Promise.all([
        api.getProducts().catch(() => []),
        api.getUsers().catch(() => []),
      ]);

      // For each product, load pipelines, applications and recent runs
      const pipelinesByProduct = {};
      const appsByProduct = {};
      const runs = [];

      await Promise.all(products.map(async p => {
        const [pipelines, apps] = await Promise.all([
          api.getPipelines(p.id).catch(() => []),
          api.getApplications(p.id).catch(() => []),
        ]);
        pipelinesByProduct[p.id] = pipelines;
        appsByProduct[p.id] = apps;

        // Fetch recent runs for each pipeline (up to 5 per pipeline)
        await Promise.all(pipelines.map(async pl => {
          try {
            const plRuns = await api.getPipelineRuns(pl.id).catch(() => []);
            plRuns.slice(0, 5).forEach(r => {
              r._product_id = p.id;   // stash for navigation
              runs.push(r);
            });
          } catch {}
        }));
      }));

      _cache = { products, users, runs, pipelinesByProduct, appsByProduct };

      // If search is open and has a query, re-render with fresh data
      if (_overlay && _overlay.style.display !== "none") {
        _render(_input.value);
      }
    } catch (e) {
      // non-fatal
    } finally {
      _loading = false;
    }
  }

  // ── Rendering ─────────────────────────────────────────────────────────────────
  function _render(query) {
    const q = (query || "").trim().toLowerCase();

    if (!_cache) {
      _list.innerHTML = `<div class="search-empty">${_loading ? "Loading…" : "Type to search"}</div>`;
      return;
    }

    if (!q) {
      _renderRecent();
      return;
    }

    const results = _search(q);

    if (!results.length) {
      _list.innerHTML = `<div class="search-empty">No results for <strong>${_esc(query)}</strong></div>`;
      return;
    }

    // Group by type
    const groups = {};
    results.forEach(r => {
      if (!groups[r.type]) groups[r.type] = [];
      groups[r.type].push(r);
    });

    const typeOrder = ["Page", "Product", "Application", "Pipeline", "Run", "User"];
    const typeIcons = {
      Page:        "🔖",
      Product:     "📦",
      Application: "🧩",
      Pipeline:    "⚙️",
      Run:         "▶️",
      User:        "👤",
    };

    let html = "";
    for (const type of typeOrder) {
      if (!groups[type]) continue;
      const groupLabel = type === "Page" ? "Pages" : `${type}s`;
      html += `<div class="search-group-label">${typeIcons[type]} ${groupLabel}</div>`;
      html += groups[type].slice(0, 6).map(r => _itemHtml(r, q)).join("");
    }

    _list.innerHTML = html;

    _list.querySelectorAll(".search-item").forEach(el => {
      el.addEventListener("click", () => {
        _recordRecent(el.dataset);
        closeSearch();
        navigate(el.dataset.hash);
      });
      el.addEventListener("mouseenter", () => {
        _selIdx = Array.from(_list.querySelectorAll(".search-item")).indexOf(el);
        _highlight(_list.querySelectorAll(".search-item"));
      });
    });
  }

  // ── Static navigation pages ─────────────────────────────────────────────────
  const _PAGES = [
    { hash: "dashboard",       label: "Dashboard",        sub: "Platform overview and recent activity",                icon: "⬛" },
    { hash: "products",        label: "Products",          sub: "Manage products, pipelines and releases",             icon: "📦" },
    { hash: "environments",    label: "Environments",      sub: "Deployment targets — dev, qa, prod",                  icon: "🌍" },
    { hash: "compliance",      label: "Compliance",        sub: "Rules that gate pipeline release attachment",         icon: "🛡" },
    { hash: "maturity",        label: "Maturity",          sub: "DevSecOps maturity scoring across all products",      icon: "📊" },
    { hash: "app-dictionary",  label: "App Dictionary",    sub: "Application artifact registry and compliance ratings",icon: "📚" },
    { hash: "monitoring",      label: "Monitoring",        sub: "Prometheus metrics, alert rules and stack setup",     icon: "📡" },
    { hash: "admin/users",     label: "User Management",   sub: "Users, groups and roles (RBAC)",                      icon: "👥" },
    { hash: "admin/keys",      label: "Key Management",    sub: "API keys and integration secrets",                    icon: "🔑" },
    { hash: "admin/variables", label: "Global Variables",  sub: "Platform-wide environment variables",                 icon: "🌐" },
    { hash: "admin/system",    label: "System Settings",   sub: "TASK_RUNNER, GROQ key, LDAP, container runtime",      icon: "🔧" },
    { hash: "admin/frameworks", label: "Framework Controls", sub: "Enable/disable ISAE 3000 and ACF controls, add custom controls", icon: "📋" },
    { hash: "templates",        label: "Templates",          sub: "Reusable pipeline blueprints — create pipelines from templates", icon: "🗂️" },
    { hash: "agents",          label: "Agent Pools",       sub: "Sandboxed pipeline execution environments",           icon: "🤖" },
    { hash: "plugins",         label: "Plugins",           sub: "CI/CD tool integrations and custom extensions",       icon: "🔌" },
    { hash: "vault",           label: "Vault",             sub: "Encrypted secret storage",                            icon: "🔒" },
    { hash: "docs",            label: "Documentation",     sub: "API reference, concepts and script contracts",        icon: "📖" },
    { hash: "tutorial",        label: "Tutorial",          sub: "Step-by-step guide from zero to a running pipeline",  icon: "🎓" },
  ];

  function _search(q) {
    const results = [];

    // Navigation pages
    _PAGES.forEach(pg => {
      if (_matches(q, pg.label, pg.sub, pg.hash)) {
        results.push({ type: "Page", id: pg.hash, label: pg.label, sub: pg.sub, hash: pg.hash });
      }
    });

    // Products
    (_cache.products || []).forEach(p => {
      if (_matches(q, p.name, p.description)) {
        results.push({ type: "Product", id: p.id, label: p.name, sub: p.description || "", hash: `products/${p.id}` });
      }
    });

    // Applications
    (_cache.products || []).forEach(p => {
      (_cache.appsByProduct[p.id] || []).forEach(a => {
        if (_matches(q, a.name, a.description, a.repository_url)) {
          results.push({ type: "Application", id: a.id, label: a.name, sub: `${p.name} · ${a.artifact_type || ""}`, hash: `products/${p.id}` });
        }
      });
    });

    // Pipelines
    (_cache.products || []).forEach(p => {
      (_cache.pipelinesByProduct[p.id] || []).forEach(pl => {
        if (_matches(q, pl.name, pl.kind, pl.git_repo)) {
          results.push({
            type: "Pipeline",
            id: pl.id,
            label: pl.name,
            sub: `${p.name} · ${pl.kind?.toUpperCase() || ""}`,
            meta: pl.compliance_rating || "",
            hash: `products/${p.id}/pipelines/${pl.id}`,
          });
        }
      });
    });

    // Pipeline runs — match run ID, pipeline name, status, triggered_by, commit_sha
    (_cache.runs || []).forEach(r => {
      const plName = _pipelineName(r.pipeline_id);
      const prodId = r._product_id || r.product_id;
      if (_matches(q, r.id, plName, r.status, r.triggered_by, r.commit_sha)) {
        results.push({
          type: "Run",
          id: r.id,
          label: plName || r.id,
          sub: `${r.status} · ${r.triggered_by || "system"} · ${_shortId(r.id)}`,
          meta: r.status,
          hash: `products/${prodId}/pipelines/${r.pipeline_id}/runs/${r.id}`,
        });
      }
    });

    // Users
    (_cache.users || []).forEach(u => {
      if (_matches(q, u.username, u.display_name, u.email, u.persona)) {
        results.push({ type: "User", id: u.id, label: u.display_name || u.username, sub: `${u.email || ""} · ${u.persona || ""}`, hash: "admin/users" });
      }
    });

    return results;
  }

  function _pipelineName(pipelineId) {
    for (const prods of Object.values(_cache.pipelinesByProduct || {})) {
      const found = prods.find(p => p.id === pipelineId);
      if (found) return found.name;
    }
    return pipelineId;
  }

  function _matches(q, ...fields) {
    return fields.some(f => f && String(f).toLowerCase().includes(q));
  }

  function _shortId(id) {
    return id ? id.split("_").pop()?.slice(-8) : "";
  }

  // ── Recent items ─────────────────────────────────────────────────────────────
  const RECENT_KEY = "cdt_search_recent";
  const MAX_RECENT = 6;

  function _getRecent() {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch { return []; }
  }

  function _recordRecent(dataset) {
    const item = { type: dataset.type, label: dataset.label, sub: dataset.sub || "", hash: dataset.hash, meta: dataset.meta || "" };
    let recent = _getRecent().filter(r => r.hash !== item.hash);
    recent.unshift(item);
    recent = recent.slice(0, MAX_RECENT);
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
  }

  function _renderRecent() {
    const recent = _getRecent();
    if (!recent.length) {
      _list.innerHTML = `<div class="search-empty">Start typing to search across the platform</div>`;
      return;
    }
    const typeIcons = { Page: "🔖", Product: "📦", Application: "🧩", Pipeline: "⚙️", Run: "▶️", User: "👤" };
    let html = `<div class="search-group-label">Recent</div>`;
    html += recent.map(r => `
      <div class="search-item" data-hash="${_esc(r.hash)}" data-label="${_esc(r.label)}" data-sub="${_esc(r.sub)}" data-type="${_esc(r.type)}" data-meta="${_esc(r.meta || "")}">
        <span class="search-item-icon">${typeIcons[r.type] || "📄"}</span>
        <span class="search-item-body">
          <span class="search-item-label">${_esc(r.label)}</span>
          ${r.sub ? `<span class="search-item-sub">${_esc(r.sub)}</span>` : ""}
        </span>
        ${r.meta ? `<span class="search-item-meta">${_esc(r.meta)}</span>` : ""}
      </div>`).join("");
    _list.innerHTML = html;

    _list.querySelectorAll(".search-item").forEach(el => {
      el.addEventListener("click", () => {
        closeSearch();
        navigate(el.dataset.hash);
      });
    });
  }

  // ── Item HTML ────────────────────────────────────────────────────────────────
  function _itemHtml(r, q) {
    const typeIcons = { Page: "🔖", Product: "📦", Application: "🧩", Pipeline: "⚙️", Run: "▶️", User: "👤" };
    const icon = typeIcons[r.type] || "📄";
    const label = _highlight_text(r.label, q);
    const sub   = _highlight_text(r.sub, q);
    return `
      <div class="search-item" data-hash="${_esc(r.hash)}" data-label="${_esc(r.label)}" data-sub="${_esc(r.sub)}" data-type="${_esc(r.type)}" data-meta="${_esc(r.meta || "")}">
        <span class="search-item-icon">${icon}</span>
        <span class="search-item-body">
          <span class="search-item-label">${label}</span>
          ${r.sub ? `<span class="search-item-sub">${sub}</span>` : ""}
        </span>
        ${r.meta ? `<span class="search-item-meta">${_esc(r.meta)}</span>` : ""}
      </div>`;
  }

  function _highlight_text(text, q) {
    if (!text || !q) return _esc(text || "");
    const idx = text.toLowerCase().indexOf(q.toLowerCase());
    if (idx === -1) return _esc(text);
    return _esc(text.slice(0, idx)) +
           `<mark>${_esc(text.slice(idx, idx + q.length))}</mark>` +
           _esc(text.slice(idx + q.length));
  }

  function _esc(s) {
    return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  // ── Keyboard shortcut ────────────────────────────────────────────────────────
  document.addEventListener("keydown", e => {
    // Ctrl+K or Cmd+K
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      if (_overlay && _overlay.style.display !== "none") {
        closeSearch();
      } else {
        openSearch();
      }
      return;
    }
    // '/' when not focused on an input/textarea
    if (e.key === "/" && !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      openSearch();
    }
  });

})();
