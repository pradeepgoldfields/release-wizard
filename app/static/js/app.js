/* ── Conduit SPA ─────────────────────────────────────────────────── */

// ── Router ─────────────────────────────────────────────────────────────────
const router = {
  current: null,
  routes: {},

  register(hash, fn) { this.routes[hash] = fn; },

  navigate(hash, push = true) {
    if (push) history.pushState({}, "", "#" + hash);
    this.current = hash;
    this._run(hash);
    this._updateNav(hash);
  },

  _run(hash) {
    const parts = hash.split("/");
    const key0 = parts[0];
    // Clear breadcrumb at the start of each navigation
    const bc = document.getElementById("breadcrumb");
    if (bc) bc.innerHTML = "";
    // try exact, then prefix matches
    for (const pattern of Object.keys(this.routes)) {
      if (this._match(pattern, hash)) {
        this.routes[pattern](hash, parts);
        return;
      }
    }
    // fallback
    if (this.routes["dashboard"]) this.routes["dashboard"]("dashboard", []);
  },

  _match(pattern, hash) {
    const pp = pattern.split("/");
    const hp = hash.split("/");
    if (pp.length !== hp.length) return false;
    return pp.every((p, i) => p.startsWith(":") || p === hp[i]);
  },

  _updateNav(hash) {
    document.querySelectorAll("#sidebar nav a").forEach(a => {
      const h = (a.getAttribute("href") || "").replace("#", "");
      a.classList.toggle("active", hash === h || hash.startsWith(h + "/"));
    });
    // Auto-expand admin section when navigating to an admin route
    if (hash.startsWith("admin")) {
      const section = document.getElementById("admin-section");
      const header = section && section.previousElementSibling;
      if (section && !section.classList.contains("open")) {
        section.classList.add("open");
        if (header) header.classList.add("open");
      }
    }
  },

  init() {
    window.addEventListener("popstate", () => {
      const h = location.hash.replace("#", "") || "dashboard";
      this._run(h);
      this._updateNav(h);
    });
    const h = location.hash.replace("#", "") || "dashboard";
    this.navigate(h, false);
  }
};

let _pollTimer = null;
let _currentUser = null;

function navigate(hash) {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  router.navigate(hash);
}

function toggleNavSection(id) {
  const section = document.getElementById(id);
  const header = section && section.previousElementSibling;
  if (!section) return;
  const open = section.classList.toggle("open");
  if (header) header.classList.toggle("open", open);
}

// ── Auth / Login ────────────────────────────────────────────────────────────
function showLoginPage(errorMsg) {
  document.getElementById("layout").style.display = "none";
  let loginEl = document.getElementById("login-page");
  if (!loginEl) {
    loginEl = document.createElement("div");
    loginEl.id = "login-page";
    document.body.insertBefore(loginEl, document.getElementById("layout"));
  }
  loginEl.style.display = "";
  loginEl.innerHTML = `
    <div class="login-wrap">
      <div class="login-card">
        <div class="login-logo">Con<span style="color:var(--brand)">duit</span></div>
        <div class="login-sub">CI/CD Orchestration Platform</div>
        ${errorMsg ? `<div class="alert alert-danger" style="margin-bottom:12px">${errorMsg}</div>` : ""}
        <div class="form-group">
          <label>Username</label>
          <input id="li-user" class="form-control" placeholder="admin" autofocus>
        </div>
        <div class="form-group">
          <label>Password</label>
          <input id="li-pass" class="form-control" type="password" placeholder="••••••••">
        </div>
        <button class="btn btn-primary" style="width:100%;margin-top:8px" onclick="doLogin()">Sign In</button>
      </div>
    </div>`;
  // Allow pressing Enter in password field
  setTimeout(() => {
    const passEl = document.getElementById("li-pass");
    if (passEl) passEl.onkeydown = (e) => { if (e.key === "Enter") doLogin(); };
    const userEl = document.getElementById("li-user");
    if (userEl) userEl.onkeydown = (e) => { if (e.key === "Enter") doLogin(); };
  }, 50);
}

async function doLogin() {
  const username = (document.getElementById("li-user")?.value || "").trim();
  const password = document.getElementById("li-pass")?.value || "";
  if (!username || !password) { showLoginPage("Username and password are required"); return; }
  try {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) { showLoginPage(data.error || "Login failed"); return; }
    auth.setToken(data.token);
    _currentUser = data.user;
    hideLoginPage();
    updateTopbarUser();
    navigate("dashboard");
  } catch (e) {
    showLoginPage("Login failed — server unreachable");
  }
}

function hideLoginPage() {
  const loginEl = document.getElementById("login-page");
  if (loginEl) loginEl.style.display = "none";
  document.getElementById("layout").style.display = "";
}

async function doLogout() {
  try { await api.logout(); } catch {}
  auth.clearToken();
  _currentUser = null;
  updateTopbarUser();
  showLoginPage();
}

function _ensureSearchBtn() {
  if (document.getElementById("topbar-search-btn")) return;
  const tb = document.getElementById("topbar");
  if (!tb) return;
  // Insert before the user widget (margin-left:auto on user widget handles spacing)
  const btn = document.createElement("button");
  btn.id = "topbar-search-btn";
  btn.className = "topbar-search-btn";
  btn.title = "Search (Ctrl+K)";
  btn.onclick = () => openSearch();
  btn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span>Search</span><kbd>Ctrl K</kbd>`;
  tb.appendChild(btn);
}

function updateTopbarUser() {
  _ensureSearchBtn();
  let widget = document.getElementById("topbar-user");
  if (!widget) {
    widget = document.createElement("div");
    widget.id = "topbar-user";
    widget.style.cssText = "position:relative";
    document.getElementById("topbar").appendChild(widget);
  }
  if (_currentUser) {
    widget.innerHTML = `
      <button class="user-menu-btn" onclick="toggleUserMenu(event)" aria-haspopup="true">
        <span class="user-avatar">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </span>
        <span class="user-name">${_currentUser.display_name || _currentUser.username}</span>
        <svg class="user-caret" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>
      <div class="user-dropdown" id="user-dropdown" style="display:none">
        <div class="user-dropdown-header">
          <div style="font-weight:600;font-size:13px">${_currentUser.display_name || _currentUser.username}</div>
          <div style="font-size:11.5px;color:var(--gray-400);margin-top:2px">${_currentUser.email || _currentUser.username}</div>
          <span class="badge badge-blue" style="font-size:10.5px;margin-top:6px;display:inline-block">${_currentUser.persona}</span>
        </div>
        <div class="user-dropdown-divider"></div>
        <button class="user-dropdown-item" onclick="closeUserMenu();showChangePassword()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          Change Password
        </button>
        <button class="user-dropdown-item user-dropdown-item-danger" onclick="closeUserMenu();doLogout()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          Sign Out
        </button>
      </div>`;
  } else {
    widget.innerHTML = "";
  }
}

function toggleUserMenu(e) {
  e.stopPropagation();
  const dd = document.getElementById("user-dropdown");
  if (!dd) return;
  const open = dd.style.display !== "none";
  dd.style.display = open ? "none" : "block";
  if (!open) {
    // Close on outside click
    setTimeout(() => document.addEventListener("click", closeUserMenu, { once: true }), 0);
  }
}

function closeUserMenu() {
  const dd = document.getElementById("user-dropdown");
  if (dd) dd.style.display = "none";
}

function showChangePassword() {
  if (!_currentUser) return;
  openModal("Change Password",
    `<div class="form-group"><label>New Password *</label><input id="cp-pass" class="form-control" type="password" placeholder="Min 6 characters"></div>
     <div class="form-group"><label>Confirm Password *</label><input id="cp-conf" class="form-control" type="password"></div>`,
    async () => {
      const p1 = el("cp-pass").value;
      const p2 = el("cp-conf").value;
      if (p1.length < 6) return modalError("Password must be at least 6 characters");
      if (p1 !== p2) return modalError("Passwords do not match");
      try {
        await api.changePassword(_currentUser.id, { password: p1 });
        closeModal(); toast("Password changed", "success");
      } catch (e) { modalError(e.message); }
    }, "Update"
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────
function el(id) { return document.getElementById(id); }
function q(sel, ctx = document) { return ctx.querySelector(sel); }

function setContent(html) {
  el("content").innerHTML = html;
}

function setBreadcrumb(...crumbs) {
  // Always prepend Home as the root crumb (unless it's the dashboard itself)
  const isDashboard = crumbs.length === 1 && crumbs[0].label === "Dashboard";
  const all = isDashboard ? crumbs : [{ label: "Home", hash: "dashboard" }, ...crumbs];

  el("breadcrumb").innerHTML = all.map((c, i) => {
    const isLast = i === all.length - 1;
    if (isLast) return `<span class="crumb-current">${c.label}</span>`;
    // For the crumb immediately before the last one, also render a ← back arrow
    const isParent = i === all.length - 2;
    const arrow = isParent ? `<span class="crumb-back-arrow">←</span>` : "";
    return `${arrow}<a href="#${c.hash}" onclick="navigate('${c.hash}');return false;">${c.label}</a><span class="crumb-sep">›</span>`;
  }).join("");
}

function toast(msg, type = "info") {
  const t = document.createElement("div");
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  el("toast-container").appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

function ratingBadge(rating) {
  const cls = (rating || "Non-Compliant").toLowerCase().replace(/[\s-]/g, "");
  const map = { platinum: "badge-platinum", gold: "badge-gold", silver: "badge-silver", bronze: "badge-bronze", noncompliant: "badge-noncompliant" };
  return `<span class="badge ${map[cls] || "badge-silver"}">${rating || "Non-Compliant"}</span>`;
}

function statusBadge(status) {
  const map = { Succeeded: "badge-success", Running: "badge-running", Failed: "badge-failed", Pending: "badge-pending", InProgress: "badge-running", Cancelled: "badge-silver" };
  return `<span class="badge ${map[status] || "badge-silver"}">${status || "—"}</span>`;
}

function scoreBar(score, rating) {
  const s = Math.min(Math.max(score || 0, 0), 100);
  return `<div class="score-bar-wrap">
    <div class="score-bar"><div class="score-bar-fill ${rating}" style="width:${s}%;max-width:100%"></div></div>
    <span style="font-size:12px;color:var(--gray-600);min-width:36px;text-align:right">${s}%</span>
  </div>`;
}

/**
 * Render a completion percentage bar with colour-coded fill.
 * pct: 0–100 integer from pipeline.completion_percentage
 */

// ── Hamburger / page-menu helper ─────────────────────────────────────────────
// Uses position:fixed so the dropdown always renders above overflow:hidden
// containers (e.g. table cells, collapsible stage bodies). Coordinates are
// computed from the trigger button's getBoundingClientRect on each open.
let _pageMenuOpenId = null;

// Single shared dropdown panel — appended to <body> once.
const _pmenuPanel = document.createElement("div");
_pmenuPanel.id = "pmenu-panel";
_pmenuPanel.style.cssText = "display:none;position:fixed;background:#fff;border:1px solid var(--gray-200);border-radius:8px;box-shadow:0 4px 24px #0003;min-width:180px;z-index:9999;padding:4px 0;overflow:hidden";
document.body.appendChild(_pmenuPanel);

document.addEventListener("click", (e) => {
  if (_pageMenuOpenId && !e.target.closest(`#pmenu-btn-${_pageMenuOpenId}`)) {
    _closePageMenu();
  }
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") _closePageMenu(); });
document.addEventListener("scroll", () => _closePageMenu(), true);

function _closePageMenu() {
  _pmenuPanel.style.display = "none";
  _pageMenuOpenId = null;
}

function _togglePageMenu(id, items) {
  if (_pageMenuOpenId === id) { _closePageMenu(); return; }
  _closePageMenu();

  // Build menu content from the items stored on the button element
  const btn = document.getElementById(`pmenu-btn-${id}`);
  if (!btn) return;

  const itemsData = JSON.parse(btn.dataset.items);
  _pmenuPanel.innerHTML = itemsData.map(item => {
    if (item.divider) return `<div style="height:1px;background:var(--gray-200);margin:4px 0"></div>`;
    const color = item.danger ? "#dc2626" : "var(--gray-700)";
    return `<button
      style="display:block;width:100%;text-align:left;padding:8px 16px;font-size:13px;border:none;background:none;cursor:pointer;color:${color};white-space:nowrap"
      onmouseover="this.style.background='var(--gray-50)'" onmouseout="this.style.background='none'"
      onclick="_closePageMenu();${item.onclick}">${item.label}</button>`;
  }).join("");

  // Position: align right edge of menu with right edge of button, below it.
  // If it would overflow the bottom, open upward instead.
  const rect = btn.getBoundingClientRect();
  const menuH = itemsData.length * 36 + 8; // rough estimate
  const spaceBelow = window.innerHeight - rect.bottom;
  const openUp = spaceBelow < menuH && rect.top > menuH;

  _pmenuPanel.style.display = "block";
  // Measure actual width after display:block
  const panelW = _pmenuPanel.offsetWidth;
  let left = rect.right - panelW;
  if (left < 4) left = 4;
  const top = openUp ? rect.top - _pmenuPanel.offsetHeight - 4 : rect.bottom + 4;
  _pmenuPanel.style.left = left + "px";
  _pmenuPanel.style.top = top + "px";
  _pageMenuOpenId = id;
}

/**
 * Render a hamburger (⋮) trigger button. The dropdown is rendered in a shared
 * fixed-position panel appended to <body>, so it is never clipped by overflow.
 * @param {string} id    — unique id (no spaces)
 * @param {Array}  items — [{label, onclick, danger?, divider?}]
 * @param {string} [btnClass]
 */
function pageMenu(id, items, btnClass) {
  const cls = btnClass || "btn btn-secondary btn-sm";
  // Encode items as JSON on the button so _togglePageMenu can read them
  const encoded = JSON.stringify(items).replace(/'/g, "&#39;").replace(/"/g, "&quot;");
  return `<button id="pmenu-btn-${id}" class="${cls}" data-items="${encoded}"
    onclick="event.stopPropagation();_togglePageMenu('${id}')" title="More actions"
    style="padding:4px 10px;font-size:16px;line-height:1">⋮</button>`;
}

// Task type tag colours
const _TASK_TYPE_COLORS = {
  sast: "#7c3aed", sca: "#0369a1", dast: "#b45309", "secret-scan": "#0f766e",
  "container-scan": "#0891b2", "unit-test": "#15803d", "integration-test": "#166534",
  "code-coverage": "#4338ca", "smoke-test": "#9333ea", build: "#374151",
  release: "#9d174d", deploy: "#1d4ed8", "security-gate": "#b91c1c", lint: "#6b7280",
  notify: "#78716c",
};

function _taskTypeBadges(taskType) {
  if (!taskType) return `<span style="color:var(--gray-400);font-size:11px">—</span>`;
  return taskType.split(",").map(t => {
    const tag = t.trim().toLowerCase();
    const color = _TASK_TYPE_COLORS[tag] || "#6366f1";
    return `<span style="display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:600;color:#fff;background:${color};margin:1px 2px 1px 0">${t.trim()}</span>`;
  }).join("");
}

// Canonical task type options (mirrors TASK_TYPE_OPTIONS on backend)
const _TASK_TYPE_OPTIONS = [
  {value:"sast",label:"SAST — Static Analysis"},
  {value:"sca",label:"SCA — Dependency Scan"},
  {value:"dast",label:"DAST — Dynamic Analysis"},
  {value:"secret-scan",label:"Secret Scanning"},
  {value:"container-scan",label:"Container / Image Scan"},
  {value:"unit-test",label:"Unit Testing"},
  {value:"integration-test",label:"Integration Testing"},
  {value:"code-coverage",label:"Code Coverage"},
  {value:"smoke-test",label:"Smoke / Health Check"},
  {value:"build",label:"Build / Compile"},
  {value:"release",label:"Release / Versioning"},
  {value:"deploy",label:"Deploy / Env Promotion"},
  {value:"security-gate",label:"Security Gate / Approval"},
  {value:"lint",label:"Lint / Format"},
  {value:"notify",label:"Notification"},
  {value:"custom",label:"Custom (type below)"},
];

function _taskTypeSelector(selectedValue) {
  const opts = _TASK_TYPE_OPTIONS.map(o =>
    `<option value="${o.value}"${selectedValue===o.value?" selected":""}>${o.label}</option>`
  ).join("");
  const customVal = selectedValue && !_TASK_TYPE_OPTIONS.find(o=>o.value===selectedValue) ? selectedValue : "";
  return `
    <div class="form-group">
      <label>Task Type <span style="font-size:11px;color:var(--gray-400)">(used for maturity scoring)</span></label>
      <select id="tf-tasktype-sel" class="form-control" onchange="document.getElementById('tf-tasktype-custom-row').style.display=this.value==='custom'?'block':'none'">
        <option value="">— none —</option>
        ${opts}
      </select>
    </div>
    <div id="tf-tasktype-custom-row" style="display:${customVal||selectedValue==='custom'?'block':'none'}">
      <div class="form-group">
        <label>Custom tag(s) <span style="font-size:11px;color:var(--gray-400)">(comma-separated, e.g. my-sast,compliance-scan)</span></label>
        <input id="tf-tasktype-custom" class="form-control" placeholder="e.g. my-security-scan" value="${customVal}">
      </div>
    </div>`;
}

function _resolveTaskType() {
  const sel = document.getElementById("tf-tasktype-sel");
  if (!sel) return "";
  if (sel.value === "custom") {
    return (document.getElementById("tf-tasktype-custom")?.value || "").trim();
  }
  return sel.value;
}

function completionBar(pct) {
  const p = pct == null ? 0 : Math.min(Math.max(pct, 0), 100);
  const color = p >= 80 ? "#22c55e" : p >= 50 ? "#f59e0b" : "#ef4444";
  return `<div style="display:flex;align-items:center;gap:6px;min-width:140px">
    <div style="flex:1;min-width:80px;height:6px;border-radius:3px;background:var(--gray-200);overflow:hidden;position:relative">
      <div style="position:absolute;top:0;left:0;height:100%;border-radius:3px;background:${color};width:${p}%;max-width:100%;transition:width .4s"></div>
    </div>
    <span style="font-size:12px;color:var(--gray-600);white-space:nowrap;min-width:32px;text-align:right">${p}%</span>
  </div>`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function fmtDuration(startIso, endIso) {
  if (!startIso) return "—";
  const end = endIso ? new Date(endIso) : new Date();
  const secs = Math.max(0, Math.floor((end - new Date(startIso)) / 1000));
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

function loading() {
  return `<div class="loading-center"><div class="spinner"></div></div>`;
}

// ── Modal helpers ──────────────────────────────────────────────────────────
function openModal(title, bodyHtml, onConfirm, confirmLabel = "Save") {
  el("modal-title").textContent = title;
  el("modal-body").innerHTML = bodyHtml;
  el("modal-confirm").textContent = confirmLabel;
  el("modal-confirm").onclick = onConfirm;
  el("modal-overlay").classList.add("open");
}

function closeModal() {
  el("modal-overlay").classList.remove("open");
}

function insertVarAtCursor(textareaId, varText) {
  const ta = document.getElementById(textareaId);
  if (!ta) return;
  const start = ta.selectionStart;
  const end = ta.selectionEnd;
  ta.value = ta.value.slice(0, start) + varText + ta.value.slice(end);
  ta.selectionStart = ta.selectionEnd = start + varText.length;
  ta.focus();
}

function modalError(msg) {
  const existing = q(".modal-alert", el("modal-body"));
  if (existing) existing.remove();
  const div = document.createElement("div");
  div.className = "alert alert-danger modal-alert";
  div.innerHTML = `⚠ ${msg}`;
  el("modal-body").prepend(div);
}

// ── Dashboard ──────────────────────────────────────────────────────────────
router.register("dashboard", async () => {
  setBreadcrumb({ label: "Dashboard" });
  setContent(loading());
  const [products, rules, users] = await Promise.all([
    api.getProducts().catch(() => []),
    api.getComplianceRules().catch(() => []),
    api.getUsers().catch(() => []),
  ]);
  setContent(`
    <div class="page-header">
      <div><h1>Dashboard</h1><div class="sub">Conduit overview</div></div>
    </div>
    <div class="grid grid-3" style="margin-bottom:24px">
      <div class="stat-tile">
        <div class="stat-label">Products</div>
        <div class="stat-value">${products.length}</div>
        <div class="stat-sub"><a href="#products">View all</a></div>
      </div>
      <div class="stat-tile">
        <div class="stat-label">Compliance Rules</div>
        <div class="stat-value">${rules.length}</div>
        <div class="stat-sub"><a href="#compliance">Manage rules</a></div>
      </div>
      <div class="stat-tile">
        <div class="stat-label">Users</div>
        <div class="stat-value">${users.length}</div>
        <div class="stat-sub"><a href="#users">Manage</a></div>
      </div>
    </div>
    <div class="card">
      <div class="card-header"><h2>Products</h2>
        <button class="btn btn-primary btn-sm" onclick="navigate('products')">View All</button>
      </div>
      ${products.length === 0
        ? `<div class="empty-state"><div class="empty-icon">📦</div><p>No products yet. <a href="#products">Create one.</a></p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Description</th><th>Actions</th></tr></thead>
          <tbody>${products.slice(0,5).map(p => `
            <tr>
              <td><a href="#products/${p.id}">${p.name}</a></td>
              <td style="color:var(--gray-600)">${p.description || "—"}</td>
              <td><button class="btn btn-secondary btn-sm" onclick="navigate('products/${p.id}')">Open</button></td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>
  `);
});

// ── Products list ──────────────────────────────────────────────────────────
router.register("products", async () => {
  setBreadcrumb({ label: "Products" });
  setContent(loading());
  const products = await api.getProducts().catch(() => []);
  setContent(`
    <div class="page-header">
      <div><h1>Products</h1><div class="sub">Organize your releases and pipelines</div></div>
      <button class="btn btn-primary" onclick="showCreateProduct()">+ New Product</button>
    </div>
    ${products.length === 0
      ? `<div class="card"><div class="empty-state"><div class="empty-icon">📦</div><p>No products yet.</p></div></div>`
      : `<div class="grid grid-3">
        ${products.map(p => `
          <div class="card">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
              <span style="font-size:16px;font-weight:600;cursor:pointer" onclick="navigate('products/${p.id}')">${p.name}</span>
              <span class="badge badge-blue">Product</span>
            </div>
            <div style="color:var(--gray-600);font-size:13px;margin-bottom:12px">${p.description || "No description"}</div>
            <div style="display:flex;gap:6px;margin-top:8px">
              <button class="btn btn-secondary btn-sm" onclick="navigate('products/${p.id}')">Open</button>
              <button class="btn btn-secondary btn-sm" onclick="showEditProduct('${p.id}','${p.name.replace(/'/g,"\\'")}','${(p.description||"").replace(/'/g,"\\'")}')">Edit</button>
              <button class="btn btn-danger btn-sm" onclick="deleteProduct('${p.id}','${p.name.replace(/'/g,"\\'")}')">Delete</button>
            </div>
          </div>`).join("")}
      </div>`
    }
  `);
});

function showEditProduct(id, name, description) {
  openModal("Edit Product",
    `<div class="form-group"><label>Name *</label><input id="ep-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Description</label><textarea id="ep-desc" class="form-control">${description}</textarea></div>`,
    async () => {
      const n = el("ep-name").value.trim();
      if (!n) return modalError("Name is required");
      try {
        await api.updateProduct(id, { name: n, description: el("ep-desc").value.trim() || null });
        closeModal(); toast("Product updated", "success");
        navigate("products");
      } catch (e) { modalError(e.message); }
    }
  );
}

function showCreateProduct() {
  openModal("New Product",
    `<div class="form-group"><label>Name *</label><input id="pf-name" class="form-control" placeholder="e.g. API Service"></div>
     <div class="form-group"><label>Description</label><textarea id="pf-desc" class="form-control" placeholder="Optional description"></textarea></div>`,
    async () => {
      const name = el("pf-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        await api.createProduct({ name, description: el("pf-desc").value.trim() || null });
        closeModal();
        toast("Product created", "success");
        navigate("products");
      } catch (e) { modalError(e.message); }
    }
  );
}

// ── Product detail ─────────────────────────────────────────────────────────
router.register("products/:id", async (hash, parts) => {
  const productId = parts[1];
  setBreadcrumb({ label: "Products", hash: "products" }, { label: "Loading…" });
  setContent(loading());
  const [product, pipelines, releases, envs, apps] = await Promise.all([
    api.getProduct(productId),
    api.getPipelines(productId).catch(() => []),
    api.getReleases(productId).catch(() => []),
    api.getProductEnvironments(productId).catch(() => []),
    api.getApplications(productId).catch(() => []),
  ]);
  setBreadcrumb({ label: "Products", hash: "products" }, { label: product.name });

  setContent(`
    <div class="page-header">
      <div><h1>${product.name}</h1><div class="sub">${product.description || "No description"}</div></div>
      ${pageMenu("prod-"+product.id, [
        {label: "⬇ Export YAML", onclick: `exportYaml('/api/v1/products/${product.id}/export','${product.name.replace(/'/g,"\\'")}product.yaml')`},
        {divider: true},
        {label: "🗑 Delete Product", onclick: `deleteProduct('${product.id}','${product.name}')`, danger: true},
      ])}
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab(this,'tab-releases')">Releases (${releases.length})</button>
      <button class="tab-btn" onclick="switchTab(this,'tab-apps')">Applications & Pipelines (${apps.length})</button>
      <button class="tab-btn" onclick="switchTab(this,'tab-envs')">Environments (${envs.length})</button>
    </div>

    <!-- Releases -->
    <div id="tab-releases" class="tab-panel active">
      <div style="display:flex;justify-content:flex-end;margin-bottom:12px">
        <button class="btn btn-primary btn-sm" onclick="showCreateRelease('${product.id}')">+ New Release</button>
      </div>
      ${releases.length === 0
        ? `<div class="empty-state"><div class="empty-icon">🚀</div><p>No releases yet.</p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Version</th><th>Pipelines</th><th>Created</th><th>Actions</th></tr></thead>
          <tbody>${releases.map(r => `
            <tr>
              <td><a href="#products/${productId}/releases/${r.id}">${r.name}</a></td>
              <td>${r.version || "—"}</td>
              <td>${(r.pipelines||[]).length}</td>
              <td style="color:var(--gray-400)">${fmtDate(r.created_at)}</td>
              <td>
                ${pageMenu("rl-"+r.id, [
                  {label: "👁 View Release", onclick: `navigate('products/${productId}/releases/${r.id}')` },
                  {label: "✏ Edit", onclick: `showEditRelease('${productId}','${r.id}','${r.name.replace(/'/g,"\\'")}','${r.version||""}','${(r.description||"").replace(/'/g,"\\'")}')` },
                  {divider: true},
                  {label: "🗑 Delete", onclick: `deleteRelease('${productId}','${r.id}','${r.name.replace(/'/g,"\\'")}')`, danger: true},
                ])}
              </td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>

    <!-- Environments -->
    <div id="tab-envs" class="tab-panel">
      <div style="display:flex;justify-content:flex-end;margin-bottom:12px;gap:8px">
        <button class="btn btn-secondary btn-sm" onclick="showAttachEnv('${product.id}')">+ Attach Environment</button>
        <button class="btn btn-primary btn-sm" onclick="navigate('environments')">Manage Environments</button>
      </div>
      ${envs.length === 0
        ? `<div class="empty-state"><div class="empty-icon">🌍</div><p>No environments attached. <a href="#environments">Create one</a> first, then attach it here.</p></div>`
        : `<div class="grid grid-3">${envs.map(e => `
            <div class="card">
              <div style="font-weight:600;margin-bottom:4px">${e.name}</div>
              <div><span class="badge badge-blue">${e.env_type}</span></div>
              <div style="font-size:11.5px;color:var(--gray-400);margin-top:8px">Order: ${e.order}</div>
              <div style="display:flex;gap:6px;margin-top:10px">
                <button class="btn btn-danger btn-sm" onclick="detachEnv('${product.id}','${e.id}','${e.name}')">Detach</button>
              </div>
            </div>`).join("")}</div>`
      }
    </div>

    <!-- Applications -->
    <div id="tab-apps" class="tab-panel">
      <div style="display:flex;justify-content:flex-end;margin-bottom:12px">
        <button class="btn btn-primary btn-sm" onclick="showCreateApp('${product.id}')">+ New Application</button>
      </div>
      ${apps.length === 0
        ? `<div class="empty-state"><div class="empty-icon">📱</div><p>No applications yet.</p></div>`
        : apps.map(a => {
            const appPipelines = pipelines.filter(pl => pl.application_id === a.id);
            return `<div class="card" style="margin-bottom:10px;padding:0;overflow:hidden">
              <!-- Collapsible header — collapsed by default -->
              <div style="display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;user-select:none;background:var(--gray-50);border-bottom:1px solid var(--gray-200)"
                onclick="toggleAppCard('app-body-${a.id}','app-chev-${a.id}')">
                <span id="app-chev-${a.id}" style="font-size:12px;color:var(--gray-400);transition:transform .15s;display:inline-block">▶</span>
                <div style="flex:1">
                  <span style="font-weight:600;font-size:14px">${a.name}</span>
                  <span class="badge badge-blue" style="margin-left:8px">${a.artifact_type}</span>
                  ${a.repository_url ? `<span style="font-size:11.5px;color:var(--gray-400);margin-left:8px">${a.repository_url}</span>` : ""}
                  <span style="font-size:12px;color:var(--gray-400);margin-left:8px">${appPipelines.length} pipeline(s)</span>
                </div>
                <div onclick="event.stopPropagation()">
                  ${pageMenu("app-"+a.id, [
                    {label: "＋ Add Pipeline", onclick: `showCreatePipelineForApp('${product.id}','${a.id}')`},
                    {label: "✏ Edit Application", onclick: `showEditApp('${product.id}','${a.id}','${a.name.replace(/'/g,"\\'")}','${a.artifact_type}','${(a.repository_url||"").replace(/'/g,"\\'")}')` },
                    {divider: true},
                    {label: "🗑 Delete Application", onclick: `deleteApp('${product.id}','${a.id}','${a.name.replace(/'/g,"\\'")}')`, danger: true},
                  ])}
                </div>
              </div>
              <!-- Body — hidden by default -->
              <div id="app-body-${a.id}" style="display:none;padding:12px 14px">
                ${appPipelines.length === 0
                  ? `<div style="font-size:12px;color:var(--gray-400);padding:4px 0">No pipelines — click "+ Pipeline" to add one.</div>`
                  : `<div class="table-wrap"><table style="font-size:13px">
                      <thead><tr><th>Pipeline</th><th>Kind</th><th>Actions</th></tr></thead>
                      <tbody>${appPipelines.map(pl => `
                        <tr>
                          <td><a href="#products/${productId}/pipelines/${pl.id}">${pl.name}</a></td>
                          <td><span class="badge badge-${pl.kind}">${pl.kind.toUpperCase()}</span></td>
                          <td>
                            ${pageMenu("plr-"+pl.id, [
                              {label: "👁 View Pipeline", onclick: `navigate('products/${productId}/pipelines/${pl.id}')` },
                              {divider: true},
                              {label: "🗑 Delete Pipeline", onclick: `deletePipeline('${productId}','${pl.id}','${pl.name.replace(/'/g,"\\'")}')`, danger: true},
                            ])}
                          </td>
                        </tr>`).join("")}
                      </tbody></table></div>`
                }
              </div>
            </div>`;
          }).join("")
      }
    </div>
  `);
});

function toggleAppCard(bodyId, chevId) {
  const body = document.getElementById(bodyId);
  const chev = document.getElementById(chevId);
  if (!body) return;
  const open = body.style.display !== "none";
  body.style.display = open ? "none" : "block";
  if (chev) chev.style.transform = open ? "" : "rotate(90deg)";
}

function switchTab(btn, tabId) {
  btn.closest(".tabs").querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  const panel = btn.closest(".tabs").nextElementSibling;
  let el2 = panel;
  // walk siblings
  const parent = btn.closest(".tabs").parentElement;
  parent.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.getElementById(tabId)?.classList.add("active");
}

async function deleteProduct(id, name) {
  if (!confirm(`Delete product "${name}"? This will remove all its data.`)) return;
  try {
    await api.deleteProduct(id);
    toast("Product deleted", "success");
    navigate("products");
  } catch (e) { toast(e.message, "error"); }
}

function showEditPipeline(productId, pipelineId, name, kind, repo, branch) {
  openModal("Edit Pipeline",
    `<div class="form-group"><label>Name *</label><input id="epl-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Kind</label><select id="epl-kind" class="form-control">
       <option value="ci"${kind==="ci"?" selected":""}>CI</option><option value="cd"${kind==="cd"?" selected":""}>CD</option>
     </select></div>
     <div class="form-group"><label>Git Repository</label><input id="epl-repo" class="form-control" value="${repo}"></div>
     <div class="form-group"><label>Branch</label><input id="epl-branch" class="form-control" value="${branch}"></div>`,
    async () => {
      const n = el("epl-name").value.trim();
      if (!n) return modalError("Name is required");
      try {
        await api.updatePipeline(productId, pipelineId, {
          name: n, kind: el("epl-kind").value,
          git_repo: el("epl-repo").value.trim() || null,
          git_branch: el("epl-branch").value.trim() || "main",
        });
        closeModal(); toast("Pipeline updated", "success");
        navigate(`products/${productId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

async function deletePipeline(productId, pipelineId, name) {
  if (!confirm(`Delete pipeline "${name}"?`)) return;
  try {
    await api.deletePipeline(productId, pipelineId);
    toast("Pipeline deleted", "success");
    navigate(`products/${productId}`);
  } catch (e) { toast(e.message, "error"); }
}

function showEditRelease(productId, releaseId, name, version, description) {
  openModal("Edit Release",
    `<div class="form-group"><label>Name *</label><input id="er-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Version</label><input id="er-ver" class="form-control" value="${version}"></div>
     <div class="form-group"><label>Description</label><textarea id="er-desc" class="form-control">${description}</textarea></div>`,
    async () => {
      const n = el("er-name").value.trim();
      if (!n) return modalError("Name is required");
      try {
        await api.updateRelease(productId, releaseId, {
          name: n,
          version: el("er-ver").value.trim() || null,
          description: el("er-desc").value.trim() || null,
        });
        closeModal(); toast("Release updated", "success");
        navigate(`products/${productId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

function showEditEnv(envId, name, envType, order, description) {
  openModal("Edit Environment",
    `<div class="form-group"><label>Name *</label><input id="ee-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Type</label><select id="ee-type" class="form-control">
       <option value="dev"${envType==="dev"?" selected":""}>dev</option>
       <option value="qa"${envType==="qa"?" selected":""}>qa</option>
       <option value="staging"${envType==="staging"?" selected":""}>staging</option>
       <option value="prod"${envType==="prod"?" selected":""}>prod</option>
       <option value="custom"${envType==="custom"?" selected":""}>custom</option>
     </select></div>
     <div class="form-group"><label>Order</label><input id="ee-order" class="form-control" type="number" value="${order}"></div>
     <div class="form-group"><label>Description</label><textarea id="ee-desc" class="form-control">${description || ""}</textarea></div>`,
    async () => {
      const n = el("ee-name").value.trim();
      if (!n) return modalError("Name is required");
      try {
        await api.updateEnvironment(envId, {
          name: n, env_type: el("ee-type").value,
          order: parseInt(el("ee-order").value) || 0,
          description: el("ee-desc").value.trim() || null,
        });
        closeModal(); toast("Environment updated", "success");
        navigate("environments");
      } catch (e) { modalError(e.message); }
    }
  );
}

async function deleteEnv(envId, name) {
  if (!confirm(`Delete environment "${name}"? It will be detached from all products.`)) return;
  try {
    await api.deleteEnvironment(envId);
    toast("Environment deleted", "success");
    navigate("environments");
  } catch (e) { toast(e.message, "error"); }
}

async function showAttachEnv(productId) {
  const allEnvs = await api.getEnvironments().catch(() => []);
  const attached = await api.getProductEnvironments(productId).catch(() => []);
  const attachedIds = new Set(attached.map(e => e.id));
  const available = allEnvs.filter(e => !attachedIds.has(e.id));
  if (available.length === 0) {
    toast("All environments are already attached, or none exist. Create one first.", "info");
    return;
  }
  openModal("Attach Environment",
    `<div class="form-group"><label>Environment</label>
       <select id="ae-sel" class="form-control">
         ${available.map(e => `<option value="${e.id}">${e.name} (${e.env_type})</option>`).join("")}
       </select>
     </div>`,
    async () => {
      const envId = el("ae-sel").value;
      if (!envId) return;
      try {
        await api.attachEnvironment(productId, { environment_id: envId });
        closeModal(); toast("Environment attached", "success");
        navigate(`products/${productId}`);
      } catch (e) { modalError(e.message); }
    }, "Attach"
  );
}

async function detachEnv(productId, envId, name) {
  if (!confirm(`Detach environment "${name}" from this product?`)) return;
  try {
    await api.detachEnvironment(productId, envId);
    toast("Environment detached", "success");
    navigate(`products/${productId}`);
  } catch (e) { toast(e.message, "error"); }
}

function showEditApp(productId, appId, name, artifactType, repoUrl) {
  openModal("Edit Application",
    `<div class="form-group"><label>Name *</label><input id="ea-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Artifact Type</label><select id="ea-type" class="form-control">
       <option value="container"${artifactType==="container"?" selected":""}>Container</option>
       <option value="library"${artifactType==="library"?" selected":""}>Library</option>
       <option value="package"${artifactType==="package"?" selected":""}>Package</option>
     </select></div>
     <div class="form-group"><label>Repository URL</label><input id="ea-repo" class="form-control" value="${repoUrl}"></div>`,
    async () => {
      const n = el("ea-name").value.trim();
      if (!n) return modalError("Name is required");
      try {
        await api.updateApplication(productId, appId, {
          name: n, artifact_type: el("ea-type").value,
          repository_url: el("ea-repo").value.trim() || null,
        });
        closeModal(); toast("Application updated", "success");
        navigate(`products/${productId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

async function deleteApp(productId, appId, name) {
  if (!confirm(`Delete application "${name}"?`)) return;
  try {
    await api.deleteApplication(productId, appId);
    toast("Application deleted", "success");
    navigate(`products/${productId}`);
  } catch (e) { toast(e.message, "error"); }
}

async function showCreatePipeline(productId) {
  const apps = await api.getApplications(productId).catch(() => []);
  if (!apps.length) {
    return openModal("No Applications",
      `<p>Create an application first — pipelines must belong to an application.</p>`,
      () => { closeModal(); navigate(`products/${productId}`); document.querySelector('[onclick*="tab-apps"]')?.click(); },
      "Go to Applications"
    );
  }
  const appSelect = `<div class="form-group"><label>Application *</label>
    <select id="plf-app" class="form-control">
      <option value="">— Select application —</option>
      ${apps.map(a => `<option value="${a.id}">${a.name}</option>`).join("")}
    </select></div>`;
  _showCreatePipelineModal(productId, null, appSelect);
}

function showCreatePipelineForApp(productId, applicationId) {
  _showCreatePipelineModal(productId, applicationId, "");
}

async function _showCreatePipelineModal(productId, applicationId, extraFieldsHtml) {
  // Fetch pipelines + templates for the "copy from" search
  const [allPipelines, templates] = await Promise.all([
    request("GET", "/products").then(products =>
      Promise.all(products.map(p => request("GET", `/products/${p.id}/pipelines`).catch(() => [])))
    ).then(lists => lists.flat()).catch(() => []),
    request("GET", "/pipeline-templates").catch(() => []),
  ]);

  openModal("New Pipeline", `
    ${extraFieldsHtml}
    <div class="form-group"><label>Name *</label><input id="plf-name" class="form-control" placeholder="e.g. API CI Pipeline"></div>
    <div class="form-group"><label>Kind</label>
      <select id="plf-kind" class="form-control"><option value="ci">CI</option><option value="cd">CD</option></select>
    </div>
    <div class="form-group"><label>Git Repository</label><input id="plf-repo" class="form-control" placeholder="git@github.com:org/repo.git"></div>
    <div class="form-group"><label>Branch</label><input id="plf-branch" class="form-control" value="main"></div>

    <!-- Copy source selector -->
    <div style="border-top:1px solid var(--gray-200);margin:16px 0 12px;padding-top:12px">
      <div style="font-weight:600;font-size:13px;margin-bottom:10px">Start from</div>
      <div style="display:flex;gap:8px;margin-bottom:12px" id="plf-mode-btns">
        <button type="button" id="plf-mode-scratch" class="btn btn-primary btn-sm"
          onclick="_setPipelineMode('scratch')" style="flex:1">✨ Scratch</button>
        <button type="button" id="plf-mode-copy" class="btn btn-secondary btn-sm"
          onclick="_setPipelineMode('copy')" style="flex:1">📋 Copy from…</button>
      </div>
      <div id="plf-copy-section" style="display:none">
        <input id="plf-copy-search" class="form-control" placeholder="Search pipelines and templates…"
          oninput="_filterCopySources()" style="margin-bottom:8px">
        <div id="plf-copy-list" style="max-height:180px;overflow-y:auto;border:1px solid var(--gray-200);border-radius:8px;padding:4px">
          ${_renderCopySourceList(allPipelines, templates, "")}
        </div>
        <input type="hidden" id="plf-copy-id">
        <input type="hidden" id="plf-copy-type">
      </div>
    </div>
  `, async () => {
    const name = el("plf-name").value.trim();
    const appId = applicationId || (el("plf-app") ? el("plf-app").value : "");
    if (!name) return modalError("Name is required");
    if (extraFieldsHtml && !appId) return modalError("Application is required");

    const mode = el("plf-mode-scratch")?.classList.contains("btn-primary") ? "scratch" : "copy";
    const copyId = el("plf-copy-id")?.value;
    const copyType = el("plf-copy-type")?.value;

    try {
      if (mode === "copy" && copyId) {
        if (copyType === "template") {
          await request("POST", `/pipeline-templates/${copyId}/create-pipeline`, {
            product_id: productId,
            application_id: appId || null,
            name,
            kind: el("plf-kind").value,
            git_repo: el("plf-repo").value.trim() || null,
            git_branch: el("plf-branch").value.trim() || "main",
          });
        } else {
          // copy from existing pipeline — find its product_id
          const srcPipeline = allPipelines.find(p => p.id === copyId);
          const srcProductId = srcPipeline?.product_id || productId;
          await request("POST", `/products/${srcProductId}/pipelines/${copyId}/copy`, {
            product_id: productId,
            application_id: appId || null,
            name,
            git_repo: el("plf-repo").value.trim() || null,
            git_branch: el("plf-branch").value.trim() || "main",
          });
        }
      } else {
        await api.createPipeline(productId, {
          name,
          application_id: appId || null,
          kind: el("plf-kind").value,
          git_repo: el("plf-repo").value.trim() || null,
          git_branch: el("plf-branch").value.trim() || "main",
        });
      }
      closeModal();
      toast("Pipeline created", "success");
      navigate(`products/${productId}`);
    } catch (e) { modalError(e.message); }
  });

  // Store copy sources for filtering
  window._plCopySources = { pipelines: allPipelines, templates };
}

function _setPipelineMode(mode) {
  const scratchBtn = el("plf-mode-scratch");
  const copyBtn    = el("plf-mode-copy");
  const copySection = el("plf-copy-section");
  if (!scratchBtn) return;
  if (mode === "scratch") {
    scratchBtn.className = "btn btn-primary btn-sm";
    copyBtn.className    = "btn btn-secondary btn-sm";
    copySection.style.display = "none";
  } else {
    scratchBtn.className = "btn btn-secondary btn-sm";
    copyBtn.className    = "btn btn-primary btn-sm";
    copySection.style.display = "block";
  }
}

function _filterCopySources() {
  const q = (el("plf-copy-search")?.value || "").toLowerCase();
  const { pipelines, templates } = window._plCopySources || { pipelines: [], templates: [] };
  el("plf-copy-list").innerHTML = _renderCopySourceList(pipelines, templates, q);
}

function _renderCopySourceList(pipelines, templates, q) {
  const items = [];

  for (const t of templates) {
    const label = `${t.name}`;
    const sub = `Template · ${t.kind?.toUpperCase() || "CI"} · ${t.stage_count ?? 0} stage(s)`;
    if (!q || label.toLowerCase().includes(q) || sub.toLowerCase().includes(q)) {
      items.push({ id: t.id, type: "template", label, sub, icon: "🗂️" });
    }
  }
  for (const p of pipelines) {
    const label = p.name;
    const sub = `Pipeline · ${p.kind?.toUpperCase() || "CI"}`;
    if (!q || label.toLowerCase().includes(q) || sub.toLowerCase().includes(q)) {
      items.push({ id: p.id, type: "pipeline", label, sub, icon: "⚙️" });
    }
  }

  if (!items.length) return `<div style="padding:12px;text-align:center;color:var(--gray-400);font-size:13px">No matches</div>`;

  return items.map(item => `
    <div class="copy-source-item" onclick="_selectCopySource('${item.id}','${item.type}',this)"
      style="padding:8px 10px;cursor:pointer;border-radius:6px;display:flex;align-items:center;gap:10px">
      <span style="font-size:18px">${item.icon}</span>
      <div>
        <div style="font-weight:600;font-size:13px">${item.label}</div>
        <div style="font-size:11px;color:var(--gray-500)">${item.sub}</div>
      </div>
    </div>`).join("");
}

function _selectCopySource(id, type, el_) {
  // Deselect all, select clicked
  document.querySelectorAll(".copy-source-item").forEach(el => {
    el.style.background = "";
    el.style.outline = "";
  });
  el_.style.background = "var(--primary-light)";
  el_.style.outline = "2px solid var(--primary)";
  document.getElementById("plf-copy-id").value = id;
  document.getElementById("plf-copy-type").value = type;
}

function showCreateRelease(productId) {
  openModal("New Release",
    `<div class="form-group"><label>Name *</label><input id="rf-name" class="form-control" placeholder="e.g. February 2026 Release"></div>
     <div class="form-group"><label>Version</label><input id="rf-ver" class="form-control" placeholder="e.g. 2026.02"></div>
     <div class="form-group"><label>Description</label><textarea id="rf-desc" class="form-control"></textarea></div>`,
    async () => {
      const name = el("rf-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        const r = await api.createRelease(productId, {
          name, version: el("rf-ver").value.trim() || null,
          description: el("rf-desc").value.trim() || null,
        });
        closeModal(); toast("Release created", "success");
        navigate(`products/${productId}/releases/${r.id}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

function showCreateEnv() {
  openModal("New Environment",
    `<div class="form-group"><label>Name *</label><input id="ef-name" class="form-control" placeholder="e.g. Production"></div>
     <div class="form-group"><label>Type</label><select id="ef-type" class="form-control">
       <option value="dev">dev</option><option value="qa">qa</option><option value="staging">staging</option><option value="prod">prod</option><option value="custom">custom</option>
     </select></div>
     <div class="form-group"><label>Order</label><input id="ef-order" class="form-control" type="number" value="0"></div>
     <div class="form-group"><label>Description</label><textarea id="ef-desc" class="form-control" placeholder="Optional"></textarea></div>`,
    async () => {
      const name = el("ef-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        await api.createEnvironment({ name, env_type: el("ef-type").value, order: parseInt(el("ef-order").value)||0, description: el("ef-desc").value.trim()||null });
        closeModal(); toast("Environment created", "success");
        navigate("environments");
      } catch (e) { modalError(e.message); }
    }
  );
}

function showCreateApp(productId) {
  openModal("New Application",
    `<div class="form-group"><label>Name *</label><input id="af-name" class="form-control" placeholder="e.g. API Service"></div>
     <div class="form-group"><label>Artifact Type</label><select id="af-type" class="form-control">
       <option value="container">Container</option><option value="library">Library</option><option value="package">Package</option>
     </select></div>
     <div class="form-group"><label>Repository URL</label><input id="af-repo" class="form-control" placeholder="Optional"></div>`,
    async () => {
      const name = el("af-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        await api.createApplication(productId, { name, artifact_type: el("af-type").value, repository_url: el("af-repo").value.trim()||null });
        closeModal(); toast("Application created", "success");
        navigate(`products/${productId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

function showScoreModal(productId, pipelineId, pipelineName) {
  openModal(`Compliance Score — ${pipelineName}`,
    `<div class="alert alert-info" style="margin-bottom:16px">Score = Mandatory×60% + Best Practice×20% + Runtime×15% + Metadata×5%</div>
     <div class="form-group"><label>Mandatory Controls (%)</label><input id="sc-mandatory" class="form-control" type="number" min="0" max="100" value="100"></div>
     <div class="form-group"><label>Best Practice (%)</label><input id="sc-bp" class="form-control" type="number" min="0" max="100" value="0"></div>
     <div class="form-group"><label>Runtime Behavior (%)</label><input id="sc-runtime" class="form-control" type="number" min="0" max="100" value="0"></div>
     <div class="form-group"><label>Metadata Completeness (%)</label><input id="sc-meta" class="form-control" type="number" min="0" max="100" value="0"></div>`,
    async () => {
      try {
        const res = await api.updateCompliance(productId, pipelineId, {
          mandatory_pct: parseFloat(el("sc-mandatory").value)||0,
          best_practice_pct: parseFloat(el("sc-bp").value)||0,
          runtime_pct: parseFloat(el("sc-runtime").value)||0,
          metadata_pct: parseFloat(el("sc-meta").value)||0,
        });
        closeModal();
        toast(`Rating updated: ${res.compliance_rating} (${res.compliance_score}%)`, "success");
        navigate(`products/${productId}`);
      } catch (e) { modalError(e.message); }
    },
    "Calculate"
  );
}

// ── Pipeline context tabs ──────────────────────────────────────────────────
function pipelineContextTabs(productId, pipelineId, activeTab) {
  const tabs = [
    { id: "definition",  label: "📋 Definition",  hash: `products/${productId}/pipelines/${pipelineId}` },
    { id: "runs",        label: "▶ Runs",          hash: `products/${productId}/pipelines/${pipelineId}/runs` },
    { id: "properties",  label: "🔧 Properties",   hash: `products/${productId}/pipelines/${pipelineId}/properties` },
    { id: "webhooks",    label: "🔗 Webhooks",     hash: `products/${productId}/pipelines/${pipelineId}/webhooks` },
  ];
  return `<div style="display:flex;gap:0;border-bottom:2px solid var(--gray-200);margin-bottom:20px">
    ${tabs.map(t => `<button
      class="btn" style="border:none;border-bottom:${t.id===activeTab?"2px solid var(--brand)":"2px solid transparent"};border-radius:0;padding:10px 18px;font-size:13px;font-weight:${t.id===activeTab?"600":"400"};color:${t.id===activeTab?"var(--brand)":"var(--gray-600)"};background:none;cursor:pointer;margin-bottom:-2px"
      onclick="navigate('${t.hash}')">${t.label}</button>`).join("")}
  </div>`;
}

// ── Pipeline detail ────────────────────────────────────────────────────────
let _pipelineVisualStages = [];
let _plEditorProductId = null;
let _plEditorPipelineId = null;
let _plYamlDebounce = null;

router.register("products/:pid/pipelines/:id", async (hash, parts) => {
  const [,productId,,pipelineId] = parts;
  _plEditorProductId = productId;
  _plEditorPipelineId = pipelineId;
  setContent(loading());
  const [product, pipeline] = await Promise.all([
    api.getProduct(productId),
    api.getPipeline(productId, pipelineId),
  ]);
  setBreadcrumb(
    { label: "Products", hash: "products" },
    { label: product.name, hash: `products/${productId}` },
    { label: pipeline.name }
  );
  const stages = pipeline.stages || [];
  _pipelineVisualStages = stages;

  const stagesHtml = stages.length === 0
    ? `<div class="empty-state"><div class="empty-icon">📋</div><p>No stages yet. Add your first stage to get started.</p></div>`
    : stages.map((s, idx) => { const _ac = s.accent_color || STAGE_GRADIENTS[idx % STAGE_GRADIENTS.length].color; return `
      <div id="stage-block-${s.id}" class="stage-block" data-stage-name="${s.name.replace(/"/g,"&quot;")}" draggable="true"
        ondragstart="stageDragStart(event,'${s.id}')"
        ondragover="stageDragOver(event)"
        ondrop="stageDrop(event,'${s.id}','${productId}','${pipelineId}')"
        style="border:1px solid var(--gray-200);border-left:4px solid ${_ac};border-radius:8px;margin-bottom:10px;background:#fff">
        <div style="display:flex;align-items:center;gap:8px;padding:10px 12px;cursor:pointer;user-select:none"
          onclick="toggleStageBlock('${s.id}')">
          <span style="color:var(--gray-400);cursor:grab;font-size:16px" title="Drag to reorder">⠿</span>
          <span id="stage-arrow-${s.id}" style="font-size:12px;color:var(--gray-500);transition:transform .15s">▼</span>
          <strong style="font-size:14px;flex:1">#${s.order} ${s.name}</strong>
          ${s.container_image ? `<code style="font-size:11px;color:var(--gray-500)">${s.container_image}</code>` : ""}
          ${s.is_protected ? `<span class="badge badge-blue">🔒</span>` : ""}
          <div onclick="event.stopPropagation()">
            ${pageMenu("stg-"+s.id, [
              {label: "＋ Add Task", onclick: `showCreateTask('${productId}','${pipelineId}','${s.id}')`},
              {label: "✏ Edit Stage", onclick: `showEditStage('${productId}','${pipelineId}','${s.id}','${s.name.replace(/'/g,"\\'")}','${s.run_language||"bash"}','${s.container_image||""}',${s.order},${s.is_protected},'${s.accent_color||""}')`},
              {label: "🎨 Change Color", onclick: `showStageColorPicker('${productId}','${pipelineId}','${s.id}','${s.name.replace(/'/g,"\\'")}','${s.accent_color||""}')`},
              {label: "📄 View YAML", onclick: `showStageYaml('${productId}','${pipelineId}','${s.id}','${s.name.replace(/'/g,"\\'")}')` },
              {divider: true},
              {label: "🗑 Delete Stage", onclick: `deleteStage('${productId}','${pipelineId}','${s.id}','${s.name.replace(/'/g,"\\'")}')`, danger: true},
            ])}
          </div>
        </div>
        <div id="stage-body-${s.id}" style="padding:0 12px 12px">
          ${(s.tasks||[]).length === 0
            ? `<div style="color:var(--gray-500);font-size:13px;padding:4px 0 2px">No tasks in this stage.</div>`
            : `<table style="margin:0;width:100%">
              <thead><tr><th style="width:28px"></th><th>#</th><th>Name</th><th>Type</th><th>Timeout</th><th>Required</th><th>Actions</th></tr></thead>
              <tbody id="task-tbody-${s.id}">${(s.tasks||[]).map(t => `
                <tr id="task-row-${t.id}" data-task-name="${t.name.replace(/"/g,"&quot;")}" draggable="true"
                  ondragstart="taskDragStart(event,'${t.id}','${s.id}')"
                  ondragover="taskDragOver(event)"
                  ondrop="taskDrop(event,'${t.id}','${s.id}','${productId}','${pipelineId}')">
                  <td style="color:var(--gray-400);cursor:grab;font-size:14px;text-align:center">⠿</td>
                  <td style="color:var(--gray-400)">${t.order}</td>
                  <td><strong>${t.name}</strong>${t.description ? `<br><small style="color:var(--gray-500)">${t.description}</small>` : ""}</td>
                  <td>${_taskTypeBadges(t.task_type)}</td>
                  <td>${t.timeout}s</td>
                  <td>${t.is_required ? '<span class="badge badge-success">Yes</span>' : '<span class="badge badge-silver">No</span>'}</td>
                  <td>
                    ${pageMenu("tsk-"+t.id, [
                      {label: "▶ Run Now", onclick: `runTaskNow('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}')` },
                      {label: "✏ Edit Settings", onclick: `showEditTask('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}','${(t.description||"").replace(/'/g,"\\'")}',${t.order},'${t.on_error||"fail"}',${t.timeout},${t.is_required},'${(t.task_type||"").replace(/'/g,"\\'")}')` },
                      {label: "📝 Edit Script", onclick: `showEditTaskScript('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}')` },
                      {label: "📄 View YAML", onclick: `showTaskYaml('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}')` },
                      {divider: true},
                      {label: "🗑 Delete Task", onclick: `deleteTask('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}')`, danger: true},
                    ])}
                  </td>
                </tr>`).join("")}
              </tbody></table>`
          }
        </div>
      </div>`; }).join("");

  setContent(`
    <div class="page-header">
      <div>
        <h1>${pipeline.name}</h1>
        <div class="sub">
          <span class="badge badge-${pipeline.kind}">${pipeline.kind.toUpperCase()}</span>
          ${pipeline.git_repo ? `<code style="font-size:12px;margin-left:8px">${pipeline.git_repo} @ ${pipeline.git_branch}</code>` : ""}
        </div>
      </div>
      <div style="display:flex;gap:6px;align-items:center">
        <button class="btn btn-primary btn-sm" onclick="showCreateRun('${pipelineId}','${productId}')">▶ Run</button>
        ${pageMenu("pl-"+pipelineId, [
          {label: "⇅ Git Sync", onclick: `showGitSyncModal('${productId}','${pipelineId}','${pipeline.git_repo||""}','${pipeline.name.replace(/'/g,"\\'")}')` },
          {label: "✎ Edit YAML", onclick: `togglePipelineMode('yaml','${productId}','${pipelineId}')`},
          {label: "⬇ Download YAML", onclick: `exportYaml('/api/v1/products/${productId}/pipelines/${pipelineId}/export','${pipeline.name.replace(/'/g,"\\'")}pipeline.yaml')`},
          {label: "⬆ Import YAML", onclick: `showImportYaml('${productId}','${pipelineId}')`},
        ])}
      </div>
    </div>

    ${pipelineContextTabs(productId, pipelineId, "definition")}

    <!-- Normal mode -->
    <div id="pl-normal-mode">

      <!-- Visual graph at the top — click stage/task to scroll to editor -->
      <div class="card" style="margin-bottom:16px">
        <div class="card-header">
          <h2>Pipeline Flow</h2>
          <span style="font-size:12px;color:var(--gray-400)">Click a stage or task to jump to its editor below</span>
        </div>
        <div style="overflow-x:auto;min-height:${stages.length ? "160px" : "60px"};background:var(--gray-50);border-radius:6px;padding:12px">
          <svg id="pipeline-visual-svg-normal" style="display:block"></svg>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <div class="card-header"><h2>Details</h2></div>
        <div class="detail-grid">
          <div class="detail-row"><span class="detail-label">ID</span><code style="font-size:12px">${pipeline.id}</code></div>
          <div class="detail-row"><span class="detail-label">Kind</span><span class="detail-value">${pipeline.kind.toUpperCase()}</span></div>
          <div class="detail-row"><span class="detail-label">Branch</span><span class="detail-value">${pipeline.git_branch||"main"}</span></div>
          <div class="detail-row"><span class="detail-label">SHA</span><span class="detail-value">${pipeline.definition_sha||"—"}</span></div>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px" id="stages-editor-card">
        <div class="card-header">
          <h2>Stages (${stages.length})</h2>
          <button class="btn btn-primary btn-sm" onclick="showCreateStage('${productId}','${pipelineId}')">+ New Stage</button>
        </div>
        ${stagesHtml}
      </div>

    </div>

    <!-- Split-screen YAML + Visual mode -->
    <div id="pl-yaml-mode" style="display:none">
      <div style="display:flex;gap:0;height:calc(100vh - 180px);min-height:500px">
        <div style="flex:0 0 45%;display:flex;flex-direction:column;border:1px solid var(--gray-200);border-radius:8px 0 0 8px;overflow:hidden">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--gray-50);border-bottom:1px solid var(--gray-200)">
            <span style="font-size:12px;font-weight:600;color:var(--gray-600)">YAML Editor</span>
            <div style="display:flex;gap:6px">
              <button class="btn btn-secondary btn-sm" onclick="loadPipelineYaml('${productId}','${pipelineId}')">↺</button>
              <button class="btn btn-primary btn-sm" onclick="savePipelineYaml('${productId}','${pipelineId}')">💾 Save</button>
            </div>
          </div>
          <textarea id="pipeline-yaml-editor" spellcheck="false"
            oninput="onPipelineYamlInput()"
            style="flex:1;width:100%;font-family:monospace;font-size:13px;padding:12px;border:none;resize:none;background:#fff;color:var(--gray-800);line-height:1.5;outline:none"
            placeholder="Loading YAML…"></textarea>
          <div id="pipeline-yaml-status" style="padding:4px 12px;font-size:12px;background:var(--gray-50);border-top:1px solid var(--gray-200)"></div>
        </div>
        <div style="flex:1;display:flex;flex-direction:column;border:1px solid var(--gray-200);border-left:none;border-radius:0 8px 8px 0;overflow:hidden">
          <div style="padding:8px 12px;background:var(--gray-50);border-bottom:1px solid var(--gray-200)">
            <span style="font-size:12px;font-weight:600;color:var(--gray-600)">Visual Preview</span>
          </div>
          <div style="flex:1;overflow:auto;padding:12px;background:#f8fafc">
            <svg id="pipeline-visual-svg-yaml" style="display:block"></svg>
          </div>
        </div>
      </div>
      <div style="margin-top:8px;display:flex;gap:8px">
        <button class="btn btn-secondary btn-sm" onclick="togglePipelineMode('normal','${productId}','${pipelineId}')">← Back to Normal View</button>
      </div>
    </div>

  `);

  // Render visual at top of normal mode immediately
  renderPipelineVisual(pipelineId, "pipeline-visual-svg-normal");
  // Auto-load YAML (populates textarea for split-screen mode when switched)
  loadPipelineYaml(productId, pipelineId);
});

function togglePipelineMode(mode, productId, pipelineId) {
  const normal = document.getElementById("pl-normal-mode");
  const yaml = document.getElementById("pl-yaml-mode");
  if (!normal) return;
  normal.style.display = mode === "normal" ? "" : "none";
  yaml.style.display = mode === "yaml" ? "" : "none";
  const ddBtn = document.getElementById("yaml-dd-btn");
  if (ddBtn) {
    ddBtn.classList.toggle("btn-primary", mode === "yaml");
    ddBtn.classList.toggle("btn-secondary", mode !== "yaml");
  }
  if (mode === "yaml") {
    renderPipelineVisual(pipelineId, "pipeline-visual-svg-yaml");
  }
}

function toggleYamlDropdown() {
  const menu = document.getElementById("yaml-dd-menu");
  if (!menu) return;
  menu.style.display = menu.style.display === "none" ? "" : "none";
  // Close on outside click
  if (menu.style.display !== "none") {
    setTimeout(() => {
      function closeDD(e) {
        const wrap = document.getElementById("yaml-dd-wrap");
        if (wrap && !wrap.contains(e.target)) {
          menu.style.display = "none";
          document.removeEventListener("click", closeDD);
        }
      }
      document.addEventListener("click", closeDD);
    }, 0);
  }
}

function onPipelineYamlInput() {
  clearTimeout(_plYamlDebounce);
  _plYamlDebounce = setTimeout(() => {
    renderPipelineVisual(_plEditorPipelineId, "pipeline-visual-svg-yaml");
  }, 800);
}

function toggleStageBlock(stageId) {
  const body = document.getElementById("stage-body-" + stageId);
  const arrow = document.getElementById("stage-arrow-" + stageId);
  if (!body) return;
  const collapsed = body.style.display === "none";
  body.style.display = collapsed ? "" : "none";
  if (arrow) arrow.style.transform = collapsed ? "" : "rotate(-90deg)";
}

// ── Drag-and-drop: Stages ─────────────────────────────────────────────────
let _dragStageId = null;

function stageDragStart(event, stageId) {
  _dragStageId = stageId;
  event.dataTransfer.effectAllowed = "move";
}

function stageDragOver(event) {
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
}

async function stageDrop(event, targetStageId, productId, pipelineId) {
  event.preventDefault();
  if (!_dragStageId || _dragStageId === targetStageId) return;
  const dragEl = document.getElementById("stage-block-" + _dragStageId);
  const targetEl = document.getElementById("stage-block-" + targetStageId);
  if (!dragEl || !targetEl) return;
  const parent = targetEl.parentNode;
  const children = [...parent.children];
  const dragIdx = children.indexOf(dragEl);
  const targetIdx = children.indexOf(targetEl);
  if (dragIdx < targetIdx) {
    parent.insertBefore(dragEl, targetEl.nextSibling);
  } else {
    parent.insertBefore(dragEl, targetEl);
  }
  // Persist new order
  const newOrder = [...parent.children].map((el, i) => ({ id: el.id.replace("stage-block-", ""), order: i + 1 }));
  try {
    for (const { id, order } of newOrder) {
      const stage = _pipelineVisualStages.find(s => s.id === id);
      if (stage && stage.order !== order) {
        await api.updateStage(productId, pipelineId, id, { order });
      }
    }
    _pipelineVisualStages = _pipelineVisualStages.map(s => {
      const found = newOrder.find(n => n.id === s.id);
      return found ? { ...s, order: found.order } : s;
    });
  } catch (e) { toast("Failed to reorder stages: " + e.message, "error"); }
  _dragStageId = null;
}

// ── Drag-and-drop: Tasks ──────────────────────────────────────────────────
let _dragTaskId = null;
let _dragTaskStageId = null;

function taskDragStart(event, taskId, stageId) {
  _dragTaskId = taskId;
  _dragTaskStageId = stageId;
  event.dataTransfer.effectAllowed = "move";
  event.stopPropagation();
}

function taskDragOver(event) {
  event.preventDefault();
  event.stopPropagation();
  event.dataTransfer.dropEffect = "move";
}

async function taskDrop(event, targetTaskId, stageId, productId, pipelineId) {
  event.preventDefault();
  event.stopPropagation();
  if (!_dragTaskId || _dragTaskId === targetTaskId || _dragTaskStageId !== stageId) return;
  const dragEl = document.getElementById("task-row-" + _dragTaskId);
  const targetEl = document.getElementById("task-row-" + targetTaskId);
  if (!dragEl || !targetEl) return;
  const tbody = targetEl.parentNode;
  const rows = [...tbody.children];
  const dragIdx = rows.indexOf(dragEl);
  const targetIdx = rows.indexOf(targetEl);
  if (dragIdx < targetIdx) {
    tbody.insertBefore(dragEl, targetEl.nextSibling);
  } else {
    tbody.insertBefore(dragEl, targetEl);
  }
  // Persist new order
  const newOrder = [...tbody.children].map((tr, i) => ({ id: tr.id.replace("task-row-", ""), order: i + 1 }));
  try {
    for (const { id, order } of newOrder) {
      const stage = _pipelineVisualStages.find(s => s.id === stageId);
      const task = stage && (stage.tasks||[]).find(t => t.id === id);
      if (task && task.order !== order) {
        await api.updateTask(productId, pipelineId, stageId, id, { order });
      }
    }
  } catch (e) { toast("Failed to reorder tasks: " + e.message, "error"); }
  _dragTaskId = null;
  _dragTaskStageId = null;
}

// ── Stage YAML modal ──────────────────────────────────────────────────────
async function showStageYaml(productId, pipelineId, stageId, stageName) {
  openModal(`Stage YAML — ${stageName}`,
    `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
       <span style="font-size:12px;color:var(--gray-500)">Edit stage definition. Click Save to apply.</span>
     </div>
     <textarea id="stage-yaml-ta" spellcheck="false"
       style="width:100%;min-height:340px;font-family:monospace;font-size:12px;padding:10px;border:1px solid var(--gray-200);border-radius:6px;background:var(--gray-50);resize:vertical;line-height:1.5">
# Loading…
     </textarea>
     <div id="stage-yaml-status" style="margin-top:6px;font-size:12px"></div>`,
    async () => {
      const ta = document.getElementById("stage-yaml-ta");
      const st = document.getElementById("stage-yaml-status");
      if (!ta || !ta.value.trim() || ta.value.startsWith("# Loading")) return;
      try {
        const pipeline = await api.getPipeline(productId, pipelineId);
        const stage = (pipeline.stages||[]).find(s => s.id === stageId);
        if (!stage) throw new Error("Stage not found");
        // Parse updated YAML fields (name, run_language, container_image, order, is_protected)
        const yamlText = ta.value;
        const lines = yamlText.split("\n");
        const parsed = {};
        for (const line of lines) {
          const m = line.match(/^(\w+):\s*(.+)$/);
          if (m) parsed[m[1]] = m[2].replace(/^['"]|['"]$/g, "");
        }
        const payload = {};
        if (parsed.name) payload.name = parsed.name;
        if (parsed.run_language) payload.run_language = parsed.run_language;
        if (parsed.container_image) payload.container_image = parsed.container_image;
        if (parsed.order) payload.order = parseInt(parsed.order);
        if (parsed.is_protected !== undefined) payload.is_protected = parsed.is_protected === "true";
        await api.updateStage(productId, pipelineId, stageId, payload);
        if (st) st.innerHTML = `<span style="color:var(--success)">✓ Saved</span>`;
        toast("Stage updated", "success");
        navigate(router.current);
      } catch (e) {
        if (st) st.innerHTML = `<span style="color:var(--danger)">✗ ${e.message}</span>`;
        throw e;
      }
    },
    "Save"
  );
  // Load current stage as YAML
  setTimeout(async () => {
    const ta = document.getElementById("stage-yaml-ta");
    if (!ta) return;
    try {
      const pipeline = await api.getPipeline(productId, pipelineId);
      const stage = (pipeline.stages||[]).find(s => s.id === stageId);
      if (!stage) { ta.value = "# Stage not found"; return; }
      ta.value = `name: ${stage.name}\norder: ${stage.order}\nrun_language: ${stage.run_language||"bash"}\ncontainer_image: ${stage.container_image||""}\nis_protected: ${stage.is_protected||false}\n`;
    } catch (e) { ta.value = "# Error: " + e.message; }
  }, 50);
}

// ── Task YAML modal ───────────────────────────────────────────────────────
async function showTaskYaml(productId, pipelineId, stageId, taskId, taskName) {
  openModal(`Task YAML — ${taskName}`,
    `<textarea id="task-yaml-ta" spellcheck="false"
       style="width:100%;min-height:380px;font-family:monospace;font-size:12px;padding:10px;border:1px solid var(--gray-200);border-radius:6px;background:var(--gray-50);resize:vertical;line-height:1.5">
# Loading…
     </textarea>
     <div id="task-yaml-status" style="margin-top:6px;font-size:12px"></div>`,
    async () => {
      const ta = document.getElementById("task-yaml-ta");
      const st = document.getElementById("task-yaml-status");
      if (!ta || ta.value.startsWith("# Loading")) return;
      try {
        const lines = ta.value.split("\n");
        const parsed = {};
        let inCode = false;
        let codeLines = [];
        for (const line of lines) {
          if (line.startsWith("run_code: |")) { inCode = true; continue; }
          if (inCode) {
            if (line.startsWith("  ")) { codeLines.push(line.slice(2)); continue; }
            else { inCode = false; }
          }
          const m = line.match(/^(\w+):\s*(.+)$/);
          if (m) parsed[m[1]] = m[2].replace(/^['"]|['"]$/g, "");
        }
        const payload = {};
        if (parsed.name) payload.name = parsed.name;
        if (parsed.description !== undefined) payload.description = parsed.description;
        if (parsed.order) payload.order = parseInt(parsed.order);
        if (parsed.timeout) payload.timeout = parseInt(parsed.timeout);
        if (parsed.on_error) payload.on_error = parsed.on_error;
        if (parsed.run_language) payload.run_language = parsed.run_language;
        if (parsed.task_type) payload.task_type = parsed.task_type;
        if (parsed.is_required !== undefined) payload.is_required = parsed.is_required === "true";
        if (codeLines.length) payload.run_code = codeLines.join("\n");
        await api.updateTask(productId, pipelineId, stageId, taskId, payload);
        if (st) st.innerHTML = `<span style="color:var(--success)">✓ Saved</span>`;
        toast("Task updated", "success");
        navigate(router.current);
      } catch (e) {
        if (st) st.innerHTML = `<span style="color:var(--danger)">✗ ${e.message}</span>`;
        throw e;
      }
    },
    "Save"
  );
  setTimeout(async () => {
    const ta = document.getElementById("task-yaml-ta");
    if (!ta) return;
    try {
      const pipeline = await api.getPipeline(productId, pipelineId);
      const stage = (pipeline.stages||[]).find(s => s.id === stageId);
      const task = stage && (stage.tasks||[]).find(t => t.id === taskId);
      if (!task) { ta.value = "# Task not found"; return; }
      const code = (task.run_code||"").split("\n").map(l => "  " + l).join("\n");
      ta.value = `name: ${task.name}\norder: ${task.order}\ntask_type: ${task.task_type}\nrun_language: ${task.run_language||"bash"}\ntimeout: ${task.timeout||60}\non_error: ${task.on_error||"fail"}\nis_required: ${task.is_required||false}\ndescription: ${task.description||""}\nrun_code: |\n${code}\n`;
    } catch (e) { ta.value = "# Error: " + e.message; }
  }, 50);
}

// ── Git Sync modal ────────────────────────────────────────────────────────
function showGitSyncModal(productId, pipelineId, gitRepo, pipelineName) {
  openModal("Git Sync",
    `<div style="margin-bottom:16px">
       <div style="font-size:13px;color:var(--gray-500);margin-bottom:12px">Repo: <code>${gitRepo||"(not configured)"}</code></div>
       <div style="display:flex;gap:12px;flex-direction:column">
         <div style="border:1px solid var(--gray-200);border-radius:8px;padding:14px">
           <h4 style="margin:0 0 6px">Pull from Git</h4>
           <p style="font-size:12px;color:var(--gray-500);margin:0 0 10px">Clone repo, read <code>conduit/${pipelineName}.yaml</code>, apply to database.</p>
           <button class="btn btn-primary btn-sm" onclick="gitPullPipeline('${productId}','${pipelineId}')">⬇ Pull &amp; Apply</button>
           <div id="git-pull-status" style="margin-top:8px;font-size:12px"></div>
         </div>
         <div style="border:1px solid var(--gray-200);border-radius:8px;padding:14px">
           <h4 style="margin:0 0 6px">Push to Git</h4>
           <div class="form-group" style="margin-bottom:8px">
             <label style="font-size:12px">Author name</label>
             <input id="git-author-name" class="form-control" style="margin-top:4px" value="${_currentUser ? (_currentUser.display_name||_currentUser.username) : 'Conduit'}">
           </div>
           <div class="form-group" style="margin-bottom:10px">
             <label style="font-size:12px">Author email</label>
             <input id="git-author-email" class="form-control" style="margin-top:4px" value="${_currentUser ? (_currentUser.email||'rw@conduit.local') : 'rw@conduit.local'}">
           </div>
           <button class="btn btn-primary btn-sm" onclick="gitPushPipeline('${productId}','${pipelineId}')">⬆ Push to Git</button>
           <div id="git-push-status" style="margin-top:8px;font-size:12px"></div>
         </div>
       </div>
     </div>`,
    null, null
  );
}

function showCreateRun(pipelineId, productId) {
  openModal("Run Pipeline",
    `<div class="form-group"><label>Commit SHA</label><input id="run-sha" class="form-control" placeholder="e.g. abc123def456"></div>
     <div class="form-group"><label>Artifact ID</label><input id="run-art" class="form-control" placeholder="e.g. api:1.0.45"></div>
     <div class="form-group"><label>Triggered By</label><input id="run-by" class="form-control" placeholder="username" value="user"></div>
     <div class="form-group">
       <label>Pipeline Runtime Properties <small style="color:var(--gray-400)">(JSON — accessible as pipelineRuntime.* in tasks)</small></label>
       <textarea id="run-props" class="form-control" rows="4" style="font-family:monospace;font-size:12px" placeholder='{"version":"1.0","env":"staging"}'>{}</textarea>
     </div>`,
    async () => {
      let props = {};
      try { props = JSON.parse(el("run-props").value || "{}"); } catch { return modalError("Runtime Properties must be valid JSON"); }
      try {
        const run = await api.createPipelineRun(pipelineId, {
          commit_sha: el("run-sha").value.trim()||null,
          artifact_id: el("run-art").value.trim()||null,
          triggered_by: el("run-by").value.trim()||"user",
          runtime_properties: props,
        });
        closeModal(); toast(`Run created: ${run.id}`, "success");
        navigate(`pipeline-runs/${run.id}`);
      } catch (e) { modalError(e.message); }
    },
    "Start Run"
  );
}

async function completeRun(runId, productId, pipelineId) {
  const status = confirm("Mark as Succeeded?") ? "Succeeded" : "Failed";
  try {
    await api.updatePipelineRun(runId, { status });
    toast(`Run marked as ${status}`, "success");
    navigate(`products/${productId}/pipelines/${pipelineId}`);
  } catch (e) { toast(e.message, "error"); }
}

// ── Pipeline sub-pages: Runs and Webhooks tabs ────────────────────────────
router.register("products/:pid/pipelines/:id/runs", async (hash, parts) => {
  const [,productId,,pipelineId] = parts;
  setContent(loading());
  const [product, pipeline, runs] = await Promise.all([
    api.getProduct(productId),
    api.getPipeline(productId, pipelineId),
    api.getPipelineRuns(pipelineId).catch(() => []),
  ]);
  setBreadcrumb(
    { label: "Products", hash: "products" },
    { label: product.name, hash: `products/${productId}` },
    { label: pipeline.name, hash: `products/${productId}/pipelines/${pipelineId}` },
    { label: "Runs" }
  );

  // unique triggered_by values for filter dropdown
  const triggeredBySet = [...new Set(runs.map(r => r.triggered_by).filter(Boolean))];

  setContent(`
    <div class="page-header">
      <div><h1>${pipeline.name}</h1><div class="sub">Pipeline Runs</div></div>
      <button class="btn btn-primary btn-sm" onclick="showCreateRun('${pipelineId}','${productId}')">▶ Run Pipeline</button>
    </div>
    ${pipelineContextTabs(productId, pipelineId, "runs")}


    <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
      <select id="filter-status" class="form-control" style="max-width:160px" onchange="filterRuns()">
        <option value="">All Statuses</option>
        <option value="Running">Running</option>
        <option value="Succeeded">Succeeded</option>
        <option value="Failed">Failed</option>
        <option value="Warning">Warning</option>
        <option value="Cancelled">Cancelled</option>
        <option value="Pending">Pending</option>
      </select>
      <select id="filter-triggered-by" class="form-control" style="max-width:200px" onchange="filterRuns()">
        <option value="">All Triggers</option>
        ${triggeredBySet.map(t => `<option value="${t}">${t}</option>`).join("")}
      </select>
      <input id="filter-date-from" type="date" class="form-control" style="max-width:160px" onchange="filterRuns()" placeholder="From date">
      <input id="filter-date-to" type="date" class="form-control" style="max-width:160px" onchange="filterRuns()" placeholder="To date">
      <button class="btn btn-secondary btn-sm" onclick="clearRunFilters()">Clear</button>
      <span id="filter-count" style="font-size:12px;color:var(--gray-500);margin-left:4px"></span>
    </div>

    <div class="card" id="runs-table-card">
      ${runs.length === 0
        ? `<div class="empty-state"><div class="empty-icon">▶</div><p>No runs yet.</p></div>`
        : `<div class="table-wrap"><table id="runs-table">
          <thead><tr><th>Run ID</th><th>Status</th><th>Progress</th><th>Commit</th><th>Artifact</th><th>Triggered By</th><th>Started</th><th>Duration</th></tr></thead>
          <tbody>${runs.map(r => `
            <tr data-status="${r.status||""}" data-triggered="${r.triggered_by||""}" data-started="${r.started_at||""}">
              <td><a href="#pipeline-runs/${r.id}" onclick="navigate('pipeline-runs/${r.id}');return false;"><code style="font-size:11.5px">${r.id}</code></a></td>
              <td>${statusBadge(r.status)}</td>
              <td>${completionBar(r.completion_percentage)}</td>
              <td><code style="font-size:11.5px">${(r.commit_sha||"").slice(0,8)||"—"}</code></td>
              <td>${r.artifact_id||"—"}</td>
              <td>${r.triggered_by||"—"}</td>
              <td style="color:var(--gray-400)">${fmtDate(r.started_at)}</td>
              <td style="color:var(--gray-400)">${fmtDuration(r.started_at, r.finished_at)}</td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>
  `);
});

function filterRuns() {
  const status = el("filter-status")?.value || "";
  const triggeredBy = el("filter-triggered-by")?.value || "";
  const dateFrom = el("filter-date-from")?.value || "";
  const dateTo = el("filter-date-to")?.value || "";
  const rows = document.querySelectorAll("#runs-table tbody tr");
  let shown = 0;
  rows.forEach(row => {
    const rowStatus = row.dataset.status;
    const rowTriggered = row.dataset.triggered;
    const rowStarted = (row.dataset.started || "").slice(0, 10);
    const matchStatus = !status || rowStatus === status;
    const matchTriggered = !triggeredBy || rowTriggered === triggeredBy;
    const matchFrom = !dateFrom || rowStarted >= dateFrom;
    const matchTo = !dateTo || rowStarted <= dateTo;
    const visible = matchStatus && matchTriggered && matchFrom && matchTo;
    row.style.display = visible ? "" : "none";
    if (visible) shown++;
  });
  const countEl = el("filter-count");
  if (countEl) countEl.textContent = `${shown} of ${rows.length} runs`;
}

function clearRunFilters() {
  const s = el("filter-status"); if (s) s.value = "";
  const t = el("filter-triggered-by"); if (t) t.value = "";
  const f = el("filter-date-from"); if (f) f.value = "";
  const d = el("filter-date-to"); if (d) d.value = "";
  filterRuns();
}

router.register("products/:pid/pipelines/:id/webhooks", async (hash, parts) => {
  const [,productId,,pipelineId] = parts;
  setContent(loading());
  const [product, pipeline, webhooks] = await Promise.all([
    api.getProduct(productId),
    api.getPipeline(productId, pipelineId),
    api.listWebhooks().then(all => all.filter(w => w.pipeline_id === pipelineId)).catch(() => []),
  ]);
  setBreadcrumb(
    { label: "Products", hash: "products" },
    { label: product.name, hash: `products/${productId}` },
    { label: pipeline.name, hash: `products/${productId}/pipelines/${pipelineId}` },
    { label: "Webhooks" }
  );
  setContent(`
    <div class="page-header">
      <div><h1>${pipeline.name}</h1><div class="sub">Inbound webhook triggers for this pipeline</div></div>
      <button class="btn btn-primary btn-sm" onclick="showCreateWebhookForPipeline('${pipelineId}')">+ Webhook</button>
    </div>
    ${pipelineContextTabs(productId, pipelineId, "webhooks")}
    ${webhooks.length === 0
      ? `<div class="card"><div class="empty-state"><div class="empty-icon">🔗</div><p>No webhooks for this pipeline yet.</p></div></div>`
      : `<div class="card"><div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Status</th><th>Created By</th><th>Trigger URL</th><th>Actions</th></tr></thead>
          <tbody>${webhooks.map(w => `
            <tr>
              <td><strong>${w.name}</strong>${w.description ? `<br><small style="color:var(--gray-500)">${w.description}</small>` : ""}</td>
              <td><span class="badge ${w.is_active?"badge-success":"badge-silver"}">${w.is_active?"Active":"Disabled"}</span></td>
              <td>${w.created_by}</td>
              <td><code style="font-size:10px">/api/v1/webhooks/${w.id}/trigger</code></td>
              <td>
                ${pageMenu("wh-"+w.id, [
                  {label: "⚡ Test", onclick: `showTestWebhook('${w.id}','${w.name.replace(/'/g,"\\'")}')` },
                  {label: "📬 Deliveries", onclick: `showWebhookDeliveries('${w.id}','${w.name.replace(/'/g,"\\'")}')` },
                  {label: w.is_active ? "⏸ Disable" : "▶ Enable", onclick: `toggleWebhook('${w.id}',${w.is_active})` },
                  {divider: true},
                  {label: "🗑 Delete", onclick: `deleteWebhookPl('${w.id}','${w.name.replace(/'/g,"\\'")}','${productId}','${pipelineId}')`, danger: true},
                ])}
              </td>
            </tr>`).join("")}
          </tbody></table></div></div>`
    }
    <div class="card" style="margin-top:16px;background:var(--gray-50)">
      <div style="padding:12px 16px;font-size:12px;color:var(--gray-600)">
        <strong>Trigger URL format:</strong>
        <pre style="background:#111;color:#e5e7eb;padding:10px;border-radius:6px;margin-top:6px;font-size:11px;overflow-x:auto">curl -X POST https://your-host/api/v1/webhooks/&lt;id&gt;/trigger \\
  -H "X-Webhook-Token: &lt;token&gt;" \\
  -d '{"commit_sha":"abc123","triggered_by":"ci"}'</pre>
      </div>
    </div>
  `);
});

// ── Pipeline Properties page ──────────────────────────────────────────────

router.register("products/:pid/pipelines/:id/properties", async (hash, parts) => {
  const [,productId,,pipelineId] = parts;
  setContent(loading());
  try {
  const [product, pipeline] = await Promise.all([
    api.getProduct(productId),
    api.getPipeline(productId, pipelineId),
  ]);
  const stages = pipeline.stages || [];
  setBreadcrumb(
    { label: "Products", hash: "products" },
    { label: product.name, hash: `products/${productId}` },
    { label: pipeline.name, hash: `products/${productId}/pipelines/${pipelineId}` },
    { label: "Properties" }
  );

  // Load all property sets in parallel — pipeline + all stages + all tasks
  const stageIds = (stages || []).map(s => s.id);
  const allTasks = (stages || []).flatMap(s => (s.tasks || []).map(t => ({ ...t, stageId: s.id })));
  const taskIds = allTasks.map(t => t.id);

  const [pipelineProps, ...restPropSets] = await Promise.all([
    api.listProperties("pipeline", pipelineId),
    ...stageIds.map(sid => api.listProperties("stage", sid)),
    ...taskIds.map(tid => api.listProperties("task", tid)),
  ]);

  const stagePropSets = restPropSets.slice(0, stageIds.length);
  const taskPropSets  = restPropSets.slice(stageIds.length);

  const stagePropsMap = {};
  stageIds.forEach((sid, i) => { stagePropsMap[sid] = stagePropSets[i] || []; });
  const taskPropsMap = {};
  taskIds.forEach((tid, i) => { taskPropsMap[tid] = taskPropSets[i] || []; });

  setContent(`
    <div class="page-header">
      <div><h1>${pipeline.name}</h1><div class="sub">Property hierarchy — pipeline, stage &amp; task level</div></div>
      <button class="btn btn-primary btn-sm" onclick="showAddProperty('pipeline','${pipelineId}',null,null)">＋ Add Pipeline Property</button>
    </div>
    ${pipelineContextTabs(productId, pipelineId, "properties")}

    <div class="card" style="margin-bottom:16px">
      <div class="card-header">
        <h2>Pipeline Properties</h2>
        <span style="font-size:12px;color:var(--gray-400)">Inherited by all stages and tasks in this pipeline</span>
      </div>
      ${_renderPropertiesTable(pipelineProps, "pipeline", pipelineId, productId, pipelineId)}
    </div>

    ${(stages||[]).map(s => `
    <div class="card" style="margin-bottom:12px">
      <div class="card-header">
        <div>
          <h2 style="font-size:14px">#${s.order} ${s.name} <span style="font-size:11px;font-weight:400;color:var(--gray-400)">Stage Properties</span></h2>
          <div style="font-size:11px;color:var(--gray-400)">Override pipeline properties for this stage and its tasks</div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="showAddProperty('stage','${s.id}','${productId}','${pipelineId}')">＋ Add</button>
      </div>
      ${_renderPropertiesTable(stagePropsMap[s.id]||[], "stage", s.id, productId, pipelineId)}

      ${(s.tasks||[]).length ? `
      <div style="border-top:1px solid var(--gray-100);padding:0 16px 12px">
        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--gray-400);padding:10px 0 6px">Tasks</div>
        ${(s.tasks||[]).map(t => `
        <div style="margin-bottom:8px">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:var(--gray-50);border:1px solid var(--gray-200);border-radius:6px;margin-bottom:4px">
            <div style="font-size:12px;font-weight:600;color:var(--gray-700)">
              <span style="color:var(--gray-400);margin-right:6px">#${t.order}</span>${t.name}
              <span style="font-size:10px;font-weight:400;color:var(--gray-400);margin-left:6px">Task Properties</span>
            </div>
            <button class="btn btn-secondary btn-sm" style="font-size:11px;padding:2px 8px" onclick="showAddProperty('task','${t.id}','${productId}','${pipelineId}')">＋ Add</button>
          </div>
          ${_renderPropertiesTable(taskPropsMap[t.id]||[], "task", t.id, productId, pipelineId, true)}
        </div>`).join("")}
      </div>` : ""}
    </div>`).join("")}

    <div class="card" style="background:var(--gray-50)">
      <div style="padding:12px 16px;font-size:12px;color:var(--gray-600)">
        <strong>Resolution order</strong> (first match wins):<br>
        <code style="font-size:11px">Runtime override (task_run → stage_run → pipeline_run) → Task → Stage → Pipeline → Product</code><br><br>
        In task scripts, resolved properties are available as <code>$CDT_PROPS</code> (JSON) and individually via
        <code>$CDT_RUNTIME</code> under the <code>properties</code> key.
      </div>
    </div>
  `);
  } catch(e) { setContent(`<div class="alert alert-danger">Failed to load properties: ${e.message}</div>`); }
});

function _renderPropertiesTable(props, ownerType, ownerId, productId, pipelineId, compact = false) {
  if (!props.length) {
    const msg = compact
      ? `<div style="padding:6px 10px;font-size:11px;color:var(--gray-400);font-style:italic">No task properties — <a href="#" onclick="event.preventDefault();showAddProperty('${ownerType}','${ownerId}','${productId}','${pipelineId}')">add one</a></div>`
      : `<div class="empty-state" style="padding:20px 0"><div class="empty-icon">🔧</div><p style="font-size:13px">No properties defined. Add one to make it available to tasks.</p></div>`;
    return msg;
  }
  const typeColor = { string: "#6366f1", number: "#0369a1", boolean: "#15803d", secret: "#dc2626", json: "#b45309" };
  const typeIcon  = { string: "Aa", number: "#", boolean: "✓", secret: "🔒", json: "{}" };
  return `<div style="display:flex;flex-direction:column;gap:8px;padding:12px 16px">
    ${props.map(p => {
      const color = typeColor[p.value_type] || "#6366f1";
      const icon  = typeIcon[p.value_type]  || "Aa";
      const displayVal = p.value_type === "secret"
        ? `<span style="letter-spacing:3px;color:var(--gray-400)">••••••••</span>`
        : p.value !== null && p.value !== undefined && p.value !== ""
          ? `<code style="background:var(--gray-100);padding:2px 8px;border-radius:4px;font-size:12px;word-break:break-all">${p.value}</code>`
          : `<em style="color:var(--gray-400);font-size:12px">not set</em>`;
      const requiredBadge = p.is_required
        ? `<span style="font-size:10px;font-weight:600;color:#dc2626;background:#fef2f2;padding:1px 6px;border-radius:8px;border:1px solid #fecaca">required</span>`
        : "";
      return `
      <div style="display:flex;align-items:flex-start;gap:12px;padding:12px 14px;background:#fff;border:1px solid var(--gray-200);border-radius:8px;border-left:3px solid ${color}">
        <div style="width:28px;height:28px;border-radius:6px;background:${color}15;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:${color};flex-shrink:0;margin-top:1px">${icon}</div>
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px">
            <strong style="font-family:monospace;font-size:13px;color:var(--gray-800)">${p.name}</strong>
            <span style="font-size:10px;font-weight:600;color:${color};background:${color}18;padding:1px 7px;border-radius:8px;text-transform:uppercase;letter-spacing:.3px">${p.value_type}</span>
            ${requiredBadge}
          </div>
          ${p.description ? `<div style="font-size:12px;color:var(--gray-500);margin-bottom:6px">${p.description}</div>` : ""}
          <div>${displayVal}</div>
        </div>
        <div onclick="event.stopPropagation()">
          ${pageMenu("prop-"+p.id,[
            {label:"✏ Edit", onclick:`showEditProperty('${ownerType}','${ownerId}','${p.name.replace(/'/g,"\\'")}','${(p.value||"").replace(/'/g,"\\'")}','${p.value_type}','${(p.description||"").replace(/'/g,"\\'")}',${p.is_required},'${productId}','${pipelineId}')`},
            {divider:true},
            {label:"🗑 Delete", onclick:`deleteProperty('${ownerType}','${ownerId}','${p.name.replace(/'/g,"\\'")}','${productId}','${pipelineId}')`,danger:true},
          ])}
        </div>
      </div>`;
    }).join("")}
  </div>`;
}

function showAddProperty(ownerType, ownerId, productId, pipelineId) {
  openModal("Add Property",
    `<div class="form-group"><label>Name *</label><input id="pr-name" class="form-control" placeholder="e.g. DEPLOY_TIMEOUT"></div>
     <div class="form-group"><label>Type</label>
       <select id="pr-type" class="form-control">
         <option value="string">string</option>
         <option value="number">number</option>
         <option value="boolean">boolean</option>
         <option value="secret">secret</option>
         <option value="json">json</option>
       </select>
     </div>
     <div class="form-group"><label>Value</label><input id="pr-value" class="form-control" placeholder="e.g. 300"></div>
     <div class="form-group"><label>Description</label><input id="pr-desc" class="form-control" placeholder="Optional"></div>
     <div class="form-group"><label>Required</label>
       <select id="pr-req" class="form-control">
         <option value="false">No</option>
         <option value="true">Yes</option>
       </select>
     </div>`,
    async () => {
      const name = el("pr-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        await api.createProperty(ownerType, ownerId, {
          name, value: el("pr-value").value || null,
          value_type: el("pr-type").value,
          description: el("pr-desc").value.trim() || null,
          is_required: el("pr-req").value === "true",
        });
        closeModal(); toast("Property saved", "success");
        navigate(`products/${productId}/pipelines/${pipelineId}/properties`);
      } catch(e) { modalError(e.message); }
    }
  );
}

function showEditProperty(ownerType, ownerId, name, value, valueType, description, isRequired, productId, pipelineId) {
  const typeOpts = ["string","number","boolean","secret","json"].map(t =>
    `<option value="${t}"${t===valueType?" selected":""}>${t}</option>`).join("");
  openModal("Edit Property",
    `<div class="form-group"><label>Name</label><input class="form-control" value="${name}" readonly style="background:var(--gray-50)"></div>
     <div class="form-group"><label>Type</label><select id="pr-type" class="form-control">${typeOpts}</select></div>
     <div class="form-group"><label>Value</label><input id="pr-value" class="form-control" value="${value}"></div>
     <div class="form-group"><label>Description</label><input id="pr-desc" class="form-control" value="${description}"></div>
     <div class="form-group"><label>Required</label>
       <select id="pr-req" class="form-control">
         <option value="false"${!isRequired?" selected":""}>No</option>
         <option value="true"${isRequired?" selected":""}>Yes</option>
       </select>
     </div>`,
    async () => {
      try {
        await api.updateProperty(ownerType, ownerId, name, {
          value: el("pr-value").value || null,
          value_type: el("pr-type").value,
          description: el("pr-desc").value.trim() || null,
          is_required: el("pr-req").value === "true",
        });
        closeModal(); toast("Property updated", "success");
        navigate(`products/${productId}/pipelines/${pipelineId}/properties`);
      } catch(e) { modalError(e.message); }
    }
  );
}

async function deleteProperty(ownerType, ownerId, name, productId, pipelineId) {
  if (!confirm(`Delete property "${name}"?`)) return;
  try {
    await api.deleteProperty(ownerType, ownerId, name);
    toast("Property deleted", "success");
    navigate(`products/${productId}/pipelines/${pipelineId}/properties`);
  } catch(e) { toast(e.message, "error"); }
}

function showCreateWebhookForPipeline(pipelineId) {
  openModal("New Webhook",
    `<div class="form-group"><label>Name *</label>
       <input id="wh-name" class="form-control" placeholder="e.g. GitHub Push"></div>
     <div class="form-group"><label>Description</label>
       <input id="wh-desc" class="form-control"></div>`,
    async () => {
      const name = el("wh-name").value.trim();
      if (!name) throw new Error("Name is required");
      const result = await api.createWebhook({ name, pipeline_id: pipelineId, description: el("wh-desc").value.trim() });
      closeModal();
      openModal("Webhook Created — Save Your Token",
        `<p style="margin-bottom:12px;color:var(--gray-600)">This token will not be shown again. Copy it now.</p>
         <input class="form-control" value="${result.token}" readonly style="font-family:monospace;font-size:13px">`,
        () => { closeModal(); navigate(router.current); }, "Done"
      );
    }, "Create"
  );
}

async function deleteWebhookPl(webhookId, name, productId, pipelineId) {
  if (!confirm(`Delete webhook "${name}"?`)) return;
  try {
    await api.deleteWebhook(webhookId);
    toast("Webhook deleted", "success");
    navigate(`products/${productId}/pipelines/${pipelineId}/webhooks`);
  } catch (e) { toast(e.message, "error"); }
}

// ── Release detail ─────────────────────────────────────────────────────────
router.register("products/:pid/releases/:id", async (hash, parts) => {
  const [,productId,,releaseId] = parts;
  setContent(loading());
  const [product, release, runs, apps, allPipelines] = await Promise.all([
    api.getProduct(productId),
    api.getRelease(productId, releaseId),
    api.getReleaseRuns(releaseId).catch(() => []),
    api.getApplications(productId).catch(() => []),
    api.getPipelines(productId).catch(() => []),
  ]);
  setBreadcrumb(
    { label: "Products", hash: "products" },
    { label: product.name, hash: `products/${productId}` },
    { label: release.name }
  );

  const groups = release.application_groups || [];
  const groupedAppIds = new Set(groups.map(g => g.application_id));

  // Build pipeline map by application
  const pipelinesByApp = {};
  allPipelines.forEach(pl => {
    if (!pl.application_id) return;
    if (!pipelinesByApp[pl.application_id]) pipelinesByApp[pl.application_id] = [];
    pipelinesByApp[pl.application_id].push(pl);
  });

  const groupCards = groups.map(g => {
    const appPipelines = pipelinesByApp[g.application_id] || [];
    const selectedIds = new Set(g.pipeline_ids || []);
    return `
      <div class="card" style="margin-bottom:12px;border-left:3px solid var(--brand)">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
          <div>
            <strong style="font-size:14px">${g.application_name || g.application_id}</strong>
            <span class="badge ${g.execution_mode==="parallel"?"badge-blue":"badge-silver"}" style="margin-left:8px">${g.execution_mode}</span>
          </div>
          <div>
            ${pageMenu("grp-"+g.id, [
              {label: "✏ Edit Group", onclick: `showEditAppGroup('${productId}','${releaseId}','${g.id}','${g.application_id}','${g.application_name||""}','${g.execution_mode}',${JSON.stringify(g.pipeline_ids||[]).replace(/"/g,"'")})`},
              {divider: true},
              {label: "🗑 Remove Group", onclick: `removeAppGroup('${productId}','${releaseId}','${g.id}','${g.application_name||g.application_id}')`, danger: true},
            ])}
          </div>
        </div>
        ${g.pipeline_ids.length === 0
          ? `<div style="font-size:12px;color:var(--gray-400)">No pipelines selected.</div>`
          : `<div style="display:flex;flex-wrap:wrap;gap:6px">${(g.pipeline_ids||[]).map(pid => {
              const pl = allPipelines.find(p => p.id === pid);
              return pl ? `<span class="badge badge-blue" style="font-size:12px">${pl.name}</span>` : "";
            }).join("")}</div>`
        }
      </div>`;
  }).join("");

  const availableApps = apps.filter(a => !groupedAppIds.has(a.id));

  setContent(`
    <div class="page-header">
      <div><h1>${release.name}</h1>
        <div class="sub">Version: ${release.version||"—"} · Created by ${release.created_by||"system"}</div>
      </div>
      <div style="display:flex;gap:6px;align-items:center">
        <button class="btn btn-primary btn-sm" onclick="showStartReleaseRun('${releaseId}')">▶ Run</button>
        ${pageMenu("rel-"+releaseId, [
          {label: "📋 Audit Report", onclick: `navigate('products/${productId}/releases/${releaseId}/audit')`},
          {label: "⬇ Export YAML", onclick: `exportYaml('/api/v1/products/${productId}/releases/${releaseId}/export','${release.name.replace(/'/g,"\\'")}release.yaml')`},
          {divider: true},
          {label: "🗑 Delete Release", onclick: `deleteRelease('${productId}','${releaseId}','${release.name}')`, danger: true},
        ])}
      </div>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab(this,'tab-rel-apps')">Applications & Pipelines (${groups.length})</button>
      <button class="tab-btn" onclick="switchTab(this,'tab-rel-runs')">Runs (${runs.length})</button>
    </div>

    <div id="tab-rel-apps" class="tab-panel active">
      ${availableApps.length > 0 ? `
        <div class="card" style="margin-bottom:14px;background:var(--brand-faint);border-color:var(--brand)">
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
            <span style="font-size:13px;font-weight:500;color:var(--brand)">Add application:</span>
            <select id="add-app-sel" class="form-control" style="max-width:220px">
              ${availableApps.map(a => `<option value="${a.id}" data-name="${a.name.replace(/"/g,"&quot;")}">${a.name}</option>`).join("")}
            </select>
            <button class="btn btn-primary btn-sm" onclick="showAddAppGroup('${productId}','${releaseId}')">Configure & Add</button>
          </div>
        </div>` : ""}
      ${groups.length === 0
        ? `<div class="empty-state"><div class="empty-icon">📦</div><p>No applications added yet. Add an application to configure which pipelines run in this release.</p></div>`
        : groupCards
      }
      <div style="margin-top:12px;font-size:12px;color:var(--gray-400)">Application groups execute <strong>sequentially</strong> (top to bottom). Pipelines within each group execute in the group's configured mode.</div>
    </div>

    <div id="tab-rel-runs" class="tab-panel">
      ${runs.length === 0
        ? `<div class="empty-state"><div class="empty-icon">▶</div><p>No release runs yet.</p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Run ID</th><th>Status</th><th>Started</th><th>Finished</th></tr></thead>
          <tbody>${runs.map(r => `
            <tr>
              <td><code style="font-size:11.5px">${r.id}</code></td>
              <td>${statusBadge(r.status)}</td>
              <td style="color:var(--gray-400)">${fmtDate(r.started_at)}</td>
              <td style="color:var(--gray-400)">${fmtDate(r.finished_at)}</td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>
  `);
});

async function showAddAppGroup(productId, releaseId) {
  const sel = el("add-app-sel");
  if (!sel) return;
  const appId = sel.value;
  const appName = sel.options[sel.selectedIndex]?.dataset.name || appId;
  const allPipelines = await api.getPipelines(productId).catch(() => []);
  const appPipelines = allPipelines.filter(pl => pl.application_id === appId);

  openModal(`Add Application: ${appName}`,
    `<div class="form-group">
       <label>Execution Mode</label>
       <select id="ag-mode" class="form-control">
         <option value="sequential">Sequential — pipelines run one after another</option>
         <option value="parallel">Parallel — pipelines run simultaneously</option>
       </select>
     </div>
     <div class="form-group">
       <label>Select Pipelines</label>
       ${appPipelines.length === 0
         ? `<div style="color:var(--gray-400);font-size:13px">No pipelines under this application.</div>`
         : appPipelines.map(pl => `
           <label style="display:flex;align-items:center;gap:8px;margin-bottom:6px;cursor:pointer">
             <input type="checkbox" class="ag-pl-check" value="${pl.id}" checked>
             <span>${pl.name} <span class="badge badge-${pl.kind}">${pl.kind.toUpperCase()}</span></span>
           </label>`).join("")
       }
     </div>`,
    async () => {
      const mode = el("ag-mode").value;
      const selectedPls = [...document.querySelectorAll(".ag-pl-check:checked")].map(c => c.value);
      try {
        await api.addReleaseAppGroup(productId, releaseId, {
          application_id: appId,
          execution_mode: mode,
          pipeline_ids: selectedPls,
        });
        closeModal(); toast("Application group added", "success");
        navigate(`products/${productId}/releases/${releaseId}`);
      } catch (e) { modalError(e.message); }
    }, "Add"
  );
}

async function showEditAppGroup(productId, releaseId, groupId, appId, appName, currentMode, currentPipelineIds) {
  const allPipelines = await api.getPipelines(productId).catch(() => []);
  const appPipelines = allPipelines.filter(pl => pl.application_id === appId);
  const selectedSet = new Set(Array.isArray(currentPipelineIds) ? currentPipelineIds : []);

  openModal(`Edit: ${appName}`,
    `<div class="form-group">
       <label>Execution Mode</label>
       <select id="ag-mode" class="form-control">
         <option value="sequential" ${currentMode==="sequential"?"selected":""}>Sequential</option>
         <option value="parallel" ${currentMode==="parallel"?"selected":""}>Parallel</option>
       </select>
     </div>
     <div class="form-group">
       <label>Select Pipelines</label>
       ${appPipelines.length === 0
         ? `<div style="color:var(--gray-400);font-size:13px">No pipelines under this application.</div>`
         : appPipelines.map(pl => `
           <label style="display:flex;align-items:center;gap:8px;margin-bottom:6px;cursor:pointer">
             <input type="checkbox" class="ag-pl-check" value="${pl.id}" ${selectedSet.has(pl.id)?"checked":""}>
             <span>${pl.name} <span class="badge badge-${pl.kind}">${pl.kind.toUpperCase()}</span></span>
           </label>`).join("")
       }
     </div>`,
    async () => {
      const mode = el("ag-mode").value;
      const selectedPls = [...document.querySelectorAll(".ag-pl-check:checked")].map(c => c.value);
      try {
        // Replace by deleting and re-adding
        await api.removeReleaseAppGroup(productId, releaseId, groupId);
        await api.addReleaseAppGroup(productId, releaseId, {
          application_id: appId,
          execution_mode: mode,
          pipeline_ids: selectedPls,
        });
        closeModal(); toast("Application group updated", "success");
        navigate(`products/${productId}/releases/${releaseId}`);
      } catch (e) { modalError(e.message); }
    }, "Save"
  );
}

async function removeAppGroup(productId, releaseId, groupId, appName) {
  if (!confirm(`Remove application "${appName}" from this release?`)) return;
  try {
    await api.removeReleaseAppGroup(productId, releaseId, groupId);
    toast("Application group removed", "success");
    navigate(`products/${productId}/releases/${releaseId}`);
  } catch (e) { toast(e.message, "error"); }
}

async function deleteRelease(productId, releaseId, name) {
  if (!confirm(`Delete release "${name}"?`)) return;
  try {
    await api.deleteRelease(productId, releaseId);
    toast("Release deleted", "success");
    navigate(`products/${productId}`);
  } catch (e) { toast(e.message, "error"); }
}

function showStartReleaseRun(releaseId) {
  openModal("Start Release Run",
    `<div class="form-group"><label>Triggered By</label><input id="rrun-by" class="form-control" value="user"></div>`,
    async () => {
      try {
        const run = await api.createReleaseRun(releaseId, { triggered_by: el("rrun-by").value.trim()||"user" });
        closeModal(); toast(`Release run started: ${run.id}`, "success");
        navigate(router.current);
      } catch (e) { modalError(e.message); }
    },
    "Start"
  );
}

async function completeReleaseRun(runId, productId, releaseId) {
  const status = confirm("Mark as Succeeded?") ? "Succeeded" : "Failed";
  try {
    await api.updateReleaseRun(runId, { status });
    toast(`Run ${status}`, "success");
    navigate(`products/${productId}/releases/${releaseId}`);
  } catch (e) { toast(e.message, "error"); }
}

// ── Audit report view ──────────────────────────────────────────────────────
router.register("products/:pid/releases/:rid/audit", async (hash, parts) => {
  const [,productId,,releaseId] = parts;
  setContent(loading());
  const [product, release, report] = await Promise.all([
    api.getProduct(productId),
    api.getRelease(productId, releaseId),
    api.getAuditReport(productId, releaseId),
  ]);
  setBreadcrumb(
    { label: "Products", hash: "products" },
    { label: product.name, hash: `products/${productId}` },
    { label: release.name, hash: `products/${productId}/releases/${releaseId}` },
    { label: "Audit Report" }
  );
  setContent(`
    <div class="page-header">
      <div><h1>Audit Report</h1><div class="sub">${release.name} · Generated ${fmtDate(report.generated_at)}</div></div>
      <a class="btn btn-primary btn-sm" href="/api/v1/products/${productId}/releases/${releaseId}/audit/export" target="_blank">⬇ Export PDF</a>
    </div>

    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>Release Summary</h2></div>
      <div class="detail-grid">
        <div class="detail-row"><span class="detail-label">ID</span><code style="font-size:12px">${report.release.id}</code></div>
        <div class="detail-row"><span class="detail-label">Version</span><span class="detail-value">${report.release.version||"—"}</span></div>
        <div class="detail-row"><span class="detail-label">Created By</span><span class="detail-value">${report.release.created_by||"—"}</span></div>
        <div class="detail-row"><span class="detail-label">Created At</span><span class="detail-value">${fmtDate(report.release.created_at)}</span></div>
        <div class="detail-row"><span class="detail-label">Definition SHA</span><span class="detail-value">${report.release.definition_sha||"—"}</span></div>
        <div class="detail-row"><span class="detail-label">Protected Segment</span><span class="detail-value">v${report.release.protected_segment_version}</span></div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>Pipelines (${report.pipelines.length})</h2></div>
      ${report.pipelines.length === 0
        ? `<div class="empty-state"><p>No pipelines attached.</p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Pipeline</th><th>Kind</th><th>Rating</th><th>Score</th><th>Definition SHA</th></tr></thead>
          <tbody>${report.pipelines.map(p => `
            <tr>
              <td>${p.name}</td>
              <td><span class="badge badge-${p.kind}">${p.kind.toUpperCase()}</span></td>
              <td>${ratingBadge(p.compliance_rating)}</td>
              <td>${scoreBar(p.compliance_score, p.compliance_rating)}</td>
              <td><code style="font-size:11.5px">${p.definition_sha||"—"}</code></td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>

    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>Release Runs (${report.runs.length})</h2></div>
      ${report.runs.length === 0
        ? `<div class="empty-state"><p>No runs yet.</p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Run ID</th><th>Status</th><th>Rating</th><th>Started</th><th>Triggered By</th></tr></thead>
          <tbody>${report.runs.map(r => `
            <tr>
              <td><code style="font-size:11.5px">${r.id}</code></td>
              <td>${statusBadge(r.status)}</td>
              <td>${ratingBadge(r.compliance_rating)}</td>
              <td>${fmtDate(r.started_at)}</td>
              <td>${r.triggered_by||"—"}</td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>

    <div class="card">
      <div class="card-header"><h2>Audit Events (${report.audit_events.length})</h2></div>
      ${report.audit_events.length === 0
        ? `<div class="empty-state"><p>No events recorded.</p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Timestamp</th><th>Event</th><th>Actor</th><th>Decision</th></tr></thead>
          <tbody>${report.audit_events.map(e => `
            <tr>
              <td style="color:var(--gray-400)">${fmtDate(e.timestamp)}</td>
              <td><code style="font-size:12px">${e.event_type}</code></td>
              <td>${e.actor||"—"}</td>
              <td><span class="badge ${e.decision==="ALLOW"?"badge-success":"badge-noncompliant"}">${e.decision}</span></td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>
  `);
});

// ── Pipeline Templates ────────────────────────────────────────────────────
router.register("templates", async () => {
  setBreadcrumb({ label: "Templates" });
  setContent(loading());

  const templates = await request("GET", "/pipeline-templates").catch(() => []);

  // Group by category
  const categories = {};
  for (const t of templates) {
    const cat = t.category || "General";
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(t);
  }

  const kindBadge = k => `<span style="background:${k==="cd"?"#ede9fe":"#dbeafe"};color:${k==="cd"?"#7c3aed":"#1d4ed8"};padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;text-transform:uppercase">${k||"CI"}</span>`;

  setContent(`
    <div class="page-header">
      <div><h1>Pipeline Templates</h1><div class="sub">Reusable pipeline blueprints — create a pipeline from any template</div></div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-primary" onclick="showCreateTemplateModal()">+ New Template</button>
      </div>
    </div>

    ${templates.length === 0 ? `
      <div class="empty-state">
        <div style="font-size:48px;margin-bottom:12px">🗂️</div>
        <h3>No templates yet</h3>
        <p>Create a template from scratch, or save an existing pipeline as a template.</p>
        <button class="btn btn-primary" onclick="showCreateTemplateModal()">+ New Template</button>
      </div>` : `
      ${Object.entries(categories).map(([cat, items]) => `
        <div style="margin-bottom:28px">
          <h2 style="font-size:14px;font-weight:700;color:var(--gray-700);margin-bottom:12px;text-transform:uppercase;letter-spacing:.05em">${cat}</h2>
          <div class="grid grid-3" style="gap:14px">
            ${items.map(t => `
              <div class="card" style="padding:18px;cursor:default">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
                  <div style="font-size:24px">🗂️</div>
                  ${kindBadge(t.kind)}
                </div>
                <div style="font-weight:700;font-size:14px;margin-bottom:4px">${t.name}</div>
                <div style="font-size:12px;color:var(--gray-500);margin-bottom:10px;min-height:36px">${t.description||""}</div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
                  ${(t.tags||[]).map(tag=>`<span style="background:var(--gray-100);color:var(--gray-600);font-size:11px;padding:1px 8px;border-radius:8px">${tag}</span>`).join("")}
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--gray-400);margin-bottom:12px">
                  <span>${t.stage_count||0} stage(s) · ${t.task_count||0} task(s)</span>
                  <span>by ${t.created_by||"system"}</span>
                </div>
                <div style="display:flex;gap:6px">
                  <button class="btn btn-primary btn-sm" style="flex:1" onclick="showUseTeplateModal('${t.id}','${t.name.replace(/'/g,"\\'")}')">Use Template</button>
                  <button class="btn btn-secondary btn-sm" onclick="showEditTemplateModal('${t.id}')">Edit</button>
                  <button class="btn btn-danger btn-sm" onclick="deleteTemplate('${t.id}','${t.name.replace(/'/g,"\\'")}')">Del</button>
                </div>
              </div>`).join("")}
          </div>
        </div>`).join("")}
    `}
  `);
});

async function showCreateTemplateModal() {
  openModal("New Pipeline Template", `
    <div class="form-group"><label>Name *</label><input id="tmpl-name" class="input" placeholder="e.g. Secure CI with SAST & SCA"></div>
    <div class="form-group"><label>Description</label><textarea id="tmpl-desc" class="input" rows="2" placeholder="What this template does"></textarea></div>
    <div class="form-group"><label>Kind</label>
      <select id="tmpl-kind" class="input"><option value="ci">CI</option><option value="cd">CD</option></select>
    </div>
    <div class="form-group"><label>Category</label><input id="tmpl-cat" class="input" placeholder="e.g. Security, Deploy, Full Stack"></div>
    <div class="form-group"><label>Tags (comma-separated)</label><input id="tmpl-tags" class="input" placeholder="e.g. sast, sca, compliance"></div>
  `, [
    { label: "Cancel", action: closeModal },
    { label: "Create Template", primary: true, action: async () => {
      const name = document.getElementById("tmpl-name").value.trim();
      if (!name) { showToast("Name is required", "error"); return; }
      await request("POST", "/pipeline-templates", {
        name,
        description: document.getElementById("tmpl-desc").value.trim() || null,
        kind: document.getElementById("tmpl-kind").value,
        category: document.getElementById("tmpl-cat").value.trim() || null,
        tags: document.getElementById("tmpl-tags").value.split(",").map(s=>s.trim()).filter(Boolean),
        stages: [],
      });
      closeModal();
      showToast("Template created", "success");
      navigate("templates");
    }}
  ]);
}

async function showEditTemplateModal(tmplId) {
  const t = await request("GET", `/pipeline-templates/${tmplId}`);
  openModal(`Edit: ${t.name}`, `
    <div class="form-group"><label>Name</label><input id="tmpl-name" class="input" value="${(t.name||"").replace(/"/g,"&quot;")}"></div>
    <div class="form-group"><label>Description</label><textarea id="tmpl-desc" class="input" rows="2">${t.description||""}</textarea></div>
    <div class="form-group"><label>Kind</label>
      <select id="tmpl-kind" class="input">
        <option value="ci"${t.kind==="ci"?" selected":""}>CI</option>
        <option value="cd"${t.kind==="cd"?" selected":""}>CD</option>
      </select>
    </div>
    <div class="form-group"><label>Category</label><input id="tmpl-cat" class="input" value="${t.category||""}"></div>
    <div class="form-group"><label>Tags (comma-separated)</label><input id="tmpl-tags" class="input" value="${(t.tags||[]).join(", ")}"></div>
  `, [
    { label: "Cancel", action: closeModal },
    { label: "Save", primary: true, action: async () => {
      await request("PUT", `/pipeline-templates/${tmplId}`, {
        name: document.getElementById("tmpl-name").value.trim(),
        description: document.getElementById("tmpl-desc").value.trim() || null,
        kind: document.getElementById("tmpl-kind").value,
        category: document.getElementById("tmpl-cat").value.trim() || null,
        tags: document.getElementById("tmpl-tags").value.split(",").map(s=>s.trim()).filter(Boolean),
      });
      closeModal();
      showToast("Template updated", "success");
      navigate("templates");
    }}
  ]);
}

async function showUseTeplateModal(tmplId, tmplName) {
  // Load products for selection
  const products = await request("GET", "/products").catch(() => []);
  openModal(`Use Template: ${tmplName}`, `
    <div class="form-group"><label>Product *</label>
      <select id="tuse-product" class="input" onchange="_loadAppsForTemplate(this.value)">
        <option value="">— Select product —</option>
        ${products.map(p=>`<option value="${p.id}">${p.name}</option>`).join("")}
      </select>
    </div>
    <div class="form-group"><label>Application</label>
      <select id="tuse-app" class="input"><option value="">— Select product first —</option></select>
    </div>
    <div class="form-group"><label>Pipeline Name</label><input id="tuse-name" class="input" value="${tmplName}"></div>
    <div class="form-group"><label>Git Repository</label><input id="tuse-repo" class="input" placeholder="git@github.com:org/repo.git"></div>
    <div class="form-group"><label>Branch</label><input id="tuse-branch" class="input" value="main"></div>
  `, [
    { label: "Cancel", action: closeModal },
    { label: "Create Pipeline", primary: true, action: async () => {
      const productId = document.getElementById("tuse-product").value;
      const name = document.getElementById("tuse-name").value.trim();
      if (!productId) { showToast("Select a product", "error"); return; }
      if (!name) { showToast("Name is required", "error"); return; }
      await request("POST", `/pipeline-templates/${tmplId}/create-pipeline`, {
        product_id: productId,
        application_id: document.getElementById("tuse-app").value || null,
        name,
        git_repo: document.getElementById("tuse-repo").value.trim() || null,
        git_branch: document.getElementById("tuse-branch").value.trim() || "main",
      });
      closeModal();
      showToast("Pipeline created from template", "success");
      navigate(`products/${productId}`);
    }}
  ]);
}

async function _loadAppsForTemplate(productId) {
  const sel = document.getElementById("tuse-app");
  if (!sel || !productId) return;
  const apps = await request("GET", `/products/${productId}/applications`).catch(() => []);
  sel.innerHTML = `<option value="">— Optional —</option>` +
    apps.map(a=>`<option value="${a.id}">${a.name}</option>`).join("");
}

async function deleteTemplate(id, name) {
  if (!confirm(`Delete template "${name}"?`)) return;
  await request("DELETE", `/pipeline-templates/${id}`);
  showToast("Template deleted", "success");
  navigate("templates");
}

// ── Environments list (top-level) ─────────────────────────────────────────
router.register("environments", async () => {
  setBreadcrumb({ label: "Environments" });
  setContent(loading());
  const envs = await api.getEnvironments().catch(() => []);
  setContent(`
    <div class="page-header">
      <div><h1>Environments</h1><div class="sub">Deployment targets shared across products</div></div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-secondary btn-sm" onclick="exportYaml('/api/v1/environments/export','environments.yaml')">⬇ Export YAML</button>
        <button class="btn btn-secondary btn-sm" onclick="showImportYaml('/api/v1/environments/import','Environments',()=>navigate('environments'))">⬆ Import YAML</button>
        <button class="btn btn-primary" onclick="showCreateEnv()">+ New Environment</button>
      </div>
    </div>
    ${envs.length === 0
      ? `<div class="card"><div class="empty-state"><div class="empty-icon">🌍</div><p>No environments yet.</p></div></div>`
      : `<div class="grid grid-3">
        ${envs.map(e => `
          <div class="card">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
              <span style="font-size:16px;font-weight:600">${e.name}</span>
              <span class="badge badge-blue">${e.env_type}</span>
            </div>
            <div style="color:var(--gray-600);font-size:13px;margin-bottom:4px">${e.description || "No description"}</div>
            <div style="font-size:11.5px;color:var(--gray-400)">Order: ${e.order}</div>
            <div style="display:flex;gap:6px;margin-top:10px">
              <button class="btn btn-secondary btn-sm" onclick="showEditEnv('${e.id}','${e.name.replace(/'/g,"\\'")}','${e.env_type}',${e.order},'${(e.description||"").replace(/'/g,"\\'")}')">Edit</button>
              <button class="btn btn-danger btn-sm" onclick="deleteEnv('${e.id}','${e.name.replace(/'/g,"\\'")}')">Delete</button>
            </div>
          </div>`).join("")}
      </div>`
    }
  `);
});

// ── Compliance page ────────────────────────────────────────────────────────
router.register("compliance", async () => {
  setBreadcrumb({ label: "Compliance" });
  setContent(loading());
  const [rules, events] = await Promise.all([
    api.getComplianceRules().catch(() => []),
    api.getAuditEvents({ limit: 20 }).catch(() => []),
  ]);
  setContent(`
    <div class="page-header">
      <div><h1>Compliance</h1><div class="sub">Release admission rules, ISO 27001:2022 controls, and audit events</div></div>
      <button class="btn btn-primary" onclick="showCreateRule()">+ New Rule</button>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab(this,'ctab-rules')">Admission Rules (${rules.length})</button>
      <button class="tab-btn" onclick="switchTab(this,'ctab-iso'); loadIso27001()">ISO 27001:2022</button>
      <button class="tab-btn" onclick="switchTab(this,'ctab-events')">Audit Events (${events.length})</button>
    </div>

    <!-- Admission Rules -->
    <div id="ctab-rules" class="tab-panel active">
      ${rules.length === 0
        ? `<div class="card"><div class="empty-state"><div class="empty-icon">🛡</div><p>No rules defined. Pipelines can be attached to any release.</p></div></div>`
        : `<div class="card"><div class="table-wrap"><table>
          <thead><tr><th>Description</th><th>Scope</th><th>Min Rating</th><th>Actions</th></tr></thead>
          <tbody>${rules.map(r => `
            <tr>
              <td>${r.description||"—"}</td>
              <td><code style="font-size:12px">${r.scope}</code></td>
              <td>${ratingBadge(r.min_rating)}</td>
              <td><button class="btn btn-danger btn-sm" onclick="deleteRule('${r.id}')">Disable</button></td>
            </tr>`).join("")}
          </tbody></table></div></div>`
      }
    </div>

    <!-- ISO 27001:2022 -->
    <div id="ctab-iso" class="tab-panel">
      <div id="iso27001-content" style="padding:24px;text-align:center;color:var(--gray-400)">Click the ISO 27001:2022 tab to load the evaluation...</div>
    </div>

    <!-- Audit Events -->
    <div id="ctab-events" class="tab-panel">
      <div class="card">
        <div class="card-header"><h2>Recent Audit Events</h2></div>
        ${events.length === 0
          ? `<div class="empty-state"><div class="empty-icon">📋</div><p>No events yet.</p></div>`
          : `<div class="table-wrap"><table>
            <thead><tr><th>Timestamp</th><th>Event</th><th>Actor</th><th>Resource</th><th>Decision</th></tr></thead>
            <tbody>${events.map(e => `
              <tr>
                <td style="color:var(--gray-400)">${fmtDate(e.timestamp)}</td>
                <td><code style="font-size:12px">${e.event_type}</code></td>
                <td>${e.actor||"—"}</td>
                <td><code style="font-size:12px">${e.resource_type}/${e.resource_id}</code></td>
                <td><span class="badge ${e.decision==="ALLOW"?"badge-success":"badge-noncompliant"}">${e.decision}</span></td>
              </tr>`).join("")}
            </tbody></table></div>`
        }
      </div>
    </div>
  `);
});

let _iso27001Loaded = false;

async function loadIso27001() {
  if (_iso27001Loaded) return;
  const container = document.getElementById("iso27001-content");
  if (!container) return;
  container.innerHTML = `<div style="padding:32px;text-align:center;color:var(--gray-400)">Evaluating controls…</div>`;
  try {
    const report = await api.getIso27001Report();
    _iso27001Loaded = true;
    _renderIso27001(report);
  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">Failed to load ISO 27001 report: ${e.message}</div>`;
  }
}

function _isoStatusBadge(status) {
  const map = {
    pass:   '<span class="badge badge-success">Pass</span>',
    fail:   '<span class="badge badge-noncompliant">Fail</span>',
    manual: '<span class="badge badge-silver">Manual</span>',
    na:     '<span class="badge badge-silver">N/A</span>',
  };
  return map[status] || `<span class="badge badge-silver">${status}</span>`;
}

function _isoCheckIcon(status) {
  return status === "pass" ? "✅" : status === "fail" ? "❌" : status === "na" ? "➖" : "🔲";
}

function _renderIso27001(report) {
  const container = document.getElementById("iso27001-content");
  if (!container) return;

  const scoreColor = report.auto_score >= 80 ? "var(--success)" : report.auto_score >= 50 ? "var(--warning,#e6a817)" : "var(--danger)";

  // Group controls by clause for collapsible sections
  const byClause = {};
  for (const ctrl of report.controls) {
    if (!byClause[ctrl.clause]) byClause[ctrl.clause] = [];
    byClause[ctrl.clause].push(ctrl);
  }

  const clauseHtml = Object.entries(byClause).map(([clause, controls]) => {
    const cp = controls.filter(c => c.status === "pass").length;
    const cf = controls.filter(c => c.status === "fail").length;
    const cm = controls.filter(c => c.status === "manual").length;
    const clauseId = `iso-clause-${clause.replace(/\s+/g,"-")}`;
    return `
      <div class="card" style="margin-bottom:12px">
        <div style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;padding:2px 0"
             onclick="document.getElementById('${clauseId}').style.display=document.getElementById('${clauseId}').style.display==='none'?'block':'none'">
          <div style="font-weight:600;font-size:14px">${clause} <span style="font-size:12px;color:var(--gray-400);font-weight:400">(${controls.length} controls)</span></div>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="badge badge-success" style="font-size:11px">✅ ${cp}</span>
            ${cf > 0 ? `<span class="badge badge-noncompliant" style="font-size:11px">❌ ${cf}</span>` : ""}
            <span class="badge badge-silver" style="font-size:11px">🔲 ${cm}</span>
            <span style="color:var(--gray-400);font-size:18px">▾</span>
          </div>
        </div>
        <div id="${clauseId}" style="display:none;margin-top:12px">
          <div class="table-wrap"><table style="font-size:12.5px">
            <thead><tr><th style="width:60px">Control</th><th>Title</th><th style="width:80px">Check</th><th style="width:80px">Status</th><th>Evidence</th></tr></thead>
            <tbody>${controls.map(c => `
              <tr>
                <td><code style="font-size:11px">${c.id}</code></td>
                <td style="font-weight:500">${c.title}</td>
                <td><span class="badge ${c.check_type==="automatic"?"badge-blue":"badge-silver"}" style="font-size:10px">${c.check_type==="automatic"?"Auto":"Manual"}</span></td>
                <td>${_isoStatusBadge(c.status)}</td>
                <td style="color:var(--gray-500);font-size:12px">${c.evidence}</td>
              </tr>`).join("")}
            </tbody>
          </table></div>
        </div>
      </div>`;
  }).join("");

  container.innerHTML = `
    <!-- Score header -->
    <div class="card" style="margin-bottom:20px">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px">
        <div>
          <div style="font-size:13px;color:var(--gray-400);margin-bottom:4px">${report.standard} · ${report.annex}</div>
          <div style="font-size:28px;font-weight:700;color:${scoreColor}">${report.auto_score}%
            <span style="font-size:14px;color:var(--gray-400);font-weight:400">automated check score</span>
          </div>
          <div style="font-size:12px;color:var(--gray-400);margin-top:4px">
            ${report.total_controls} controls total ·
            ✅ ${report.passed} pass · ❌ ${report.failed} fail · 🔲 ${report.manual} manual
          </div>
        </div>
        <div style="display:flex;gap:24px;flex-wrap:wrap">
          ${report.clause_summary.map(cs => `
            <div style="text-align:center;min-width:100px">
              <div style="font-size:11px;color:var(--gray-400);margin-bottom:4px">${cs.clause.split(" ").slice(1).join(" ")}</div>
              <div style="display:flex;gap:6px;justify-content:center">
                <span class="badge badge-success" style="font-size:11px">✅ ${cs.passed}</span>
                ${cs.failed > 0 ? `<span class="badge badge-noncompliant" style="font-size:11px">❌ ${cs.failed}</span>` : ""}
                <span class="badge badge-silver" style="font-size:11px">🔲 ${cs.manual}</span>
              </div>
            </div>`).join("")}
        </div>
      </div>
    </div>

    <!-- Platform context -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><h3 style="margin:0;font-size:14px">Platform Evidence Summary</h3></div>
      <div style="display:flex;flex-wrap:wrap;gap:16px;padding-top:8px">
        ${[
          ["Users", report.platform_context.user_count],
          ["Roles", report.platform_context.role_count],
          ["Role Bindings", report.platform_context.binding_count],
          ["Pipelines", report.platform_context.pipeline_count],
          ["Pipeline Runs", report.platform_context.pipeline_run_count],
          ["Environments", report.platform_context.environment_count],
          ["Vault Secrets", report.platform_context.vault_secret_count],
          ["Audit Events", report.platform_context.audit_event_count],
          ["Compliance Rules", report.platform_context.compliance_rule_count],
          ["Webhooks", report.platform_context.webhook_count],
        ].map(([label, val]) => `
          <div style="background:var(--gray-50,#f8f9fa);border-radius:6px;padding:8px 14px;min-width:110px;text-align:center">
            <div style="font-size:20px;font-weight:700;color:var(--brand)">${val}</div>
            <div style="font-size:11px;color:var(--gray-400)">${label}</div>
          </div>`).join("")}
      </div>
    </div>

    <!-- Controls by clause (collapsible) -->
    <div style="margin-bottom:8px;display:flex;gap:8px">
      <button class="btn btn-secondary btn-sm" onclick="document.querySelectorAll('[id^=iso-clause-]').forEach(el=>el.style.display='block')">Expand All</button>
      <button class="btn btn-secondary btn-sm" onclick="document.querySelectorAll('[id^=iso-clause-]').forEach(el=>el.style.display='none')">Collapse All</button>
    </div>
    ${clauseHtml}
  `;
}

function showCreateRule() {
  openModal("New Compliance Rule",
    `<div class="form-group"><label>Description</label><input id="cr-desc" class="form-control" placeholder="e.g. Gold required for prod"></div>
     <div class="form-group"><label>Scope *</label><input id="cr-scope" class="form-control" placeholder="e.g. environment:prod or product:api-service or organization"></div>
     <div class="form-group"><label>Minimum Rating *</label><select id="cr-rating" class="form-control">
       <option value="Bronze">Bronze</option><option value="Silver">Silver</option><option value="Gold" selected>Gold</option><option value="Platinum">Platinum</option>
     </select></div>`,
    async () => {
      const scope = el("cr-scope").value.trim();
      if (!scope) return modalError("Scope is required");
      try {
        await api.createComplianceRule({ description: el("cr-desc").value.trim()||null, scope, min_rating: el("cr-rating").value });
        closeModal(); toast("Rule created", "success");
        _iso27001Loaded = false;
        navigate("compliance");
      } catch (e) { modalError(e.message); }
    }
  );
}

async function deleteRule(id) {
  if (!confirm("Disable this compliance rule?")) return;
  try {
    await api.deleteComplianceRule(id);
    toast("Rule disabled", "success");
    _iso27001Loaded = false;
    navigate("compliance");
  } catch (e) { toast(e.message, "error"); }
}

// ── DevSecOps Maturity Model ───────────────────────────────────────────────

const MATURITY_GRADES = {
  Initiation:  { icon: "🥚", color: "#9ca3af", bg: "#f3f4f6" },
  Developing:  { icon: "🌱", color: "#16a34a", bg: "#f0fdf4" },
  Defined:     { icon: "⚙️",  color: "#2559a7", bg: "#eff6ff" },
  Managed:     { icon: "🏆", color: "#d97706", bg: "#fffbeb" },
  Optimizing:  { icon: "🚀", color: "#7c3aed", bg: "#f5f3ff" },
};

function _matGradeInfo(grade) { return MATURITY_GRADES[grade] || MATURITY_GRADES.Initiation; }
function _matIcon(grade)  { return _matGradeInfo(grade).icon; }
function _matColor(grade) { return _matGradeInfo(grade).color; }
function _matBg(grade)    { return _matGradeInfo(grade).bg; }

function _matGradeFromScore(score) {
  if (score >= 80) return "Optimizing";
  if (score >= 60) return "Managed";
  if (score >= 40) return "Defined";
  if (score >= 20) return "Developing";
  return "Initiation";
}

function _matXpBar(score, grade, showLabel = true) {
  const color = _matColor(grade);
  const bands = [0, 20, 40, 60, 80, 100];
  const lower = [...bands].reverse().find(b => b <= score) ?? 0;
  const upper = Math.min(lower + 20, 100);
  const pct = upper > lower ? Math.round((score - lower) / (upper - lower) * 100) : 100;
  return `<div class="mat-xp-bar-wrap">
    ${showLabel ? `<div style="font-size:11px;color:var(--gray-400);margin-bottom:3px">${score}% · ${_matIcon(grade)} ${grade}</div>` : ""}
    <div class="mat-xp-bar"><div class="mat-xp-fill" style="width:${pct}%;background:${color}"></div></div>
  </div>`;
}

function _matDimLevelBar(score) {
  return `<div class="mat-level-bar">${[1,2,3].map(i =>
    `<div class="mat-level-seg${score >= i ? " filled" : ""}"></div>`
  ).join("")}</div>`;
}

function _matDimDot(score) {
  const colors = ["#e5e7eb","#f59e0b","#3b82f6","#16a34a"];
  const labels = ["Absent","Basic","Configured","Enforced"];
  return `<span class="mat-dim-dot" style="background:${colors[score]}" title="${labels[score]}"></span>`;
}

let _matRoadmapLoaded = false;

router.register("maturity", async () => {
  setBreadcrumb({ label: "Maturity" });
  setContent(loading());
  let overview;
  try { overview = await api.getMaturityOverview(); }
  catch (e) { setContent(`<div class="card"><div class="alert alert-danger">Failed to load maturity data: ${e.message}</div></div>`); return; }

  const platGrade = _matGradeFromScore(overview.platform_avg_score);

  setContent(`
    <div class="page-header">
      <div>
        <h1>DevSecOps Maturity</h1>
        <div class="sub">Pipeline security posture across 12 dimensions</div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <span class="mat-platform-score">Platform avg: <strong style="color:${_matColor(platGrade)}">${overview.platform_avg_score}% ${_matIcon(platGrade)}</strong></span>
      </div>
    </div>

    <div class="tabs" style="margin-bottom:0">
      <button class="tab-btn active" onclick="switchTab(this,'mtab-overview')">Overview</button>
      <button class="tab-btn" onclick="switchTab(this,'mtab-roadmap');_loadMatRoadmap()">Roadmap</button>
      <button class="tab-btn" onclick="switchTab(this,'mtab-model')">Security Model</button>
    </div>

    <div id="mtab-overview" class="tab-panel active">
      ${_renderMatOverview(overview)}
    </div>

    <div id="mtab-roadmap" class="tab-panel">
      <div id="mat-roadmap-wrap">
        <div style="text-align:center;color:var(--gray-400);padding:32px">Click the Roadmap tab to load improvement plans…</div>
      </div>
    </div>

    <div id="mtab-model" class="tab-panel">
      ${_renderMatModel()}
    </div>
  `);
});

function _renderMatOverview(overview) {
  const platGrade = _matGradeFromScore(overview.platform_avg_score);
  const optimizing = overview.products.filter(p => p.score >= 80).length;

  return `
    <div class="grid grid-3" style="margin:16px 0">
      <div class="stat-tile">
        <div class="stat-label">Products Assessed</div>
        <div class="stat-value">${overview.total_products}</div>
      </div>
      <div class="stat-tile">
        <div class="stat-label">Platform Avg Score</div>
        <div class="stat-value" style="color:${_matColor(platGrade)}">${overview.platform_avg_score}%</div>
        <div class="stat-sub">${_matIcon(platGrade)} ${platGrade}</div>
      </div>
      <div class="stat-tile">
        <div class="stat-label">Optimizing Products</div>
        <div class="stat-value" style="color:#7c3aed">${optimizing}</div>
        <div class="stat-sub">score ≥ 80%</div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><h2>Product Leaderboard</h2></div>
      ${overview.products.length === 0
        ? `<div class="empty-state"><div class="empty-icon">📊</div><p>No pipelines found. Create products and pipelines to begin maturity assessment.</p></div>`
        : `<div style="padding:0 16px">${overview.products.map((p, i) => `
          <div class="mat-product-row" onclick="toggleMatProduct('${p.product_id}')">
            <div class="mat-rank">#${i+1}</div>
            <div class="mat-product-icon">${_matIcon(p.grade)}</div>
            <div class="mat-product-info">
              <div class="mat-product-name">${p.product_name}</div>
              <div class="mat-product-meta">${p.application_count ?? 0} app(s) · ${p.pipeline_count} pipeline(s) · <strong>${p.grade}</strong></div>
            </div>
            <div class="mat-xp-section">${_matXpBar(p.score, p.grade)}</div>
            <div class="mat-chevron" id="mat-chev-${p.product_id}">▾</div>
          </div>
          <div id="mat-pd-${p.product_id}" class="mat-product-detail" style="display:none"></div>
        `).join("")}</div>`
      }
    </div>`;
}

async function toggleMatProduct(productId) {
  const detail = document.getElementById("mat-pd-" + productId);
  const chev = document.getElementById("mat-chev-" + productId);
  if (!detail) return;
  const open = detail.style.display !== "none";
  detail.style.display = open ? "none" : "block";
  if (chev) chev.textContent = open ? "▾" : "▴";
  if (!open && !detail.dataset.loaded) {
    detail.innerHTML = `<div style="padding:16px;text-align:center">${loading()}</div>`;
    try {
      const data = await api.getProductMaturity(productId);
      detail.dataset.loaded = "1";
      detail.innerHTML = _renderMatProductDetail(data);
    } catch (e) {
      detail.innerHTML = `<div class="alert alert-danger" style="margin:12px">Failed: ${e.message}</div>`;
    }
  }
}

function _renderMatProductDetail(data) {
  if (!data.applications || !data.applications.length) return `<div style="padding:16px;color:var(--gray-400)">No applications found. Register application artifacts and link pipelines to begin assessment.</div>`;
  return `<div style="padding:8px 16px 16px">${data.applications.map((app, idx) => {
    const appGrade = _matGradeFromScore(app.score);
    const bodyId = `mat-app-body-${app.application_id}`;
    const chevId = `mat-app-chev-${app.application_id}`;
    return `
    <div style="margin-bottom:12px;border:1px solid var(--gray-200);border-radius:8px;overflow:hidden">
      <div class="mat-app-row" onclick="toggleMatApp('${bodyId}','${chevId}')">
        <span style="font-size:18px">${_matIcon(appGrade)}</span>
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;font-size:13px">${app.application_name}${app.build_version ? `<span style="font-size:11px;color:var(--gray-400);margin-left:6px">v${app.build_version}</span>` : ""}</div>
          <div style="font-size:11px;color:var(--gray-400)">${app.pipeline_count} pipeline(s) · <strong style="color:${_matColor(appGrade)}">${app.grade}</strong></div>
        </div>
        <div style="min-width:140px">${_matXpBar(app.score, appGrade)}</div>
        <span id="${chevId}" style="font-size:14px;color:var(--gray-400);transition:transform .2s;display:inline-block">▾</span>
      </div>
      <div id="${bodyId}" style="display:none;border-top:1px solid var(--gray-200)">
        ${!app.pipelines.length
          ? `<div style="padding:12px 16px;font-size:13px;color:var(--gray-400)">No pipelines linked to this application.</div>`
          : `<div class="table-wrap"><table style="font-size:12px">
              <thead><tr><th>Pipeline</th><th>Kind</th><th>Score</th><th>Grade</th><th>Badges</th></tr></thead>
              <tbody>${app.pipelines.map(pl => `
                <tr>
                  <td><a href="#products/${pl.product_id}/pipelines/${pl.pipeline_id}" onclick="navigate('products/${pl.product_id}/pipelines/${pl.pipeline_id}');return false;">${pl.pipeline_name}</a></td>
                  <td><span class="badge badge-${pl.pipeline_kind}">${pl.pipeline_kind.toUpperCase()}</span></td>
                  <td style="min-width:140px">${_matXpBar(pl.score, pl.grade)}</td>
                  <td><span style="font-size:16px">${_matIcon(pl.grade)}</span> <strong>${pl.grade}</strong></td>
                  <td>${(pl.badges||[]).slice(0,5).map(b => `<span class="mat-badge-chip" title="${b.level_label}">${b.icon} ${b.label}</span>`).join("")}${pl.badge_count > 5 ? `<span style="font-size:11px;color:var(--gray-400)">+${pl.badge_count-5}</span>` : ""}</td>
                </tr>`).join("")}
              </tbody>
            </table></div>`
        }
      </div>
    </div>`;
  }).join("")}</div>`;
}

function toggleMatApp(bodyId, chevId) {
  const body = document.getElementById(bodyId);
  const chev = document.getElementById(chevId);
  if (!body) return;
  const open = body.style.display !== "none";
  body.style.display = open ? "none" : "block";
  if (chev) chev.style.transform = open ? "" : "rotate(180deg)";
}

function _toggleMatPipelineDetail(bodyId) {
  const body = document.getElementById(bodyId);
  if (!body) return;
  const plId = bodyId.replace("mat-pl-body-", "");
  const chev = document.getElementById("mat-pl-chev-" + plId);
  const open = body.style.display !== "none";
  body.style.display = open ? "none" : "block";
  if (chev) chev.style.transform = open ? "" : "rotate(180deg)";
}

async function _loadMatRoadmap() {
  if (_matRoadmapLoaded) return;
  const wrap = document.getElementById("mat-roadmap-wrap");
  if (!wrap) return;
  wrap.innerHTML = loading();
  try {
    const overview = await api.getMaturityOverview();
    const details = await Promise.all(
      overview.products.map(p => api.getProductMaturity(p.product_id).catch(() => null))
    );
    _matRoadmapLoaded = true;
    wrap.innerHTML = _renderMatRoadmap(details.filter(Boolean));
  } catch (e) {
    wrap.innerHTML = `<div class="alert alert-danger">Failed to load roadmap: ${e.message}</div>`;
  }
}

function _renderMatRoadmap(products) {
  if (!products.length) return `<div class="empty-state"><div class="empty-icon">🗺️</div><p>No products found.</p></div>`;
  return products.map(prod => `
    <div style="margin-bottom:28px">
      <h2 style="margin-bottom:12px">${_matIcon(prod.grade)} ${prod.product_name}
        <span style="font-size:14px;font-weight:400;color:var(--gray-400);margin-left:8px">${prod.score}% · ${prod.grade} · ${prod.application_count ?? 0} app(s)</span>
      </h2>
      ${(!prod.applications || !prod.applications.length)
        ? `<div style="color:var(--gray-400);font-size:13px;padding:12px 0">No applications registered for this product.</div>`
        : prod.applications.map(app => {
          const appGrade = _matGradeFromScore(app.score);
          return `
          <div style="margin-bottom:16px;border:1px solid var(--gray-200);border-radius:10px;overflow:hidden">
            <div style="padding:12px 16px;background:var(--gray-50);display:flex;align-items:center;gap:10px;flex-wrap:wrap">
              <span style="font-size:20px">${_matIcon(appGrade)}</span>
              <div style="flex:1;min-width:0">
                <div style="font-weight:700;font-size:14px">${app.application_name}${app.build_version ? `<span style="font-size:11px;font-weight:400;color:var(--gray-400);margin-left:6px">v${app.build_version}</span>` : ""}</div>
                <div style="font-size:11px;color:var(--gray-400)">${app.pipeline_count} pipeline(s) · <strong style="color:${_matColor(appGrade)}">${app.grade}</strong> · ${app.score}%</div>
              </div>
              ${_matXpBar(app.score, appGrade, false)}
              <span class="mat-grade-pill" style="background:${_matColor(appGrade)}">${app.grade}</span>
            </div>
            ${(!app.pipelines || !app.pipelines.length)
              ? `<div style="padding:12px 16px;font-size:13px;color:var(--gray-400)">No pipelines linked.</div>`
              : app.pipelines.map(pl => `
                <div class="mat-roadmap-pipeline-card" style="border-top:1px solid var(--gray-200);margin:0;border-radius:0">
                  <div class="mat-roadmap-pipeline-header" onclick="_toggleMatPipelineDetail('mat-pl-body-${pl.pipeline_id}')" style="cursor:pointer">
                    <span style="font-size:20px">${_matIcon(pl.grade)}</span>
                    <div style="flex:1">
                      <div style="font-weight:600">${pl.pipeline_name}</div>
                      <div style="font-size:12px;color:var(--gray-400)">${pl.score}% · ${pl.grade} · ${pl.stage_count} stages · ${pl.task_count} tasks</div>
                    </div>
                    ${_matXpBar(pl.score, pl.grade, false)}
                    <span class="mat-grade-pill" style="background:${_matColor(pl.grade)}">${pl.grade}</span>
                    <span id="mat-pl-chev-${pl.pipeline_id}" style="font-size:13px;color:var(--gray-400);margin-left:8px;transition:transform .2s;display:inline-block">▾</span>
                  </div>
                  <div id="mat-pl-body-${pl.pipeline_id}" style="display:none">
                    ${pl.next_milestone.next_grade !== pl.grade ? `
                    <div class="mat-milestone-card" style="margin:12px 16px 0">
                      <div class="mat-milestone-title">🎯 Next: ${_matIcon(pl.next_milestone.next_grade)} ${pl.next_milestone.next_grade} (need ${pl.next_milestone.points_needed} more points)</div>
                      <div style="font-size:12px;color:var(--gray-600)">
                        <strong>${pl.next_milestone.suggested_icon} ${pl.next_milestone.suggested_label}</strong> is your biggest gap
                        (currently ${["Absent","Basic","Configured","Enforced"][pl.next_milestone.current_dim_score]}) —
                        ${pl.next_milestone.action_hint}
                      </div>
                    </div>` : `
                    <div style="margin:12px 16px 0;padding:10px 14px;border-radius:8px;background:#f0fdf4;border:1px solid #86efac;font-size:13px;color:#16a34a;font-weight:600">
                      🚀 All dimensions fully enforced! Excellent DevSecOps posture.
                    </div>`}
                    <div class="mat-dim-grid" style="padding:12px 16px">
                      ${(pl.dimensions||[]).map(d => _renderMatDimCard(d)).join("")}
                    </div>
                  </div>
                </div>`).join("")}
          </div>`;
        }).join("")}
    </div>
  `).join("");
}

function _renderMatDimCard(d) {
  if (d.applicable === false) {
    return `<div class="mat-dim-card" style="opacity:0.35;border-color:var(--gray-100);background:var(--gray-50)">
      <div class="mat-dim-card-header">
        <span style="font-size:16px">${d.icon}</span>
        <div><div style="font-weight:600;font-size:12px;color:var(--gray-400)">${d.label}</div>
          <div style="font-size:10px;color:var(--gray-400)">N/A for this pipeline kind</div>
        </div>
      </div>
    </div>`;
  }
  return `<div class="mat-dim-card" style="border-color:${d.score===3?"#86efac":d.score===2?"#93c5fd":d.score===1?"#fde68a":"var(--gray-200)"}">
    <div class="mat-dim-card-header">
      <span style="font-size:16px">${d.icon}</span>
      <div>
        <div style="font-weight:600;font-size:12px">${d.label}</div>
        ${_matDimLevelBar(d.score)}
      </div>
      ${d.score===3?`<span style="margin-left:auto;font-size:12px">✅</span>`:""}
    </div>
    <div style="font-size:11px;color:var(--gray-400);margin-bottom:4px">${["Absent","Basic","Configured","Enforced"][d.score]}</div>
    ${d.matched_tasks.length ? `<div style="font-size:10.5px;color:#3b82f6">📌 ${d.matched_tasks.slice(0,2).join(", ")}</div>` : ""}
    ${d.score < 3 ? `<div style="font-size:10.5px;color:var(--gray-500);margin-top:4px;line-height:1.4">${d.action_hint}</div>` : ""}
  </div>`;
}

function _renderMatModel() {
  return `
    <div style="max-width:860px;margin-top:16px">
      <div class="mat-model-section">
        <h3>What is the DevSecOps Maturity Model?</h3>
        <p style="color:var(--gray-600);font-size:13px;line-height:1.7">
          The Conduit Maturity Model evaluates each pipeline against 12 security and quality
          dimensions derived from industry best practices (OWASP, NIST SSDF, SLSA, CIS Controls).
          Maturity is computed automatically by analysing your task names, descriptions, and scripts —
          no manual scoring required.
        </p>
      </div>

      <div class="mat-model-section">
        <h3>Grade Levels</h3>
        <table class="mat-grade-table">
          <thead><tr><th>Grade</th><th>Score</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td>🥚 Initiation</td><td>0–19%</td><td>Security is ad hoc. No consistent tooling or enforcement.</td></tr>
            <tr><td>🌱 Developing</td><td>20–39%</td><td>Some security tasks exist but are not required or enforced.</td></tr>
            <tr><td>⚙️ Defined</td><td>40–59%</td><td>Key security dimensions covered; tooling configured with specific parameters.</td></tr>
            <tr><td>🏆 Managed</td><td>60–79%</td><td>Most dimensions enforced. Security gates and compliance checks in place.</td></tr>
            <tr><td>🚀 Optimizing</td><td>80–100%</td><td>All critical dimensions enforced at maximum level. Continuous improvement culture.</td></tr>
          </tbody>
        </table>
      </div>

      <div class="mat-model-section">
        <h3>Scoring Per Dimension (0–3)</h3>
        <table class="mat-grade-table">
          <thead><tr><th>Level</th><th>Criteria</th></tr></thead>
          <tbody>
            <tr><td>0 Absent</td><td>No task matching the dimension's tool keywords found in the pipeline</td></tr>
            <tr><td>1 Basic</td><td>A matching task exists but uses default settings</td></tr>
            <tr><td>2 Configured</td><td>Matching task has a specific name/non-default timeout indicating intentional configuration</td></tr>
            <tr><td>3 Enforced</td><td>Task is configured AND marked <code>is_required=true</code> with <code>on_error=fail</code> — will block the pipeline on failure</td></tr>
          </tbody>
        </table>
      </div>

      <div class="mat-model-section">
        <h3>The 12 Dimensions</h3>
        <div class="mat-dim-grid">
          ${[
            {icon:"🔍",label:"SAST",desc:"Static code analysis for security vulnerabilities"},
            {icon:"📦",label:"SCA",desc:"Open-source dependency vulnerability scanning"},
            {icon:"🌐",label:"DAST",desc:"Dynamic scanning of running application"},
            {icon:"🧪",label:"Unit Testing",desc:"Automated unit test suite"},
            {icon:"🔗",label:"Integration Testing",desc:"API and service integration tests"},
            {icon:"📊",label:"Code Coverage",desc:"Test coverage measurement and thresholds"},
            {icon:"💨",label:"Smoke Testing",desc:"Post-deploy health and sanity checks"},
            {icon:"🏷️",label:"Release Practices",desc:"Semantic versioning, changelogs, tagging"},
            {icon:"🚀",label:"Env Promotion",desc:"Gate-based promotion between environments"},
            {icon:"🔐",label:"Security Gates",desc:"Policy enforcement and manual approvals"},
            {icon:"🐳",label:"Container Security",desc:"Image scanning and signing"},
            {icon:"🕵️",label:"Secret Scanning",desc:"Detection of leaked credentials in code"},
          ].map(d => `
            <div class="mat-dim-card">
              <div class="mat-dim-card-header"><span style="font-size:18px">${d.icon}</span><strong style="font-size:12px">${d.label}</strong></div>
              <div style="font-size:11.5px;color:var(--gray-500)">${d.desc}</div>
            </div>`).join("")}
        </div>
      </div>

      <div class="mat-model-section">
        <h3>Score Formula</h3>
        <div style="background:var(--gray-900);border:1px solid var(--gray-700);border-radius:8px;padding:14px;font-size:13px;font-family:monospace;color:#e2e8f0">
          score = Σ (dimension_level × dimension_weight) / (Σ max_weights × 3) × 100
        </div>
        <p style="font-size:12px;color:var(--gray-400);margin-top:8px">
          Weights reflect importance: SAST, SCA, Security Gates (w=4 each) · Unit Testing, Release Practices, Env Promotion (w=3 each) · DAST, Integration Testing (w=3) · Coverage, Smoke Testing, Secret Scanning (w=2 each)
        </p>
      </div>

      <div class="mat-model-section">
        <h3>How to Reach Optimizing</h3>
        <ol style="font-size:13px;line-height:2;color:var(--gray-600);padding-left:20px">
          <li>Add SAST tasks (SonarQube, Semgrep, Bandit) with <code>on_error=fail</code></li>
          <li>Add SCA tasks (Trivy, Grype, pip-audit) to catch vulnerable dependencies</li>
          <li>Add Security Gates (OPA/Conftest policy checks) before production deployments</li>
          <li>Enforce unit + integration tests — set <code>is_required=true</code></li>
          <li>Add container image scanning and secret scanning to your CI pipeline</li>
          <li>Implement DAST scanning against staging environments</li>
          <li>Add smoke tests after every deployment</li>
          <li>Protect critical stages to prevent bypassing security controls</li>
        </ol>
      </div>
    </div>
  `;
}

// ── Application Dictionary ──────────────────────────────────────────────────

const COMPLIANCE_DOT_COLOR = {
  "Platinum": "#7c3aed", "Gold": "#d97706", "Silver": "#6b7280",
  "Bronze": "#92400e", "Non-Compliant": "#dc2626",
};

function _appDictComplianceDot(rating) {
  const color = COMPLIANCE_DOT_COLOR[rating] || "#dc2626";
  return `<span class="compliance-dot" style="background:${color}"></span>`;
}

router.register("app-dictionary", async () => {
  setBreadcrumb({ label: "App Dictionary" });
  setContent(loading());
  const products = await api.getProducts().catch(() => []);
  // Load all applications across all products
  const appLists = await Promise.all(products.map(p => api.getAppDictionary(p.id).catch(() => [])));
  const allApps = appLists.flatMap((apps, i) => apps.map(a => ({ ...a, _product_name: products[i].name })));

  const ratings = ["Platinum","Gold","Silver","Bronze","Non-Compliant"];

  setContent(`
    <div class="page-header">
      <div><h1>Application Dictionary</h1>
           <div class="sub">All application artifacts and their build versions</div></div>
      <button class="btn btn-primary" onclick="showCreateAppDictEntry()">+ Register Artifact</button>
    </div>

    <div class="appdict-filter-row">
      <input id="adict-search" class="form-control" style="max-width:220px" placeholder="Search name or version…" oninput="filterAppDict()">
      <select id="adict-product" class="form-control" style="max-width:200px" onchange="filterAppDict()">
        <option value="">All Products</option>
        ${products.map(p => `<option value="${p.id}">${p.name}</option>`).join("")}
      </select>
      <select id="adict-rating" class="form-control" style="max-width:180px" onchange="filterAppDict()">
        <option value="">All Ratings</option>
        ${ratings.map(r => `<option value="${r}">${r}</option>`).join("")}
      </select>
      <select id="adict-type" class="form-control" style="max-width:160px" onchange="filterAppDict()">
        <option value="">All Types</option>
        <option value="container">Container</option>
        <option value="library">Library</option>
        <option value="package">Package</option>
      </select>
      <button class="btn btn-secondary btn-sm" onclick="clearAppDictFilters()">Clear</button>
      <span id="adict-count" style="font-size:12px;color:var(--gray-400)"></span>
    </div>

    <div class="card">
      ${allApps.length === 0
        ? `<div class="empty-state"><div class="empty-icon">📚</div>
           <p>No application artifacts registered yet. <a href="#products">Create a product and application first.</a></p></div>`
        : `<div class="table-wrap">
          <table id="adict-table">
            <thead><tr>
              <th>Application</th>
              <th>Build Version</th>
              <th>Type</th>
              <th>Product</th>
              <th>Compliance</th>
              <th>Repository</th>
              <th>Registered</th>
              <th>Actions</th>
            </tr></thead>
            <tbody>${allApps.map(a => `
              <tr data-product="${a.product_id||""}" data-rating="${a.compliance_rating||"Non-Compliant"}" data-type="${a.artifact_type||""}">
                <td>
                  <div style="font-weight:600">${a.name}</div>
                  ${a.description ? `<div style="font-size:11.5px;color:var(--gray-400)">${a.description}</div>` : ""}
                </td>
                <td><code style="font-size:12px">${a.build_version || "—"}</code></td>
                <td><span class="badge badge-blue">${a.artifact_type}</span></td>
                <td>${a._product_name}</td>
                <td>${_appDictComplianceDot(a.compliance_rating)}${ratingBadge(a.compliance_rating)}</td>
                <td>${a.repository_url ? `<a href="${a.repository_url}" target="_blank" style="font-size:12px;word-break:break-all">${a.repository_url.replace(/^https?:\/\//,"").slice(0,40)}${a.repository_url.length>45?"…":""}</a>` : "—"}</td>
                <td style="color:var(--gray-400);font-size:12px">${fmtDate(a.created_at)}</td>
                <td style="display:flex;gap:4px;flex-wrap:wrap">
                  <button class="btn btn-secondary btn-sm" onclick="showEditAppDictEntry('${a.product_id}','${a.id}','${a.name.replace(/'/g,"\\'")}','${(a.build_version||"").replace(/'/g,"\\'")}','${a.artifact_type}','${(a.repository_url||"").replace(/'/g,"\\'")}','${a.compliance_rating||"Non-Compliant"}','${(a.description||"").replace(/'/g,"\\'")}')">Edit</button>
                  <button class="btn btn-danger btn-sm" onclick="deleteAppDictEntry('${a.product_id}','${a.id}','${a.name.replace(/'/g,"\\'")}')">Delete</button>
                </td>
              </tr>`).join("")}
            </tbody>
          </table>
          </div>`
      }

      <!-- Summary stats -->
      ${allApps.length > 0 ? `
      <div style="padding:12px 0;border-top:1px solid var(--gray-200);margin-top:8px">
        <div style="display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--gray-600)">
          ${ratings.map(r => {
            const n = allApps.filter(a => (a.compliance_rating || "Non-Compliant") === r).length;
            return n > 0 ? `<span>${_appDictComplianceDot(r)}<strong>${r}</strong>: ${n}</span>` : "";
          }).join("")}
        </div>
      </div>` : ""}
    </div>
  `);
  filterAppDict();
});

function filterAppDict() {
  const search = (document.getElementById("adict-search")?.value || "").toLowerCase();
  const productFilter = document.getElementById("adict-product")?.value || "";
  const ratingFilter = document.getElementById("adict-rating")?.value || "";
  const typeFilter = document.getElementById("adict-type")?.value || "";
  const rows = document.querySelectorAll("#adict-table tbody tr");
  let shown = 0;
  rows.forEach(row => {
    const text = row.textContent.toLowerCase();
    const matchSearch = !search || text.includes(search);
    const matchProduct = !productFilter || row.dataset.product === productFilter;
    const matchRating = !ratingFilter || row.dataset.rating === ratingFilter;
    const matchType = !typeFilter || row.dataset.type === typeFilter;
    const visible = matchSearch && matchProduct && matchRating && matchType;
    row.style.display = visible ? "" : "none";
    if (visible) shown++;
  });
  const countEl = document.getElementById("adict-count");
  if (countEl) countEl.textContent = `${shown} of ${rows.length} entries`;
}

function clearAppDictFilters() {
  ["adict-search","adict-product","adict-rating","adict-type"].forEach(id => {
    const el2 = document.getElementById(id);
    if (el2) el2.value = "";
  });
  filterAppDict();
}

async function showCreateAppDictEntry() {
  const products = await api.getProducts().catch(() => []);
  openModal("Register Application Artifact",
    `<div class="form-group"><label>Product *</label>
       <select id="adce-product" class="form-control">
         <option value="">— Select product —</option>
         ${products.map(p => `<option value="${p.id}">${p.name}</option>`).join("")}
       </select></div>
     <div class="form-group"><label>Application Name *</label>
       <input id="adce-name" class="form-control" placeholder="e.g. payment-service"></div>
     <div class="form-group"><label>Build Version</label>
       <input id="adce-version" class="form-control" placeholder="e.g. 2.4.1 or main-abc123"></div>
     <div class="form-group"><label>Artifact Type</label>
       <select id="adce-type" class="form-control">
         <option value="container">Container</option>
         <option value="library">Library</option>
         <option value="package">Package</option>
       </select></div>
     <div class="form-group"><label>Compliance Rating</label>
       <select id="adce-rating" class="form-control">
         <option value="Non-Compliant">Non-Compliant</option>
         <option value="Bronze">Bronze</option>
         <option value="Silver">Silver</option>
         <option value="Gold">Gold</option>
         <option value="Platinum">Platinum</option>
       </select></div>
     <div class="form-group"><label>Repository URL</label>
       <input id="adce-repo" class="form-control" placeholder="https://github.com/org/repo"></div>
     <div class="form-group"><label>Description</label>
       <input id="adce-desc" class="form-control" placeholder="Optional description"></div>`,
    async () => {
      const productId = document.getElementById("adce-product")?.value;
      const name = document.getElementById("adce-name")?.value.trim();
      if (!productId) { modalError("Please select a product"); return; }
      if (!name) { modalError("Application name is required"); return; }
      await api.createAppDictionaryEntry(productId, {
        name,
        build_version: document.getElementById("adce-version")?.value.trim() || null,
        artifact_type: document.getElementById("adce-type")?.value || "container",
        compliance_rating: document.getElementById("adce-rating")?.value || "Non-Compliant",
        repository_url: document.getElementById("adce-repo")?.value.trim() || null,
        description: document.getElementById("adce-desc")?.value.trim() || null,
      });
      toast("Artifact registered", "success");
      navigate("app-dictionary");
    },
    "Register"
  );
}

function showEditAppDictEntry(productId, appId, name, buildVersion, artifactType, repoUrl, rating, description) {
  openModal("Edit Application Artifact",
    `<div class="form-group"><label>Application Name *</label>
       <input id="ade-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Build Version</label>
       <input id="ade-version" class="form-control" value="${buildVersion}"></div>
     <div class="form-group"><label>Artifact Type</label>
       <select id="ade-type" class="form-control">
         ${["container","library","package"].map(t => `<option value="${t}"${t===artifactType?" selected":""}>${t.charAt(0).toUpperCase()+t.slice(1)}</option>`).join("")}
       </select></div>
     <div class="form-group"><label>Compliance Rating</label>
       <select id="ade-rating" class="form-control">
         ${["Non-Compliant","Bronze","Silver","Gold","Platinum"].map(r => `<option value="${r}"${r===rating?" selected":""}>${r}</option>`).join("")}
       </select></div>
     <div class="form-group"><label>Repository URL</label>
       <input id="ade-repo" class="form-control" value="${repoUrl}"></div>
     <div class="form-group"><label>Description</label>
       <input id="ade-desc" class="form-control" value="${description}"></div>`,
    async () => {
      const newName = document.getElementById("ade-name")?.value.trim();
      if (!newName) { modalError("Name is required"); return; }
      await api.updateAppDictionaryEntry(productId, appId, {
        name: newName,
        build_version: document.getElementById("ade-version")?.value.trim() || null,
        artifact_type: document.getElementById("ade-type")?.value,
        compliance_rating: document.getElementById("ade-rating")?.value,
        repository_url: document.getElementById("ade-repo")?.value.trim() || null,
        description: document.getElementById("ade-desc")?.value.trim() || null,
      });
      toast("Artifact updated", "success");
      navigate("app-dictionary");
    }
  );
}

async function deleteAppDictEntry(productId, appId, name) {
  if (!confirm(`Delete artifact "${name}"?`)) return;
  try {
    await api.deleteAppDictionaryEntry(productId, appId);
    toast("Artifact deleted", "success");
    navigate("app-dictionary");
  } catch (e) { toast(e.message, "error"); }
}

// ── Administration (Users / Groups / Roles) ────────────────────────────────

const PERSONAS = [
  "PlatformAdmin", "ProductOwner", "ReleaseManager", "PipelineAuthor",
  "Deployer", "Approver", "ComplianceAdmin", "ReadOnly",
];

const PERSONA_COLOR = {
  PlatformAdmin: "badge-platinum", ProductOwner: "badge-gold",
  ReleaseManager: "badge-gold", PipelineAuthor: "badge-blue",
  Deployer: "badge-running", Approver: "badge-success",
  ComplianceAdmin: "badge-bronze", ReadOnly: "badge-silver",
};

function personaBadge(p) {
  return `<span class="badge ${PERSONA_COLOR[p] || "badge-silver"}">${p || "—"}</span>`;
}

// ── Vault ──────────────────────────────────────────────────────────────────
router.register("vault", async () => {
  setBreadcrumb({ label: "Secrets Vault" });
  setContent(loading());
  const secrets = await api.listSecrets().catch(() => []);
  setContent(`
    <div class="page-header">
      <div><h1>Secrets Vault</h1><div class="sub">Encrypted secrets storage — values are never exposed in logs or API responses</div></div>
      <button class="btn btn-primary" onclick="showCreateSecret()">+ New Secret</button>
    </div>
    ${secrets.length === 0
      ? `<div class="card"><div class="empty-state"><div class="empty-icon">🔐</div><p>No secrets yet. Create your first secret to get started.</p></div></div>`
      : `<div class="card"><div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Description</th><th>Allowed Users</th><th>Created By</th><th>Updated</th><th>Actions</th></tr></thead>
          <tbody>${secrets.map(s => `
            <tr>
              <td><strong>${s.name}</strong></td>
              <td style="color:var(--gray-600)">${s.description || "—"}</td>
              <td><code style="font-size:11px">${s.allowed_users || "*"}</code></td>
              <td>${s.created_by}</td>
              <td style="color:var(--gray-400)">${fmtDate(s.updated_at)}</td>
              <td style="display:flex;gap:4px;flex-wrap:wrap">
                <button class="btn btn-secondary btn-sm" onclick="revealSecret('${s.id}','${s.name.replace(/'/g,"\\'")}')">👁 Reveal</button>
                <button class="btn btn-secondary btn-sm" onclick="showEditSecret('${s.id}','${s.name.replace(/'/g,"\\'")}','${(s.description||"").replace(/'/g,"\\'")}','${s.allowed_users||"*"}')">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteSecret('${s.id}','${s.name.replace(/'/g,"\\'")}')">Delete</button>
              </td>
            </tr>`).join("")}
          </tbody></table></div></div>`
    }
  `);
});

function showCreateSecret() {
  openModal("New Secret",
    `<div class="form-group"><label>Name <span style="color:var(--danger)">*</span></label>
       <input id="sec-name" class="form-control" placeholder="e.g. DB_PASSWORD"></div>
     <div class="form-group"><label>Value <span style="color:var(--danger)">*</span></label>
       <input id="sec-value" class="form-control" type="password" placeholder="secret value"></div>
     <div class="form-group"><label>Description</label>
       <input id="sec-desc" class="form-control" placeholder="What is this secret used for?"></div>
     <div class="form-group"><label>Allowed Users</label>
       <input id="sec-users" class="form-control" value="*" placeholder="* for all admins, or comma-separated usernames">
       <small style="color:var(--gray-500)">Use <code>*</code> for all admins, or list usernames: <code>alice,bob</code></small></div>`,
    async () => {
      const name = el("sec-name").value.trim();
      const value = el("sec-value").value;
      if (!name || !value) throw new Error("Name and value are required");
      await api.createSecret({
        name,
        value,
        description: el("sec-desc").value.trim(),
        allowed_users: el("sec-users").value.trim() || "*",
      });
      toast("Secret created", "success");
      navigate("vault");
    },
    "Create Secret"
  );
}

async function revealSecret(secretId, secretName) {
  openModal(`Reveal Secret — ${secretName}`,
    `<div id="reveal-loading" style="text-align:center;padding:24px;color:var(--gray-500)">Decrypting…</div>
     <div id="reveal-value" style="display:none">
       <label style="font-size:12px;color:var(--gray-600);margin-bottom:6px;display:block">Secret value:</label>
       <div style="position:relative">
         <input id="reveal-input" class="form-control" type="text" readonly
           style="font-family:monospace;font-size:13px;background:var(--gray-50);padding-right:80px">
         <button class="btn btn-secondary btn-sm"
           style="position:absolute;right:6px;top:50%;transform:translateY(-50%)"
           onclick="navigator.clipboard.writeText(document.getElementById('reveal-input').value);toast('Copied','success')">Copy</button>
       </div>
       <p style="font-size:12px;color:var(--gray-400);margin-top:8px">This value is only visible in this session. Close the modal to dismiss.</p>
     </div>`,
    null, null
  );
  setTimeout(async () => {
    try {
      const res = await api.revealSecret(secretId);
      const loadingEl = document.getElementById("reveal-loading");
      const valueEl = document.getElementById("reveal-value");
      const inputEl = document.getElementById("reveal-input");
      if (loadingEl) loadingEl.style.display = "none";
      if (valueEl) valueEl.style.display = "";
      if (inputEl) inputEl.value = res.value;
    } catch (e) {
      const loadingEl = document.getElementById("reveal-loading");
      if (loadingEl) loadingEl.innerHTML = `<span style="color:var(--danger)">✗ ${e.message}</span>`;
    }
  }, 50);
}

function showEditSecret(secretId, name, description, allowedUsers) {
  openModal(`Edit Secret — ${name}`,
    `<div class="form-group"><label>New Value <small style="color:var(--gray-400)">(leave blank to keep current)</small></label>
       <input id="esec-value" class="form-control" type="password" placeholder="new secret value"></div>
     <div class="form-group"><label>Description</label>
       <input id="esec-desc" class="form-control" value="${description}"></div>
     <div class="form-group"><label>Allowed Users</label>
       <input id="esec-users" class="form-control" value="${allowedUsers}"></div>`,
    async () => {
      const payload = {
        description: el("esec-desc").value.trim(),
        allowed_users: el("esec-users").value.trim() || "*",
      };
      const v = el("esec-value").value;
      if (v) payload.value = v;
      await api.updateSecret(secretId, payload);
      toast("Secret updated", "success");
      navigate("vault");
    },
    "Save"
  );
}

async function deleteSecret(secretId, secretName) {
  if (!confirm(`Delete secret "${secretName}"? This cannot be undone.`)) return;
  try {
    await api.deleteSecret(secretId);
    toast("Secret deleted", "success");
    navigate("vault");
  } catch (e) { toast(e.message, "error"); }
}

// ── Webhooks page ─────────────────────────────────────────────────────────
router.register("webhooks", async () => {
  setBreadcrumb({ label: "Webhooks" });
  setContent(loading());
  const webhooks = await api.listWebhooks().catch(() => []);
  setContent(`
    <div class="page-header">
      <div><h1>Webhooks</h1><div class="sub">Inbound HTTP triggers that start pipeline runs</div></div>
      <button class="btn btn-primary" onclick="showCreateWebhook()">+ New Webhook</button>
    </div>
    ${webhooks.length === 0
      ? `<div class="card"><div class="empty-state"><div class="empty-icon">🔗</div><p>No webhooks yet.</p></div></div>`
      : `<div class="card"><div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Pipeline</th><th>Status</th><th>Created By</th><th>Trigger URL</th><th>Actions</th></tr></thead>
          <tbody>${webhooks.map(w => `
            <tr>
              <td><strong>${w.name}</strong>${w.description ? `<br><small style="color:var(--gray-500)">${w.description}</small>` : ""}</td>
              <td><code style="font-size:11px">${w.pipeline_id}</code></td>
              <td><span class="badge ${w.is_active ? "badge-success" : "badge-silver"}">${w.is_active ? "Active" : "Disabled"}</span></td>
              <td>${w.created_by}</td>
              <td><code style="font-size:10px;word-break:break-all">/api/v1/webhooks/${w.id}/trigger</code></td>
              <td style="display:flex;gap:4px;flex-wrap:wrap">
                <button class="btn btn-primary btn-sm" onclick="showTestWebhook('${w.id}','${w.name.replace(/'/g,"\\'")}')">⚡ Test</button>
                <button class="btn btn-secondary btn-sm" onclick="showWebhookDeliveries('${w.id}','${w.name.replace(/'/g,"\\'")}')">Deliveries</button>
                <button class="btn btn-secondary btn-sm" onclick="toggleWebhook('${w.id}',${w.is_active})">${w.is_active ? "Disable" : "Enable"}</button>
                <button class="btn btn-danger btn-sm" onclick="deleteWebhook('${w.id}','${w.name.replace(/'/g,"\\'")}')">Delete</button>
              </td>
            </tr>`).join("")}
          </tbody></table></div></div>`
    }
    <div class="card" style="margin-top:16px;background:var(--gray-50)">
      <div class="card-header"><h2>How to trigger</h2></div>
      <pre style="font-size:12px;padding:12px;background:#111;color:#e5e7eb;border-radius:6px;overflow-x:auto">curl -X POST https://your-host/api/v1/webhooks/&lt;id&gt;/trigger \\
  -H "X-Webhook-Token: &lt;token&gt;" \\
  -H "Content-Type: application/json" \\
  -d '{"commit_sha": "abc123", "triggered_by": "ci"}'</pre>
    </div>
  `);
});

async function showCreateWebhook() {
  // Load all pipelines across all products for the dropdown
  let pipelineOptions = `<option value="">Loading pipelines…</option>`;
  openModal("New Webhook",
    `<div class="form-group"><label>Name *</label>
       <input id="wh-name" class="form-control" placeholder="e.g. GitHub Push Trigger"></div>
     <div class="form-group"><label>Pipeline *</label>
       <select id="wh-pipeline" class="form-control">${pipelineOptions}</select></div>
     <div class="form-group"><label>Description</label>
       <input id="wh-desc" class="form-control" placeholder="When is this triggered?"></div>`,
    async () => {
      const name = el("wh-name").value.trim();
      const pipelineId = el("wh-pipeline").value.trim();
      if (!name || !pipelineId) throw new Error("Name and Pipeline are required");
      const result = await api.createWebhook({
        name, pipeline_id: pipelineId,
        description: el("wh-desc").value.trim(),
      });
      closeModal();
      openModal("Webhook Created — Save Your Token",
        `<p style="margin-bottom:12px;color:var(--gray-600)">This token will not be shown again. Copy it now.</p>
         <input class="form-control" id="wh-token-display" value="${result.token}" readonly style="font-family:monospace;font-size:13px">
         <button class="btn btn-secondary btn-sm" style="margin-top:8px" onclick="navigator.clipboard.writeText(document.getElementById('wh-token-display').value)">Copy to clipboard</button>`,
        () => { closeModal(); navigate("webhooks"); }, "Done"
      );
    },
    "Create"
  );

  // Populate pipeline dropdown asynchronously
  try {
    const products = await api.getProducts();
    const pipelineLists = await Promise.all(products.map(p => api.getPipelines(p.id).catch(() => [])));
    const allPipelines = products.flatMap((p, i) =>
      (pipelineLists[i] || []).map(pl => ({ ...pl, productName: p.name }))
    );
    const sel = document.getElementById("wh-pipeline");
    if (!sel) return;
    if (allPipelines.length === 0) {
      sel.innerHTML = `<option value="">No pipelines found</option>`;
    } else {
      sel.innerHTML = `<option value="">Select a pipeline…</option>` +
        allPipelines.map(pl => `<option value="${pl.id}">${pl.productName} / ${pl.name}</option>`).join("");
    }
  } catch {
    const sel = document.getElementById("wh-pipeline");
    if (sel) sel.innerHTML = `<option value="">Failed to load pipelines</option>`;
  }
}

async function showWebhookDeliveries(webhookId, webhookName) {
  openModal(`Deliveries — ${webhookName}`,
    `<div id="wh-deliveries-loading" style="text-align:center;padding:24px;color:var(--gray-500)">Loading…</div>`,
    null, null
  );
  setTimeout(async () => {
    const container = document.getElementById("wh-deliveries-loading");
    if (!container) return;
    try {
      const deliveries = await api.getWebhookDeliveries(webhookId);
      if (!deliveries.length) { container.innerHTML = "<p>No deliveries yet.</p>"; return; }
      container.outerHTML = `<div class="table-wrap"><table>
        <thead><tr><th>Time</th><th>Status</th><th>Pipeline Run</th></tr></thead>
        <tbody>${deliveries.map(d => `
          <tr>
            <td style="color:var(--gray-400)">${fmtDate(d.triggered_at)}</td>
            <td><span class="badge ${d.status==="triggered"?"badge-success":"badge-failed"}">${d.status}</span></td>
            <td><code style="font-size:11px">${d.pipeline_run_id||"—"}</code></td>
          </tr>`).join("")}
        </tbody></table></div>`;
    } catch (e) { container.innerHTML = `<span style="color:var(--danger)">${e.message}</span>`; }
  }, 50);
}

async function toggleWebhook(webhookId, isActive) {
  try {
    await api.updateWebhook(webhookId, { is_active: !isActive });
    toast(`Webhook ${isActive ? "disabled" : "enabled"}`, "success");
    navigate("webhooks");
  } catch (e) { toast(e.message, "error"); }
}

async function deleteWebhook(webhookId, name) {
  if (!confirm(`Delete webhook "${name}"?`)) return;
  try {
    await api.deleteWebhook(webhookId);
    toast("Webhook deleted", "success");
    navigate("webhooks");
  } catch (e) { toast(e.message, "error"); }
}

function showTestWebhook(webhookId, webhookName) {
  const samplePayload = JSON.stringify({
    commit_sha: "abc1234def5678",
    triggered_by: "manual-test",
    ref: "refs/heads/main",
    repository: { name: "my-repo", full_name: "org/my-repo" },
  }, null, 2);

  openModal(`Test Webhook — ${webhookName}`,
    `<div class="form-group">
       <label>Token</label>
       <div style="display:flex;gap:6px;align-items:center">
         <input id="wht-token" class="form-control" type="password" placeholder="Fetching token…" style="flex:1" readonly>
         <button class="btn btn-secondary btn-sm" type="button" onclick="
           const i=document.getElementById('wht-token');
           i.type=i.type==='password'?'text':'password'">Show</button>
       </div>
       <div id="wht-token-status" style="font-size:11px;color:var(--gray-500);margin-top:4px">Retrieving token…</div>
     </div>
     <div class="form-group">
       <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
         <label style="margin:0">Payload (JSON)</label>
         <div style="display:flex;gap:4px">
           <button class="btn btn-secondary btn-sm" type="button" style="font-size:11px"
             onclick="document.getElementById('wht-payload').value=JSON.stringify({commit_sha:'abc1234',triggered_by:'test',ref:'refs/heads/main'},null,2)">GitHub Push</button>
           <button class="btn btn-secondary btn-sm" type="button" style="font-size:11px"
             onclick="document.getElementById('wht-payload').value=JSON.stringify({commit_sha:'abc1234',triggered_by:'ci',artifact_id:'build-42'},null,2)">CI Build</button>
           <button class="btn btn-secondary btn-sm" type="button" style="font-size:11px"
             onclick="document.getElementById('wht-payload').value='{}'">Empty</button>
         </div>
       </div>
       <textarea id="wht-payload" class="form-control" rows="8" spellcheck="false"
         style="font-family:monospace;font-size:12px;resize:vertical">${samplePayload}</textarea>
     </div>
     <div id="wht-result" style="display:none;margin-top:4px;border-radius:8px;padding:12px;font-size:13px"></div>`,
    _sendWebhookTest.bind(null, webhookId),
    "⚡ Send"
  );

  // Auto-fetch token after modal renders
  api.getWebhookToken(webhookId).then(data => {
    const tokenEl = document.getElementById("wht-token");
    const statusEl = document.getElementById("wht-token-status");
    if (tokenEl) {
      tokenEl.value = data.token;
      tokenEl.placeholder = "";
    }
    if (statusEl) statusEl.textContent = "Token retrieved automatically.";
  }).catch(() => {
    const tokenEl = document.getElementById("wht-token");
    const statusEl = document.getElementById("wht-token-status");
    if (tokenEl) { tokenEl.placeholder = "Paste the webhook token here"; tokenEl.removeAttribute("readonly"); }
    if (statusEl) statusEl.textContent = "Could not retrieve token — paste it manually.";
  });
}

async function _sendWebhookTest(webhookId) {
  const tokenEl = el("wht-token");
  const payloadEl = el("wht-payload");
  const resultEl = el("wht-result");
  const sendBtn = el("modal-confirm");

  const token = tokenEl?.value.trim();
  if (!token) { modalError("Token is required"); return; }

  let payload;
  try {
    payload = JSON.parse(payloadEl?.value || "{}");
  } catch {
    modalError("Payload must be valid JSON");
    return;
  }

  if (resultEl) resultEl.style.display = "none";
  if (sendBtn) { sendBtn.disabled = true; sendBtn.textContent = "Sending…"; }

  try {
    const res = await fetch(`/api/v1/webhooks/${webhookId}/trigger`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Webhook-Token": token,
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));

    if (resultEl) {
      resultEl.style.display = "";
      if (res.ok) {
        resultEl.style.cssText = "display:block;margin-top:4px;border-radius:8px;padding:12px;font-size:13px;background:#f0fdf4;border:1px solid #86efac";
        resultEl.innerHTML = `
          <div style="font-weight:600;color:#16a34a;margin-bottom:8px">✓ Triggered successfully — HTTP ${res.status}</div>
          <div style="display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:12px;color:var(--gray-600)">
            <span>Delivery ID</span><code>${data.delivery_id || "—"}</code>
            <span>Pipeline Run</span><code>${data.pipeline_run_id || "—"}</code>
            <span>Status</span><code>${data.status || "triggered"}</code>
          </div>
          ${data.pipeline_run_id
            ? `<button class="btn btn-primary btn-sm" style="margin-top:10px"
                 onclick="closeModal();navigate('pipeline-runs/${data.pipeline_run_id}')">View Pipeline Run →</button>`
            : ""}`;
      } else {
        resultEl.style.cssText = "display:block;margin-top:4px;border-radius:8px;padding:12px;font-size:13px;background:#fef2f2;border:1px solid #fca5a5";
        resultEl.innerHTML = `
          <div style="font-weight:600;color:#dc2626;margin-bottom:6px">✗ Failed — HTTP ${res.status}</div>
          <div style="font-size:12px;color:var(--gray-600)">${data.error || JSON.stringify(data)}</div>`;
      }
    }
  } catch (e) {
    if (resultEl) {
      resultEl.style.cssText = "display:block;margin-top:4px;border-radius:8px;padding:12px;font-size:13px;background:#fef2f2;border:1px solid #fca5a5";
      resultEl.innerHTML = `<div style="font-weight:600;color:#dc2626">✗ Network error: ${e.message}</div>`;
    }
  } finally {
    if (sendBtn) { sendBtn.disabled = false; sendBtn.textContent = "⚡ Send"; }
  }
}

// ── Administration ─────────────────────────────────────────────────────────

// Redirect bare /admin to /admin/users
router.register("admin", (hash, parts) => navigate("admin/users"));

// ── User Management (Users / Groups / Roles) ──────────────────────────────
async function _renderAdminUsers(subTab) {
  setBreadcrumb({ label: "Administration", hash: "admin/users" }, { label: "User Management" });
  setContent(loading());

  const [users, groups, roles] = await Promise.all([
    api.getUsers().catch(() => []),
    api.getGroups().catch(() => []),
    api.getRoles().catch(() => []),
  ]);

  const subTabs = [
    { id: "users",  label: `Users (${users.length})` },
    { id: "groups", label: `Groups (${groups.length})` },
    { id: "roles",  label: `Roles (${roles.length})` },
  ];

  const subBar = `<div class="tab-bar">
    ${subTabs.map(t => `<button class="tab-btn${subTab === t.id ? " active" : ""}"
      onclick="navigate('admin/users-${t.id}')">${t.label}</button>`).join("")}
  </div>`;

  let panel = "";

  if (subTab === "users") {
    panel = `
      <div class="page-header">
        <div><h1>User Management</h1><div class="sub">Manage platform users, personas and access</div></div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-secondary" onclick="showBulkImportUsers()">⬆ Import</button>
          <button class="btn btn-primary" onclick="showCreateUser()">+ New User</button>
        </div>
      </div>
      ${subBar}
      ${users.length === 0
        ? `<div class="card"><div class="empty-state"><p>No users yet.</p></div></div>`
        : `<div class="card"><div class="table-wrap"><table>
            <thead><tr><th>Username</th><th>Display Name</th><th>Email</th><th>Persona</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>${users.map(u => `
              <tr>
                <td><a href="#admin/users/${u.id}" onclick="navigate('admin/users/${u.id}');return false;">${u.username}</a></td>
                <td>${u.display_name || "—"}</td>
                <td style="color:var(--gray-600)">${u.email}</td>
                <td>${personaBadge(u.persona)}</td>
                <td><span class="badge ${u.is_active ? "badge-success" : "badge-failed"}">${u.is_active ? "Active" : "Inactive"}</span></td>
                <td style="display:flex;gap:4px;flex-wrap:wrap">
                  <button class="btn btn-secondary btn-sm" onclick="navigate('admin/users/${u.id}')">View</button>
                  <button class="btn btn-secondary btn-sm" onclick="showEditPersona('${u.id}','${u.persona}')">Persona</button>
                  <button class="btn btn-danger btn-sm" onclick="deleteUser('${u.id}','${u.username}')">Delete</button>
                </td>
              </tr>`).join("")}
            </tbody></table></div></div>`}`;
  } else if (subTab === "groups") {
    panel = `
      <div class="page-header">
        <div><h1>User Management</h1><div class="sub">Organise users into teams for bulk access control</div></div>
        <button class="btn btn-primary" onclick="showCreateGroup()">+ New Group</button>
      </div>
      ${subBar}
      ${groups.length === 0
        ? `<div class="card"><div class="empty-state"><p>No groups yet.</p></div></div>`
        : `<div class="grid grid-3">
          ${groups.map(g => `
            <div class="card">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                <strong>${g.name}</strong>
                <span class="badge badge-blue">${(g.members || []).length} members</span>
              </div>
              <div style="color:var(--gray-600);font-size:13px;margin-bottom:12px">${g.description || "No description"}</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap">
                <button class="btn btn-secondary btn-sm" onclick="showGroupMembers('${g.id}','${g.name}')">Members</button>
                <button class="btn btn-secondary btn-sm" onclick="showEditGroup('${g.id}','${g.name.replace(/'/g,"\\'")}','${(g.description||"").replace(/'/g,"\\'")}')">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteGroup('${g.id}','${g.name.replace(/'/g,"\\'")}')">Delete</button>
              </div>
            </div>`).join("")}
          </div>`}`;
  } else if (subTab === "roles") {
    panel = `
      <div class="page-header">
        <div><h1>User Management</h1><div class="sub">Permission bundles assigned to users and groups</div></div>
        <button class="btn btn-primary" onclick="showCreateRole()">+ New Role</button>
      </div>
      ${subBar}
      ${roles.length === 0
        ? `<div class="card"><div class="empty-state"><p>No roles yet.</p></div></div>`
        : `<div class="card"><div class="table-wrap"><table>
            <thead><tr><th>Name</th><th>Description</th><th>Permissions</th><th>Actions</th></tr></thead>
            <tbody>${roles.map(r => `
              <tr>
                <td><strong>${r.name}</strong></td>
                <td style="color:var(--gray-600)">${r.description || "—"}</td>
                <td><div style="display:flex;flex-wrap:wrap;gap:4px">${(r.permissions || []).slice(0,6).map(p =>
                  `<code style="background:var(--gray-100);padding:1px 6px;border-radius:4px;font-size:11px">${p}</code>`).join("")}
                  ${(r.permissions || []).length > 6 ? `<span style="font-size:11px;color:var(--gray-500)">+${r.permissions.length - 6} more</span>` : ""}
                </div></td>
                <td style="display:flex;gap:4px">
                  <button class="btn btn-secondary btn-sm" onclick="showEditRole('${r.id}','${r.name.replace(/'/g,"\\'")}','${(r.description||"").replace(/'/g,"\\'")}',${JSON.stringify(r.permissions||[])})">Edit</button>
                  <button class="btn btn-danger btn-sm" onclick="deleteRole('${r.id}','${r.name.replace(/'/g,"\\'")}')">Delete</button>
                </td>
              </tr>`).join("")}
            </tbody></table></div></div>`}`;
  }

  setContent(panel);
}

router.register("admin/users",       () => _renderAdminUsers("users"));
router.register("admin/users-users",  () => _renderAdminUsers("users"));
router.register("admin/users-groups", () => _renderAdminUsers("groups"));
router.register("admin/users-roles",  () => _renderAdminUsers("roles"));
// legacy routes kept for back-compat
router.register("admin/groups",  () => _renderAdminUsers("groups"));
router.register("admin/roles",   () => _renderAdminUsers("roles"));

// ── Key Management (API Keys + Vault) ─────────────────────────────────────
router.register("admin/keys", async () => {
  setBreadcrumb({ label: "Administration", hash: "admin/users" }, { label: "Key Management" });
  setContent(loading());

  const [settings, secrets] = await Promise.all([
    api.getSettings().catch(() => []),
    api.listSecrets().catch(() => []),
  ]);

  const apiKeysHtml = `
    <div class="card" style="margin-bottom:20px">
      <div class="card-header">
        <h2>API Keys</h2>
        <div style="font-size:12px;color:var(--gray-500);margin-top:2px">Runtime-configurable service credentials stored securely in the database</div>
      </div>
      ${settings.length === 0
        ? `<div class="empty-state"><p>No configurable API keys.</p></div>`
        : settings.map(s => `
          <div style="padding:16px 0;border-bottom:1px solid var(--gray-100)">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap">
              <div style="flex:1;min-width:200px">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                  <span style="font-weight:600;font-size:13px">${s.key}</span>
                  ${s.is_secret ? `<span class="badge badge-blue" style="font-size:10px">Secret</span>` : ""}
                </div>
                <div style="font-size:12px;color:var(--gray-500)">${s.description}</div>
                <div style="margin-top:6px">
                  ${s.is_set
                    ? `<span class="badge badge-success">Configured</span>`
                    : `<span class="badge badge-noncompliant">Not set</span>`}
                  ${s.updated_at ? `<span style="font-size:11px;color:var(--gray-400);margin-left:8px">Updated ${fmtDate(s.updated_at)}</span>` : ""}
                </div>
              </div>
              <div style="display:flex;gap:6px;align-items:center">
                <button class="btn btn-primary btn-sm" onclick="showSetSetting('${s.key}','${s.description}',${s.is_secret})">
                  ${s.is_set ? "Update" : "Set Key"}
                </button>
                ${s.is_set ? `<button class="btn btn-danger btn-sm" onclick="clearSettingFromKeys('${s.key}')">Clear</button>` : ""}
              </div>
            </div>
          </div>`).join("")}
    </div>`;

  const vaultHtml = `
    <div class="card">
      <div class="card-header" style="display:flex;align-items:center;justify-content:space-between">
        <div>
          <h2>Vault Secrets</h2>
          <div style="font-size:12px;color:var(--gray-500);margin-top:2px">Fernet-encrypted secrets with per-secret access control</div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="navigate('vault')">Manage Vault</button>
      </div>
      ${secrets.length === 0
        ? `<div class="empty-state"><p>No secrets stored yet. <a href="#vault" onclick="navigate('vault');return false;">Go to Vault</a></p></div>`
        : `<div class="table-wrap"><table>
            <thead><tr><th>Name</th><th>Description</th><th>Access</th><th>Updated</th></tr></thead>
            <tbody>${secrets.map(s => `
              <tr>
                <td><strong>${s.name}</strong></td>
                <td style="color:var(--gray-600)">${s.description || "—"}</td>
                <td><code style="font-size:11px">${s.allowed_users || "*"}</code></td>
                <td style="color:var(--gray-500);font-size:12px">${fmtDate(s.updated_at || s.created_at)}</td>
              </tr>`).join("")}
            </tbody></table></div>`}
    </div>`;

  setContent(`
    <div class="page-header">
      <div><h1>Key Management</h1><div class="sub">API credentials and encrypted vault secrets</div></div>
    </div>
    ${apiKeysHtml}
    ${vaultHtml}`);
});

// ── Global Variables (LDAP + env config display) ──────────────────────────
router.register("admin/variables", async () => {
  setBreadcrumb({ label: "Administration", hash: "admin/users" }, { label: "Global Variables" });
  setContent(loading());

  const envVars = [
    { key: "DATABASE_URL",      desc: "SQLAlchemy database connection string",          secret: true },
    { key: "JWT_SECRET_KEY",    desc: "JWT signing key (HS256)",                        secret: true },
    { key: "JWT_EXPIRY_HOURS",  desc: "Token lifetime in hours",                        secret: false },
    { key: "HOST",              desc: "Bind address for the application server",        secret: false },
    { key: "PORT",              desc: "Port the application server listens on",         secret: false },
    { key: "LOG_LEVEL",         desc: "Python logging verbosity (DEBUG/INFO/WARNING)",  secret: false },
    { key: "REDIS_URL",         desc: "Redis connection URL for caching",               secret: true },
    { key: "AUDIT_STORAGE_PATH",desc: "Filesystem path for PDF audit report storage",   secret: false },
  ];

  const envHtml = `
    <div class="card">
      <div class="card-header"><h2>Environment Variables</h2></div>
      <div style="color:var(--gray-500);font-size:13px;margin-bottom:16px">
        These variables are injected from your Kubernetes ConfigMap or Secret at pod startup and cannot be changed at runtime.
        Modify your Helm values or Terraform config and redeploy to update them.
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>Variable</th><th>Description</th><th>Sensitive</th></tr></thead>
        <tbody>${envVars.map(v => `
          <tr>
            <td><code style="font-size:12px">${v.key}</code></td>
            <td style="color:var(--gray-600);font-size:13px">${v.desc}</td>
            <td>${v.secret
              ? `<span class="badge badge-noncompliant" style="font-size:10px">Secret</span>`
              : `<span class="badge badge-blue" style="font-size:10px">Config</span>`}
            </td>
          </tr>`).join("")}
        </tbody>
      </table></div>
      <div style="margin-top:16px;padding:12px;background:var(--gray-50);border-radius:6px;font-size:12px;color:var(--gray-600)">
        <strong>Helm:</strong> <code>helm upgrade --install conduit ./helm/conduit -f values-prod.yaml --set image.tag=1.2.3</code><br>
        <strong>Terraform:</strong> <code>terraform apply -var="image_tag=1.2.3"</code>
      </div>
    </div>`;

  setContent(`
    <div class="page-header">
      <div><h1>Global Variables</h1><div class="sub">Environment variables injected at pod startup</div></div>
    </div>
    ${envHtml}`);
});

// ── System (LDAP / Agents / Plugins / Webhooks) ───────────────────────────
router.register("admin/system", async () => {
  setBreadcrumb({ label: "Administration", hash: "admin/users" }, { label: "System" });
  setContent(loading());

  const [pools, plugins, webhooks] = await Promise.all([
    api.getAgentPools().catch(() => []),
    api.getPlugins().catch(() => []),
    api.listWebhooks().catch(() => []),
  ]);

  const ldapHtml = `
    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><h2>LDAP / Active Directory</h2></div>
      <div style="color:var(--gray-500);font-size:13px;margin-bottom:16px">
        Directory integration settings — read from environment variables at startup.
        Update your Kubernetes ConfigMap and restart to change these values.
      </div>
      <div class="detail-grid" style="margin-bottom:20px">
        <div class="detail-row"><span class="detail-label">LDAP_URL</span><code id="ldap-url-display" style="font-size:12px">Loading…</code></div>
        <div class="detail-row"><span class="detail-label">LDAP_BIND_DN</span><code id="ldap-bind-dn-display" style="font-size:12px">Loading…</code></div>
        <div class="detail-row"><span class="detail-label">LDAP_BASE_DN</span><code id="ldap-base-dn-display" style="font-size:12px">Loading…</code></div>
        <div class="detail-row"><span class="detail-label">LDAP_USER_SEARCH_BASE</span><code id="ldap-search-base-display" style="font-size:12px">Loading…</code></div>
      </div>
      <div style="border-top:1px solid var(--gray-100);padding-top:16px">
        <div style="font-weight:600;font-size:13px;margin-bottom:8px">Test Connection</div>
        <div style="color:var(--gray-500);font-size:12px;margin-bottom:12px">
          Optionally provide credentials to test a full user bind, or leave blank to test service-account connectivity only.
        </div>
        <div class="grid grid-2" style="gap:12px;margin-bottom:12px">
          <div class="form-group"><label>Username (optional)</label><input id="ldap-test-user" class="form-control" placeholder="e.g. jdoe"></div>
          <div class="form-group"><label>Password (optional)</label><input id="ldap-test-pass" class="form-control" type="password" placeholder="••••••••"></div>
        </div>
        <button class="btn btn-primary" onclick="testLdapConnection()">Test Connection</button>
        <div id="ldap-test-result" style="margin-top:12px;font-size:13px"></div>
      </div>
    </div>`;

  const agentsHtml = `
    <div class="card" style="margin-bottom:20px">
      <div class="card-header" style="display:flex;align-items:center;justify-content:space-between">
        <div>
          <h2>Agent Pools</h2>
          <div style="font-size:12px;color:var(--gray-500);margin-top:2px">Sandboxed execution environments for pipeline tasks</div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="navigate('agents')">Manage Agents</button>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>Name</th><th>Type</th><th>CPU Limit</th><th>Memory Limit</th><th>Max Agents</th><th>Status</th></tr></thead>
        <tbody>${pools.map(p => `
          <tr>
            <td><strong>${p.name}</strong>${p.description ? `<br><span style="font-size:12px;color:var(--gray-500)">${p.description}</span>` : ""}</td>
            <td><span class="badge ${p.pool_type === "builtin" ? "badge-blue" : "badge-gold"}">${p.pool_type}</span></td>
            <td><code style="font-size:11px">${p.cpu_limit}</code></td>
            <td><code style="font-size:11px">${p.memory_limit}</code></td>
            <td>${p.max_agents}</td>
            <td><span class="badge ${p.is_active ? "badge-success" : "badge-failed"}">${p.is_active ? "Active" : "Inactive"}</span></td>
          </tr>`).join("")}
        </tbody></table></div>
    </div>`;

  const pluginsHtml = `
    <div class="card" style="margin-bottom:20px">
      <div class="card-header" style="display:flex;align-items:center;justify-content:space-between">
        <div>
          <h2>Plugins</h2>
          <div style="font-size:12px;color:var(--gray-500);margin-top:2px">CI/CD tool integrations</div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="navigate('plugins')">Manage Plugins</button>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>Plugin</th><th>Category</th><th>Version</th><th>Status</th></tr></thead>
        <tbody>${plugins.map(p => `
          <tr>
            <td><strong>${p.icon || "🔌"} ${p.display_name}</strong>${p.description ? `<br><span style="font-size:12px;color:var(--gray-500)">${p.description}</span>` : ""}</td>
            <td><span class="badge badge-blue">${p.category || "—"}</span></td>
            <td><code style="font-size:11px">${p.version || "—"}</code></td>
            <td><span class="badge ${p.is_enabled ? "badge-success" : "badge-failed"}">${p.is_enabled ? "Enabled" : "Disabled"}</span></td>
          </tr>`).join("")}
        </tbody></table></div>
    </div>`;

  const webhooksHtml = `
    <div class="card">
      <div class="card-header" style="display:flex;align-items:center;justify-content:space-between">
        <div>
          <h2>Webhooks</h2>
          <div style="font-size:12px;color:var(--gray-500);margin-top:2px">Inbound triggers for pipeline execution</div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="navigate('webhooks')">Manage Webhooks</button>
      </div>
      ${webhooks.length === 0
        ? `<div class="empty-state"><p>No webhooks configured yet.</p></div>`
        : `<div class="table-wrap"><table>
            <thead><tr><th>Name</th><th>Pipeline</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>${webhooks.map(w => `
              <tr>
                <td><strong>${w.name}</strong>${w.description ? `<br><span style="font-size:12px;color:var(--gray-500)">${w.description}</span>` : ""}</td>
                <td><code style="font-size:11px">${w.pipeline_id || "—"}</code></td>
                <td><span class="badge ${w.is_active ? "badge-success" : "badge-failed"}">${w.is_active ? "Active" : "Inactive"}</span></td>
                <td style="color:var(--gray-500);font-size:12px">${fmtDate(w.created_at)}</td>
              </tr>`).join("")}
            </tbody></table></div>`}
    </div>`;

  const runnerHtml = `
    <div class="card" style="margin-bottom:20px" id="runner-card">
      <div class="card-header">
        <div>
          <h2>Task Runner</h2>
          <div style="font-size:12px;color:var(--gray-500);margin-top:2px">Execution backend for pipeline task scripts</div>
        </div>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:16px">
          Choose how Conduit executes task scripts. <strong>subprocess</strong> runs scripts directly on the host
          (default). <strong>docker</strong> or <strong>podman</strong> wraps each task in an isolated container
          using the specified image — providing full sandbox isolation with resource limits.
        </p>

        <div class="grid grid-2" style="gap:16px;margin-bottom:16px">
          <div>
            <div class="form-group" style="margin-bottom:12px">
              <label style="font-size:13px">Runner type</label>
              <select id="runner-type-select" class="form-control" style="margin-top:4px">
                <option value="subprocess">subprocess (host, default)</option>
                <option value="docker">docker</option>
                <option value="podman">podman</option>
              </select>
            </div>
            <div class="form-group">
              <label style="font-size:13px">Container image <span style="color:var(--gray-400);font-weight:400">(docker/podman only)</span></label>
              <input id="runner-image-input" class="form-control" style="margin-top:4px"
                     placeholder="python:3.12-slim" value="python:3.12-slim">
            </div>
            <div style="margin-top:12px;display:flex;gap:8px">
              <button class="btn btn-primary btn-sm" onclick="saveRunnerSettings()">Save</button>
              <button class="btn btn-secondary btn-sm" onclick="testRunnerSettings()">Test Connection</button>
            </div>
            <div id="runner-test-result" style="margin-top:10px;font-size:13px"></div>
          </div>
          <div style="background:var(--gray-50);border-radius:8px;padding:14px;font-size:12px;color:var(--gray-600)">
            <strong>How it works</strong><br><br>
            <div style="line-height:1.8">
              <div><strong>subprocess</strong> — task script is written to a temp file and executed directly. Uses the host's bash/python. No isolation.</div><br>
              <div><strong>docker / podman</strong> — script is volume-mounted into a fresh container (<code>--rm</code>). Resource limits: 512 MB RAM, 1 CPU. Image must include bash (for bash tasks) or python3 (for python tasks).</div><br>
              <div>Recommended images:<br>
                <code>python:3.12-slim</code> — python + bash<br>
                <code>ubuntu:22.04</code> — full toolchain<br>
                <code>alpine:3.19</code> — minimal (no bash by default)<br>
                <code>registry.access.redhat.com/ubi9/python-312</code> — RHEL-compatible
              </div>
            </div>
          </div>
        </div>

        <div style="border-top:1px solid var(--gray-100);padding-top:12px">
          <div style="font-size:12px;font-weight:600;color:var(--gray-500);margin-bottom:6px">CURRENT SETTINGS</div>
          <div id="runner-current-settings" style="font-size:12px;color:var(--gray-600)">Loading…</div>
        </div>
      </div>
    </div>`;

  setContent(`
    <div class="page-header">
      <div><h1>System</h1><div class="sub">LDAP integration, task runner, agent pools, plugins and webhooks</div></div>
    </div>
    ${runnerHtml}
    ${ldapHtml}
    ${agentsHtml}
    ${pluginsHtml}
    ${webhooksHtml}`);

  loadLdapConfig();
  // Load current runner settings into form
  api.getSettings().then(settings => {
    const runnerSetting = settings.find(s => s.key === "TASK_RUNNER");
    const imageSetting  = settings.find(s => s.key === "TASK_RUNNER_IMAGE");
    const runner = runnerSetting?.value || "subprocess";
    const image  = imageSetting?.value  || "python:3.12-slim";
    const sel = document.getElementById("runner-type-select");
    const inp = document.getElementById("runner-image-input");
    if (sel) sel.value = runner;
    if (inp && image) inp.value = image;
    const display = document.getElementById("runner-current-settings");
    if (display) display.innerHTML = `Runner: <strong>${runner}</strong> &nbsp;|&nbsp; Image: <strong>${image}</strong>`;
  }).catch(() => {});
});

// ── Framework Controls ─────────────────────────────────────────────────────
router.register("admin/frameworks", async (hash, parts) => {
  const framework = parts[2] || "isae";
  setBreadcrumb({ label: "Administration", hash: "admin/users" }, { label: "Framework Controls" });
  setContent(loading());

  const [isaeControls, acfControls] = await Promise.all([
    request("GET", "/framework-controls/isae"),
    request("GET", "/framework-controls/acf"),
  ]);

  const frameworks = { isae: isaeControls, acf: acfControls };

  function renderFrameworkTab(fw) {
    const controls = frameworks[fw] || [];
    const enabledCount = controls.filter(c => c.enabled).length;
    const customCount = controls.filter(c => !c.is_builtin).length;

    // Group by category/domain
    const groups = {};
    for (const c of controls) {
      const grp = c.category_label || c.domain || c.category || "Other";
      if (!groups[grp]) groups[grp] = [];
      groups[grp].push(c);
    }

    return `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px">
        <div style="display:flex;gap:12px">
          <div style="background:var(--gray-50);border-radius:8px;padding:10px 16px;text-align:center">
            <div style="font-size:22px;font-weight:700;color:var(--primary)">${enabledCount}</div>
            <div style="font-size:11px;color:var(--gray-500)">Enabled</div>
          </div>
          <div style="background:var(--gray-50);border-radius:8px;padding:10px 16px;text-align:center">
            <div style="font-size:22px;font-weight:700;color:var(--gray-600)">${controls.length - enabledCount}</div>
            <div style="font-size:11px;color:var(--gray-500)">Disabled</div>
          </div>
          <div style="background:var(--gray-50);border-radius:8px;padding:10px 16px;text-align:center">
            <div style="font-size:22px;font-weight:700;color:#8b5cf6">${customCount}</div>
            <div style="font-size:11px;color:var(--gray-500)">Custom</div>
          </div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-primary btn-sm" onclick="showAddControlModal('${fw}')">+ Add Control</button>
          <button class="btn btn-secondary btn-sm" onclick="resetFrameworkControls('${fw}')">Reset to Defaults</button>
        </div>
      </div>

      ${Object.entries(groups).map(([grp, items]) => `
        <div class="card" style="margin-bottom:12px">
          <div class="card-header" style="padding:10px 16px">
            <h3 style="font-size:13px;margin:0">${grp}</h3>
            <span style="font-size:11px;color:var(--gray-400)">${items.filter(i=>i.enabled).length}/${items.length} enabled</span>
          </div>
          <div class="table-wrap"><table>
            <thead><tr><th style="width:80px">ID</th><th>Title</th><th style="width:80px">Weight</th><th style="width:90px">Status</th><th style="width:130px">Actions</th></tr></thead>
            <tbody>
              ${items.map(c => `
                <tr style="${!c.enabled ? "opacity:0.45" : ""}">
                  <td style="font-family:monospace;font-size:11px;color:var(--primary)">${c.id}</td>
                  <td>
                    <div style="font-weight:600;font-size:13px">${c.title}</div>
                    <div style="font-size:11px;color:var(--gray-500);margin-top:2px">${(c.description||"").substring(0,100)}${(c.description||"").length>100?"…":""}</div>
                    ${c.task_types&&c.task_types.length ? `<div style="margin-top:4px">${c.task_types.map(t=>`<span style="background:var(--primary-light);color:var(--primary);font-size:10px;padding:1px 6px;border-radius:4px;margin-right:3px">${t}</span>`).join("")}</div>` : ""}
                  </td>
                  <td style="text-align:center">
                    <span style="background:var(--gray-100);border-radius:4px;padding:2px 8px;font-size:12px;font-weight:600">${c.weight||2}</span>
                  </td>
                  <td>
                    ${c.enabled
                      ? `<span style="background:#dcfce7;color:#16a34a;padding:2px 10px;border-radius:8px;font-size:11px;font-weight:600">Enabled</span>`
                      : `<span style="background:#fee2e2;color:#ef4444;padding:2px 10px;border-radius:8px;font-size:11px;font-weight:600">Disabled</span>`}
                    ${!c.is_builtin ? `<span style="background:#ede9fe;color:#7c3aed;padding:2px 6px;border-radius:6px;font-size:10px;font-weight:600;margin-left:4px">Custom</span>` : ""}
                  </td>
                  <td style="white-space:nowrap">
                    <button class="btn btn-secondary btn-sm" style="padding:2px 8px;font-size:11px" onclick="toggleFrameworkControl('${fw}','${c.id}',${!c.enabled})">${c.enabled?"Disable":"Enable"}</button>
                    <button class="btn btn-secondary btn-sm" style="padding:2px 8px;font-size:11px;margin-left:4px" onclick="editFrameworkControl('${fw}','${c.id}')">Edit</button>
                    ${!c.is_builtin ? `<button class="btn btn-danger btn-sm" style="padding:2px 8px;font-size:11px;margin-left:4px" onclick="deleteFrameworkControl('${fw}','${c.id}')">Del</button>` : ""}
                  </td>
                </tr>`).join("")}
            </tbody>
          </table></div>
        </div>`).join("")}`;
  }

  setContent(`
    <div class="page-header">
      <div><h1>Framework Controls</h1><div class="sub">Configure ISAE 3000 / SOC 2 and ACF controls — enable, disable, override, or add custom controls</div></div>
    </div>
    <div class="tab-bar">
      <button class="tab-btn${framework==="isae"?" active":""}" onclick="navigate('admin/frameworks/isae')">ISAE 3000 / SOC 2 (${(frameworks.isae||[]).filter(c=>c.enabled).length} enabled)</button>
      <button class="tab-btn${framework==="acf"?" active":""}" onclick="navigate('admin/frameworks/acf')">ACF / APRA CPS 234 (${(frameworks.acf||[]).filter(c=>c.enabled).length} enabled)</button>
    </div>
    <div style="margin-top:16px">
      ${renderFrameworkTab(framework)}
    </div>
  `);
});

router.register("admin/frameworks/isae", (hash, parts) => router.routes["admin/frameworks"](hash, ["admin","frameworks","isae"]));
router.register("admin/frameworks/acf",  (hash, parts) => router.routes["admin/frameworks"](hash, ["admin","frameworks","acf"]));

async function toggleFrameworkControl(fw, id, enable) {
  await request("PUT", `/framework-controls/${fw}/${encodeURIComponent(id)}`, { enabled: enable });
  navigate("admin/frameworks/" + fw);
}

async function deleteFrameworkControl(fw, id) {
  if (!confirm(`Delete custom control "${id}"? This cannot be undone.`)) return;
  await request("DELETE", `/framework-controls/${fw}/${encodeURIComponent(id)}`);
  navigate("admin/frameworks/" + fw);
}

async function resetFrameworkControls(fw) {
  if (!confirm(`Reset all ${fw.toUpperCase()} controls to defaults? All customisations will be lost.`)) return;
  await request("POST", `/framework-controls/${fw}/reset`);
  showToast(`${fw.toUpperCase()} controls reset to defaults`, "success");
  navigate("admin/frameworks/" + fw);
}

function showAddControlModal(fw) {
  const categoryLabel = fw === "isae" ? "Category (e.g. CC1 — Control Environment)" : "Domain (e.g. Governance)";
  openModal(`Add Custom ${fw.toUpperCase()} Control`, `
    <div class="form-group"><label>Control ID *</label><input id="fc-id" class="input" placeholder="e.g. CC10.1 or ACF-CUSTOM-1"></div>
    <div class="form-group"><label>Title *</label><input id="fc-title" class="input" placeholder="Short control title"></div>
    <div class="form-group"><label>${categoryLabel}</label><input id="fc-category" class="input"></div>
    <div class="form-group"><label>Description</label><textarea id="fc-desc" class="input" rows="3" placeholder="What this control checks and how pipeline evidence maps to it"></textarea></div>
    <div class="form-group"><label>Task Types (comma-separated)</label><input id="fc-types" class="input" placeholder="e.g. sast, unit-test, deploy"></div>
    <div class="form-group"><label>Evidence Keywords (comma-separated)</label><input id="fc-keywords" class="input" placeholder="e.g. scan, test, approve"></div>
    <div class="form-group"><label>Weight (1–5)</label><input id="fc-weight" class="input" type="number" min="1" max="5" value="2"></div>
  `, [
    { label: "Cancel", action: closeModal },
    {
      label: "Add Control", primary: true, action: async () => {
        const id = document.getElementById("fc-id").value.trim();
        const title = document.getElementById("fc-title").value.trim();
        if (!id || !title) { showToast("ID and Title are required", "error"); return; }
        const cat = document.getElementById("fc-category").value.trim();
        const task_types = document.getElementById("fc-types").value.split(",").map(s=>s.trim()).filter(Boolean);
        const evidence_keywords = document.getElementById("fc-keywords").value.split(",").map(s=>s.trim()).filter(Boolean);
        const weight = parseInt(document.getElementById("fc-weight").value) || 2;
        await request("POST", `/framework-controls/${fw}`, {
          id, title,
          category: cat,
          category_label: cat,
          description: document.getElementById("fc-desc").value.trim(),
          task_types: task_types.length ? task_types : null,
          evidence_keywords: evidence_keywords.length ? evidence_keywords : null,
          weight,
        });
        closeModal();
        showToast("Control added", "success");
        navigate("admin/frameworks/" + fw);
      }
    }
  ]);
}

function editFrameworkControl(fw, id) {
  // Fetch all controls, find this one, pre-fill modal
  request("GET", `/framework-controls/${fw}`).then(controls => {
    const c = controls.find(x => x.id === id);
    if (!c) return;
    openModal(`Edit Control: ${id}`, `
      <div class="form-group"><label>Title</label><input id="fce-title" class="input" value="${(c.title||"").replace(/"/g,"&quot;")}"></div>
      <div class="form-group"><label>Description</label><textarea id="fce-desc" class="input" rows="3">${c.description||""}</textarea></div>
      <div class="form-group"><label>Task Types (comma-separated)</label><input id="fce-types" class="input" value="${(c.task_types||[]).join(", ")}"></div>
      <div class="form-group"><label>Evidence Keywords (comma-separated)</label><input id="fce-keywords" class="input" value="${(c.evidence_keywords||[]).join(", ")}"></div>
      <div class="form-group"><label>Weight (1–5)</label><input id="fce-weight" class="input" type="number" min="1" max="5" value="${c.weight||2}"></div>
    `, [
      { label: "Cancel", action: closeModal },
      {
        label: "Save", primary: true, action: async () => {
          const task_types = document.getElementById("fce-types").value.split(",").map(s=>s.trim()).filter(Boolean);
          const evidence_keywords = document.getElementById("fce-keywords").value.split(",").map(s=>s.trim()).filter(Boolean);
          await request("PUT", `/framework-controls/${fw}/${encodeURIComponent(id)}`, {
            title: document.getElementById("fce-title").value.trim() || null,
            description: document.getElementById("fce-desc").value.trim() || null,
            task_types: task_types.length ? task_types : null,
            evidence_keywords: evidence_keywords.length ? evidence_keywords : null,
            weight: parseInt(document.getElementById("fce-weight").value) || null,
          });
          closeModal();
          showToast("Control updated", "success");
          navigate("admin/frameworks/" + fw);
        }
      }
    ]);
  });
}

// legacy compatibility — redirect old routes to new sections
router.register("admin/ldap",     () => navigate("admin/system"));
router.register("admin/settings", () => navigate("admin/keys"));

function showSetSetting(key, description, isSecret) {
  openModal(`Configure: ${key}`,
    `<div class="form-group">
       <label style="font-size:12px;color:var(--gray-500);margin-bottom:8px;display:block">${description}</label>
       <input id="setting-val" class="form-control" type="${isSecret ? "password" : "text"}"
              placeholder="${isSecret ? "Paste your API key…" : "Enter value…"}" autocomplete="off">
       ${isSecret ? `<div style="font-size:11.5px;color:var(--gray-400);margin-top:6px">The key is stored securely in the database and masked in the UI.</div>` : ""}
     </div>`,
    async () => {
      const value = el("setting-val").value.trim();
      if (!value) return modalError("Value is required");
      try {
        await api.setSetting(key, value);
        closeModal();
        toast(`${key} saved`, "success");
        navigate("admin/keys");
      } catch (e) { modalError(e.message); }
    },
    "Save"
  );
  setTimeout(() => el("setting-val")?.focus(), 100);
}

async function clearSetting(key) {
  if (!confirm(`Clear ${key}? The AI assistant will stop working until a new key is set.`)) return;
  try {
    await api.clearSetting(key);
    toast(`${key} cleared`, "success");
    navigate("admin/keys");
  } catch (e) { toast(e.message, "error"); }
}

async function clearSettingFromKeys(key) {
  return clearSetting(key);
}

// user detail page
router.register("admin/users/:id", async (hash, parts) => {
  const userId = parts[2];
  setBreadcrumb({ label: "Administration", hash: "admin/users" }, { label: "User" });
  setContent(loading());

  const [user, bindings, roles] = await Promise.all([
    api.getUser(userId).catch(() => null),
    api.getUserBindings(userId).catch(() => []),
    api.getRoles().catch(() => []),
  ]);

  if (!user) { setContent(`<div class="card"><div class="empty-state"><p>User not found.</p></div></div>`); return; }

  const roleMap = Object.fromEntries(roles.map(r => [r.id, r.name]));

  setBreadcrumb(
    { label: "Administration", hash: "admin/users" },
    { label: user.username }
  );

  setContent(`
    <div class="page-header">
      <div>
        <h1>${user.display_name || user.username}</h1>
        <div class="sub">${user.email} · ${personaBadge(user.persona)}</div>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-secondary" onclick="showEditPersona('${user.id}','${user.persona}')">Change Persona</button>
        <button class="btn btn-primary" onclick="showAddBinding('${user.id}')">+ Add Role Binding</button>
      </div>
    </div>

    <div class="grid grid-2" style="margin-bottom:24px">
      <div class="card">
        <div class="card-header"><h3>User Details</h3></div>
        <table style="width:100%"><tbody>
          <tr><td style="color:var(--gray-600);width:140px">Username</td><td><strong>${user.username}</strong></td></tr>
          <tr><td style="color:var(--gray-600)">Email</td><td>${user.email}</td></tr>
          <tr><td style="color:var(--gray-600)">Display Name</td><td>${user.display_name || "—"}</td></tr>
          <tr><td style="color:var(--gray-600)">Persona</td><td>${personaBadge(user.persona)}</td></tr>
          <tr><td style="color:var(--gray-600)">Status</td><td><span class="badge ${user.is_active ? "badge-success" : "badge-failed"}">${user.is_active ? "Active" : "Inactive"}</span></td></tr>
          ${user.ldap_dn ? `<tr><td style="color:var(--gray-600)">LDAP DN</td><td><code style="font-size:12px">${user.ldap_dn}</code></td></tr>` : ""}
        </tbody></table>
      </div>

      <div class="card">
        <div class="card-header"><h3>Role Bindings</h3></div>
        ${bindings.length === 0
          ? `<div class="empty-state"><p>No role bindings.</p></div>`
          : `<div class="table-wrap"><table>
              <thead><tr><th>Role</th><th>Scope</th><th>Expires</th><th></th></tr></thead>
              <tbody>${bindings.map(b => `
                <tr>
                  <td><strong>${roleMap[b.role_id] || b.role_id}</strong></td>
                  <td><code style="font-size:12px">${b.scope}</code></td>
                  <td style="color:var(--gray-600)">${b.expires_at ? fmtDate(b.expires_at) : "Never"}</td>
                  <td><button class="btn btn-danger btn-sm" onclick="removeBinding('${user.id}','${b.id}')">Remove</button></td>
                </tr>`).join("")}
              </tbody></table></div>`
        }
      </div>
    </div>
  `);
});

function showBulkImportUsers() {
  openModal("Bulk Import Users",
    `<p style="font-size:13px;color:var(--gray-600);margin-bottom:12px">
       Paste a JSON array or CSV (with header row) to create multiple users at once.
       Existing usernames are skipped. Default persona is <strong>ReadOnly</strong>.
     </p>
     <div style="font-size:12px;color:var(--gray-500);margin-bottom:8px">
       CSV columns: <code>username, email, display_name, persona, password</code><br>
       JSON fields: <code>username, email, display_name, persona, password, ldap_dn</code>
     </div>
     <textarea id="bulk-import-text" class="form-control" rows="10" spellcheck="false"
       placeholder='[{"username":"alice","email":"alice@example.com","persona":"Developer"},
{"username":"bob","email":"bob@example.com","persona":"ReadOnly"}]
-- or CSV --
username,email,display_name,persona
alice,alice@example.com,Alice Smith,Developer
bob,bob@example.com,Bob Jones,ReadOnly'
       style="font-family:monospace;font-size:12px;resize:vertical"></textarea>`,
    async () => {
      const text = (el("bulk-import-text")?.value || "").trim();
      if (!text) throw new Error("Paste JSON or CSV content first");

      let body, contentType;
      if (text.startsWith("[") || text.startsWith("{")) {
        try { JSON.parse(text); } catch { throw new Error("Invalid JSON — check syntax"); }
        body = text;
        contentType = "application/json";
      } else {
        body = text;
        contentType = "text/csv";
      }

      const token = auth.getToken();
      const headers = { "Content-Type": contentType };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch("/api/v1/users/import", { method: "POST", headers, body });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Import failed");

      closeModal();
      const errTxt = result.errors?.length ? `\n\nErrors:\n${result.errors.join("\n")}` : "";
      toast(`Imported: ${result.created} created, ${result.skipped} skipped${errTxt ? " (see console)" : ""}`, result.errors?.length ? "warning" : "success");
      if (result.errors?.length) console.warn("Bulk import errors:", result.errors);
      navigate("admin/users");
    },
    "Import"
  );
}

function showCreateUser() {
  openModal("New User",
    `<div class="form-group"><label>Username *</label><input id="uf-username" class="form-control" placeholder="e.g. jdoe"></div>
     <div class="form-group"><label>Email *</label><input id="uf-email" class="form-control" type="email" placeholder="jdoe@example.com"></div>
     <div class="form-group"><label>Display Name</label><input id="uf-name" class="form-control" placeholder="Jane Doe"></div>
     <div class="form-group"><label>Persona *</label><select id="uf-persona" class="form-control">
       ${PERSONAS.map(p => `<option value="${p}">${p}</option>`).join("")}
     </select></div>
     <div class="form-group"><label>LDAP DN</label><input id="uf-ldap" class="form-control" placeholder="cn=jdoe,ou=users,dc=example,dc=com"></div>`,
    async () => {
      const username = el("uf-username").value.trim();
      const email = el("uf-email").value.trim();
      if (!username || !email) return modalError("Username and email are required");
      try {
        await api.createUser({
          username, email,
          display_name: el("uf-name").value.trim() || null,
          persona: el("uf-persona").value,
          ldap_dn: el("uf-ldap").value.trim() || null,
        });
        closeModal(); toast("User created", "success");
        navigate("admin/users");
      } catch (e) { modalError(e.message); }
    }
  );
}

function showEditPersona(userId, current) {
  openModal("Change Persona",
    `<div class="form-group"><label>Persona</label><select id="ep-persona" class="form-control">
       ${PERSONAS.map(p => `<option value="${p}"${p === current ? " selected" : ""}>${p}</option>`).join("")}
     </select></div>
     <p style="color:var(--gray-600);font-size:13px;margin-top:8px">Changing the persona will replace the user's organisation-level role binding.</p>`,
    async () => {
      try {
        await api.updateUser(userId, { persona: el("ep-persona").value });
        closeModal(); toast("Persona updated", "success");
        navigate("admin/users/" + userId);
      } catch (e) { modalError(e.message); }
    }
  );
}

async function showAddBinding(userId) {
  const roles = await api.getRoles().catch(() => []);
  openModal("Add Role Binding",
    `<div class="form-group"><label>Role *</label><select id="ab-role" class="form-control">
       ${roles.map(r => `<option value="${r.id}">${r.name}</option>`).join("")}
     </select></div>
     <div class="form-group"><label>Scope *</label><input id="ab-scope" class="form-control" placeholder="organization · product:prod-id · environment:prod-env-id"></div>
     <div class="form-group"><label>Expires At (JIT access)</label><input id="ab-exp" class="form-control" type="datetime-local"></div>`,
    async () => {
      const scope = el("ab-scope").value.trim();
      const role_id = el("ab-role").value;
      if (!scope || !role_id) return modalError("Role and scope are required");
      const expires_at = el("ab-exp").value ? new Date(el("ab-exp").value).toISOString() : null;
      try {
        await api.addUserBinding(userId, { role_id, scope, expires_at });
        closeModal(); toast("Binding added", "success");
        navigate("admin/users/" + userId);
      } catch (e) { modalError(e.message); }
    }
  );
}

async function removeBinding(userId, bindingId) {
  if (!confirm("Remove this role binding?")) return;
  try {
    await api.removeUserBinding(userId, bindingId);
    toast("Binding removed", "success");
    navigate("admin/users/" + userId);
  } catch (e) { toast(e.message, "error"); }
}

function showCreateGroup() {
  openModal("New Group",
    `<div class="form-group"><label>Name *</label><input id="gf-name" class="form-control" placeholder="e.g. Platform Team"></div>
     <div class="form-group"><label>Description</label><textarea id="gf-desc" class="form-control" placeholder="Optional"></textarea></div>`,
    async () => {
      const name = el("gf-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        await api.createGroup({ name, description: el("gf-desc").value.trim() || null });
        closeModal(); toast("Group created", "success");
        navigate("admin/groups");
      } catch (e) { modalError(e.message); }
    }
  );
}

async function showGroupMembers(groupId, groupName) {
  const [group, users] = await Promise.all([
    api.getGroup(groupId).catch(() => ({ members: [] })),
    api.getUsers().catch(() => []),
  ]);
  const memberIds = new Set((group.members || []).map(m => m.id));
  const nonMembers = users.filter(u => !memberIds.has(u.id));

  openModal(`Members — ${groupName}`,
    `<div style="margin-bottom:12px">
       <strong>Current members (${group.members?.length || 0})</strong>
       <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">
         ${(group.members || []).length === 0 ? "<span style='color:var(--gray-500)'>None</span>"
           : (group.members || []).map(m => `
             <span style="background:var(--gray-100);padding:3px 10px;border-radius:12px;font-size:13px;display:flex;align-items:center;gap:6px">
               ${m.username}
               <button style="background:none;border:none;cursor:pointer;color:var(--danger);font-size:16px;line-height:1" onclick="removeGroupMemberAndRefresh('${groupId}','${m.id}','${groupName}')">×</button>
             </span>`).join("")}
       </div>
     </div>
     ${nonMembers.length > 0 ? `
     <div class="form-group" style="margin-top:16px">
       <label>Add member</label>
       <select id="gm-add" class="form-control">
         <option value="">— select user —</option>
         ${nonMembers.map(u => `<option value="${u.id}">${u.username} (${u.persona})</option>`).join("")}
       </select>
     </div>` : ""}`,
    async () => {
      const uid = el("gm-add")?.value;
      if (!uid) return closeModal();
      try {
        await api.addGroupMember(groupId, uid);
        closeModal(); toast("Member added", "success");
        navigate("admin/groups");
      } catch (e) { modalError(e.message); }
    }, "Add Member"
  );
}

async function removeGroupMemberAndRefresh(groupId, userId, groupName) {
  try {
    await api.removeGroupMember(groupId, userId);
    toast("Member removed", "success");
    closeModal();
    navigate("admin/groups");
  } catch (e) { toast(e.message, "error"); }
}

async function deleteUser(id, username) {
  if (!confirm(`Delete user "${username}"? This removes all their role bindings.`)) return;
  try {
    await api.deleteUser(id);
    toast("User deleted", "success");
    navigate("admin/users");
  } catch (e) { toast(e.message, "error"); }
}

function showEditGroup(id, name, description) {
  openModal("Edit Group",
    `<div class="form-group"><label>Name *</label><input id="eg-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Description</label><textarea id="eg-desc" class="form-control">${description}</textarea></div>`,
    async () => {
      const n = el("eg-name").value.trim();
      if (!n) return modalError("Name is required");
      try {
        await api.updateGroup(id, { name: n, description: el("eg-desc").value.trim() || null });
        closeModal(); toast("Group updated", "success");
        navigate("admin/groups");
      } catch (e) { modalError(e.message); }
    }
  );
}

async function deleteGroup(id, name) {
  if (!confirm(`Delete group "${name}"?`)) return;
  try {
    await api.deleteGroup(id);
    toast("Group deleted", "success");
    navigate("admin/groups");
  } catch (e) { toast(e.message, "error"); }
}

function showEditRole(id, name, description, permissions) {
  openModal("Edit Role",
    `<div class="form-group"><label>Name *</label><input id="er2-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Description</label><input id="er2-desc" class="form-control" value="${description}"></div>
     <div class="form-group"><label>Permissions</label>
       <textarea id="er2-perms" class="form-control" rows="5">${permissions.join("\n")}</textarea>
       <div style="color:var(--gray-500);font-size:12px;margin-top:4px">One permission per line. Wildcards supported: <code>release.*</code></div>
     </div>`,
    async () => {
      const n = el("er2-name").value.trim();
      const perms = el("er2-perms").value.trim().split("\n").map(p => p.trim()).filter(Boolean);
      if (!n) return modalError("Name is required");
      if (!perms.length) return modalError("At least one permission is required");
      try {
        await api.updateRole(id, { name: n, description: el("er2-desc").value.trim() || null, permissions: perms });
        closeModal(); toast("Role updated", "success");
        navigate("admin/roles");
      } catch (e) { modalError(e.message); }
    }
  );
}

async function deleteRole(id, name) {
  if (!confirm(`Delete role "${name}"? Users with this role will lose access.`)) return;
  try {
    await api.deleteRole(id);
    toast("Role deleted", "success");
    navigate("admin/roles");
  } catch (e) { toast(e.message, "error"); }
}

function showCreateRole() {
  openModal("New Role",
    `<div class="form-group"><label>Name *</label><input id="rf2-name" class="form-control" placeholder="e.g. SeniorDeployer"></div>
     <div class="form-group"><label>Description</label><input id="rf2-desc" class="form-control" placeholder="Optional"></div>
     <div class="form-group"><label>Permissions *</label>
       <textarea id="rf2-perms" class="form-control" rows="4" placeholder="One permission per line, e.g.&#10;release.view&#10;release.create&#10;pipeline.*"></textarea>
       <div style="color:var(--gray-500);font-size:12px;margin-top:4px">Wildcards supported: <code>release.*</code> grants all release permissions</div>
     </div>`,
    async () => {
      const name = el("rf2-name").value.trim();
      const perms = el("rf2-perms").value.trim().split("\n").map(p => p.trim()).filter(Boolean);
      if (!name) return modalError("Name is required");
      if (perms.length === 0) return modalError("At least one permission is required");
      try {
        await api.createRole({ name, description: el("rf2-desc").value.trim() || null, permissions: perms });
        closeModal(); toast("Role created", "success");
        navigate("admin/roles");
      } catch (e) { modalError(e.message); }
    }
  );
}

// ── Task management (pipeline detail) ─────────────────────────────────────
function showCreateTask(productId, pipelineId, stageId) {
  openModal("New Task",
    `<div class="form-group"><label>Name *</label><input id="tf-name" class="form-control" placeholder="e.g. Run unit tests"></div>
     <div class="form-group"><label>Description</label><input id="tf-desc" class="form-control" placeholder="Optional"></div>
     ${_taskTypeSelector("")}
     <div class="form-group"><label>Language *</label>
       <select id="tf-lang" class="form-control">
         <option value="bash">Bash</option>
         <option value="python">Python</option>
       </select>
     </div>
     <div class="form-group"><label>Script</label>
       <textarea id="tf-code" class="form-control code-editor" rows="8" placeholder="#!/bin/bash&#10;echo 'Hello'&#10;exit 0"></textarea>
     </div>
     <div class="form-group"><label>Execution Mode</label>
       <select id="tf-mode" class="form-control">
         <option value="sequential">Sequential (runs after previous task)</option>
         <option value="parallel">Parallel (runs alongside others)</option>
       </select>
     </div>
     <div class="form-group"><label>On Error</label>
       <select id="tf-err" class="form-control">
         <option value="fail">Fail stage</option>
         <option value="warn">Warn (continue with warning)</option>
         <option value="continue">Continue (ignore error)</option>
       </select>
     </div>
     <div class="form-group"><label>Order</label><input id="tf-order" class="form-control" type="number" value="0"></div>
     <div class="form-group"><label>Timeout (seconds)</label><input id="tf-timeout" class="form-control" type="number" value="300"></div>`,
    async () => {
      const name = el("tf-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        await api.createTask(productId, pipelineId, stageId, {
          name,
          description: el("tf-desc").value.trim() || null,
          task_type: _resolveTaskType() || null,
          run_language: el("tf-lang").value,
          run_code: el("tf-code").value || "",
          execution_mode: el("tf-mode").value,
          on_error: el("tf-err").value,
          order: parseInt(el("tf-order").value) || 0,
          timeout: parseInt(el("tf-timeout").value) || 300,
        });
        closeModal(); toast("Task created", "success");
        navigate(`products/${productId}/pipelines/${pipelineId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

function showEditTask(productId, pipelineId, stageId, taskId, name, desc, order, onError, timeout, isRequired, taskType) {
  openModal("Edit Task",
    `<div class="form-group"><label>Name *</label><input id="et-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Description</label><input id="et-desc" class="form-control" value="${desc}"></div>
     ${_taskTypeSelector(taskType || "")}
     <div class="form-group"><label>On Error</label>
       <select id="et-err" class="form-control">
         <option value="fail"${onError==="fail"?" selected":""}>Fail stage</option>
         <option value="warn"${onError==="warn"?" selected":""}>Warn (continue with warning)</option>
         <option value="continue"${onError==="continue"?" selected":""}>Continue (ignore error)</option>
       </select>
     </div>
     <div class="form-group"><label>Order</label><input id="et-order" class="form-control" type="number" value="${order}"></div>
     <div class="form-group"><label>Timeout (seconds)</label><input id="et-timeout" class="form-control" type="number" value="${timeout}"></div>
     <div class="form-group"><label>Required</label>
       <select id="et-req" class="form-control">
         <option value="true"${isRequired?" selected":""}>Yes</option>
         <option value="false"${!isRequired?" selected":""}>No</option>
       </select>
     </div>`,
    async () => {
      const n = el("et-name").value.trim();
      if (!n) return modalError("Name is required");
      try {
        await api.updateTask(productId, pipelineId, stageId, taskId, {
          name: n, description: el("et-desc").value.trim() || null,
          task_type: _resolveTaskType() || null,
          on_error: el("et-err").value,
          order: parseInt(el("et-order").value) || 0,
          timeout: parseInt(el("et-timeout").value) || 300,
          is_required: el("et-req").value === "true",
        });
        closeModal(); toast("Task updated", "success");
        navigate(`products/${productId}/pipelines/${pipelineId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

function showEditTaskScript(productId, pipelineId, stageId, taskId, taskName) {
  // Load current script then open editor
  api.getTask(productId, pipelineId, stageId, taskId).then(task => {
    openModal(`Script — ${taskName}`,
      `<div class="form-group"><label>Language</label>
         <select id="es-lang" class="form-control" style="width:160px">
           <option value="bash"${(task.run_language||"bash")==="bash"?" selected":""}>Bash</option>
           <option value="python"${task.run_language==="python"?" selected":""}>Python</option>
         </select>
       </div>
       <div class="form-group"><label>Execution Mode</label>
         <select id="es-mode" class="form-control" style="width:220px">
           <option value="sequential"${(task.execution_mode||"sequential")==="sequential"?" selected":""}>Sequential</option>
           <option value="parallel"${task.execution_mode==="parallel"?" selected":""}>Parallel</option>
         </select>
       </div>
       <div class="form-group" style="margin-top:8px">
         <label>Script</label>
         <textarea id="es-code" class="form-control code-editor" rows="14" style="font-family:monospace;font-size:13px">${(task.run_code||"").replace(/</g,"&lt;").replace(/>/g,"&gt;")}</textarea>
       </div>
       <div style="color:var(--gray-500);font-size:12px;margin-top:8px;background:var(--gray-50);border:1px solid var(--gray-200);border-radius:6px;padding:10px">
         <strong style="font-size:11px;color:var(--gray-700)">Available context variables ($CDT_* / os.environ)</strong>
         <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px">
           ${["CDT_PIPELINE_RUN_ID","CDT_PIPELINE_ID","CDT_PIPELINE_NAME","CDT_COMMIT_SHA","CDT_ARTIFACT_ID","CDT_TRIGGERED_BY","CDT_GIT_REPO","CDT_GIT_BRANCH","CDT_STAGE_RUN_ID","CDT_STAGE_ID","CDT_STAGE_NAME","CDT_TASK_RUN_ID","CDT_TASK_ID","CDT_TASK_NAME"].map(v =>
             `<code style="background:#e2e8f0;padding:1px 6px;border-radius:4px;font-size:10px;cursor:pointer"
               onclick="insertVarAtCursor('es-code','${(task.run_language||'bash')==='bash' ? '\\$'+v : 'os.environ[\\"'+v+'\\"]'}')">
               ${(task.run_language||'bash')==='bash' ? '$'+v : v}
             </code>`).join("")}
         </div>
         <div style="margin-top:8px">Exit 0 = Succeeded · exit 1 = Warning (on_error=warn) · exit 2+ = Failed<br>
         Print a JSON object as the last stdout line to pass data downstream.</div>
       </div>`,
      async () => {
        try {
          await api.updateTask(productId, pipelineId, stageId, taskId, {
            run_language: el("es-lang").value,
            run_code: el("es-code").value,
            execution_mode: el("es-mode").value,
          });
          closeModal(); toast("Script saved", "success");
          navigate(`products/${productId}/pipelines/${pipelineId}`);
        } catch (e) { modalError(e.message); }
      }, "Save Script"
    );
  }).catch(() => toast("Could not load task", "error"));
}

async function deleteTask(productId, pipelineId, stageId, taskId, name) {
  if (!confirm(`Delete task "${name}"?`)) return;
  try {
    await api.deleteTask(productId, pipelineId, stageId, taskId);
    toast("Task deleted", "success");
    navigate(`products/${productId}/pipelines/${pipelineId}`);
  } catch (e) { toast(e.message, "error"); }
}

async function runTaskNow(productId, pipelineId, stageId, taskId, taskName) {
  const STATUS_COLOR = { Succeeded: "#22c55e", Warning: "#f59e0b", Failed: "#ef4444", Running: "#3b82f6", Pending: "#9ca3af" };
  openModal(`▶ Run — ${taskName}`,
    `<div id="run-status-bar" style="padding:8px 12px;border-radius:6px;background:var(--gray-100);font-size:13px;margin-bottom:12px">
       <span id="run-status-dot" style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#9ca3af;margin-right:8px"></span>
       <strong id="run-status-label">Pending</strong>
       <span id="run-rc" style="margin-left:12px;color:var(--gray-500)"></span>
     </div>
     <div id="run-log-wrap" style="background:#111;border-radius:6px;padding:12px;min-height:120px;max-height:320px;overflow-y:auto">
       <pre id="run-log" style="color:#e5e7eb;font-size:12px;margin:0;white-space:pre-wrap">Starting…</pre>
     </div>
     <div id="run-output-wrap" style="display:none;margin-top:12px">
       <strong style="font-size:13px">Output JSON</strong>
       <pre id="run-output" style="background:var(--gray-100);padding:10px;border-radius:6px;font-size:12px;margin-top:6px"></pre>
     </div>`,
    () => closeModal(), "Close"
  );

  // Hide the confirm button — it's just a close
  el("modal-confirm").style.display = "none";

  try {
    const run = await api.runTask(productId, pipelineId, stageId, taskId, {});
    // Poll until terminal status
    let poll;
    poll = setInterval(async () => {
      try {
        const r = await api.getTaskRun(run.id);
        const dot = el("run-status-dot");
        const lbl = el("run-status-label");
        const logEl = el("run-log");
        const rc = el("run-rc");
        if (!dot) { clearInterval(poll); return; }
        const color = STATUS_COLOR[r.status] || "#9ca3af";
        dot.style.background = color;
        lbl.textContent = r.status;
        lbl.style.color = color;
        if (r.return_code !== null && r.return_code !== undefined) {
          rc.textContent = `exit ${r.return_code}`;
        }
        if (r.logs) logEl.textContent = r.logs;
        // Auto-scroll
        const wrap = el("run-log-wrap");
        if (wrap) wrap.scrollTop = wrap.scrollHeight;
        if (r.output_json) {
          const ow = el("run-output-wrap");
          if (ow) { ow.style.display = "block"; el("run-output").textContent = r.output_json; }
        }
        if (["Succeeded","Warning","Failed"].includes(r.status)) {
          clearInterval(poll);
          el("modal-confirm").style.display = "";
        }
      } catch { clearInterval(poll); }
    }, 1000);
  } catch (e) {
    const logEl = el("run-log");
    if (logEl) logEl.textContent = `Error: ${e.message}`;
    el("modal-confirm").style.display = "";
  }
}

// ── Stage management ───────────────────────────────────────────────────────
function showCreateStage(productId, pipelineId) {
  openModal("New Stage",
    `<div class="form-group"><label>Name *</label><input id="sf-name" class="form-control" placeholder="e.g. Build, Test, Deploy"></div>
     <div class="form-group"><label>Language</label>
       <select id="sf-lang" class="form-control">
         <option value="bash">Bash</option>
         <option value="python">Python</option>
       </select>
     </div>
     <div class="form-group"><label>Container Image</label><input id="sf-img" class="form-control" placeholder="e.g. ubuntu:22.04 (optional)"></div>
     <div class="form-group"><label>Order</label><input id="sf-order" class="form-control" type="number" value="0"></div>
     <div class="form-group"><label>Protected</label>
       <select id="sf-prot" class="form-control">
         <option value="false">No</option>
         <option value="true">Yes (requires approval gate)</option>
       </select>
     </div>
     <div class="form-group"><label>Accent Color</label>${_gradientPickerHtml("sf-color", STAGE_GRADIENTS[0].color)}</div>`,
    async () => {
      const name = el("sf-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        await api.createStage(productId, pipelineId, {
          name,
          run_language: el("sf-lang").value,
          container_image: el("sf-img").value.trim() || null,
          order: parseInt(el("sf-order").value) || 0,
          is_protected: el("sf-prot").value === "true",
          accent_color: document.getElementById("sf-color").value || null,
        });
        closeModal(); toast("Stage created", "success");
        navigate(`products/${productId}/pipelines/${pipelineId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

function showEditStage(productId, pipelineId, stageId, name, runLang, containerImg, order, isProtected, accentColor) {
  openModal("Edit Stage",
    `<div class="form-group"><label>Name *</label><input id="es2-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Language</label>
       <select id="es2-lang" class="form-control">
         <option value="bash"${runLang==="bash"?" selected":""}>Bash</option>
         <option value="python"${runLang==="python"?" selected":""}>Python</option>
       </select>
     </div>
     <div class="form-group"><label>Container Image</label><input id="es2-img" class="form-control" value="${containerImg}"></div>
     <div class="form-group"><label>Order</label><input id="es2-order" class="form-control" type="number" value="${order}"></div>
     <div class="form-group"><label>Protected</label>
       <select id="es2-prot" class="form-control">
         <option value="false"${!isProtected?" selected":""}>No</option>
         <option value="true"${isProtected?" selected":""}>Yes</option>
       </select>
     </div>
     <div class="form-group"><label>Accent Color</label>${_gradientPickerHtml("es2-color", accentColor || STAGE_GRADIENTS[0].color)}</div>`,
    async () => {
      const n = el("es2-name").value.trim();
      if (!n) return modalError("Name is required");
      try {
        await api.updateStage(productId, pipelineId, stageId, {
          name: n,
          run_language: el("es2-lang").value,
          container_image: el("es2-img").value.trim() || null,
          order: parseInt(el("es2-order").value) || 0,
          is_protected: el("es2-prot").value === "true",
          accent_color: document.getElementById("es2-color").value || null,
        });
        closeModal(); toast("Stage updated", "success");
        navigate(`products/${productId}/pipelines/${pipelineId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

async function deleteStage(productId, pipelineId, stageId, name) {
  if (!confirm(`Delete stage "${name}" and all its tasks?`)) return;
  try {
    await api.deleteStage(productId, pipelineId, stageId);
    toast("Stage deleted", "success");
    navigate(`products/${productId}/pipelines/${pipelineId}`);
  } catch (e) { toast(e.message, "error"); }
}

// ── Agents page ────────────────────────────────────────────────────────────
router.register("agents", async () => {
  setBreadcrumb({ label: "Agents" });
  setContent(loading());
  const pools = await api.getAgentPools().catch(() => []);
  const builtins = pools.filter(p => p.pool_type === "builtin");
  const custom   = pools.filter(p => p.pool_type === "custom");

  setContent(`
    <div class="page-header">
      <div><h1>Agent Pools</h1><div class="sub">Sandboxed execution environments for tasks</div></div>
      <button class="btn btn-primary" onclick="showCreateAgentPool()">+ New Agent Pool</button>
    </div>

    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><h2>Built-in Pools</h2></div>
      <div class="grid grid-3" style="padding:16px">
        ${builtins.length === 0
          ? `<div style="color:var(--gray-500)">No built-in pools found.</div>`
          : builtins.map(p => agentPoolCard(p, false)).join("")}
      </div>
    </div>

    <div class="card">
      <div class="card-header"><h2>Custom Pools</h2></div>
      ${custom.length === 0
        ? `<div class="empty-state"><div class="empty-icon">⚙️</div><p>No custom agent pools yet.</p></div>`
        : `<div class="grid grid-3" style="padding:16px">${custom.map(p => agentPoolCard(p, true)).join("")}</div>`}
    </div>
  `);
});

function agentPoolCard(pool, canDelete) {
  return `<div class="card" style="border:2px solid ${pool.is_active?"var(--brand)":"var(--gray-200)"}">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px">
      <strong>${pool.name}</strong>
      <span class="badge ${pool.is_active?"badge-success":"badge-silver"}">${pool.is_active?"Active":"Inactive"}</span>
    </div>
    <div style="font-size:12px;color:var(--gray-500);margin-bottom:6px">${pool.description||"No description"}</div>
    <div style="font-size:12px;margin-bottom:10px">
      <span class="badge badge-blue">${pool.pool_type}</span>
      <span style="margin-left:8px;color:var(--gray-500)">CPU: ${pool.cpu_limit||"500m"} · Mem: ${pool.memory_limit||"256Mi"}</span>
    </div>
    <div style="display:flex;gap:6px">
      ${canDelete
        ? `<button class="btn btn-danger btn-sm" onclick="deleteAgentPool('${pool.id}','${pool.name}')">Delete</button>`
        : `<span style="font-size:12px;color:var(--gray-400)">System pool</span>`}
    </div>
  </div>`;
}

function showCreateAgentPool() {
  openModal("New Agent Pool",
    `<div class="form-group"><label>Name *</label><input id="ap-name" class="form-control" placeholder="e.g. High-Memory Pool"></div>
     <div class="form-group"><label>Description</label><input id="ap-desc" class="form-control" placeholder="Optional"></div>
     <div class="form-group"><label>CPU Limit</label><input id="ap-cpu" class="form-control" value="500m" placeholder="e.g. 500m, 2"></div>
     <div class="form-group"><label>Memory Limit</label><input id="ap-mem" class="form-control" value="256Mi" placeholder="e.g. 256Mi, 1Gi"></div>
     <div class="form-group"><label>Max Concurrent Agents</label><input id="ap-max" class="form-control" type="number" value="5"></div>`,
    async () => {
      const name = el("ap-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        await api.createAgentPool({
          name, description: el("ap-desc").value.trim() || null,
          cpu_limit: el("ap-cpu").value.trim() || "500m",
          memory_limit: el("ap-mem").value.trim() || "256Mi",
          max_agents: parseInt(el("ap-max").value) || 5,
        });
        closeModal(); toast("Agent pool created", "success");
        navigate("agents");
      } catch (e) { modalError(e.message); }
    }
  );
}

async function deleteAgentPool(id, name) {
  if (!confirm(`Delete agent pool "${name}"?`)) return;
  try {
    await api.deleteAgentPool(id);
    toast("Agent pool deleted", "success");
    navigate("agents");
  } catch (e) { toast(e.message, "error"); }
}

// ── Container runner helpers ───────────────────────────────────────────────
async function saveRunnerSettings() {
  const runner = document.getElementById("runner-type-select")?.value || "subprocess";
  const image  = document.getElementById("runner-image-input")?.value?.trim() || "python:3.12-slim";
  try {
    await api.setSetting("TASK_RUNNER", runner);
    await api.setSetting("TASK_RUNNER_IMAGE", image);
    toast("Runner settings saved", "success");
    const display = document.getElementById("runner-current-settings");
    if (display) display.innerHTML = `Runner: <strong>${runner}</strong> &nbsp;|&nbsp; Image: <strong>${image}</strong>`;
  } catch (e) { toast(e.message, "error"); }
}

async function testRunnerSettings() {
  const runtime = document.getElementById("runner-type-select")?.value || "subprocess";
  const image   = document.getElementById("runner-image-input")?.value?.trim() || "python:3.12-slim";
  const el_     = document.getElementById("runner-test-result");
  if (el_) el_.innerHTML = `<span style="color:var(--gray-500)">Testing ${runtime}…</span>`;
  try {
    const res = await api.testRunner({ runtime, image });
    if (el_) {
      if (res.ok) {
        el_.innerHTML = `<span style="color:#059669">✓ ${res.message}</span>`;
      } else {
        el_.innerHTML = `<span style="color:#dc2626">✗ ${res.message}</span>`;
      }
    }
  } catch (e) {
    if (el_) el_.innerHTML = `<span style="color:#dc2626">✗ ${e.message}</span>`;
  }
}

// ── LDAP admin helpers ─────────────────────────────────────────────────────
async function loadLdapConfig() {
  const fields = {
    "ldap-url-display": "LDAP_URL",
    "ldap-bind-dn-display": "LDAP_BIND_DN",
    "ldap-base-dn-display": "LDAP_BASE_DN",
    "ldap-search-base-display": "LDAP_USER_SEARCH_BASE",
  };
  try {
    const cfg = await api.getLdapConfig();
    for (const [elId, key] of Object.entries(fields)) {
      const el2 = document.getElementById(elId);
      if (el2) el2.textContent = cfg[key] || "(not set)";
    }
  } catch (_) {
    for (const elId of Object.keys(fields)) {
      const el2 = document.getElementById(elId);
      if (el2) el2.textContent = "(read from environment)";
    }
  }
}

async function testLdapConnection() {
  const result = document.getElementById("ldap-test-result");
  if (result) result.innerHTML = `<span style="color:var(--gray-400)">Testing…</span>`;
  try {
    const body = {
      username: (document.getElementById("ldap-test-user")||{}).value || "",
      password: (document.getElementById("ldap-test-pass")||{}).value || "",
    };
    const res = await api.testLdap(body);
    if (res.ok) {
      if (result) result.innerHTML = `<span style="color:var(--success)">✓ ${res.message}</span>`;
      toast(res.message, "success");
    } else {
      if (result) result.innerHTML = `<span style="color:var(--danger)">✗ ${res.error}</span>`;
      toast(res.error, "error");
    }
  } catch (e) {
    if (result) result.innerHTML = `<span style="color:var(--danger)">✗ ${e.message}</span>`;
    toast(e.message, "error");
  }
}

// ── Stage gradient / colour picker ────────────────────────────────────────
const STAGE_GRADIENTS = [
  { label: "Ocean Blue",    color: "#3b82f6", grad: ["#2563eb","#60a5fa"] },
  { label: "Violet",        color: "#8b5cf6", grad: ["#7c3aed","#a78bfa"] },
  { label: "Emerald",       color: "#10b981", grad: ["#059669","#34d399"] },
  { label: "Amber",         color: "#f59e0b", grad: ["#d97706","#fcd34d"] },
  { label: "Rose",          color: "#f43f5e", grad: ["#e11d48","#fb7185"] },
  { label: "Cyan",          color: "#06b6d4", grad: ["#0891b2","#67e8f9"] },
  { label: "Orange",        color: "#f97316", grad: ["#ea580c","#fdba74"] },
  { label: "Indigo",        color: "#6366f1", grad: ["#4f46e5","#a5b4fc"] },
  { label: "Pink",          color: "#ec4899", grad: ["#db2777","#f9a8d4"] },
  { label: "Teal",          color: "#14b8a6", grad: ["#0d9488","#5eead4"] },
  { label: "Lime",          color: "#84cc16", grad: ["#65a30d","#bef264"] },
  { label: "Slate",         color: "#64748b", grad: ["#475569","#94a3b8"] },
  { label: "Fuchsia",       color: "#d946ef", grad: ["#c026d3","#e879f9"] },
  { label: "Sky",           color: "#0ea5e9", grad: ["#0284c7","#7dd3fc"] },
  { label: "Red",           color: "#ef4444", grad: ["#dc2626","#fca5a5"] },
  { label: "Green",         color: "#22c55e", grad: ["#16a34a","#86efac"] },
];

function _gradientPickerHtml(inputId, currentColor) {
  const swatches = STAGE_GRADIENTS.map((g, i) => {
    const sel = currentColor === g.color ? "outline:3px solid #1e293b;outline-offset:2px;" : "";
    return `<div title="${g.label}"
      onclick="document.getElementById('${inputId}').value='${g.color}';document.querySelectorAll('.grad-swatch-${inputId}').forEach(s=>s.style.outline='');this.style.outline='3px solid #1e293b';this.style.outlineOffset='2px'"
      class="grad-swatch-${inputId}"
      style="width:32px;height:32px;border-radius:8px;cursor:pointer;background:linear-gradient(135deg,${g.grad[0]},${g.grad[1]});${sel}flex-shrink:0"></div>`;
  }).join("");
  return `
    <div style="display:flex;flex-wrap:wrap;gap:8px;padding:10px;background:var(--gray-50);border:1px solid var(--gray-200);border-radius:10px">
      ${swatches}
    </div>
    <input type="hidden" id="${inputId}" value="${currentColor || STAGE_GRADIENTS[0].color}">`;
}

function _getGradForColor(color) {
  const g = STAGE_GRADIENTS.find(g => g.color === color);
  return g ? g.grad : [color, color];
}

async function showStageColorPicker(productId, pipelineId, stageId, stageName, currentColor) {
  openModal(`Stage Color — ${stageName}`,
    `<div class="form-group">
       <label style="margin-bottom:8px;display:block">Choose an accent color for this stage</label>
       ${_gradientPickerHtml("scp-color", currentColor || STAGE_GRADIENTS[0].color)}
     </div>`,
    async () => {
      const color = document.getElementById("scp-color").value;
      try {
        await api.updateStage(productId, pipelineId, stageId, { accent_color: color });
        closeModal(); toast("Stage color updated", "success");
        navigate(`products/${productId}/pipelines/${pipelineId}`);
      } catch(e) { modalError(e.message); }
    }
  );
}

// ── Pipeline visual editor (SVG) ──────────────────────────────────────────
function renderPipelineVisual(pipelineId, svgId) {
  const svg = document.getElementById(svgId || "pipeline-visual-svg-normal");
  if (!svg) return;
  const stages = _pipelineVisualStages;
  if (!stages || stages.length === 0) {
    svg.innerHTML = `<text x="20" y="40" font-size="14" fill="#888">No stages to display.</text>`;
    svg.setAttribute("width", 300);
    svg.setAttribute("height", 60);
    return;
  }

  // ── Layout constants ──────────────────────────────────────────────────────
  const COL_W      = 200;   // column card width
  const COL_GAP    = 48;    // gap between columns (arrow space)
  const PAD_X      = 24;    // canvas left/right padding
  const PAD_Y      = 24;    // canvas top/bottom padding
  const HDR_H      = 52;    // column header height
  const ACCENT_H   = 4;     // coloured accent bar at top of column
  const TASK_H     = 48;    // task card height
  const TASK_GAP   = 6;     // gap between task cards
  const TASK_MX    = 10;    // task card horizontal margin inside column
  const COL_FOOT   = 10;    // padding below last task card
  const CORNER     = 8;     // card border radius
  const TASK_CR    = 5;     // task card border radius

  // Stage accent colours — cycle through palette
  const ACCENT_PALETTE = ["#3b82f6","#8b5cf6","#10b981","#f59e0b","#ef4444","#06b6d4","#f97316","#6366f1"];

  // ── Column metrics ────────────────────────────────────────────────────────
  const sorted = [...stages].sort((a, b) => a.order - b.order);
  const cols = sorted.map((stage, idx) => {
    const tasks = (stage.tasks || []).sort((a, b) => a.order - b.order);
    const colH = HDR_H + tasks.length * (TASK_H + TASK_GAP) + (tasks.length ? TASK_GAP : 0) + COL_FOOT;
    const accent = stage.accent_color || ACCENT_PALETTE[idx % ACCENT_PALETTE.length];
    return { stage, tasks, colH, accent };
  });

  const maxColH = Math.max(...cols.map(c => c.colH), HDR_H + COL_FOOT + 20);
  const totalW  = PAD_X * 2 + cols.length * COL_W + (cols.length - 1) * COL_GAP;
  const totalH  = PAD_Y * 2 + maxColH;

  // ── Task-type colour map ──────────────────────────────────────────────────
  const TYPE_COLOR = {
    "unit-test":"#3b82f6","integration-test":"#8b5cf6","e2e-test":"#6366f1",
    "build":"#f59e0b","docker-build":"#f97316","compile":"#eab308",
    "deploy":"#10b981","helm-deploy":"#059669","canary":"#34d399",
    "security-scan":"#ef4444","dast":"#dc2626","sast":"#f87171",
    "code-coverage":"#0ea5e9","lint":"#64748b","notify":"#a855f7",
    "python":"#3b82f6",
  };

  function taskAccent(task) {
    if (task.task_type) {
      for (const t of task.task_type.split(",")) {
        const c = TYPE_COLOR[t.trim().toLowerCase()];
        if (c) return c;
      }
    }
    return "#94a3b8";
  }

  // ── SVG elements ──────────────────────────────────────────────────────────
  const el = [];

  // ── defs: drop-shadow filters, arrowhead, per-stage gradients ────────────
  const gradDefs = cols.map(({ stage, accent }) => {
    const grad = _getGradForColor(accent);
    return `<linearGradient id="stg-grad-${stage.id}" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="${grad[0]}"/>
      <stop offset="100%" stop-color="${grad[1]}"/>
    </linearGradient>`;
  }).join("\n");
  el.push(`<defs>
    <filter id="dshadow-${pipelineId}" x="-10%" y="-10%" width="130%" height="130%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#00000018"/>
    </filter>
    <filter id="tshadow-${pipelineId}" x="-5%" y="-10%" width="120%" height="140%">
      <feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#00000010"/>
    </filter>
    <marker id="arr-${pipelineId}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
      <path d="M1,1 L7,4 L1,7 Z" fill="#94a3b8"/>
    </marker>
    ${gradDefs}
  </defs>`);

  // ── background ────────────────────────────────────────────────────────────
  el.push(`<rect width="${totalW}" height="${totalH}" fill="#f1f5f9" rx="10"/>`);

  cols.forEach(({ stage, tasks, colH, accent }, idx) => {
    const cx = PAD_X + idx * (COL_W + COL_GAP);
    const cy = PAD_Y;

    // ── Connector arrow to next column ──────────────────────────────────────
    if (idx < cols.length - 1) {
      const ax1 = cx + COL_W + 6;
      const ax2 = cx + COL_W + COL_GAP - 6;
      const ay  = cy + HDR_H / 2;
      el.push(`<line x1="${ax1}" y1="${ay}" x2="${ax2}" y2="${ay}" stroke="#94a3b8" stroke-width="2" stroke-dasharray="4,3" marker-end="url(#arr-${pipelineId})"/>`);
    }

    // ── Column card ─────────────────────────────────────────────────────────
    el.push(`<rect x="${cx}" y="${cy}" width="${COL_W}" height="${maxColH}" rx="${CORNER}" fill="#ffffff" stroke="#e2e8f0" stroke-width="1.5" filter="url(#dshadow-${pipelineId})"/>`);
    // Accent bar top (gradient)
    el.push(`<rect x="${cx}" y="${cy}" width="${COL_W}" height="${ACCENT_H}" rx="${CORNER}" fill="url(#stg-grad-${stage.id})"/>`);
    el.push(`<rect x="${cx}" y="${cy + ACCENT_H - CORNER}" width="${COL_W}" height="${CORNER}" fill="url(#stg-grad-${stage.id})"/>`);

    // ── Column header (clickable) ────────────────────────────────────────────
    const stageLabel = stage.name.length > 20 ? stage.name.slice(0, 18) + "…" : stage.name;
    el.push(`<g style="cursor:pointer" onclick="visualScrollToStage('${stage.id}')" title="Go to stage">`);
    // Stage number badge
    el.push(`<rect x="${cx + 10}" y="${cy + ACCENT_H + 8}" width="22" height="18" rx="4" fill="${accent}18"/>`);
    el.push(`<text x="${cx + 21}" y="${cy + ACCENT_H + 20}" text-anchor="middle" font-size="10" font-weight="700" fill="${accent}" font-family="system-ui,sans-serif">${stage.order}</text>`);
    // Stage name
    el.push(`<text x="${cx + 38}" y="${cy + ACCENT_H + 18}" font-size="12" font-weight="700" fill="#0f172a" font-family="system-ui,sans-serif">${stageLabel}</text>`);
    // Task count chip
    const tCount = tasks.length;
    const chipLabel = `${tCount} task${tCount !== 1 ? "s" : ""}`;
    el.push(`<rect x="${cx + 10}" y="${cy + ACCENT_H + 30}" width="${chipLabel.length * 6 + 10}" height="14" rx="7" fill="${accent}15"/>`);
    el.push(`<text x="${cx + 15}" y="${cy + ACCENT_H + 41}" font-size="10" fill="${accent}" font-weight="600" font-family="system-ui,sans-serif">${chipLabel}</text>`);
    // Protected lock icon
    if (stage.is_protected) {
      el.push(`<text x="${cx + COL_W - 14}" y="${cy + ACCENT_H + 20}" text-anchor="middle" font-size="12" fill="#64748b" font-family="system-ui,sans-serif">🔒</text>`);
    }
    el.push(`</g>`);

    // ── Divider under header ─────────────────────────────────────────────────
    el.push(`<line x1="${cx + 8}" y1="${cy + HDR_H}" x2="${cx + COL_W - 8}" y2="${cy + HDR_H}" stroke="#f1f5f9" stroke-width="1.5"/>`);

    // ── Task cards ───────────────────────────────────────────────────────────
    let ty = cy + HDR_H + TASK_GAP;
    if (tasks.length === 0) {
      el.push(`<text x="${cx + COL_W/2}" y="${ty + 20}" text-anchor="middle" font-size="11" fill="#cbd5e1" font-family="system-ui,sans-serif">No tasks yet</text>`);
    }
    for (const task of tasks) {
      const tx    = cx + TASK_MX;
      const tw    = COL_W - TASK_MX * 2;
      const tacc  = taskAccent(task);
      const tName = task.name.length > 22 ? task.name.slice(0, 20) + "…" : task.name;
      const tTag  = task.task_type ? task.task_type.split(",")[0].trim() : (task.run_language && task.run_language !== "bash" ? task.run_language : "");
      const tRequired = task.is_required;
      const tOnErr = task.on_error || "fail";

      el.push(`<g style="cursor:pointer" onclick="visualScrollToTask('${task.id}','${stage.id}')" title="${task.name}">`);
      // Card
      el.push(`<rect x="${tx}" y="${ty}" width="${tw}" height="${TASK_H}" rx="${TASK_CR}" fill="#ffffff" stroke="#e8eef6" stroke-width="1" filter="url(#tshadow-${pipelineId})"/>`);
      // Left accent stripe
      el.push(`<rect x="${tx}" y="${ty}" width="3" height="${TASK_H}" rx="${TASK_CR}" fill="${tacc}"/>`);
      el.push(`<rect x="${tx + 3 - TASK_CR}" y="${ty}" width="${TASK_CR}" height="${TASK_H}" fill="${tacc}"/>`);

      // Task number circle
      el.push(`<circle cx="${tx + 18}" cy="${ty + TASK_H/2}" r="9" fill="${tacc}15"/>`);
      el.push(`<text x="${tx + 18}" y="${ty + TASK_H/2 + 4}" text-anchor="middle" font-size="9" font-weight="700" fill="${tacc}" font-family="system-ui,sans-serif">${task.order}</text>`);

      // Task name
      el.push(`<text x="${tx + 32}" y="${ty + 16}" font-size="11" font-weight="600" fill="#1e293b" font-family="system-ui,sans-serif">${tName}</text>`);

      // Tag + on_error indicator row
      if (tTag) {
        const tagW = Math.min(tTag.length * 5.8 + 10, tw - 44);
        el.push(`<rect x="${tx + 32}" y="${ty + 22}" width="${tagW}" height="13" rx="3" fill="${tacc}15"/>`);
        el.push(`<text x="${tx + 37}" y="${ty + 32}" font-size="9" font-weight="600" fill="${tacc}" font-family="system-ui,sans-serif">${tTag.length > 14 ? tTag.slice(0,13)+"…" : tTag}</text>`);
      }

      // on_error dot
      const dotColor = tOnErr === "warn" ? "#f59e0b" : "#ef4444";
      el.push(`<circle cx="${tx + tw - 10}" cy="${ty + TASK_H - 12}" r="4" fill="${dotColor}30" stroke="${dotColor}" stroke-width="1.2"/>`);

      // Required star
      if (tRequired) {
        el.push(`<text x="${tx + tw - 22}" y="${ty + TASK_H - 8}" font-size="10" fill="#f59e0b" font-family="system-ui,sans-serif">★</text>`);
      }

      el.push(`</g>`);
      ty += TASK_H + TASK_GAP;
    }
  });

  svg.innerHTML = el.join("\n");
  svg.setAttribute("width", totalW);
  svg.setAttribute("height", totalH);
}

// ── Visual graph navigation helpers ──────────────────────────────────────────
function _isYamlModeActive() {
  const m = document.getElementById("pl-yaml-mode");
  return m && m.style.display !== "none";
}

function _yamlScrollToPattern(pattern) {
  const ta = document.getElementById("pipeline-yaml-editor");
  if (!ta) return;
  const lines = ta.value.split("\n");
  let matchLine = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes(pattern)) { matchLine = i; break; }
  }
  if (matchLine === -1) return;

  // Compute character offset to that line
  let offset = 0;
  for (let i = 0; i < matchLine; i++) offset += lines[i].length + 1;
  const end = offset + lines[matchLine].length;

  // Select and scroll to the line
  ta.focus();
  ta.setSelectionRange(offset, end);

  // Scroll the textarea so the matched line is visible
  const lineH = parseFloat(getComputedStyle(ta).lineHeight) || 18;
  ta.scrollTop = Math.max(0, (matchLine - 3) * lineH);

  // Flash the textarea border to draw attention
  ta.style.outline = "2px solid var(--brand)";
  setTimeout(() => { ta.style.outline = ""; }, 1500);
}

function visualScrollToStage(stageId) {
  if (_isYamlModeActive()) {
    const block = document.getElementById("stage-block-" + stageId);
    const stageName = block ? block.dataset.stageName : stageId;
    _yamlScrollToPattern(`name: ${stageName}`);
    return;
  }
  const el = document.getElementById("stage-block-" + stageId);
  if (!el) return;
  // Expand if collapsed
  const body = document.getElementById("stage-body-" + stageId);
  const arrow = document.getElementById("stage-arrow-" + stageId);
  if (body && body.style.display === "none") {
    body.style.display = "";
    if (arrow) arrow.style.transform = "";
  }
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.style.outline = "2px solid var(--brand)";
  setTimeout(() => { el.style.outline = ""; }, 1500);
}

function visualScrollToTask(taskId, stageId) {
  if (_isYamlModeActive()) {
    const row = document.getElementById("task-row-" + taskId);
    const taskName = row ? row.dataset.taskName : taskId;
    _yamlScrollToPattern(`name: ${taskName}`);
    return;
  }
  // Expand stage first
  visualScrollToStage(stageId);
  setTimeout(() => {
    const row = document.getElementById("task-row-" + taskId);
    if (!row) return;
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    row.style.background = "var(--brand-faint)";
    setTimeout(() => { row.style.background = ""; }, 1500);
  }, 300);
}

// ── Pipeline YAML editor ───────────────────────────────────────────────────
async function loadPipelineYaml(productId, pipelineId) {
  const ta = document.getElementById("pipeline-yaml-editor");
  const st = document.getElementById("pipeline-yaml-status");
  if (!ta) return;
  ta.value = "# Loading…";
  try {
    const token = api.auth ? api.auth.getToken() : auth.getToken();
    const headers = {};
    const t = auth.getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
    const res = await fetch(`/api/v1/products/${productId}/pipelines/${pipelineId}/export`, { headers });
    if (!res.ok) throw new Error("Failed to load YAML");
    ta.value = await res.text();
    if (st) st.innerHTML = `<span style="color:var(--gray-400)">Loaded at ${new Date().toLocaleTimeString()}</span>`;
  } catch (e) {
    ta.value = "# Error loading YAML: " + e.message;
  }
}

async function savePipelineYaml(productId, pipelineId) {
  const ta = document.getElementById("pipeline-yaml-editor");
  const st = document.getElementById("pipeline-yaml-status");
  if (!ta) return;
  const yaml = ta.value.trim();
  if (!yaml) return;
  if (st) st.innerHTML = `<span style="color:var(--gray-400)">Saving…</span>`;
  try {
    await api.importPipelineYaml(productId, pipelineId, yaml);
    if (st) st.innerHTML = `<span style="color:var(--success)">✓ Saved successfully at ${new Date().toLocaleTimeString()}</span>`;
    toast("Pipeline definition saved", "success");
  } catch (e) {
    if (st) st.innerHTML = `<span style="color:var(--danger)">✗ ${e.message}</span>`;
    toast(e.message, "error");
  }
}

async function gitPullPipeline(productId, pipelineId) {
  const st = document.getElementById("git-pull-status");
  if (st) st.innerHTML = `<span style="color:var(--gray-400)">Pulling…</span>`;
  try {
    const result = await api.gitPullPipeline(productId, pipelineId);
    if (st) st.innerHTML = `<span style="color:var(--success)">✓ Applied @ <code>${result.sha}</code></span>`;
    toast(`Pulled @ ${result.sha}`, "success");
    await loadPipelineYaml(productId, pipelineId);
  } catch (e) {
    if (st) st.innerHTML = `<span style="color:var(--danger)">✗ ${e.message}</span>`;
    toast(e.message, "error");
  }
}

async function gitPushPipeline(productId, pipelineId) {
  const st = document.getElementById("git-push-status");
  const authorName = (document.getElementById("git-author-name")||{}).value || "Conduit";
  const authorEmail = (document.getElementById("git-author-email")||{}).value || "rw@conduit.local";
  if (st) st.innerHTML = `<span style="color:var(--gray-400)">Pushing…</span>`;
  try {
    const result = await api.gitPushPipeline(productId, pipelineId, { author_name: authorName, author_email: authorEmail });
    if (st) st.innerHTML = `<span style="color:var(--success)">✓ Pushed @ <code>${result.sha}</code></span>`;
    toast(`Pushed @ ${result.sha}`, "success");
  } catch (e) {
    if (st) st.innerHTML = `<span style="color:var(--danger)">✗ ${e.message}</span>`;
    toast(e.message, "error");
  }
}

// ── YAML export helpers ────────────────────────────────────────────────────
async function exportYaml(url, filename) {
  try {
    const headers = {};
    const t = auth.getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error("Export failed");
    const text = await res.text();
    const blob = new Blob([text], { type: "text/yaml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
    toast("YAML exported", "success");
  } catch (e) { toast(e.message, "error"); }
}

function showImportYaml(url, label, onDone) {
  openModal(`Import YAML — ${label}`,
    `<div class="form-group"><label>YAML File</label>
       <input id="yml-file" type="file" class="form-control" accept=".yaml,.yml">
     </div>
     <div class="form-group"><label>or paste YAML</label>
       <textarea id="yml-paste" class="form-control code-editor" rows="10" placeholder="Paste YAML here..."></textarea>
     </div>`,
    async () => {
      let text = el("yml-paste").value.trim();
      if (!text) {
        const file = el("yml-file").files[0];
        if (!file) return modalError("Provide a YAML file or paste content");
        text = await file.text();
      }
      try {
        const hdrs = { "Content-Type": "application/x-yaml" };
        const tok = auth.getToken(); if (tok) hdrs["Authorization"] = `Bearer ${tok}`;
        const res = await fetch(url, { method: "POST", headers: hdrs, body: text });
        if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.error || res.statusText); }
        closeModal(); toast("Import successful", "success");
        if (onDone) onDone();
      } catch (e) { modalError(e.message); }
    }, "Import"
  );
}

// ── Pipeline run detail ────────────────────────────────────────────────────
const TERMINAL = new Set(["Succeeded", "Failed", "Cancelled", "Warning"]);

function _statusIcon(status) {
  return { Succeeded: "✓", Failed: "✕", Running: "◉", Pending: "○", Warning: "⚠", Cancelled: "⊘" }[status] || "○";
}

function _stageBoxClass(status) {
  const m = { Running: "status-running", Succeeded: "status-succeeded", Failed: "status-failed", Warning: "status-warning", Cancelled: "status-cancelled" };
  return m[status] || "";
}

function _statusColor(status) {
  return { Succeeded: "#22c55e", Failed: "#ef4444", Running: "#3b82f6", Warning: "#f59e0b", Cancelled: "#94a3b8", Pending: "#cbd5e1" }[status] || "#cbd5e1";
}

// Muted status palette for run flow diagram — readable without being garish
const _RUN_STATUS = {
  Succeeded: { dot: "#16a34a", dotBg: "#dcfce7", text: "#15803d", bar: "#22c55e" },
  Failed:    { dot: "#dc2626", dotBg: "#fee2e2", text: "#b91c1c", bar: "#ef4444" },
  Running:   { dot: "#2563eb", dotBg: "#dbeafe", text: "#1d4ed8", bar: "#3b82f6" },
  Warning:   { dot: "#d97706", dotBg: "#fef3c7", text: "#b45309", bar: "#f59e0b" },
  Cancelled: { dot: "#6b7280", dotBg: "#f3f4f6", text: "#4b5563", bar: "#9ca3af" },
  Pending:   { dot: "#94a3b8", dotBg: "#f1f5f9", text: "#64748b", bar: "#cbd5e1" },
};
function _rs(status) { return _RUN_STATUS[status] || _RUN_STATUS.Pending; }

function _renderPipelineRun(run, productId, pipelineId) {
  const stageRuns = (run.stage_runs || []).sort((a, b) => (a.stage_order || 0) - (b.stage_order || 0));

  // ── Visual flow graph ─────────────────────────────────────────────────
  const STAGE_W = 210;
  const COL_GAP  = 48;
  const HEAD_H   = 54;
  const ACCENT_H = 4;
  const TASK_H   = 30;
  const TASK_PAD = 5;
  const PAD_X    = 16;
  const PAD_Y    = 16;
  const CORNER   = 8;

  // Match stage accent colors from the pipeline definition if available
  const stageAccentMap = {};
  (_pipelineVisualStages || []).forEach(s => { stageAccentMap[s.id] = s.accent_color; });

  let svgCols = [];
  let cx = PAD_X;
  for (const sr of stageRuns) {
    const tasks = sr.task_runs || [];
    const colH = HEAD_H + tasks.length * (TASK_H + TASK_PAD) + TASK_PAD + 8;
    svgCols.push({ sr, tasks, x: cx, colH });
    cx += STAGE_W + COL_GAP;
  }
  const totalW = Math.max(cx - COL_GAP + PAD_X, 300);
  const totalH = Math.max(...(svgCols.map(c => c.colH)), 100) + PAD_Y * 2;

  let svgEls = [];

  // Defs — per-stage accent gradients + drop shadow + arrow
  const gradDefs = svgCols.map(({ sr }, i) => {
    const ac = stageAccentMap[sr.stage_id] || STAGE_GRADIENTS[i % STAGE_GRADIENTS.length].color;
    const g  = _getGradForColor(ac);
    return `<linearGradient id="rg-ac-${sr.id}" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="${g[0]}"/><stop offset="100%" stop-color="${g[1]}"/>
    </linearGradient>`;
  }).join("");

  svgEls.push(`<defs>
    ${gradDefs}
    <filter id="rf-shadow" x="-8%" y="-8%" width="120%" height="130%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#00000014"/>
    </filter>
    <filter id="rf-tshadow" x="-5%" y="-5%" width="115%" height="130%">
      <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#0000000d"/>
    </filter>
    <marker id="run-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
      <path d="M1,1 L7,4 L1,7 Z" fill="#94a3b8"/>
    </marker>
  </defs>`);

  // Canvas background
  svgEls.push(`<rect width="${totalW}" height="${totalH}" fill="#f8fafc" rx="10"/>`);

  // Connector arrows
  for (let i = 0; i < svgCols.length - 1; i++) {
    const { x: ax, colH: ah } = svgCols[i];
    const { x: bx } = svgCols[i + 1];
    const ay = PAD_Y + HEAD_H / 2;
    svgEls.push(`<line x1="${ax+STAGE_W+4}" y1="${ay}" x2="${bx-4}" y2="${ay}" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#run-arrow)"/>`);
  }

  // Stage columns
  for (let ci = 0; ci < svgCols.length; ci++) {
    const { sr, tasks, x: sx, colH } = svgCols[ci];
    const sy  = PAD_Y;
    const rs  = _rs(sr.status);
    const ac  = stageAccentMap[sr.stage_id] || STAGE_GRADIENTS[ci % STAGE_GRADIENTS.length].color;

    // Card
    svgEls.push(`<rect x="${sx}" y="${sy}" width="${STAGE_W}" height="${colH}" rx="${CORNER}" fill="#ffffff" stroke="#e2e8f0" stroke-width="1.5" filter="url(#rf-shadow)"/>`);

    // Accent bar (stage color, not status color)
    svgEls.push(`<rect x="${sx}" y="${sy}" width="${STAGE_W}" height="${ACCENT_H}" rx="${CORNER}" fill="url(#rg-ac-${sr.id})"/>`);
    svgEls.push(`<rect x="${sx}" y="${sy+ACCENT_H-CORNER}" width="${STAGE_W}" height="${CORNER}" fill="url(#rg-ac-${sr.id})"/>`);

    // Stage name
    const sName = (sr.stage_name || sr.stage_id || "Stage").slice(0, 22);
    svgEls.push(`<text x="${sx+12}" y="${sy+ACCENT_H+16}" font-size="12" font-weight="700" fill="#0f172a" font-family="system-ui,sans-serif">${sName}</text>`);

    // Status pill
    const dur = fmtDuration(sr.started_at, sr.finished_at);
    const pillW = 90;
    svgEls.push(`<rect x="${sx+10}" y="${sy+ACCENT_H+22}" width="${pillW}" height="16" rx="8" fill="${rs.dotBg}"/>`);
    svgEls.push(`<circle cx="${sx+20}" cy="${sy+ACCENT_H+30}" r="4" fill="${rs.dot}"/>`);
    svgEls.push(`<text x="${sx+27}" y="${sy+ACCENT_H+34}" font-size="9" font-weight="600" fill="${rs.text}" font-family="system-ui,sans-serif">${sr.status}${dur ? " · "+dur : ""}</text>`);

    // Clickable header overlay
    svgEls.push(`<rect x="${sx}" y="${sy}" width="${STAGE_W}" height="${HEAD_H}" rx="${CORNER}" fill="transparent" style="cursor:pointer" onclick="document.getElementById('sr-${sr.id}')?.scrollIntoView({behavior:'smooth'})"/>`);

    // Divider
    svgEls.push(`<line x1="${sx+8}" y1="${sy+HEAD_H}" x2="${sx+STAGE_W-8}" y2="${sy+HEAD_H}" stroke="#f1f5f9" stroke-width="1.5"/>`);

    // Task rows
    let ty = sy + HEAD_H + TASK_PAD;
    for (const tr of tasks) {
      const trs  = _rs(tr.status);
      const tName = (tr.task_name || tr.task_id || "Task").slice(0, 24);
      const tdur  = fmtDuration(tr.started_at, tr.finished_at);
      // Task card
      svgEls.push(`<rect x="${sx+8}" y="${ty}" width="${STAGE_W-16}" height="${TASK_H}" rx="5" fill="#ffffff" stroke="#edf2f7" stroke-width="1" filter="url(#rf-tshadow)"/>`);
      // Left status stripe
      svgEls.push(`<rect x="${sx+8}" y="${ty}" width="3" height="${TASK_H}" rx="5" fill="${trs.bar}"/>`);
      svgEls.push(`<rect x="${sx+8+3-5}" y="${ty}" width="5" height="${TASK_H}" fill="${trs.bar}"/>`);
      // Status dot
      svgEls.push(`<circle cx="${sx+22}" cy="${ty+TASK_H/2}" r="4" fill="${trs.dotBg}" stroke="${trs.dot}" stroke-width="1.2"/>`);
      // Task name
      svgEls.push(`<text x="${sx+31}" y="${ty+12}" font-size="10" font-weight="600" fill="#1e293b" font-family="system-ui,sans-serif">${tName}</text>`);
      // Duration
      svgEls.push(`<text x="${sx+31}" y="${ty+23}" font-size="9" fill="#94a3b8" font-family="system-ui,sans-serif">${tdur || sr.status}</text>`);
      // Clickable
      svgEls.push(`<rect x="${sx+8}" y="${ty}" width="${STAGE_W-16}" height="${TASK_H}" rx="5" fill="transparent" style="cursor:pointer" onclick="toggleLog('log-${tr.id}')"/>`);
      ty += TASK_H + TASK_PAD;
    }
    if (!tasks.length) {
      svgEls.push(`<text x="${sx+STAGE_W/2}" y="${sy+HEAD_H+24}" text-anchor="middle" font-size="11" fill="#cbd5e1" font-family="system-ui,sans-serif">No tasks</text>`);
    }
  }

  const flowSvg = stageRuns.length
    ? `<svg width="${totalW}" height="${totalH}" style="display:block">${svgEls.join("")}</svg>`
    : `<p style="color:var(--gray-400);padding:16px">No stages to display.</p>`;

  // ── Stage detail cards ────────────────────────────────────────────────
  const stageDetails = stageRuns.map(sr => {
    const taskRows = (sr.task_runs || []).map(tr => {
      const tc = _statusColor(tr.status);
      return `
        <div class="task-run-row" style="border-left:3px solid ${tc}">
          <div style="display:flex;align-items:center;gap:8px;flex:1;flex-wrap:wrap">
            <span class="task-run-name">${tr.task_name || tr.task_id}</span>
            ${statusBadge(tr.status)}
            <span class="task-run-duration">${fmtDuration(tr.started_at, tr.finished_at)}</span>
            ${tr.return_code !== null && tr.return_code !== undefined
              ? `<code style="font-size:11px;color:var(--gray-400)">exit ${tr.return_code}</code>`
              : ""}
            <button class="btn btn-secondary btn-sm ctx-inspect-btn" style="font-size:11px;padding:2px 8px"
              onclick="toggleLog('ctx-${tr.id}')">Context</button>
            <button class="task-log-toggle" onclick="toggleLog('log-${tr.id}')">Logs</button>
          </div>
          <div id="ctx-${tr.id}" class="task-log-block">
            <div class="ctx-inspector" id="ctx-inner-${tr.id}">
              <div class="ctx-tabs">
                <button class="ctx-tab active" onclick="ctxTab('${tr.id}','env',this)">CDT Variables</button>
                <button class="ctx-tab" onclick="ctxTab('${tr.id}','props',this)">Properties</button>
                <button class="ctx-tab" onclick="ctxTab('${tr.id}','output',this)">Output JSON</button>
              </div>
              <div id="ctx-pane-env-${tr.id}" class="ctx-pane ctx-pane-active">
                ${_ctxEnvTable(tr)}
              </div>
              <div id="ctx-pane-props-${tr.id}" class="ctx-pane">
                ${_ctxPropsTable(tr)}
              </div>
              <div id="ctx-pane-output-${tr.id}" class="ctx-pane">
                ${_ctxOutputPanel(tr)}
              </div>
            </div>
          </div>
          <div id="log-${tr.id}" class="task-log-block">
            <div class="log-viewer"><pre style="margin:0;white-space:pre-wrap;font-size:12px">${tr.logs ? tr.logs.replace(/</g,"&lt;").replace(/>/g,"&gt;") : "(no logs)"}</pre></div>
          </div>
        </div>`;
    }).join("");

    const headerBg = { Succeeded: "#f8fafc", Failed: "#fef2f2", Running: "#eff6ff", Warning: "#fffbeb", Cancelled: "#f8fafc" }[sr.status] || "var(--gray-50)";
    const stageAccent = ((_pipelineVisualStages||[]).find(s => s.id === sr.stage_id) || {}).accent_color || _statusColor(sr.status);
    const canRestart = TERMINAL.has(run.status);
    const srProps = sr.runtime_properties || {};
    const srPropsJson = Object.keys(srProps).length ? JSON.stringify(srProps, null, 2) : null;
    return `
      <div id="sr-${sr.id}" class="card" style="margin-bottom:14px;border-left:4px solid ${stageAccent}">
        <div class="card-header" style="background:${headerBg}">
          <h3 style="margin:0;font-size:15px">${_statusIcon(sr.status)} ${sr.stage_name || sr.stage_id}</h3>
          <div style="display:flex;align-items:center;gap:10px">
            ${statusBadge(sr.status)}
            <span style="font-size:12px;color:var(--gray-400)">${fmtDuration(sr.started_at, sr.finished_at)}</span>
            ${srPropsJson ? `<button class="btn btn-secondary btn-sm" style="font-size:11px;padding:2px 8px" onclick="toggleLog('srctx-${sr.id}')">Context</button>` : ""}
            ${canRestart ? `<button class="btn btn-secondary btn-sm" style="font-size:11px;padding:2px 8px" onclick="rerunFromStage('${run.id}','${sr.id}')">↺ Restart from here</button>` : ""}
          </div>
        </div>
        ${srPropsJson ? `<div id="srctx-${sr.id}" class="task-log-block"><pre class="ctx-json-pre">${srPropsJson.replace(/</g,"&lt;")}</pre></div>` : ""}
        ${(sr.task_runs||[]).length === 0
          ? `<div style="padding:14px;color:var(--gray-400);font-size:13px">No tasks.</div>`
          : taskRows}
      </div>`;
  }).join("");

  const runColor = _statusColor(run.status);
  const ctxTabs = productId && pipelineId ? pipelineContextTabs(productId, pipelineId, "runs") : "";
  const pipelineProps = run.runtime_properties || {};
  const pipelinePropsJson = JSON.stringify(pipelineProps, null, 2);

  return `
    <div class="page-header">
      <div>
        ${productId ? `<div style="font-size:13px;margin-bottom:4px"><a href="#products/${productId}/pipelines/${pipelineId}" onclick="navigate('products/${productId}/pipelines/${pipelineId}');return false;">← Pipeline</a></div>` : ""}
        <h1>Pipeline Run</h1>
        <div class="sub"><code style="font-size:12px">${run.id}</code></div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        ${statusBadge(run.status)}
        <span style="font-size:13px;color:var(--gray-400)">by ${run.triggered_by||"system"} · ${fmtDate(run.started_at)}</span>
        ${run.finished_at ? `<span style="font-size:13px;color:var(--gray-400)">· ${fmtDuration(run.started_at, run.finished_at)} total</span>` : ""}
        <button class="btn btn-secondary btn-sm" onclick="openRunContextInspector('${run.id}')">🔍 Inspect Context</button>
        <button class="btn btn-secondary btn-sm" onclick="rerunPipeline('${run.id}')">↺ Re-run</button>
      </div>
    </div>

    <!-- Audit / Compliance reports — top of page for quick access -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-header">
        <h3 style="font-size:14px;margin:0">📋 Compliance Audit Reports</h3>
        <div style="display:flex;gap:8px">
          <button class="btn btn-secondary btn-sm" style="font-size:11px" onclick="loadAuditReport('${run.id}','isae')">ISAE 3000 / SOC 2</button>
          <button class="btn btn-secondary btn-sm" style="font-size:11px" onclick="loadAuditReport('${run.id}','acf')">ACF</button>
        </div>
      </div>
      <div id="audit-report-${run.id}" style="display:none;padding:14px">
        <div class="loading-center"><div class="spinner"></div></div>
      </div>
    </div>

    ${ctxTabs}

    <!-- Overall progress bar -->
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
      <div style="flex:1;min-width:100px;height:8px;border-radius:4px;background:var(--gray-200);overflow:hidden;position:relative">
        <div style="position:absolute;top:0;left:0;height:100%;border-radius:4px;background:${runColor};width:${Math.min(run.completion_percentage ?? 0, 100)}%;max-width:100%;transition:width .4s"></div>
      </div>
      <span style="font-size:13px;font-weight:600;color:var(--gray-600);white-space:nowrap;min-width:40px;text-align:right">${run.completion_percentage ?? 0}%</span>
    </div>

    <!-- Pipeline-level runtime properties (webhook payload, etc.) -->
    ${Object.keys(pipelineProps).length ? `
    <div class="card" style="margin-bottom:16px">
      <div class="card-header" style="cursor:pointer" onclick="toggleLog('run-rtprops-${run.id}')">
        <h3 style="font-size:13px;margin:0;color:var(--gray-600)">⚙ Pipeline Runtime Properties</h3>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <div id="run-rtprops-${run.id}" class="task-log-block">
        <pre class="ctx-json-pre">${pipelinePropsJson.replace(/</g,"&lt;")}</pre>
      </div>
    </div>` : ""}

    <!-- Visual flow -->
    <div class="card" style="margin-bottom:16px;overflow-x:auto">
      <div style="padding:8px 16px 4px">
        <div style="font-size:11px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:.06em">Pipeline Flow — click a stage or task to jump to details</div>
      </div>
      <div style="padding:8px 8px 12px;min-height:80px">${flowSvg}</div>
    </div>

    ${stageDetails || `<div class="card"><div class="empty-state"><div class="empty-icon">📋</div><p>No stages in this pipeline.</p></div></div>`}

    <!-- Resolved properties for this run -->
    <div class="card" style="margin-top:16px">
      <div class="card-header" style="cursor:pointer" onclick="loadRunResolvedProps('${run.id}','rp-${run.id}',this)">
        <h3 style="font-size:14px;margin:0">🔧 Resolved Properties</h3>
        <span id="rp-chev-${run.id}" style="font-size:12px;color:var(--gray-400)">▾ Load</span>
      </div>
      <div id="rp-${run.id}" style="display:none;padding:14px"></div>
    </div>

  `;
}

// ── Context Inspector helpers ─────────────────────────────────────────────────

// CDT_* env vars — rendered as a two-column table grouped by prefix
function _ctxEnvTable(tr) {
  let env = {};
  if (tr.context_env) { try { env = JSON.parse(tr.context_env); } catch {} }
  const keys = Object.keys(env).filter(k => k.startsWith("CDT_")).sort();
  if (!keys.length) return `<div class="ctx-empty">No CDT variables recorded for this task run.<br><small>Only runs executed after this feature was deployed will have context data.</small></div>`;
  const rows = keys.map(k => {
    const val = String(env[k] || "").slice(0, 300);
    const isJson = val.startsWith("{") || val.startsWith("[");
    return `<tr>
      <td class="ctx-key"><code>${k}</code></td>
      <td class="ctx-val">${isJson
        ? `<button class="ctx-json-toggle" onclick="this.nextElementSibling.classList.toggle('ctx-json-open')">▶ JSON</button><pre class="ctx-json-inline">${val.replace(/</g,"&lt;")}</pre>`
        : `<span>${val.replace(/</g,"&lt;") || '<em style="color:var(--gray-400)">(empty)</em>'}</span>`
      }</td>
    </tr>`;
  }).join("");
  return `<table class="ctx-table"><tbody>${rows}</tbody></table>`;
}

// Properties from CDT_PROPS (parsed from context_env)
function _ctxPropsTable(tr) {
  let env = {};
  if (tr.context_env) { try { env = JSON.parse(tr.context_env); } catch {} }
  let props = {};
  if (env.CDT_PROPS) { try { props = JSON.parse(env.CDT_PROPS); } catch {} }
  const keys = Object.keys(props).sort();
  if (!keys.length) return `<div class="ctx-empty">No design-time properties were resolved for this task.</div>`;
  const rows = keys.map(k => `<tr>
    <td class="ctx-key"><code>${k}</code></td>
    <td class="ctx-val">${String(props[k] ?? "").replace(/</g,"&lt;") || '<em style="color:var(--gray-400)">(empty)</em>'}</td>
  </tr>`).join("");
  return `<table class="ctx-table"><tbody>${rows}</tbody></table>`;
}

// Output JSON captured from last stdout line
function _ctxOutputPanel(tr) {
  if (!tr.output_json) return `<div class="ctx-empty">No JSON output captured for this task run.<br><small>Tasks can emit a JSON object as their last stdout line to pass data downstream.</small></div>`;
  let parsed;
  try { parsed = JSON.parse(tr.output_json); } catch { parsed = tr.output_json; }
  const pretty = typeof parsed === "object" ? JSON.stringify(parsed, null, 2) : String(parsed);
  return `<pre class="ctx-json-pre">${pretty.replace(/</g,"&lt;")}</pre>`;
}

// Switch active tab within a task's context inspector
function ctxTab(taskRunId, pane, btn) {
  const inner = document.getElementById("ctx-inner-" + taskRunId);
  if (!inner) return;
  inner.querySelectorAll(".ctx-tab").forEach(b => b.classList.remove("active"));
  inner.querySelectorAll(".ctx-pane").forEach(p => p.classList.remove("ctx-pane-active"));
  btn.classList.add("active");
  const target = document.getElementById(`ctx-pane-${pane}-${taskRunId}`);
  if (target) target.classList.add("ctx-pane-active");
}

// Full-run context inspector modal — loads /api/v1/pipeline-runs/<id>/context
async function openRunContextInspector(runId) {
  openModal("Run Context Inspector",
    `<div id="ctx-modal-body">${loading()}</div>`,
    null, null
  );
  // Hide confirm button
  const confirmBtn = document.getElementById("modal-confirm");
  if (confirmBtn) confirmBtn.style.display = "none";
  const cancelBtn = document.getElementById("modal-cancel");
  if (cancelBtn) cancelBtn.textContent = "Close";

  try {
    const ctx = await api.getPipelineRunContext(runId);
    const body = document.getElementById("ctx-modal-body");
    if (!body) return;

    // Pipeline-level section
    let html = `
      <div class="ctx-section">
        <div class="ctx-section-title">Pipeline Run</div>
        <table class="ctx-table">
          <tbody>
            <tr><td class="ctx-key">Run ID</td><td class="ctx-val"><code>${ctx.run_id}</code></td></tr>
            <tr><td class="ctx-key">Pipeline</td><td class="ctx-val">${ctx.pipeline?.name || "—"}</td></tr>
            <tr><td class="ctx-key">Git Branch</td><td class="ctx-val">${ctx.pipeline?.git_branch || "—"}</td></tr>
            <tr><td class="ctx-key">Commit SHA</td><td class="ctx-val"><code>${ctx.commit_sha || "—"}</code></td></tr>
            <tr><td class="ctx-key">Triggered By</td><td class="ctx-val">${ctx.triggered_by || "—"}</td></tr>
          </tbody>
        </table>
      </div>`;

    const rtProps = ctx.runtime_properties || {};
    if (Object.keys(rtProps).length) {
      html += `<div class="ctx-section">
        <div class="ctx-section-title">Runtime Properties (Pipeline Level)</div>
        <pre class="ctx-json-pre">${JSON.stringify(rtProps, null, 2).replace(/</g,"&lt;")}</pre>
      </div>`;
    }

    // Per-stage / per-task sections
    for (const stage of (ctx.stages || [])) {
      html += `<div class="ctx-section">
        <div class="ctx-section-title" style="background:var(--gray-50);border-left:3px solid var(--accent)">
          Stage: ${stage.stage_name} <span class="badge ${stage.status==='Succeeded'?'badge-success':stage.status==='Failed'?'badge-failed':'badge-pending'}" style="font-size:10px">${stage.status}</span>
        </div>`;

      const stRt = stage.runtime_properties || {};
      if (Object.keys(stRt).length) {
        html += `<div style="padding:6px 12px 0;font-size:11px;font-weight:600;color:var(--gray-400);text-transform:uppercase">Stage Runtime Properties</div>
          <pre class="ctx-json-pre" style="margin:4px 12px 8px">${JSON.stringify(stRt, null, 2).replace(/</g,"&lt;")}</pre>`;
      }

      for (const task of (stage.tasks || [])) {
        const env = task.context_env || {};
        const cdtKeys = Object.keys(env).filter(k => k.startsWith("CDT_")).sort();
        let propsObj = {};
        if (env.CDT_PROPS) { try { propsObj = JSON.parse(env.CDT_PROPS); } catch {} }
        const propsKeys = Object.keys(propsObj);

        html += `<div class="ctx-task-block">
          <div class="ctx-task-header">
            <span>${task.task_name}</span>
            <span class="badge ${task.status==='Succeeded'?'badge-success':task.status==='Failed'?'badge-failed':'badge-pending'}" style="font-size:10px">${task.status}</span>
          </div>`;

        if (cdtKeys.length) {
          html += `<div style="padding:4px 12px 0;font-size:11px;font-weight:600;color:var(--gray-400);text-transform:uppercase;letter-spacing:.05em">CDT Variables</div>
            <table class="ctx-table" style="margin:4px 12px 0">
              <tbody>${cdtKeys.map(k => {
                const val = String(env[k] || "");
                const isJson = val.startsWith("{") || val.startsWith("[");
                return `<tr>
                  <td class="ctx-key" style="width:200px"><code style="font-size:10.5px">${k}</code></td>
                  <td class="ctx-val">${isJson
                    ? `<button class="ctx-json-toggle" onclick="this.nextElementSibling.classList.toggle('ctx-json-open')">▶ JSON</button><pre class="ctx-json-inline">${val.replace(/</g,"&lt;")}</pre>`
                    : `<span style="font-size:11.5px">${val.replace(/</g,"&lt;") || '<em style="color:var(--gray-400)">(empty)</em>'}</span>`
                  }</td>
                </tr>`;
              }).join("")}</tbody>
            </table>`;
        }

        if (propsKeys.length) {
          html += `<div style="padding:8px 12px 0;font-size:11px;font-weight:600;color:var(--gray-400);text-transform:uppercase;letter-spacing:.05em">Resolved Properties (CDT_PROPS)</div>
            <table class="ctx-table" style="margin:4px 12px 8px">
              <tbody>${propsKeys.sort().map(k =>
                `<tr><td class="ctx-key" style="width:200px"><code style="font-size:10.5px">${k}</code></td><td class="ctx-val" style="font-size:11.5px">${String(propsObj[k] ?? "").replace(/</g,"&lt;")}</td></tr>`
              ).join("")}</tbody>
            </table>`;
        }

        if (task.output_json) {
          const outStr = typeof task.output_json === "object"
            ? JSON.stringify(task.output_json, null, 2)
            : String(task.output_json);
          html += `<div style="padding:8px 12px 0;font-size:11px;font-weight:600;color:var(--gray-400);text-transform:uppercase;letter-spacing:.05em">Output JSON</div>
            <pre class="ctx-json-pre" style="margin:4px 12px 8px">${outStr.replace(/</g,"&lt;")}</pre>`;
        }

        if (!cdtKeys.length && !propsKeys.length && !task.output_json) {
          html += `<div class="ctx-empty" style="padding:8px 12px">No context data recorded (run predates this feature).</div>`;
        }

        html += `</div>`;
      }
      html += `</div>`;
    }

    body.innerHTML = html;
  } catch (e) {
    const body = document.getElementById("ctx-modal-body");
    if (body) body.innerHTML = `<div class="alert alert-danger">Failed to load context: ${e.message}</div>`;
  }
}

async function loadRunResolvedProps(runId, panelId, headerEl) {
  const panel = document.getElementById(panelId);
  const chev = document.getElementById("rp-chev-" + runId);
  if (!panel) return;
  if (panel.style.display !== "none") {
    panel.style.display = "none";
    if (chev) chev.textContent = "▾ Load";
    return;
  }
  panel.style.display = "block";
  if (chev) chev.textContent = "▴";
  if (panel.dataset.loaded) return;
  panel.innerHTML = loading();
  try {
    const data = await api.resolveForPipelineRun(runId);
    panel.dataset.loaded = "1";
    const props = data.properties || {};
    const keys = Object.keys(props).sort();
    if (!keys.length) {
      panel.innerHTML = `<div style="font-size:13px;color:var(--gray-400)">No properties defined in the hierarchy for this run.</div>`;
      return;
    }
    panel.innerHTML = `
      <div style="font-size:12px;color:var(--gray-500);margin-bottom:12px">
        ${keys.length} resolved propert${keys.length===1?"y":"ies"} — runtime overrides take precedence over design-time defaults.
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px">
        ${keys.map(k => {
          const v = props[k];
          const isNull = v === null || v === undefined;
          const isObj  = !isNull && typeof v === "object";
          const isBool = !isNull && typeof v === "boolean";
          const isNum  = !isNull && typeof v === "number";
          const color  = isNull ? "#94a3b8" : isObj ? "#b45309" : isBool ? "#15803d" : isNum ? "#0369a1" : "#6366f1";
          const typeLabel = isNull ? "null" : isObj ? "json" : isBool ? "boolean" : isNum ? "number" : "string";
          const typeIcon  = { json:"{}", boolean:"✓", number:"#", null:"∅", string:"Aa" }[typeLabel] || "Aa";
          const display = isNull ? `<em style="color:var(--gray-400);font-size:12px">null</em>`
            : isObj  ? `<code style="background:var(--gray-100);padding:2px 8px;border-radius:4px;font-size:11px;word-break:break-all">${JSON.stringify(v)}</code>`
            : `<code style="background:var(--gray-100);padding:2px 8px;border-radius:4px;font-size:12px;word-break:break-all">${String(v)}</code>`;
          return `
          <div style="display:flex;align-items:flex-start;gap:10px;padding:10px 12px;background:#fff;border:1px solid var(--gray-200);border-radius:8px;border-left:3px solid ${color}">
            <div style="width:24px;height:24px;border-radius:5px;background:${color}15;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:${color};flex-shrink:0">${typeIcon}</div>
            <div style="flex:1;min-width:0">
              <div style="font-family:monospace;font-size:12px;font-weight:600;color:var(--gray-700);margin-bottom:4px">${k}</div>
              <div>${display}</div>
            </div>
          </div>`;
        }).join("")}
      </div>`;
  } catch(e) {
    panel.innerHTML = `<div class="alert alert-danger">Failed to load: ${e.message}</div>`;
  }
}

function toggleLog(id) {
  const el2 = document.getElementById(id);
  if (el2) el2.classList.toggle("open");
}

async function loadAuditReport(runId, framework) {
  const panel = document.getElementById(`audit-report-${runId}`);
  if (!panel) return;
  panel.style.display = "block";
  panel.innerHTML = `<div class="loading-center"><div class="spinner"></div></div>`;

  let report;
  try {
    report = await request("GET", `/pipeline-runs/${runId}/audit/${framework}`);
  } catch (e) {
    panel.innerHTML = `<div class="alert alert-danger" style="margin:0">Failed to load ${framework.toUpperCase()} report: ${e.message}</div>`;
    return;
  }

  const confidenceStyle = {
    confirmed: "background:#dcfce7;color:#15803d",
    partial:   "background:#fef9c3;color:#a16207",
    manual:    "background:#f1f5f9;color:#475569",
    not_met:   "background:#fee2e2;color:#b91c1c",
  };
  const confidenceLabel = {
    confirmed: "Confirmed",
    partial:   "Partial",
    manual:    "Manual review",
    not_met:   "Not met",
  };

  const s = report.summary || {};
  const total = s.total || 0;
  const confirmedPct = total ? Math.round((s.confirmed / total) * 100) : 0;

  const ratingColor = {
    "Largely Effective": "#22c55e",
    "Partially Effective": "#f59e0b",
    "Needs Improvement": "#ef4444",
    "Significant Gaps": "#dc2626",
  }[report.overall_rating] || "#9ca3af";

  // Determine grouping key
  const groupData = report.categories || report.domains || {};

  let sectionsHtml = "";
  for (const [groupKey, groupVal] of Object.entries(groupData)) {
    const controls = groupVal.controls || [];
    const label = groupVal.label || groupKey;
    const groupConfirmed = controls.filter(c => c.confidence === "confirmed").length;
    const groupPct = controls.length ? Math.round((groupConfirmed / controls.length) * 100) : 0;
    sectionsHtml += `
      <div style="margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;cursor:pointer" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
          <strong style="font-size:13px">${groupKey}: ${label}</strong>
          <div style="flex:1;max-width:120px;height:6px;background:var(--gray-200);border-radius:3px;overflow:hidden;position:relative">
            <div style="position:absolute;top:0;left:0;height:100%;width:${groupPct}%;background:${groupPct>=70?"#22c55e":groupPct>=40?"#f59e0b":"#ef4444"};border-radius:3px"></div>
          </div>
          <span style="font-size:11px;color:var(--gray-500)">${groupConfirmed}/${controls.length}</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
        <div>
          <table style="width:100%;font-size:12px;border-collapse:collapse">
            <thead><tr style="background:var(--gray-50)">
              <th style="padding:6px 10px;text-align:left;font-weight:600;border-bottom:1px solid var(--gray-200)">Control ID</th>
              <th style="padding:6px 10px;text-align:left;font-weight:600;border-bottom:1px solid var(--gray-200)">Title</th>
              <th style="padding:6px 10px;text-align:left;font-weight:600;border-bottom:1px solid var(--gray-200)">Status</th>
              <th style="padding:6px 10px;text-align:left;font-weight:600;border-bottom:1px solid var(--gray-200)">Evidence</th>
            </tr></thead>
            <tbody>
              ${controls.map(ctrl => `
                <tr style="border-bottom:1px solid var(--gray-100)">
                  <td style="padding:7px 10px;font-family:monospace;font-size:11px;color:var(--primary);white-space:nowrap">${ctrl.id}</td>
                  <td style="padding:7px 10px">
                    <div style="font-weight:600;margin-bottom:2px">${ctrl.title}</div>
                    <div style="color:var(--gray-500);font-size:11px;line-height:1.4">${ctrl.description}</div>
                  </td>
                  <td style="padding:7px 10px;white-space:nowrap">
                    <span style="padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;${confidenceStyle[ctrl.confidence] || ''}">${confidenceLabel[ctrl.confidence] || ctrl.confidence}</span>
                  </td>
                  <td style="padding:7px 10px">
                    ${ctrl.evidences && ctrl.evidences.length
                      ? ctrl.evidences.map(e => `<div style="color:var(--gray-600);font-size:11px;line-height:1.5">• ${e}</div>`).join("")
                      : `<div style="color:var(--gray-400);font-size:11px;font-style:italic">No automated evidence found — manual attestation required</div>`
                    }
                  </td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>
      </div>`;
  }

  panel.innerHTML = `
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;padding:14px;background:var(--gray-50);border-radius:8px">
      <div style="text-align:center;min-width:80px">
        <div style="font-size:28px;font-weight:700;color:${ratingColor}">${confirmedPct}%</div>
        <div style="font-size:11px;color:var(--gray-500)">Controls Confirmed</div>
      </div>
      <div style="flex:1">
        <div style="font-weight:700;font-size:14px;margin-bottom:4px">${report.framework}</div>
        <div style="font-size:12px;color:var(--gray-500);margin-bottom:8px">Run: <code>${report.run_id}</code> · Pipeline: ${report.pipeline_name} · Status: ${report.run_status}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${[
            [`${s.confirmed} Confirmed`, "#dcfce7", "#15803d"],
            [`${s.partial} Partial`, "#fef9c3", "#a16207"],
            [`${s.not_met} Not Met`, "#fee2e2", "#b91c1c"],
            [`${s.manual} Manual`, "#f1f5f9", "#475569"],
          ].map(([t,bg,col]) => `<span style="padding:2px 10px;border-radius:8px;font-size:11px;font-weight:600;background:${bg};color:${col}">${t}</span>`).join("")}
          <span style="padding:2px 10px;border-radius:8px;font-size:11px;font-weight:700;background:${ratingColor}22;color:${ratingColor}">${report.overall_rating}</span>
        </div>
      </div>
      <button class="btn btn-secondary btn-sm" style="font-size:11px;white-space:nowrap" onclick="downloadAuditPdf('${runId}','${framework}')">⬇ Export PDF</button>
    </div>
    ${sectionsHtml}
    <div style="font-size:11px;color:var(--gray-400);margin-top:12px;text-align:right">Generated at ${new Date(report.generated_at).toLocaleString()}</div>
  `;
}

async function downloadAuditPdf(runId, framework) {
  try {
    const token = auth.getToken();
    const res = await fetch(`/api/v1/pipeline-runs/${runId}/audit/${framework}/pdf`, {
      headers: token ? { "Authorization": `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      toast(j.error || "PDF export failed", "error");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${framework}_audit_${runId}.pdf`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
  } catch (e) {
    toast("PDF export error: " + e.message, "error");
  }
}

async function rerunPipeline(runId) {
  try {
    const newRun = await api.rerunPipeline(runId);
    navigate("pipeline-runs/" + newRun.id);
  } catch (e) {
    alert("Failed to re-run pipeline: " + (e.message || e));
  }
}

async function rerunFromStage(runId, stageRunId) {
  try {
    const newRun = await api.rerunFromStage(runId, stageRunId);
    navigate("pipeline-runs/" + newRun.id);
  } catch (e) {
    alert("Failed to restart from stage: " + (e.message || e));
  }
}

router.register("pipeline-runs/:id", async (hash, parts) => {
  const runId = parts[1];
  setBreadcrumb({ label: "Pipeline Run" });
  setContent(loading());

  async function fetchAndRender() {
    const run = await api.getPipelineRun(runId).catch(() => null);
    if (!run) { setContent(`<div class="card"><div class="empty-state"><p>Run not found.</p></div></div>`); return; }

    // Try to recover product/pipeline context from run for back-link
    const productId = run.product_id || null;
    const pipelineId = run.pipeline_id || null;

    // Build richer breadcrumb if we have product/pipeline context
    if (productId && pipelineId) {
      try {
        const [product, pipeline] = await Promise.all([
          api.getProduct(productId).catch(() => null),
          api.getPipeline(productId, pipelineId).catch(() => null),
        ]);
        const pName = product?.name || "Product";
        const plName = pipeline?.name || "Pipeline";
        setBreadcrumb(
          { label: "Products", hash: "products" },
          { label: pName, hash: `products/${productId}` },
          { label: plName, hash: `products/${productId}/pipelines/${pipelineId}` },
          { label: "Run" }
        );
      } catch {
        setBreadcrumb({ label: "Products", hash: "products" }, { label: "Pipeline Run" });
      }
    } else {
      setBreadcrumb({ label: "Products", hash: "products" }, { label: "Pipeline Run" });
    }
    setContent(_renderPipelineRun(run, productId, pipelineId));

    if (!TERMINAL.has(run.status)) {
      _pollTimer = setInterval(async () => {
        if (!document.getElementById(`sr-${(run.stage_runs||[])[0]?.id}`) && run.stage_runs?.length) {
          clearInterval(_pollTimer); _pollTimer = null; return;
        }
        const updated = await api.getPipelineRun(runId).catch(() => null);
        if (!updated) return;
        setContent(_renderPipelineRun(updated, productId, pipelineId));
        if (TERMINAL.has(updated.status)) { clearInterval(_pollTimer); _pollTimer = null; }
      }, 2000);
    }
  }

  await fetchAndRender();
});

// ── Plugins page ──────────────────────────────────────────────────────────
router.register("plugins", async () => {
  setBreadcrumb({ label: "Plugins" });
  setContent(loading());
  const plugins = await api.getPlugins().catch(() => []);
  const builtins = plugins.filter(p => p.is_builtin);
  const custom   = plugins.filter(p => !p.is_builtin);

  setContent(`
    <div class="page-header">
      <div><h1>Plugins</h1><div class="sub">CI/CD tool integrations and custom extensions</div></div>
      <button class="btn btn-primary" onclick="showUploadPlugin()">+ Register Plugin</button>
    </div>

    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><h2>Built-in Integrations</h2></div>
      <div class="grid grid-3" style="padding:16px">
        ${builtins.length === 0
          ? `<div style="color:var(--gray-500)">No built-in plugins found.</div>`
          : builtins.map(p => pluginCard(p)).join("")}
      </div>
    </div>

    <div class="card">
      <div class="card-header"><h2>Custom Plugins</h2></div>
      ${custom.length === 0
        ? `<div class="empty-state"><div class="empty-icon">🔌</div><p>No custom plugins registered yet.</p></div>`
        : `<div class="grid grid-3" style="padding:16px">${custom.map(p => pluginCard(p)).join("")}</div>`}
    </div>
  `);
});

function pluginCard(plugin) {
  return `<div class="card" style="border:2px solid ${plugin.is_enabled?"var(--brand)":"var(--gray-200)"}">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
      <div style="font-size:22px;line-height:1">${plugin.icon || "🔌"}</div>
      <span class="badge ${plugin.is_enabled?"badge-success":"badge-silver"}">${plugin.is_enabled?"Enabled":"Disabled"}</span>
    </div>
    <div style="font-weight:600;font-size:15px;margin-bottom:4px">${plugin.display_name}</div>
    <div style="font-size:12px;color:var(--gray-500);margin-bottom:6px">${plugin.description||"No description"}</div>
    <div style="font-size:11.5px;margin-bottom:10px">
      <span class="badge badge-blue">${plugin.category||"custom"}</span>
      <span style="margin-left:8px;color:var(--gray-400)">v${plugin.version||"0.1.0"}</span>
      <span style="margin-left:8px;color:var(--gray-400)">${plugin.config_count||0} config(s)</span>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap">
      <button class="btn btn-secondary btn-sm" onclick="navigate('plugins/${plugin.id}')">Configure</button>
      <button class="btn btn-secondary btn-sm" onclick="togglePlugin('${plugin.id}','${plugin.display_name.replace(/'/g,"\\'")}')">
        ${plugin.is_enabled?"Disable":"Enable"}
      </button>
      ${!plugin.is_builtin
        ? `<button class="btn btn-danger btn-sm" onclick="deletePlugin('${plugin.id}','${plugin.display_name.replace(/'/g,"\\'")}')">Delete</button>`
        : ""}
    </div>
  </div>`;
}

async function togglePlugin(pluginId, name) {
  try {
    const r = await api.togglePlugin(pluginId);
    toast(`${name} ${r.is_enabled?"enabled":"disabled"}`, "success");
    navigate("plugins");
  } catch (e) { toast(e.message, "error"); }
}

async function deletePlugin(pluginId, name) {
  if (!confirm(`Delete plugin "${name}"?`)) return;
  try {
    await api.deletePlugin(pluginId);
    toast("Plugin deleted", "success");
    navigate("plugins");
  } catch (e) { toast(e.message, "error"); }
}

function showUploadPlugin() {
  openModal("Register Plugin",
    `<div class="form-group"><label>Name * (slug)</label><input id="plg-name" class="form-control" placeholder="e.g. my-tool"></div>
     <div class="form-group"><label>Display Name *</label><input id="plg-dname" class="form-control" placeholder="e.g. My Tool"></div>
     <div class="form-group"><label>Description</label><textarea id="plg-desc" class="form-control" rows="2"></textarea></div>
     <div class="form-group"><label>Category</label>
       <select id="plg-cat" class="form-control">
         <option value="ci">CI</option>
         <option value="cd">CD</option>
         <option value="scm">SCM</option>
         <option value="notification">Notification</option>
         <option value="custom" selected>Custom</option>
       </select>
     </div>
     <div class="form-group"><label>Icon (emoji)</label><input id="plg-icon" class="form-control" value="🔌" style="width:80px"></div>
     <div class="form-group"><label>Version</label><input id="plg-ver" class="form-control" value="0.1.0" style="width:120px"></div>`,
    async () => {
      const name = el("plg-name").value.trim();
      const display_name = el("plg-dname").value.trim();
      if (!name || !display_name) return modalError("Name and Display Name are required");
      try {
        await api.uploadPlugin({
          name, display_name,
          description: el("plg-desc").value.trim() || null,
          category: el("plg-cat").value,
          icon: el("plg-icon").value.trim() || "🔌",
          version: el("plg-ver").value.trim() || "0.1.0",
        });
        closeModal(); toast("Plugin registered", "success");
        navigate("plugins");
      } catch (e) { modalError(e.message); }
    }
  );
}

// ── Plugin detail / config manager ─────────────────────────────────────────
router.register("plugins/:id", async (hash, parts) => {
  const pluginId = parts[1];
  setBreadcrumb({ label: "Plugins", hash: "plugins" }, { label: "Loading…" });
  setContent(loading());
  const plugin = await api.getPlugin(pluginId).catch(() => null);
  if (!plugin) { setContent(`<div class="card"><div class="empty-state"><p>Plugin not found.</p></div></div>`); return; }
  setBreadcrumb({ label: "Plugins", hash: "plugins" }, { label: plugin.display_name });
  const configs = plugin.configs || [];

  // Parse config_schema to know which fields to show when creating a config
  let schemaFields = [];
  try { schemaFields = (JSON.parse(plugin.config_schema || "{}")).fields || []; } catch {}

  setContent(`
    <div class="page-header">
      <div>
        <h1>${plugin.icon || "🔌"} ${plugin.display_name}</h1>
        <div class="sub">${plugin.description || "No description"} · v${plugin.version}</div>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-secondary btn-sm" onclick="togglePlugin('${plugin.id}','${plugin.display_name.replace(/'/g,"\\'")}')">
          ${plugin.is_enabled?"Disable":"Enable"}
        </button>
        <button class="btn btn-primary btn-sm" onclick="showCreatePluginConfig('${plugin.id}')">+ Add Configuration</button>
      </div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><h2>Details</h2></div>
      <div class="detail-grid" style="padding:0 16px 16px">
        <div class="detail-row"><span class="detail-label">Category</span><span class="badge badge-blue">${plugin.category||"custom"}</span></div>
        <div class="detail-row"><span class="detail-label">Type</span><span class="detail-value">${plugin.plugin_type}</span></div>
        <div class="detail-row"><span class="detail-label">Built-in</span><span class="detail-value">${plugin.is_builtin?"Yes":"No"}</span></div>
        <div class="detail-row"><span class="detail-label">Status</span><span class="badge ${plugin.is_enabled?"badge-success":"badge-silver"}">${plugin.is_enabled?"Enabled":"Disabled"}</span></div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><h2>Configurations (${configs.length})</h2></div>
      ${configs.length === 0
        ? `<div class="empty-state"><div class="empty-icon">⚙️</div><p>No configurations yet. Add one to connect this plugin to a tool instance.</p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Config Name</th><th>Tool URL</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead>
          <tbody>${configs.map(c => `
            <tr>
              <td><strong>${c.config_name}</strong></td>
              <td style="color:var(--gray-500);font-size:12px">${c.tool_url||"—"}</td>
              <td><span class="badge ${c.is_active?"badge-success":"badge-silver"}">${c.is_active?"Active":"Inactive"}</span></td>
              <td style="color:var(--gray-400)">${fmtDate(c.created_at)}</td>
              <td style="display:flex;gap:4px;flex-wrap:wrap">
                <button class="btn btn-secondary btn-sm" id="test-btn-${c.id}" onclick="testPluginConfig('${plugin.id}','${c.id}')">⚡ Test</button>
                <button class="btn btn-secondary btn-sm" onclick="showEditPluginConfig('${plugin.id}','${c.id}','${c.config_name.replace(/'/g,"\\'")}','${(c.tool_url||"").replace(/'/g,"\\'")}',${c.is_active})">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deletePluginConfig('${plugin.id}','${c.id}','${c.config_name.replace(/'/g,"\\'")}')">Delete</button>
              </td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>
  `);
});

function showCreatePluginConfig(pluginId) {
  openModal("Add Configuration",
    `<div class="form-group"><label>Config Name *</label><input id="pcf-name" class="form-control" placeholder="e.g. prod-jenkins, staging-gitlab"></div>
     <div class="form-group"><label>Tool URL</label><input id="pcf-url" class="form-control" type="url" placeholder="https://tool.example.com"></div>
     <div class="form-group"><label>Credentials (JSON)</label>
       <textarea id="pcf-creds" class="form-control code-editor" rows="5" placeholder='{"token":"abc123"}'></textarea>
     </div>
     <div class="form-group"><label>Extra Config (JSON)</label>
       <textarea id="pcf-extra" class="form-control code-editor" rows="3" placeholder='{}'></textarea>
     </div>`,
    async () => {
      const config_name = el("pcf-name").value.trim();
      if (!config_name) return modalError("Config name is required");
      let credentials = {}, extra_config = {};
      try { credentials = JSON.parse(el("pcf-creds").value || "{}"); } catch { return modalError("Credentials must be valid JSON"); }
      try { extra_config = JSON.parse(el("pcf-extra").value || "{}"); } catch { return modalError("Extra config must be valid JSON"); }
      try {
        await api.createPluginConfig(pluginId, {
          config_name,
          tool_url: el("pcf-url").value.trim() || null,
          credentials,
          extra_config,
        });
        closeModal(); toast("Configuration added", "success");
        navigate(`plugins/${pluginId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

function showEditPluginConfig(pluginId, configId, configName, toolUrl, isActive) {
  openModal("Edit Configuration",
    `<div class="form-group"><label>Config Name *</label><input id="epcf-name" class="form-control" value="${configName}"></div>
     <div class="form-group"><label>Tool URL</label><input id="epcf-url" class="form-control" type="url" value="${toolUrl}"></div>
     <div class="form-group"><label>Status</label>
       <select id="epcf-active" class="form-control">
         <option value="true"${isActive?" selected":""}>Active</option>
         <option value="false"${!isActive?" selected":""}>Inactive</option>
       </select>
     </div>`,
    async () => {
      const config_name = el("epcf-name").value.trim();
      if (!config_name) return modalError("Config name is required");
      try {
        await api.updatePluginConfig(pluginId, configId, {
          config_name,
          tool_url: el("epcf-url").value.trim() || null,
          is_active: el("epcf-active").value === "true",
        });
        closeModal(); toast("Configuration updated", "success");
        navigate(`plugins/${pluginId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

async function deletePluginConfig(pluginId, configId, name) {
  if (!confirm(`Delete configuration "${name}"?`)) return;
  try {
    await api.deletePluginConfig(pluginId, configId);
    toast("Configuration deleted", "success");
    navigate(`plugins/${pluginId}`);
  } catch (e) { toast(e.message, "error"); }
}

async function testPluginConfig(pluginId, configId) {
  const btn = document.getElementById(`test-btn-${configId}`);
  if (btn) { btn.disabled = true; btn.textContent = "Testing…"; }
  try {
    const result = await api.testPluginConfig(pluginId, configId);
    if (result.ok) {
      toast(`✓ ${result.message}`, "success");
      if (btn) { btn.textContent = "✓ OK"; btn.classList.remove("btn-secondary"); btn.classList.add("btn-success"); }
    } else {
      toast(`✗ ${result.message}`, "error");
      if (btn) { btn.textContent = "✗ Failed"; btn.classList.remove("btn-secondary"); btn.classList.add("btn-danger"); }
    }
  } catch (e) {
    toast(`Test failed: ${e.message}`, "error");
    if (btn) { btn.textContent = "⚡ Test"; btn.disabled = false; }
    return;
  }
  // Re-enable button after 3 seconds
  setTimeout(() => {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "⚡ Test";
      btn.className = "btn btn-secondary btn-sm";
    }
  }, 3000);
}

// ── Docs page ──────────────────────────────────────────────────────────────
router.register("docs", () => {
  setBreadcrumb({ label: "Documentation" });
  setContent(`
    <div class="page-header">
      <div><h1>Documentation</h1><div class="sub">Conduit — comprehensive usage guide and API reference</div></div>
      <div style="display:flex;gap:8px">
        <a class="btn btn-secondary btn-sm" href="/api/v1/docs/swagger" target="_blank">Swagger UI</a>
        <button class="btn btn-primary btn-sm" onclick="navigate('tutorial')">Tutorial &rarr;</button>
      </div>
    </div>

    <!-- ── Architecture overview ── -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>Architecture Overview</h2></div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:16px">
          Conduit is a <strong>release orchestration platform</strong> — it manages the full lifecycle of software delivery
          from code commit to production deployment. It sits above individual CI tools (Jenkins, GitHub Actions) as a
          policy-aware coordinator, providing compliance gates, audit trails, maturity scoring, and cross-team visibility.
        </p>
        <div class="grid grid-2" style="gap:16px">
          <div>
            <strong style="font-size:13px;display:block;margin-bottom:8px">Object hierarchy</strong>
            <div style="font-size:13px;line-height:2;padding-left:4px">
              <div><span style="color:var(--primary);font-weight:600">Product</span> — top-level team/project namespace</div>
              <div style="padding-left:20px">└ <span style="color:#7c3aed;font-weight:600">Application</span> — a deployable artifact belonging to the product</div>
              <div style="padding-left:20px">└ <span style="color:#0891b2;font-weight:600">Release</span> — versioned bundle of pipelines ready to ship</div>
              <div style="padding-left:40px">└ <span style="color:#059669;font-weight:600">Pipeline</span> (CI or CD) — attached to the release</div>
              <div style="padding-left:60px">└ <span style="color:#d97706;font-weight:600">Stage</span> — logical group of tasks</div>
              <div style="padding-left:80px">└ <span style="color:#dc2626;font-weight:600">Task</span> — bash/python script with typed output</div>
            </div>
          </div>
          <div>
            <strong style="font-size:13px;display:block;margin-bottom:8px">Execution flow</strong>
            <div style="display:flex;flex-direction:column;gap:6px;font-size:12px">
              ${[
                ["1", "Trigger", "Webhook, manual click, or API call starts a PipelineRun"],
                ["2", "Agent pickup", "An agent in the pool claims the run (or inline executor if no agent)"],
                ["3", "Stage loop", "Stages run in order; tasks within a stage may run in parallel"],
                ["4", "Task execution", "Script runs in a sandbox with CDT_* env vars injected"],
                ["5", "Output capture", "Last stdout JSON line → stored as task output, available downstream"],
                ["6", "Status propagation", "Succeeded / Warning / Failed / Cancelled rolled up to pipeline"],
                ["7", "Audit & metrics", "Every run, event, and status change is recorded in the audit log and Prometheus"],
              ].map(([n,t,d]) => `<div style="display:flex;gap:10px;align-items:flex-start"><div style="min-width:20px;height:20px;border-radius:50%;background:var(--primary);color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0">${n}</div><div><strong>${t}</strong> — <span style="color:var(--gray-600)">${d}</span></div></div>`).join("")}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Key concepts grid ── -->
    <div class="grid grid-2" style="margin-bottom:16px">
      <div class="card">
        <div class="card-header"><h2>Core Concepts</h2></div>
        <div class="detail-grid">
          ${[
            ["Product", "Namespace for all pipelines, releases, environments and applications. One team = one product. Products share environments but have isolated releases."],
            ["Environment", "A named deployment target (dev/qa/staging/prod). Defined centrally, attached to products. Environments gate release promotion and carry their own compliance rules."],
            ["Pipeline", "An ordered sequence of stages. Typed as CI (build/test) or CD (deploy). Pipelines have a compliance score (0–100) based on the DevSecOps maturity model."],
            ["Stage", "A group of tasks sharing execution context. Stages run sequentially; tasks within a stage can run in parallel. Each stage has its own run log."],
            ["Task", "A bash or python script. Runs in an isolated container sandbox. Emits structured JSON output on the last stdout line. Has typed tags (SAST, DAST, unit-test, deploy…)."],
            ["Agent Pool", "Named pool of sandboxed executors. Tasks are dispatched to an available agent. Agents execute scripts and stream logs back. Supports Docker/Podman container runners."],
            ["Release", "A versioned collection of pipelines. Has status (Draft → Ready → Running → Succeeded/Failed). Compliance rules gate pipeline attachment."],
            ["Compliance Rule", "A JSONPath/regex-based policy evaluated against pipeline metadata. Rules must pass before a pipeline can be attached to a release targeted at a protected environment."],
            ["Property", "A typed key-value pair (string/int/bool/secret) scoped to pipeline, stage, or task. Resolved at runtime with narrowest-scope wins. Available as CDT_PROPS."],
            ["CDT Variables", "Injected env vars at task runtime: CDT_PIPELINE_ID, CDT_STAGE_NAME, CDT_TASK_NAME, CDT_RUN_ID, CDT_TRIGGERED_BY, CDT_ENV, CDT_PROPS (JSON), and CDT_TASK_OUTPUT_* for prior task outputs."],
          ].map(([k,v]) => `<div class="detail-row"><span class="detail-label" style="min-width:120px">${k}</span><span class="detail-value" style="font-size:12px">${v}</span></div>`).join("")}
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h2>Quick Start</h2></div>
        <div style="padding:0 16px 16px">
          <ol style="padding-left:18px;line-height:1.8;font-size:13px">
            <li style="margin-bottom:8px">Go to <strong>Products</strong> → <em>New Product</em>. Give it a name and slug.</li>
            <li style="margin-bottom:8px">Go to <strong>Environments</strong> → create <em>dev</em>, <em>qa</em>, <em>prod</em>.</li>
            <li style="margin-bottom:8px">Open your product → <em>Attach Environment</em> for each env you need.</li>
            <li style="margin-bottom:8px">Inside the product → <em>New Pipeline</em>. Choose kind: <strong>CI</strong> or <strong>CD</strong>.</li>
            <li style="margin-bottom:8px">Add stages, then add tasks to each stage. Write a bash script in the task editor.</li>
            <li style="margin-bottom:8px">Tag each task with its type (SAST, unit-test, deploy…) to earn DevSecOps maturity XP.</li>
            <li style="margin-bottom:8px">Create a <strong>Release</strong>, attach the pipeline, then click <em>Run</em>.</li>
            <li style="margin-bottom:8px">Watch the pipeline execute live — click any task to see its logs, CDT vars, and output JSON.</li>
            <li style="margin-bottom:8px">Check the <strong>Maturity</strong> tab to see your pipeline's DevSecOps score and how to improve it.</li>
            <li>Set up <strong>Webhooks</strong> to trigger pipelines automatically from GitHub/GitLab pushes.</li>
          </ol>
          <div style="background:var(--gray-900);border-radius:8px;padding:12px;font-size:12px;color:#e2e8f0;margin-top:8px">
            <strong>Tip:</strong> Seed the <em>conduit-e2e-demo</em> pipeline to see a fully wired example
            (run <code>python scripts/create_e2e_demo.py</code> then look for it under the <em>Demo</em> product).
          </div>
        </div>
      </div>
    </div>

    <!-- ── Task script contract ── -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>Task Script Contract</h2></div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:16px">
          Tasks run as non-root processes in an isolated sandbox (native subprocess or Docker/Podman container depending on
          the <em>TASK_RUNNER</em> platform setting). Scripts are injected with a set of <code>CDT_*</code> environment
          variables and may emit a structured JSON payload on the final stdout line.
        </p>
        <div class="grid grid-3" style="gap:12px;margin-bottom:16px">
          <div>
            <strong style="font-size:13px">Exit codes</strong>
            <table style="margin-top:8px;font-size:13px;width:100%"><tbody>
              <tr><td style="padding:5px 12px 5px 0;font-family:monospace;color:var(--gray-500)">0</td><td>Succeeded</td></tr>
              <tr><td style="padding:5px 12px 5px 0;font-family:monospace;color:var(--gray-500)">1</td><td>Warning — pipeline continues (on_error=warn)</td></tr>
              <tr><td style="padding:5px 12px 5px 0;font-family:monospace;color:var(--gray-500)">2+</td><td>Failed — depends on is_required / on_error setting</td></tr>
            </tbody></table>
          </div>
          <div>
            <strong style="font-size:13px">on_error behaviour</strong>
            <table style="margin-top:8px;font-size:13px;width:100%"><tbody>
              <tr><td style="padding:5px 12px 5px 0;color:var(--gray-500)">fail</td><td>Stage and pipeline stop immediately</td></tr>
              <tr><td style="padding:5px 12px 5px 0;color:var(--gray-500)">warn</td><td>Pipeline continues, status becomes Warning</td></tr>
              <tr><td style="padding:5px 12px 5px 0;color:var(--gray-500)">ignore</td><td>Failure is silently swallowed</td></tr>
            </tbody></table>
          </div>
          <div>
            <strong style="font-size:13px">Task type tags (sample)</strong>
            <table style="margin-top:8px;font-size:12px;width:100%"><tbody>
              ${[["sast","Static analysis"],["sca","Dependency scan"],["dast","Dynamic scan"],["unit-test","Unit tests"],["deploy","Deploy/promote"],["secret-scan","Secret scanning"],["supply-chain","SBOM / signing"]].map(([t,d]) => `<tr><td style="padding:3px 8px 3px 0;font-family:monospace;color:var(--primary);font-size:11px">${t}</td><td style="color:var(--gray-600)">${d}</td></tr>`).join("")}
            </tbody></table>
          </div>
        </div>

        <div class="grid grid-2" style="gap:16px">
          <div>
            <strong style="font-size:13px">Injected CDT_* environment variables</strong>
            <div class="detail-grid" style="margin-top:8px;font-size:12px">
              ${[
                ["CDT_PIPELINE_ID","UUID of the executing pipeline"],
                ["CDT_PIPELINE_NAME","Human-readable pipeline name"],
                ["CDT_STAGE_ID","UUID of the current stage"],
                ["CDT_STAGE_NAME","Stage name"],
                ["CDT_TASK_ID","UUID of the current task"],
                ["CDT_TASK_NAME","Task name"],
                ["CDT_RUN_ID","PipelineRun UUID"],
                ["CDT_TRIGGERED_BY","Username or webhook ID that triggered the run"],
                ["CDT_ENV","Target environment name (if set)"],
                ["CDT_PROPS","JSON object of resolved properties (pipeline→stage→task)"],
                ["CDT_TASK_OUTPUT_<ID>","JSON output from any previously completed task"],
              ].map(([k,v]) => `<div class="detail-row"><span class="detail-label" style="font-family:monospace;font-size:11px">${k}</span><span class="detail-value">${v}</span></div>`).join("")}
            </div>
          </div>
          <div>
            <strong style="font-size:13px">Reading properties in scripts</strong>
            <pre style="background:var(--gray-900);color:#e2e8f0;border-radius:8px;padding:14px;font-size:12px;margin-top:8px;overflow-x:auto">#!/bin/bash
# CDT_PROPS is a JSON object — use jq or python to read
IMAGE_REPO=$(echo "$CDT_PROPS" | python3 -c "
import sys, json
p = json.load(sys.stdin)
print(p.get('IMAGE_REPO', 'registry.example.com/app'))
")
IMAGE_TAG=$(echo "$CDT_PROPS" | python3 -c "
import sys, json
p = json.load(sys.stdin)
print(p.get('IMAGE_TAG', 'latest'))
")
echo "Building $IMAGE_REPO:$IMAGE_TAG"
docker build -t "$IMAGE_REPO:$IMAGE_TAG" .
echo '{"image":"'"$IMAGE_REPO:$IMAGE_TAG"'","status":"pushed"}'</pre>

            <strong style="font-size:13px;display:block;margin-top:14px">Chaining task outputs</strong>
            <pre style="background:var(--gray-900);color:#e2e8f0;border-radius:8px;padding:14px;font-size:12px;margin-top:8px;overflow-x:auto">#!/bin/bash
# Read output from a previous task named "build"
BUILD_OUT=$(echo "$CDT_TASK_OUTPUT_BUILD" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('image', ''))
")
echo "Deploying image: $BUILD_OUT"
kubectl set image deployment/app app="$BUILD_OUT"
echo '{"deployed":"'"$BUILD_OUT"'","cluster":"prod-us-east-1"}'</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Properties ── -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>Properties — Configuration Hierarchy</h2></div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          Properties are typed key-value pairs that parameterise pipelines without hard-coding values in task scripts.
          They are resolved at runtime using a <strong>narrowest-scope-wins</strong> rule: a task-level property
          overrides the same key at stage level, which overrides pipeline level.
        </p>
        <div class="grid grid-3" style="gap:12px;margin-bottom:12px">
          ${[
            ["Pipeline level", "Default values shared across all stages and tasks in the pipeline. E.g. IMAGE_REPO, COVERAGE_MIN=80, NOTIFY_ON_FAIL=true"],
            ["Stage level", "Overrides for a specific stage. E.g. the test stage might raise COVERAGE_MIN=90"],
            ["Task level", "Fine-grained overrides for a single task. E.g. a specific health-check task sets HEALTHCHECK_URL to an internal endpoint"],
          ].map(([t,d]) => `<div style="background:var(--gray-50);border-radius:8px;padding:14px;font-size:13px"><strong style="display:block;margin-bottom:6px">${t}</strong><span style="color:var(--gray-600);font-size:12px">${d}</span></div>`).join("")}
        </div>
        <div style="background:var(--gray-50);border-radius:8px;padding:14px;font-size:13px">
          <strong>Property types:</strong>
          <span style="background:#dbeafe;color:#1d4ed8;padding:2px 8px;border-radius:6px;font-size:11px;margin-left:8px">string</span>
          <span style="background:#dcfce7;color:#15803d;padding:2px 8px;border-radius:6px;font-size:11px;margin-left:4px">int</span>
          <span style="background:#fef9c3;color:#a16207;padding:2px 8px;border-radius:6px;font-size:11px;margin-left:4px">bool</span>
          <span style="background:#fee2e2;color:#b91c1c;padding:2px 8px;border-radius:6px;font-size:11px;margin-left:4px">secret</span>
          &nbsp;— Secret values are masked in the UI and never appear in plain text in logs or audit trails.
        </div>
      </div>
    </div>

    <!-- ── Compliance & Maturity ── -->
    <div class="grid grid-2" style="margin-bottom:16px">
      <div class="card">
        <div class="card-header"><h2>Compliance Rules</h2></div>
        <div style="padding:0 16px 16px;font-size:13px;color:var(--gray-700)">
          <p style="margin-bottom:10px">Compliance rules are <strong>admission policies</strong> evaluated against pipeline metadata before it can be attached to a release targeting a protected environment.</p>
          <div class="detail-grid" style="margin-bottom:10px">
            ${[
              ["JSONPath match", "e.g. $.kind == 'CD' — checks pipeline metadata"],
              ["Regex match", "e.g. pipeline name must match '^release-.*'"],
              ["Required score", "Pipeline compliance score must be ≥ threshold"],
              ["Task presence", "Pipeline must contain a task of a given type tag"],
            ].map(([k,v]) => `<div class="detail-row"><span class="detail-label">${k}</span><span class="detail-value" style="font-size:12px">${v}</span></div>`).join("")}
          </div>
          <p style="color:var(--gray-500);font-size:12px">Rules are evaluated when a pipeline is attached to a release. A pipeline that fails any rule is blocked — the release owner must fix the pipeline before the release can proceed.</p>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h2>DevSecOps Maturity Model</h2></div>
        <div style="padding:0 16px 16px;font-size:13px;color:var(--gray-700)">
          <p style="margin-bottom:10px">Every pipeline is automatically scored across <strong>20 dimensions</strong> aligned with DSOMM, OWASP SAMM, NIST SSDF and OpenSSF Scorecard.</p>
          <div class="detail-grid" style="margin-bottom:10px">
            ${[
              ["0 — Absent", "No evidence of the practice in this pipeline"],
              ["1 — Basic", "Practice is present (keyword/tag match found)"],
              ["2 — Configured", "Explicit task_type tag or named task with specific config"],
              ["3 — Enforced", "Score ≥ 2 AND task is is_required=true AND on_error=fail"],
            ].map(([k,v]) => `<div class="detail-row"><span class="detail-label" style="min-width:130px">${k}</span><span class="detail-value" style="font-size:12px">${v}</span></div>`).join("")}
          </div>
          <div style="background:var(--gray-50);border-radius:6px;padding:10px;font-size:12px;color:var(--gray-600)">
            Scores are kind-aware — CD pipelines are not penalised for missing CI-only dimensions (unit testing) and vice versa. Go to <strong>Maturity</strong> to see your scores and improvement hints.
          </div>
        </div>
      </div>
    </div>

    <!-- ── Webhooks & Triggers ── -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>Webhooks &amp; Triggers</h2></div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          Pipelines can be triggered via webhooks. Each pipeline can have one or more webhooks with different tokens and event filters.
        </p>
        <div class="grid grid-2" style="gap:16px">
          <div>
            <strong style="font-size:13px">Create a webhook</strong>
            <ol style="font-size:13px;padding-left:18px;line-height:2;margin-top:8px">
              <li>Open a pipeline → <em>Webhooks</em> tab</li>
              <li>Click <em>New Webhook</em>, set a name and secret token</li>
              <li>Configure the endpoint in GitHub/GitLab</li>
              <li>Trigger events: push, tag, PR open, custom JSON payload</li>
            </ol>
          </div>
          <div>
            <strong style="font-size:13px">Trigger manually via curl</strong>
            <pre style="background:var(--gray-900);color:#e2e8f0;border-radius:8px;padding:14px;font-size:12px;margin-top:8px;overflow-x:auto">curl -X POST \\
  http://localhost:8080/api/v1/webhooks/&lt;WEBHOOK_ID&gt;/trigger \\
  -H "X-Webhook-Token: &lt;SECRET&gt;" \\
  -H "Content-Type: application/json" \\
  -d '{"ref":"refs/heads/main","after":"abc1234"}'</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- ── RBAC ── -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>RBAC — Roles &amp; Permissions</h2></div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          Conduit uses role-based access control. Roles are assigned to users directly or via groups. Role bindings are
          scoped to a resource (product, pipeline) or global.
        </p>
        <div class="grid grid-2" style="gap:12px">
          <div>
            <strong style="font-size:13px">Built-in roles</strong>
            <div class="detail-grid" style="margin-top:8px">
              ${[
                ["admin","Full access to everything including user management and system settings"],
                ["developer","Create and edit products, pipelines, tasks, and trigger runs"],
                ["viewer","Read-only access to all resources and run history"],
                ["releaser","Trigger releases and approve environment promotion gates"],
              ].map(([r,d]) => `<div class="detail-row"><span class="detail-label" style="font-family:monospace">${r}</span><span class="detail-value" style="font-size:12px">${d}</span></div>`).join("")}
            </div>
          </div>
          <div>
            <strong style="font-size:13px">Assign roles</strong>
            <ol style="font-size:13px;padding-left:18px;line-height:2;margin-top:8px">
              <li>Go to <em>Administration → User Management</em></li>
              <li>Open a user, click <em>Assign Role</em></li>
              <li>Choose role + optional resource scope</li>
              <li>Or assign via Groups for bulk management</li>
            </ol>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Full API reference ── -->
    <div class="card">
      <div class="card-header">
        <h2>API Reference</h2>
        <a class="btn btn-secondary btn-sm" href="/api/v1/docs/swagger" target="_blank">Open Swagger UI &rarr;</a>
      </div>
      <p style="padding:0 16px;color:var(--gray-600);font-size:13px;margin-bottom:8px">All endpoints require JWT authentication (<code>Authorization: Bearer &lt;token&gt;</code>) except <code>/api/v1/auth/login</code>, <code>/healthz</code>, <code>/readyz</code>, and <code>/metrics</code>.</p>
      <div class="table-wrap" style="padding:0 16px 16px"><table>
        <thead><tr><th>Resource</th><th>Base Path</th><th>Methods</th><th>Notes</th></tr></thead>
        <tbody>
          ${[
            ["Auth","/api/v1/auth/login · /logout","POST","Returns JWT token"],
            ["Products","/api/v1/products","GET POST PUT DELETE","Top-level namespace"],
            ["Applications","/api/v1/products/:id/applications","GET POST PUT DELETE","Artifact versions per product"],
            ["Environments","/api/v1/environments","GET POST PUT DELETE","Shared deployment targets"],
            ["Pipelines","/api/v1/products/:pid/pipelines","GET POST PUT DELETE","kind: ci | cd | release | build"],
            ["Stages","/api/v1/products/:pid/pipelines/:id/stages","GET POST PUT DELETE","Ordered stage list"],
            ["Tasks","/api/v1/products/:pid/pipelines/:id/stages/:sid/tasks","GET POST PUT DELETE","Scripts with task_type tags"],
            ["Properties","/api/v1/properties/:scope/:owner_id","GET POST PUT DELETE","scope: pipeline | stage | task"],
            ["Releases","/api/v1/products/:pid/releases","GET POST PUT DELETE","Versioned pipeline bundles"],
            ["Pipeline Runs","/api/v1/pipeline-runs","GET POST · /pipeline-runs/:id","Trigger and poll"],
            ["Release Runs","/api/v1/release-runs","GET POST · /release-runs/:id","Trigger full release"],
            ["Webhooks","/api/v1/products/:pid/pipelines/:id/webhooks","GET POST DELETE · /trigger","Inbound triggers"],
            ["Agent Pools","/api/v1/agent-pools","GET POST DELETE","Execution sandbox pools"],
            ["Compliance Rules","/api/v1/compliance/rules","GET POST DELETE","Admission policies"],
            ["Maturity","/api/v1/maturity/pipelines/:id · /products/:id","GET","DevSecOps scoring"],
            ["Users / Groups / Roles","/api/v1/users · /groups · /roles","GET POST PATCH DELETE","RBAC entities"],
            ["Settings","/api/v1/settings/:key","GET PUT","Platform settings (GROQ_API_KEY, TASK_RUNNER…)"],
            ["Metrics","/metrics · /api/v1/metrics/stats · /alerts","GET","Prometheus + JSON snapshot"],
            ["AI Chat","/api/v1/chat","POST","LLM assistant with platform tools"],
          ].map(([r,p,m,n]) => `<tr><td><strong>${r}</strong></td><td><code style="font-size:11px">${p}</code></td><td style="font-size:12px;color:var(--gray-500);white-space:nowrap">${m}</td><td style="font-size:12px;color:var(--gray-600)">${n}</td></tr>`).join("")}
        </tbody>
      </table></div>
    </div>
  `);
});

// ── Tutorial ───────────────────────────────────────────────────────────────

router.register("tutorial", () => {
  setBreadcrumb({ label: "Tutorial" });
  setContent(`
    <div class="page-header">
      <div><h1>Conduit Tutorial</h1><div class="sub">Step-by-step guide from zero to a running pipeline</div></div>
      <button class="btn btn-primary btn-sm" onclick="navigate('products')">Get Started &rarr;</button>
    </div>

    <!-- ── Overview cards ── -->
    <div class="grid grid-4" style="margin-bottom:24px">
      ${[
        { n:"1", icon:"📦", title:"Product", desc:"Top-level project that owns pipelines, releases and applications" },
        { n:"2", icon:"🔧", title:"Pipeline", desc:"Ordered stages and tasks that run your CI/CD scripts" },
        { n:"3", icon:"🚀", title:"Release",  desc:"A versioned snapshot of pipelines ready to ship" },
        { n:"4", icon:"▶",  title:"Run",      desc:"Execute a pipeline or release and watch it progress live" },
      ].map(c => `
        <div class="card" style="text-align:center;padding:20px 12px">
          <div style="font-size:32px;margin-bottom:8px">${c.icon}</div>
          <div style="font-size:11px;font-weight:700;color:var(--primary);background:var(--primary-light);padding:2px 8px;border-radius:8px;display:inline-block;margin-bottom:8px">Step ${c.n}</div>
          <div style="font-weight:700;margin-bottom:6px">${c.title}</div>
          <div style="font-size:12px;color:var(--gray-500)">${c.desc}</div>
        </div>`).join("")}
    </div>

    <!-- ── Step 1: Create a Product ── -->
    <div class="card" style="margin-bottom:16px" id="tut-step-1">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">1</div>
          <div><h2 style="margin:0">Create a Product</h2><div style="font-size:12px;color:var(--gray-400)">Products → New Product</div></div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="navigate('products')">Open Products &rarr;</button>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          A <strong>Product</strong> is the top-level namespace for everything else — pipelines, releases,
          applications and environments all belong to a product.
        </p>
        <div class="grid grid-2" style="gap:12px">
          <div>
            <strong style="font-size:13px">What to fill in</strong>
            <div class="detail-grid" style="margin-top:8px">
              <div class="detail-row"><span class="detail-label">Name</span><span class="detail-value">Human-readable name, e.g. <em>Acme Platform</em></span></div>
              <div class="detail-row"><span class="detail-label">Slug</span><span class="detail-value">URL-safe identifier, auto-generated from name</span></div>
              <div class="detail-row"><span class="detail-label">Description</span><span class="detail-value">Optional — shown in search results and lists</span></div>
            </div>
          </div>
          <div style="background:var(--gray-900);border-radius:8px;padding:12px;font-size:12px;color:#e2e8f0">
            <strong>Tip</strong><br>
            Use one product per team or bounded context. Products can share environments
            (e.g. a shared <em>prod</em> environment) without duplicating configuration.
          </div>
        </div>
      </div>
    </div>

    <!-- ── Step 2: Add an Environment ── -->
    <div class="card" style="margin-bottom:16px" id="tut-step-2">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">2</div>
          <div><h2 style="margin:0">Add Environments</h2><div style="font-size:12px;color:var(--gray-400)">Environments → New Environment</div></div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="navigate('environments')">Open Environments &rarr;</button>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          Environments represent deployment targets like <em>dev</em>, <em>qa</em> and <em>prod</em>.
          Create them centrally, then attach them to products as needed.
        </p>
        <div class="grid grid-2" style="gap:12px">
          <div>
            <strong style="font-size:13px">Common setup</strong>
            <table style="margin-top:8px;font-size:12px;width:100%"><tbody>
              <tr><td style="padding:4px 12px 4px 0;color:var(--gray-500)">dev</td><td>Daily development, auto-deployed on every push</td></tr>
              <tr><td style="padding:4px 12px 4px 0;color:var(--gray-500)">qa</td><td>Integration tests, gated by a compliance check</td></tr>
              <tr><td style="padding:4px 12px 4px 0;color:var(--gray-500)">prod</td><td>Manual approval gate + full audit trail</td></tr>
            </tbody></table>
          </div>
          <div style="background:var(--gray-900);border-radius:8px;padding:12px;font-size:12px;color:#e2e8f0">
            <strong>Attach to a Product</strong><br>
            After creating an environment, go to your product's detail page and click
            <em>+ Attach Environment</em>. This controls which environments appear in release
            drop-downs for that product.
          </div>
        </div>
      </div>
    </div>

    <!-- ── Step 3: Build a Pipeline ── -->
    <div class="card" style="margin-bottom:16px" id="tut-step-3">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">3</div>
          <div><h2 style="margin:0">Build a Pipeline</h2><div style="font-size:12px;color:var(--gray-400)">Products → your product → Pipelines → New Pipeline</div></div>
        </div>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:16px">
          A <strong>Pipeline</strong> is a sequence of <strong>Stages</strong>, each containing one or more
          <strong>Tasks</strong>. Tasks are bash or python scripts that run in an isolated sandbox.
        </p>

        <div style="display:flex;align-items:center;gap:0;margin-bottom:20px;overflow-x:auto">
          ${["Stage 1: prepare","Stage 2: test","Stage 3: release"].map((s,i) => `
          <div style="display:flex;align-items:center;gap:0">
            <div style="background:var(--primary-light);border:1px solid var(--primary);border-radius:8px;padding:8px 16px;font-size:12px;font-weight:600;color:var(--primary);white-space:nowrap">${s}</div>
            ${i < 2 ? '<div style="width:24px;height:2px;background:var(--gray-300)"></div>' : ""}
          </div>`).join("")}
        </div>

        <div class="grid grid-2" style="gap:12px;margin-bottom:16px">
          <div>
            <strong style="font-size:13px">Stages</strong>
            <ul style="font-size:12px;color:var(--gray-600);margin:8px 0 0 0;padding-left:18px;line-height:1.8">
              <li>Give each stage a name and an optional accent colour</li>
              <li>Stages execute <strong>sequentially</strong> by default</li>
              <li>A failing stage stops subsequent stages (unless <code>on_error=warn</code>)</li>
            </ul>
          </div>
          <div>
            <strong style="font-size:13px">Tasks</strong>
            <ul style="font-size:12px;color:var(--gray-600);margin:8px 0 0 0;padding-left:18px;line-height:1.8">
              <li>Write a bash or python script in the built-in editor</li>
              <li>Use <code>CDT_*</code> env vars for run context (branch, commit, etc.)</li>
              <li>Print a JSON object as the <strong>last line</strong> to capture output</li>
              <li>Set <code>on_error=warn</code> for non-blocking tasks</li>
            </ul>
          </div>
        </div>

        <div style="background:var(--gray-900);border-radius:8px;padding:14px 16px;font-family:monospace;font-size:12px;color:#e2e8f0;overflow-x:auto">
          <div style="color:#94a3b8;margin-bottom:6px"># Example task script</div>
          <div><span style="color:#7dd3fc">#!/usr/bin/env bash</span></div>
          <div style="margin-top:8px"><span style="color:#94a3b8"># CDT_ vars are injected automatically</span></div>
          <div>echo <span style="color:#86efac">"Pipeline: <span style="color:#fde68a">\${CDT_PIPELINE_NAME}</span>"</span></div>
          <div>echo <span style="color:#86efac">"Branch  : <span style="color:#fde68a">\${CDT_GIT_BRANCH}</span>"</span></div>
          <div style="margin-top:8px"><span style="color:#94a3b8"># Read a property resolved from the hierarchy</span></div>
          <div>MIN=<span style="color:#fde68a">$(python3 -c "import json,os; print(json.loads(os.environ.get('CDT_PROPS','{}')). get('COVERAGE_MIN',80))")</span></div>
          <div style="margin-top:8px"><span style="color:#94a3b8"># Emit structured output (captured by Conduit)</span></div>
          <div>echo <span style="color:#86efac">'{"status":"ok","coverage_pct":92,"min_required":'</span><span style="color:#fde68a">\$MIN</span><span style="color:#86efac">'}'</span></div>
        </div>
      </div>
    </div>

    <!-- ── Step 4: CDT_ variables ── -->
    <div class="card" style="margin-bottom:16px" id="tut-step-4">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:#0369a1;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">4</div>
          <div><h2 style="margin:0">CDT_ Context Variables</h2><div style="font-size:12px;color:var(--gray-400)">Injected into every task at runtime</div></div>
        </div>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          Every task script receives these environment variables. Read them with <code>\${VAR}</code> in bash
          or <code>os.environ.get("VAR")</code> in python.
        </p>
        <div class="table-wrap"><table>
          <thead><tr><th>Variable</th><th>Example value</th><th>Description</th></tr></thead>
          <tbody>
            ${[
              ["CDT_PIPELINE_RUN_ID","plrun_01ABC…","Unique ID of this pipeline run"],
              ["CDT_PIPELINE_NAME","my-ci-pipeline","Pipeline name"],
              ["CDT_PIPELINE_ID","pipe_01…","Pipeline ID"],
              ["CDT_GIT_BRANCH","main","Git branch from pipeline definition"],
              ["CDT_GIT_REPO","github.com/org/repo","Git repo URL"],
              ["CDT_COMMIT_SHA","abc1234","Commit passed when triggering the run"],
              ["CDT_ARTIFACT_ID","v1.2.3","Artifact ID (optional)"],
              ["CDT_TRIGGERED_BY","webhook / ci / admin","Who/what triggered the run"],
              ["CDT_STAGE_NAME","test","Current stage name"],
              ["CDT_STAGE_ID","stg_01…","Current stage ID"],
              ["CDT_TASK_NAME","run-tests","Current task name"],
              ["CDT_TASK_ID","task_01…","Current task ID"],
              ["CDT_PROPS","{\"COVERAGE_MIN\":\"82\",…}","Resolved design-time properties (JSON)"],
              ["CDT_RUNTIME","{\"properties\":{…},…}","Full runtime context (JSON)"],
              ["CDT_WEBHOOK_PAYLOAD","{\"ref\":\"refs/heads/main\",…}","Raw webhook payload if triggered by webhook"],
            ].map(([v,e,d]) => `<tr>
              <td><code style="font-size:11px">${v}</code></td>
              <td style="color:var(--gray-500);font-size:11px">${e}</td>
              <td style="font-size:12px;color:var(--gray-600)">${d}</td>
            </tr>`).join("")}
          </tbody>
        </table></div>
      </div>
    </div>

    <!-- ── Step 5: Properties ── -->
    <div class="card" style="margin-bottom:16px" id="tut-step-5">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:#0369a1;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">5</div>
          <div><h2 style="margin:0">Properties &amp; Configuration</h2><div style="font-size:12px;color:var(--gray-400)">Pipeline → Properties tab</div></div>
        </div>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          Properties are named values that follow a strict inheritance hierarchy.
          A task always sees the <em>most specific</em> value defined for a given name.
        </p>
        <div style="display:flex;align-items:center;gap:0;flex-wrap:wrap;margin-bottom:16px">
          ${[
            { label:"Product", color:"#6366f1", desc:"Widest scope" },
            { label:"Pipeline", color:"#0369a1", desc:"" },
            { label:"Stage", color:"#0891b2", desc:"" },
            { label:"Task", color:"#059669", desc:"Narrowest — wins" },
          ].map((l,i,a) => `
          <div style="display:flex;align-items:center">
            <div style="background:${l.color}18;border:1px solid ${l.color}55;border-radius:6px;padding:6px 14px;font-size:12px;font-weight:600;color:${l.color}">${l.label}${l.desc ? `<div style="font-size:10px;font-weight:400;color:var(--gray-400)">${l.desc}</div>` : ""}</div>
            ${i < a.length - 1 ? '<div style="margin:0 4px;color:var(--gray-400);font-size:16px">&rarr;</div>' : ""}
          </div>`).join("")}
          <div style="margin-left:12px;font-size:12px;color:var(--gray-500)">(runtime overrides take precedence over all)</div>
        </div>
        <div class="grid grid-2" style="gap:12px">
          <div>
            <strong style="font-size:13px">Types</strong>
            <div class="detail-grid" style="margin-top:8px">
              <div class="detail-row"><span class="detail-label">string</span><span class="detail-value">Plain text — the default</span></div>
              <div class="detail-row"><span class="detail-label">number</span><span class="detail-value">Coerced to int/float when resolved</span></div>
              <div class="detail-row"><span class="detail-label">boolean</span><span class="detail-value">true / false</span></div>
              <div class="detail-row"><span class="detail-label">secret</span><span class="detail-value">Masked in UI, passed as plain text to scripts</span></div>
              <div class="detail-row"><span class="detail-label">json</span><span class="detail-value">Parsed as a JSON object/array</span></div>
            </div>
          </div>
          <div style="background:var(--gray-900);border-radius:8px;padding:12px;font-size:12px;color:#e2e8f0">
            <strong>Access in scripts</strong>
            <pre style="background:var(--gray-100);padding:8px;border-radius:4px;margin-top:6px;font-size:11px;overflow-x:auto">props=$(echo "\$CDT_PROPS" | python3 -c \\
  "import json,sys; d=json.load(sys.stdin); \\
   print(d.get('COVERAGE_MIN','80'))")
echo "Min coverage: \$props"</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Step 6: Webhooks ── -->
    <div class="card" style="margin-bottom:16px" id="tut-step-6">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:#b45309;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">6</div>
          <div><h2 style="margin:0">Webhooks — Trigger from CI</h2><div style="font-size:12px;color:var(--gray-400)">Pipeline → Webhooks tab</div></div>
        </div>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          Create a webhook to trigger a pipeline from any external system (GitHub, GitLab, Jenkins, curl).
          Conduit passes the raw payload to tasks as <code>$CDT_WEBHOOK_PAYLOAD</code>.
        </p>
        <div style="background:var(--gray-900);border-radius:8px;padding:14px 16px;font-family:monospace;font-size:12px;color:#e2e8f0;overflow-x:auto;margin-bottom:12px">
          <div style="color:#94a3b8;margin-bottom:6px"># Trigger the E2E demo pipeline</div>
          <div>curl -s -X POST \\</div>
          <div style="padding-left:16px">http://localhost:8080/api/v1/webhooks/<span style="color:#fde68a">&lt;webhook-id&gt;</span>/trigger \\</div>
          <div style="padding-left:16px">-H <span style="color:#86efac">"X-Webhook-Token: <span style="color:#fde68a">&lt;token&gt;</span>"</span> \\</div>
          <div style="padding-left:16px">-H <span style="color:#86efac">"Content-Type: application/json"</span> \\</div>
          <div style="padding-left:16px">-d <span style="color:#86efac">'{"ref":"refs/heads/main","after":"abc1234","pusher":{"name":"you"}}'</span></div>
        </div>
        <div style="background:var(--gray-900);border-radius:8px;padding:12px;font-size:12px;color:#e2e8f0">
          <strong>GitHub / GitLab integration</strong><br>
          Point your repository's webhook at <code>/api/v1/webhooks/&lt;id&gt;/trigger</code>
          and set the <em>Secret</em> to your webhook token. Conduit validates the token,
          stores the raw payload, and starts a pipeline run.
        </div>
      </div>
    </div>

    <!-- ── Step 7: Releases ── -->
    <div class="card" style="margin-bottom:16px" id="tut-step-7">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:#b45309;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">7</div>
          <div><h2 style="margin:0">Create a Release</h2><div style="font-size:12px;color:var(--gray-400)">Products → your product → Releases → New Release</div></div>
        </div>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          A <strong>Release</strong> groups one or more pipelines into a versioned artefact.
          When you run a release, all attached pipelines run — either in parallel or
          in the order you define with <em>Application Groups</em>.
        </p>
        <div class="grid grid-2" style="gap:12px">
          <div>
            <strong style="font-size:13px">Workflow</strong>
            <ol style="font-size:12px;color:var(--gray-600);margin:8px 0 0 0;padding-left:18px;line-height:2">
              <li>Create a release with a version string (e.g. <code>v1.2.3</code>)</li>
              <li>Attach pipelines from the same product</li>
              <li>Optionally group them for parallel/sequential execution</li>
              <li>Click <strong>Run Release</strong> — watch all pipelines progress live</li>
            </ol>
          </div>
          <div>
            <strong style="font-size:13px">Application Groups</strong>
            <p style="font-size:12px;color:var(--gray-600);margin:8px 0 0 0;line-height:1.7">
              Group pipelines by <em>application</em> to run them in parallel within a group
              and sequentially across groups. E.g. run <em>api</em> and <em>frontend</em>
              pipelines in parallel, but only after <em>infra</em> has succeeded.
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Step 8: Compliance ── -->
    <div class="card" style="margin-bottom:16px" id="tut-step-8">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:#dc2626;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">8</div>
          <div><h2 style="margin:0">Compliance Rules</h2><div style="font-size:12px;color:var(--gray-400)">Compliance → Rules</div></div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="navigate('compliance')">Open Compliance &rarr;</button>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          Compliance rules enforce policies before a pipeline can be attached to a release.
          They evaluate pipeline metadata (score, rating, last run status, required tasks, etc.).
        </p>
        <div class="detail-grid">
          <div class="detail-row"><span class="detail-label">score_gte</span><span class="detail-value">Minimum compliance score (0–100)</span></div>
          <div class="detail-row"><span class="detail-label">rating_in</span><span class="detail-value">Allowed ratings, e.g. Gold, Silver</span></div>
          <div class="detail-row"><span class="detail-label">last_run_status</span><span class="detail-value">Pipeline's last run must have this status</span></div>
          <div class="detail-row"><span class="detail-label">required_tasks</span><span class="detail-value">Task names that must exist in the pipeline</span></div>
          <div class="detail-row"><span class="detail-label">has_git_repo</span><span class="detail-value">Pipeline must have a git repo configured</span></div>
        </div>
      </div>
    </div>

    <!-- ── Step 9: Context Inspector ── -->
    <div class="card" style="margin-bottom:16px" id="tut-step-9">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:#7c3aed;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">9</div>
          <div><h2 style="margin:0">Context Inspector &amp; Run Debugging</h2><div style="font-size:12px;color:var(--gray-400)">Pipeline Run → task → Context button</div></div>
        </div>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          Every completed run stores the full execution context. Open any pipeline run and
          click the <strong>Context</strong> button on a task row to inspect:
        </p>
        <div class="grid grid-3" style="gap:12px;margin-bottom:12px">
          <div style="background:var(--gray-50);border-radius:8px;padding:12px">
            <div style="font-weight:600;font-size:13px;margin-bottom:6px;color:var(--primary)">CDT Variables</div>
            <div style="font-size:12px;color:var(--gray-600)">All CDT_* env vars that were injected into this specific task — pipeline name, run ID, branch, triggered-by, etc.</div>
          </div>
          <div style="background:var(--gray-50);border-radius:8px;padding:12px">
            <div style="font-weight:600;font-size:13px;margin-bottom:6px;color:#0369a1">Properties</div>
            <div style="font-size:12px;color:var(--gray-600)">The resolved CDT_PROPS map — shows exactly which property values were visible to the task after hierarchy resolution.</div>
          </div>
          <div style="background:var(--gray-50);border-radius:8px;padding:12px">
            <div style="font-weight:600;font-size:13px;margin-bottom:6px;color:#059669">Output JSON</div>
            <div style="font-size:12px;color:var(--gray-600)">The JSON object printed as the last line of stdout — captured by Conduit as structured task output for downstream tasks.</div>
          </div>
        </div>
        <div style="background:var(--gray-900);border-radius:8px;padding:12px;font-size:12px;color:#e2e8f0">
          <strong>Full-run inspector</strong> — Use the <em>Inspect Context</em> button at the top of any pipeline run
          to open a modal with the entire run tree: every stage's runtime properties and every task's context, all in one view.
        </div>
      </div>
    </div>

    <!-- ── Step 10: E2E Demo ── -->
    <div class="card" style="margin-bottom:24px;border:2px solid var(--primary)" id="tut-step-10">
      <div class="card-header" style="background:var(--primary-light)">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="width:32px;height:32px;border-radius:50%;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0">10</div>
          <div><h2 style="margin:0;color:var(--primary)">Try It: E2E Demo Pipeline</h2><div style="font-size:12px;color:var(--gray-500)">A pre-built pipeline you can trigger right now</div></div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="navigate('products')">Find in Products &rarr;</button>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:16px">
          The <strong>conduit-e2e-demo</strong> pipeline is pre-loaded with 3 stages, 6 real tasks,
          seeded properties at every level, and a fixed webhook token. Trigger it with this curl command:
        </p>
        <div style="background:var(--gray-900);border-radius:8px;padding:14px 16px;font-family:monospace;font-size:12px;color:#e2e8f0;overflow-x:auto;margin-bottom:12px">
          <div>curl -s -X POST \\</div>
          <div style="padding-left:16px">http://localhost:8080/api/v1/webhooks/wh_01KN2M82NGX0QMBPA69R1BG509/trigger \\</div>
          <div style="padding-left:16px">-H <span style="color:#86efac">"X-Webhook-Token: conduit-e2e-demo-token-2024"</span> \\</div>
          <div style="padding-left:16px">-H <span style="color:#86efac">"Content-Type: application/json"</span> \\</div>
          <div style="padding-left:16px">-d <span style="color:#86efac">'{"ref":"refs/heads/main","after":"abc1234","pusher":{"name":"you"}}'</span> \\</div>
          <div style="padding-left:16px">| python3 -m json.tool</div>
        </div>
        <div class="grid grid-3" style="gap:8px">
          <div style="background:var(--gray-50);border-radius:6px;padding:10px;font-size:12px">
            <div style="font-weight:600;color:#3b82f6;margin-bottom:4px">Stage 1 — prepare</div>
            <div style="color:var(--gray-600)">Preflight checks, parse webhook payload, emit CDT vars &amp; properties as output JSON</div>
          </div>
          <div style="background:var(--gray-50);border-radius:6px;padding:10px;font-size:12px">
            <div style="font-weight:600;color:#10b981;margin-bottom:4px">Stage 2 — test</div>
            <div style="color:var(--gray-600)">Run 8 test cases, compute coverage using <code>COVERAGE_MIN</code> property, emit results</div>
          </div>
          <div style="background:var(--gray-50);border-radius:6px;padding:10px;font-size:12px">
            <div style="font-weight:600;color:#f59e0b;margin-bottom:4px">Stage 3 — release</div>
            <div style="color:var(--gray-600)">Smoke-test the live API, generate completion report with full context summary</div>
          </div>
        </div>
        <div style="margin-top:12px;font-size:12px;color:var(--gray-600);background:var(--gray-50);border-radius:6px;padding:10px">
          After triggering, open the pipeline run and click <strong>Context</strong> on any task to see the
          CDT variables, resolved properties, and output JSON — all captured automatically.
        </div>
      </div>
    </div>

    <!-- ── Cheatsheet ── -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>Quick Reference Cheatsheet</h2></div>
      <div class="grid grid-2" style="padding:0 16px 16px;gap:16px">
        <div>
          <strong style="font-size:13px">Keyboard shortcuts</strong>
          <div class="detail-grid" style="margin-top:8px">
            <div class="detail-row"><span class="detail-label" style="font-family:monospace">Ctrl+K</span><span class="detail-value">Open system-wide search</span></div>
            <div class="detail-row"><span class="detail-label" style="font-family:monospace">/</span><span class="detail-value">Open search (when not in an input)</span></div>
            <div class="detail-row"><span class="detail-label" style="font-family:monospace">Esc</span><span class="detail-value">Close any modal or overlay</span></div>
            <div class="detail-row"><span class="detail-label" style="font-family:monospace">↑ ↓</span><span class="detail-value">Navigate search results</span></div>
          </div>
        </div>
        <div>
          <strong style="font-size:13px">Useful API endpoints</strong>
          <div class="detail-grid" style="margin-top:8px">
            <div class="detail-row"><span class="detail-label" style="font-family:monospace">GET /healthz</span><span class="detail-value">Liveness probe</span></div>
            <div class="detail-row"><span class="detail-label" style="font-family:monospace">GET /api/v1/docs/swagger</span><span class="detail-value">Interactive API explorer</span></div>
            <div class="detail-row"><span class="detail-label" style="font-family:monospace">POST /pipelines/:id/runs</span><span class="detail-value">Trigger a pipeline run</span></div>
            <div class="detail-row"><span class="detail-label" style="font-family:monospace">GET /pipeline-runs/:id/context</span><span class="detail-value">Full execution context</span></div>
          </div>
        </div>
      </div>
    </div>
  `);
});

// ── Monitoring ─────────────────────────────────────────────────────────────

router.register("monitoring", async () => {
  setBreadcrumb({ label: "Monitoring" });
  setContent(`<div class="loading-center"><div class="spinner"></div></div>`);

  let stats = null, alerts = [];
  try {
    [stats, alerts] = await Promise.all([
      request("GET", "/metrics/stats"),
      request("GET", "/metrics/alerts"),
    ]);
  } catch (e) {
    setContent(`<div class="page-header"><div><h1>Monitoring</h1></div></div>
      <div class="alert alert-danger">Could not load metrics: ${e.message}</div>`);
    return;
  }

  const p = stats.platform || {};
  const r = stats.runs_last_24h || {};
  const a = stats.active_runs || {};
  const c = stats.compliance || {};
  const perf = stats.performance || {};

  const statCard = (icon, label, value, sub) => `
    <div class="card" style="padding:20px;text-align:center">
      <div style="font-size:28px;margin-bottom:6px">${icon}</div>
      <div style="font-size:28px;font-weight:700;color:var(--gray-900)">${value}</div>
      <div style="font-size:13px;font-weight:600;color:var(--gray-600);margin-top:2px">${label}</div>
      ${sub ? `<div style="font-size:11px;color:var(--gray-400);margin-top:4px">${sub}</div>` : ""}
    </div>`;

  const firingCount = alerts.filter(a => a.firing).length;
  const alertBadge = firingCount > 0
    ? `<span style="background:#ef4444;color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700">${firingCount} FIRING</span>`
    : `<span style="background:#22c55e;color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700">All Clear</span>`;

  const severityColor = { critical: "#ef4444", warning: "#f59e0b", info: "#3b82f6" };

  const successRate = r.total > 0 ? Math.round((r.succeeded / r.total) * 100) : 0;
  const failRate = r.total > 0 ? Math.round((r.failed / r.total) * 100) : 0;

  setContent(`
    <div class="page-header">
      <div><h1>Monitoring</h1><div class="sub">Live platform health — Prometheus metrics &amp; alert rules</div></div>
      <div style="display:flex;gap:8px;align-items:center">
        ${alertBadge}
        <a class="btn btn-secondary btn-sm" href="/metrics" target="_blank">Raw /metrics</a>
      </div>
    </div>

    <!-- ── Platform counters ── -->
    <div class="grid grid-4" style="margin-bottom:20px">
      ${statCard("📦", "Products", p.products ?? "—")}
      ${statCard("⚙️", "Pipelines", p.pipelines ?? "—")}
      ${statCard("🚀", "Releases", p.releases ?? "—")}
      ${statCard("👥", "Users", p.users ?? "—")}
    </div>

    <!-- ── Run stats + compliance row ── -->
    <div class="grid grid-3" style="margin-bottom:20px">
      <div class="card" style="padding:20px">
        <div style="font-weight:700;margin-bottom:14px;font-size:14px">Runs — last 24 h</div>
        ${[
          ["Total", r.total ?? 0, "#6366f1"],
          ["Succeeded", r.succeeded ?? 0, "#22c55e"],
          ["Failed", r.failed ?? 0, "#ef4444"],
          ["Running", r.running ?? 0, "#3b82f6"],
          ["Warning", r.warning ?? 0, "#f59e0b"],
          ["Cancelled", r.cancelled ?? 0, "#9ca3af"],
        ].map(([lbl, val, col]) => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid var(--gray-100)">
            <span style="font-size:13px;color:var(--gray-600)">${lbl}</span>
            <span style="font-weight:700;color:${col}">${val}</span>
          </div>`).join("")}
        <div style="margin-top:12px">
          <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--gray-400);margin-bottom:4px">
            <span>Success rate</span><span>${successRate}%</span>
          </div>
          <div style="height:8px;background:var(--gray-200);border-radius:4px;overflow:hidden;position:relative">
            <div style="position:absolute;top:0;left:0;height:100%;width:${successRate}%;background:#22c55e;border-radius:4px"></div>
          </div>
        </div>
      </div>

      <div class="card" style="padding:20px">
        <div style="font-weight:700;margin-bottom:14px;font-size:14px">Active Runs</div>
        <div style="display:flex;gap:16px;margin-bottom:20px">
          <div style="flex:1;text-align:center;background:var(--gray-50);border-radius:8px;padding:16px">
            <div style="font-size:32px;font-weight:700;color:#3b82f6">${a.pipeline ?? 0}</div>
            <div style="font-size:12px;color:var(--gray-500);margin-top:4px">Pipeline Runs</div>
          </div>
          <div style="flex:1;text-align:center;background:var(--gray-50);border-radius:8px;padding:16px">
            <div style="font-size:32px;font-weight:700;color:#8b5cf6">${a.release ?? 0}</div>
            <div style="font-size:12px;color:var(--gray-500);margin-top:4px">Release Runs</div>
          </div>
        </div>
        <div style="font-weight:700;margin-bottom:10px;font-size:13px">Performance</div>
        <div class="detail-grid">
          <div class="detail-row">
            <span class="detail-label">Avg run duration</span>
            <span class="detail-value">${perf.avg_run_duration_s ?? 0}s</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Sample size</span>
            <span class="detail-value">${perf.sample_size ?? 0} runs</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Failure rate (24h)</span>
            <span class="detail-value" style="color:${failRate > 20 ? "#ef4444" : failRate > 10 ? "#f59e0b" : "#22c55e"}">${failRate}%</span>
          </div>
        </div>
      </div>

      <div class="card" style="padding:20px">
        <div style="font-weight:700;margin-bottom:14px;font-size:14px">Compliance Health</div>
        <div style="text-align:center;margin-bottom:16px">
          <div style="font-size:48px;font-weight:700;color:${(c.avg_score ?? 0) >= 80 ? "#22c55e" : (c.avg_score ?? 0) >= 60 ? "#f59e0b" : "#ef4444"}">${c.avg_score ?? 0}</div>
          <div style="font-size:12px;color:var(--gray-400)">avg compliance score</div>
          <div style="height:8px;background:var(--gray-200);border-radius:4px;overflow:hidden;position:relative;margin-top:10px">
            <div style="position:absolute;top:0;left:0;height:100%;width:${c.avg_score ?? 0}%;background:${(c.avg_score ?? 0) >= 80 ? "#22c55e" : (c.avg_score ?? 0) >= 60 ? "#f59e0b" : "#ef4444"};border-radius:4px"></div>
          </div>
        </div>
        <div class="detail-grid">
          <div class="detail-row">
            <span class="detail-label">Compliant pipelines</span>
            <span class="detail-value" style="color:#22c55e">${c.compliant_pipelines ?? 0} / ${c.total_pipelines ?? 0}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Alert rules ── -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header">
        <h2>Alert Rules</h2>
        <div style="font-size:12px;color:var(--gray-400)">Evaluated live from platform data — mirrors Prometheus/Alertmanager rules</div>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>Rule</th><th>Severity</th><th>Description</th><th>Condition</th><th>Status</th></tr></thead>
        <tbody>
          ${alerts.map(rule => `
            <tr>
              <td><strong>${rule.name}</strong></td>
              <td><span style="background:${(severityColor[rule.severity] || "#9ca3af")}22;color:${severityColor[rule.severity] || "#9ca3af"};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;text-transform:uppercase">${rule.severity}</span></td>
              <td style="font-size:12px;color:var(--gray-600)">${rule.description}</td>
              <td style="font-family:monospace;font-size:11px;color:var(--gray-500);max-width:260px;word-break:break-all">${rule.condition}</td>
              <td>${rule.firing
                ? `<span style="background:#fee2e2;color:#ef4444;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700">🔴 FIRING</span>`
                : `<span style="background:#dcfce7;color:#16a34a;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:600">✅ OK</span>`
              }</td>
            </tr>`).join("")}
        </tbody>
      </table></div>
    </div>

    <!-- ── Prometheus endpoint info ── -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><h2>Prometheus Scrape Endpoint</h2></div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">
          The application exposes a standard Prometheus text-format metrics endpoint at <code>/metrics</code> (public, no auth required).
          Point your Prometheus instance at this endpoint to collect all <code>conduit_*</code> metrics.
        </p>
        <div class="grid grid-2" style="gap:12px;margin-bottom:16px">
          <div>
            <strong style="font-size:13px">Available metric families</strong>
            <div class="detail-grid" style="margin-top:8px;font-size:12px">
              ${[
                ["conduit_pipeline_runs_total", "Counter — runs by pipeline/status"],
                ["conduit_pipeline_run_duration_seconds", "Histogram — run durations"],
                ["conduit_active_pipeline_runs", "Gauge — currently running"],
                ["conduit_task_runs_total", "Counter — task runs by name/status"],
                ["conduit_task_run_duration_seconds", "Histogram — task durations"],
                ["conduit_products_total", "Gauge — total products"],
                ["conduit_pipelines_total", "Gauge — total pipelines"],
                ["conduit_releases_total", "Gauge — total releases"],
                ["conduit_compliance_score_avg", "Gauge — avg compliance score"],
                ["conduit_pipelines_compliant_total", "Gauge — pipelines with score ≥ 80"],
                ["conduit_release_runs_total", "Counter — release runs by status"],
                ["conduit_active_release_runs", "Gauge — active release runs"],
                ["conduit_http_requests_total", "Counter — HTTP by method/endpoint/status"],
                ["conduit_http_request_duration_seconds", "Histogram — HTTP latency"],
              ].map(([m, d]) => `<div class="detail-row"><span class="detail-label" style="font-family:monospace;font-size:11px">${m}</span><span class="detail-value">${d}</span></div>`).join("")}
            </div>
          </div>
          <div>
            <strong style="font-size:13px">Prometheus scrape config (prometheus.yml)</strong>
            <pre style="background:var(--gray-900);color:#e2e8f0;border-radius:8px;padding:14px;font-size:12px;margin-top:8px;overflow-x:auto">scrape_configs:
  - job_name: conduit
    static_configs:
      - targets: ['conduit:8080']
    metrics_path: /metrics
    scrape_interval: 15s</pre>
            <strong style="font-size:13px;display:block;margin-top:14px">Verify scraping works</strong>
            <pre style="background:var(--gray-900);color:#e2e8f0;border-radius:8px;padding:14px;font-size:12px;margin-top:8px;overflow-x:auto">curl -s http://localhost:8080/metrics | grep conduit_</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Telemetry stack launcher ── -->
    <div class="card" style="margin-bottom:20px" id="stack-launcher-card">
      <div class="card-header">
        <h2>Telemetry Stack</h2>
        <div style="display:flex;gap:8px">
          <button class="btn btn-primary btn-sm" onclick="startMonitoringStack()" id="stack-start-btn">▶ Start Stack</button>
          <button class="btn btn-secondary btn-sm" onclick="stopMonitoringStack()" id="stack-stop-btn">■ Stop Stack</button>
          <button class="btn btn-secondary btn-sm" onclick="refreshStackStatus()">↻ Refresh</button>
        </div>
      </div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:14px">
          One-click launcher for Prometheus, Alertmanager, and Grafana. Config files and a pre-built
          Conduit dashboard are written automatically. Requires Docker or Podman on this host.
        </p>
        <div id="stack-status-panel">
          <div class="loading-center" style="padding:12px"><div class="spinner"></div></div>
        </div>
      </div>
    </div>

    <!-- ── Grafana dashboard tips ── -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><h2>Recommended Grafana Panels</h2></div>
      <div class="grid grid-3" style="padding:0 16px 16px;gap:12px">
        ${[
          { icon:"📈", title:"Pipeline Run Rate", query:"rate(conduit_pipeline_runs_total[5m])", type:"Time series", desc:"Runs started per second, split by status label" },
          { icon:"⏱️", title:"P95 Run Duration", query:'histogram_quantile(0.95, rate(conduit_pipeline_run_duration_seconds_bucket[5m]))', type:"Gauge / Stat", desc:"95th percentile pipeline duration" },
          { icon:"🎯", title:"Success Rate %", query:'rate(conduit_pipeline_runs_total{status="Succeeded"}[1h]) / rate(conduit_pipeline_runs_total[1h]) * 100', type:"Gauge", desc:"Pipeline success percentage over 1h window" },
          { icon:"🐌", title:"Active Runs", query:"conduit_active_pipeline_runs", type:"Stat panel", desc:"Currently executing pipeline runs" },
          { icon:"🛡️", title:"Compliance Score", query:"conduit_compliance_score_avg", type:"Gauge", desc:"Average compliance score across all pipelines" },
          { icon:"🌐", title:"HTTP Latency P99", query:'histogram_quantile(0.99, rate(conduit_http_request_duration_seconds_bucket[5m]))', type:"Time series", desc:"API tail latency — alert if > 1s" },
        ].map(p => `
          <div style="background:var(--gray-50);border-radius:8px;padding:14px">
            <div style="font-size:22px;margin-bottom:6px">${p.icon}</div>
            <div style="font-weight:700;font-size:13px;margin-bottom:4px">${p.title}</div>
            <div style="font-size:11px;color:var(--primary);background:var(--primary-light);padding:2px 8px;border-radius:6px;display:inline-block;margin-bottom:6px">${p.type}</div>
            <div style="font-size:11px;color:var(--gray-500);margin-bottom:6px">${p.desc}</div>
            <pre style="background:var(--gray-200);border-radius:4px;padding:6px 8px;font-size:10px;overflow-x:auto;margin:0">${p.query}</pre>
          </div>`).join("")}
      </div>
    </div>
  `);

  // Load stack status after DOM is rendered
  setTimeout(refreshStackStatus, 50);
});

// ── Monitoring stack launcher ─────────────────────────────────────────────

async function refreshStackStatus() {
  const panel = document.getElementById("stack-status-panel");
  if (!panel) return;
  panel.innerHTML = `<div class="loading-center" style="padding:12px"><div class="spinner"></div></div>`;
  try {
    const data = await request("GET", "/metrics/stack/status");
    if (data.error) {
      panel.innerHTML = `<div style="color:var(--danger);padding:12px;font-size:13px">
        <strong>No container runtime found.</strong> Install Docker or Podman to use the telemetry stack.
      </div>`;
      return;
    }
    const services = data.services || {};
    const stateColor = s => s === "running" ? "#22c55e" : s === "exited" ? "#f59e0b" : "#9ca3af";
    const stateLabel = s => s === "running" ? "Running" : s === "exited" ? "Stopped" : s === "not found" ? "Not started" : s;
    panel.innerHTML = `
      <div class="grid grid-3" style="gap:12px;margin-bottom:14px">
        ${Object.entries(services).map(([name, svc]) => `
          <div style="background:var(--gray-50);border-radius:8px;padding:14px;text-align:center">
            <div style="font-size:22px;margin-bottom:6px">${name.includes("prometheus") ? "📊" : name.includes("grafana") ? "📈" : "🔔"}</div>
            <div style="font-weight:700;font-size:13px;margin-bottom:4px">${name.replace("conduit-", "")}</div>
            <div style="margin-bottom:8px">
              <span style="background:${stateColor(svc.state)}22;color:${stateColor(svc.state)};padding:2px 10px;border-radius:8px;font-size:11px;font-weight:600">${stateLabel(svc.state)}</span>
            </div>
            ${svc.state === "running"
              ? `<a href="${svc.url}" target="_blank" style="font-size:12px;color:var(--primary);text-decoration:none">Open ↗</a>`
              : `<span style="font-size:12px;color:var(--gray-400)">${svc.url}</span>`
            }
          </div>`).join("")}
      </div>
      <div style="font-size:12px;color:var(--gray-500)">
        Runtime: <strong>${data.runtime || "—"}</strong> &nbsp;·&nbsp; Config dir: <code style="font-size:11px">${data.stack_dir || "—"}</code>
      </div>`;
  } catch (e) {
    panel.innerHTML = `<div style="color:var(--danger);padding:12px;font-size:13px">Failed to fetch stack status: ${e.message}</div>`;
  }
}

async function startMonitoringStack() {
  const btn = document.getElementById("stack-start-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Starting…"; }
  try {
    const data = await request("POST", "/metrics/stack/start");
    if (data.ok) {
      showToast("Monitoring stack started", "success");
    } else {
      showToast("Failed to start stack: " + (data.error || "unknown error"), "error");
    }
  } catch (e) {
    showToast("Error: " + e.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "▶ Start Stack"; }
    refreshStackStatus();
  }
}

async function stopMonitoringStack() {
  const btn = document.getElementById("stack-stop-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Stopping…"; }
  try {
    const data = await request("POST", "/metrics/stack/stop");
    if (data.ok) {
      showToast("Monitoring stack stopped", "success");
    } else {
      showToast("Failed to stop stack: " + (data.error || "unknown error"), "error");
    }
  } catch (e) {
    showToast("Error: " + e.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "■ Stop Stack"; }
    refreshStackStatus();
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  // Modal close
  el("modal-cancel").onclick = closeModal;
  el("modal-close-btn").onclick = closeModal;
  el("modal-overlay").addEventListener("click", e => { if (e.target === el("modal-overlay")) closeModal(); });

  // Check auth before initialising the router
  if (auth.isLoggedIn()) {
    try {
      _currentUser = await api.me();
      updateTopbarUser();
      router.init();
    } catch {
      // Token invalid/expired — show login
      auth.clearToken();
      showLoginPage();
    }
  } else {
    showLoginPage();
  }
});
