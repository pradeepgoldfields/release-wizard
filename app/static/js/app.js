/* ── Release Wizard SPA ─────────────────────────────────────────────────── */

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
        <div class="login-logo">Release <span style="color:var(--brand)">Wizard</span></div>
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

function updateTopbarUser() {
  let widget = document.getElementById("topbar-user");
  if (!widget) {
    widget = document.createElement("div");
    widget.id = "topbar-user";
    widget.style.cssText = "margin-left:auto;position:relative";
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
  el("breadcrumb").innerHTML = "";
}

function setBreadcrumb(...crumbs) {
  el("breadcrumb").innerHTML = crumbs.map((c, i) =>
    i === crumbs.length - 1
      ? `<span class="crumb-current">${c.label}</span>`
      : `<a href="#${c.hash}">${c.label}</a><span class="crumb-sep">›</span>`
  ).join("");
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
  return `<div class="score-bar-wrap">
    <div class="score-bar"><div class="score-bar-fill ${rating}" style="width:${score||0}%"></div></div>
    <span style="font-size:12px;color:var(--gray-600);min-width:36px">${score||0}%</span>
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
  const [products, rules] = await Promise.all([
    api.getProducts().catch(() => []),
    api.getComplianceRules().catch(() => []),
  ]);
  setContent(`
    <div class="page-header">
      <div><h1>Dashboard</h1><div class="sub">Release Wizard overview</div></div>
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
        <div class="stat-label">Platform</div>
        <div class="stat-value" style="font-size:18px">Release Wizard</div>
        <div class="stat-sub">v0.1.0 · UBI9/K8s</div>
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
      <div style="display:flex;gap:8px">
        <button class="btn btn-secondary btn-sm" onclick="exportYaml('/api/v1/products/${product.id}/export','${product.name.replace(/'/g,"\\'")}product.yaml')">⬇ YAML</button>
        <button class="btn btn-danger btn-sm" onclick="deleteProduct('${product.id}','${product.name}')">Delete</button>
      </div>
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
              <td style="display:flex;gap:6px">
                <button class="btn btn-secondary btn-sm" onclick="navigate('products/${productId}/releases/${r.id}')">View</button>
                <button class="btn btn-secondary btn-sm" onclick="showEditRelease('${productId}','${r.id}','${r.name.replace(/'/g,"\\'")}','${r.version||""}','${(r.description||"").replace(/'/g,"\\'")}')">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteRelease('${productId}','${r.id}','${r.name.replace(/'/g,"\\'")}')">Delete</button>
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
            return `<div class="card" style="margin-bottom:14px">
              <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:8px">
                <div>
                  <div style="font-weight:600;font-size:15px">${a.name}</div>
                  <span class="badge badge-blue">${a.artifact_type}</span>
                  ${a.repository_url ? `<div style="font-size:12px;color:var(--gray-400);margin-top:4px">${a.repository_url}</div>` : ""}
                </div>
                <div style="display:flex;gap:6px">
                  <button class="btn btn-primary btn-sm" onclick="showCreatePipelineForApp('${product.id}','${a.id}')">+ Pipeline</button>
                  <button class="btn btn-secondary btn-sm" onclick="showEditApp('${product.id}','${a.id}','${a.name.replace(/'/g,"\\'")}','${a.artifact_type}','${(a.repository_url||"").replace(/'/g,"\\'")}')">Edit</button>
                  <button class="btn btn-danger btn-sm" onclick="deleteApp('${product.id}','${a.id}','${a.name.replace(/'/g,"\\'")}')">Delete</button>
                </div>
              </div>
              ${appPipelines.length === 0
                ? `<div style="font-size:12px;color:var(--gray-400);padding:6px 0">No pipelines — click "+ Pipeline" to add one.</div>`
                : `<div class="table-wrap"><table style="font-size:13px">
                    <thead><tr><th>Pipeline</th><th>Kind</th><th>Compliance</th><th>Actions</th></tr></thead>
                    <tbody>${appPipelines.map(pl => `
                      <tr>
                        <td><a href="#products/${productId}/pipelines/${pl.id}">${pl.name}</a></td>
                        <td><span class="badge badge-${pl.kind}">${pl.kind.toUpperCase()}</span></td>
                        <td>${ratingBadge(pl.compliance_rating)}</td>
                        <td style="display:flex;gap:4px">
                          <button class="btn btn-secondary btn-sm" onclick="navigate('products/${productId}/pipelines/${pl.id}')">View</button>
                          <button class="btn btn-danger btn-sm" onclick="deletePipeline('${productId}','${pl.id}','${pl.name.replace(/'/g,"\\'")}')">Delete</button>
                        </td>
                      </tr>`).join("")}
                    </tbody></table></div>`
              }
            </div>`;
          }).join("")
      }
    </div>
  `);
});

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
  openModal("New Pipeline",
    `<div class="form-group"><label>Application *</label>
       <select id="plf-app" class="form-control">
         <option value="">— Select application —</option>
         ${apps.map(a => `<option value="${a.id}">${a.name}</option>`).join("")}
       </select></div>
     <div class="form-group"><label>Name *</label><input id="plf-name" class="form-control" placeholder="e.g. API CI Pipeline"></div>
     <div class="form-group"><label>Kind</label><select id="plf-kind" class="form-control"><option value="ci">CI</option><option value="cd">CD</option></select></div>
     <div class="form-group"><label>Git Repository</label><input id="plf-repo" class="form-control" placeholder="git@github.com:org/repo.git"></div>
     <div class="form-group"><label>Branch</label><input id="plf-branch" class="form-control" value="main"></div>`,
    async () => {
      const name = el("plf-name").value.trim();
      const appId = el("plf-app").value;
      if (!name) return modalError("Name is required");
      if (!appId) return modalError("Application is required");
      try {
        await api.createPipeline(productId, {
          name,
          application_id: appId,
          kind: el("plf-kind").value,
          git_repo: el("plf-repo").value.trim() || null,
          git_branch: el("plf-branch").value.trim() || "main",
        });
        closeModal(); toast("Pipeline created", "success");
        navigate(`products/${productId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

function showCreatePipelineForApp(productId, applicationId) {
  openModal("New Pipeline",
    `<div class="form-group"><label>Name *</label><input id="plf-name" class="form-control" placeholder="e.g. API CI Pipeline"></div>
     <div class="form-group"><label>Kind</label><select id="plf-kind" class="form-control"><option value="ci">CI</option><option value="cd">CD</option></select></div>
     <div class="form-group"><label>Git Repository</label><input id="plf-repo" class="form-control" placeholder="git@github.com:org/repo.git"></div>
     <div class="form-group"><label>Branch</label><input id="plf-branch" class="form-control" value="main"></div>`,
    async () => {
      const name = el("plf-name").value.trim();
      if (!name) return modalError("Name is required");
      try {
        await api.createPipeline(productId, {
          name,
          application_id: applicationId,
          kind: el("plf-kind").value,
          git_repo: el("plf-repo").value.trim() || null,
          git_branch: el("plf-branch").value.trim() || "main",
        });
        closeModal(); toast("Pipeline created", "success");
        navigate(`products/${productId}`);
      } catch (e) { modalError(e.message); }
    }
  );
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
    { id: "definition", label: "📋 Definition", hash: `products/${productId}/pipelines/${pipelineId}` },
    { id: "runs",       label: "▶ Runs",        hash: `products/${productId}/pipelines/${pipelineId}/runs` },
    { id: "webhooks",   label: "🔗 Webhooks",   hash: `products/${productId}/pipelines/${pipelineId}/webhooks` },
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
    : stages.map(s => `
      <div id="stage-block-${s.id}" class="stage-block" data-stage-name="${s.name.replace(/"/g,"&quot;")}" draggable="true"
        ondragstart="stageDragStart(event,'${s.id}')"
        ondragover="stageDragOver(event)"
        ondrop="stageDrop(event,'${s.id}','${productId}','${pipelineId}')"
        style="border:1px solid var(--gray-200);border-radius:8px;margin-bottom:10px;background:#fff">
        <div style="display:flex;align-items:center;gap:8px;padding:10px 12px;cursor:pointer;user-select:none"
          onclick="toggleStageBlock('${s.id}')">
          <span style="color:var(--gray-400);cursor:grab;font-size:16px" title="Drag to reorder">⠿</span>
          <span id="stage-arrow-${s.id}" style="font-size:12px;color:var(--gray-500);transition:transform .15s">▼</span>
          <strong style="font-size:14px;flex:1">#${s.order} ${s.name}</strong>
          <code style="font-size:11px;color:var(--gray-500)">${s.container_image || s.run_language || "—"}</code>
          ${s.is_protected ? `<span class="badge badge-blue">🔒</span>` : ""}
          <div style="display:flex;gap:4px" onclick="event.stopPropagation()">
            <button class="btn btn-secondary btn-sm" onclick="showStageYaml('${productId}','${pipelineId}','${s.id}','${s.name.replace(/'/g,"\\'")}')">YAML</button>
            <button class="btn btn-secondary btn-sm" onclick="showEditStage('${productId}','${pipelineId}','${s.id}','${s.name.replace(/'/g,"\\'")}','${s.run_language||"bash"}','${s.container_image||""}',${s.order},${s.is_protected})">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="deleteStage('${productId}','${pipelineId}','${s.id}','${s.name.replace(/'/g,"\\'")}')">Delete</button>
            <button class="btn btn-primary btn-sm" onclick="showCreateTask('${productId}','${pipelineId}','${s.id}')">+ Task</button>
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
                  <td><span class="badge badge-blue">${t.task_type}</span></td>
                  <td>${t.timeout}s</td>
                  <td>${t.is_required ? '<span class="badge badge-success">Yes</span>' : '<span class="badge badge-silver">No</span>'}</td>
                  <td style="display:flex;gap:4px;flex-wrap:wrap">
                    <button class="btn btn-secondary btn-sm" onclick="showTaskYaml('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}')">YAML</button>
                    <button class="btn btn-primary btn-sm" onclick="runTaskNow('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}')">▶</button>
                    <button class="btn btn-secondary btn-sm" onclick="showEditTaskScript('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}')">Script</button>
                    <button class="btn btn-secondary btn-sm" onclick="showEditTask('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}','${(t.description||"").replace(/'/g,"\\'")}',${t.order},'${t.on_error||"fail"}',${t.timeout},${t.is_required})">Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteTask('${productId}','${pipelineId}','${s.id}','${t.id}','${t.name.replace(/'/g,"\\'")}')">Del</button>
                  </td>
                </tr>`).join("")}
              </tbody></table>`
          }
        </div>
      </div>`).join("");

  setContent(`
    <div class="page-header">
      <div>
        <h1>${pipeline.name}</h1>
        <div class="sub">
          <span class="badge badge-${pipeline.kind}">${pipeline.kind.toUpperCase()}</span>
          ${pipeline.git_repo ? `<code style="font-size:12px;margin-left:8px">${pipeline.git_repo} @ ${pipeline.git_branch}</code>` : ""}
        </div>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
        <button class="btn btn-primary btn-sm" onclick="showCreateRun('${pipelineId}','${productId}')">▶ Run Pipeline</button>
        <button class="btn btn-secondary btn-sm" onclick="showScoreModal('${productId}','${pipelineId}','${pipeline.name}')">Score</button>
        <button class="btn btn-secondary btn-sm" onclick="showGitSyncModal('${productId}','${pipelineId}','${pipeline.git_repo||""}','${pipeline.name.replace(/'/g,"\\'")}')">⇅ Git Sync</button>
        <div style="position:relative;display:inline-block" id="yaml-dd-wrap">
          <button class="btn btn-secondary btn-sm" onclick="toggleYamlDropdown()" id="yaml-dd-btn">YAML ▾</button>
          <div id="yaml-dd-menu" style="display:none;position:absolute;right:0;top:100%;margin-top:4px;background:#fff;border:1px solid var(--gray-200);border-radius:8px;box-shadow:0 4px 16px #0002;min-width:180px;z-index:200;padding:4px 0">
            <button class="btn" style="display:block;width:100%;text-align:left;padding:8px 14px;font-size:13px;border:none;background:none;cursor:pointer"
              onclick="toggleYamlDropdown();togglePipelineMode('yaml','${productId}','${pipelineId}')">✎ Edit YAML</button>
            <button class="btn" style="display:block;width:100%;text-align:left;padding:8px 14px;font-size:13px;border:none;background:none;cursor:pointer"
              onclick="toggleYamlDropdown();exportYaml('/api/v1/products/${productId}/pipelines/${pipelineId}/export','${pipeline.name.replace(/'/g,"\\'")}pipeline.yaml')">⬇ Download YAML</button>
            <button class="btn" style="display:block;width:100%;text-align:left;padding:8px 14px;font-size:13px;border:none;background:none;cursor:pointer"
              onclick="toggleYamlDropdown();showImportYaml('${productId}','${pipelineId}')">⬆ Import YAML</button>
          </div>
        </div>
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

      <div class="grid grid-2" style="margin-bottom:16px">
        <div class="card">
          <div class="card-header"><h2>Compliance</h2></div>
          <div style="margin-bottom:10px">${ratingBadge(pipeline.compliance_rating)}</div>
          ${scoreBar(pipeline.compliance_score, pipeline.compliance_rating)}
        </div>
        <div class="card">
          <div class="card-header"><h2>Details</h2></div>
          <div class="detail-grid">
            <div class="detail-row"><span class="detail-label">ID</span><code style="font-size:12px">${pipeline.id}</code></div>
            <div class="detail-row"><span class="detail-label">Kind</span><span class="detail-value">${pipeline.kind.toUpperCase()}</span></div>
            <div class="detail-row"><span class="detail-label">Branch</span><span class="detail-value">${pipeline.git_branch||"main"}</span></div>
            <div class="detail-row"><span class="detail-label">SHA</span><span class="detail-value">${pipeline.definition_sha||"—"}</span></div>
          </div>
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
           <p style="font-size:12px;color:var(--gray-500);margin:0 0 10px">Clone repo, read <code>release-wizard/${pipelineName}.yaml</code>, apply to database.</p>
           <button class="btn btn-primary btn-sm" onclick="gitPullPipeline('${productId}','${pipelineId}')">⬇ Pull &amp; Apply</button>
           <div id="git-pull-status" style="margin-top:8px;font-size:12px"></div>
         </div>
         <div style="border:1px solid var(--gray-200);border-radius:8px;padding:14px">
           <h4 style="margin:0 0 6px">Push to Git</h4>
           <div class="form-group" style="margin-bottom:8px">
             <label style="font-size:12px">Author name</label>
             <input id="git-author-name" class="form-control" style="margin-top:4px" value="${_currentUser ? (_currentUser.display_name||_currentUser.username) : 'Release Wizard'}">
           </div>
           <div class="form-group" style="margin-bottom:10px">
             <label style="font-size:12px">Author email</label>
             <input id="git-author-email" class="form-control" style="margin-top:4px" value="${_currentUser ? (_currentUser.email||'rw@release-wizard.local') : 'rw@release-wizard.local'}">
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
          <thead><tr><th>Run ID</th><th>Status</th><th>Commit</th><th>Artifact</th><th>Triggered By</th><th>Rating</th><th>Started</th><th>Duration</th></tr></thead>
          <tbody>${runs.map(r => `
            <tr data-status="${r.status||""}" data-triggered="${r.triggered_by||""}" data-started="${r.started_at||""}">
              <td><a href="#pipeline-runs/${r.id}" onclick="navigate('pipeline-runs/${r.id}');return false;"><code style="font-size:11.5px">${r.id}</code></a></td>
              <td>${statusBadge(r.status)}</td>
              <td><code style="font-size:11.5px">${(r.commit_sha||"").slice(0,8)||"—"}</code></td>
              <td>${r.artifact_id||"—"}</td>
              <td>${r.triggered_by||"—"}</td>
              <td>${ratingBadge(r.compliance_rating)}</td>
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
      <button class="btn btn-primary btn-sm" onclick="showCreateWebhookForPipeline('${pipelineId}')">+ New Webhook</button>
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
              <td style="display:flex;gap:4px">
                <button class="btn btn-secondary btn-sm" onclick="showWebhookDeliveries('${w.id}','${w.name.replace(/'/g,"\\'")}')">Deliveries</button>
                <button class="btn btn-secondary btn-sm" onclick="toggleWebhook('${w.id}',${w.is_active})">${w.is_active?"Disable":"Enable"}</button>
                <button class="btn btn-danger btn-sm" onclick="deleteWebhookPl('${w.id}','${w.name.replace(/'/g,"\\'")}','${productId}','${pipelineId}')">Delete</button>
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
  const [product, release, runs, allPipelines] = await Promise.all([
    api.getProduct(productId),
    api.getRelease(productId, releaseId),
    api.getReleaseRuns(releaseId).catch(() => []),
    api.getPipelines(productId).catch(() => []),
  ]);
  setBreadcrumb(
    { label: "Products", hash: "products" },
    { label: product.name, hash: `products/${productId}` },
    { label: release.name }
  );
  const attachedIds = new Set((release.pipelines||[]).map(p => p.id));
  const available = allPipelines.filter(p => !attachedIds.has(p.id));

  setContent(`
    <div class="page-header">
      <div><h1>${release.name}</h1>
        <div class="sub">Version: ${release.version||"—"} · Created by ${release.created_by||"system"}</div>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-primary btn-sm" onclick="showStartReleaseRun('${releaseId}')">▶ Start Run</button>
        <button class="btn btn-secondary btn-sm" onclick="navigate('products/${productId}/releases/${releaseId}/audit')">📋 Audit Report</button>
        <button class="btn btn-secondary btn-sm" onclick="exportYaml('/api/v1/products/${productId}/releases/${releaseId}/export','${release.name.replace(/'/g,"\\'")}release.yaml')">⬇ YAML</button>
        <button class="btn btn-danger btn-sm" onclick="deleteRelease('${productId}','${releaseId}','${release.name}')">Delete</button>
      </div>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab(this,'tab-rel-pipelines')">Pipelines (${(release.pipelines||[]).length})</button>
      <button class="tab-btn" onclick="switchTab(this,'tab-rel-runs')">Runs (${runs.length})</button>
    </div>

    <div id="tab-rel-pipelines" class="tab-panel active">
      ${available.length > 0 ? `
        <div class="card" style="margin-bottom:16px;background:var(--brand-faint);border-color:var(--brand)">
          <div style="display:flex;align-items:center;gap:12px">
            <span style="font-size:13px;font-weight:500;color:var(--brand)">Attach a pipeline:</span>
            <select id="attach-pl-sel" class="form-control" style="max-width:320px">
              ${available.map(p => `<option value="${p.id}">${p.name} (${p.compliance_rating})</option>`).join("")}
            </select>
            <button class="btn btn-primary btn-sm" onclick="attachPipeline('${productId}','${releaseId}')">Attach</button>
          </div>
        </div>` : ""}
      ${(release.pipelines||[]).length === 0
        ? `<div class="empty-state"><div class="empty-icon">🔧</div><p>No pipelines attached.</p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Pipeline</th><th>Kind</th><th>Compliance</th><th>Score</th><th>Actions</th></tr></thead>
          <tbody>${(release.pipelines||[]).map(p => `
            <tr>
              <td><a href="#products/${productId}/pipelines/${p.id}">${p.name}</a></td>
              <td><span class="badge badge-${p.kind}">${p.kind.toUpperCase()}</span></td>
              <td>${ratingBadge(p.compliance_rating)}</td>
              <td>${scoreBar(p.compliance_score, p.compliance_rating)}</td>
              <td><button class="btn btn-danger btn-sm" onclick="detachPipeline('${productId}','${releaseId}','${p.id}')">Detach</button></td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>

    <div id="tab-rel-runs" class="tab-panel">
      ${runs.length === 0
        ? `<div class="empty-state"><div class="empty-icon">▶</div><p>No release runs yet.</p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Run ID</th><th>Status</th><th>Rating</th><th>Started</th><th>Finished</th><th>Actions</th></tr></thead>
          <tbody>${runs.map(r => `
            <tr>
              <td><code style="font-size:11.5px">${r.id}</code></td>
              <td>${statusBadge(r.status)}</td>
              <td>${ratingBadge(r.compliance_rating)}</td>
              <td style="color:var(--gray-400)">${fmtDate(r.started_at)}</td>
              <td style="color:var(--gray-400)">${fmtDate(r.finished_at)}</td>
              <td>
                ${r.status==="Pending"||r.status==="InProgress"
                  ? `<button class="btn btn-secondary btn-sm" onclick="completeReleaseRun('${r.id}','${productId}','${releaseId}')">Update</button>`
                  : ""}
              </td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>
  `);
});

async function attachPipeline(productId, releaseId) {
  const pipelineId = el("attach-pl-sel")?.value;
  if (!pipelineId) return;
  try {
    await api.attachPipeline(productId, releaseId, { pipeline_id: pipelineId, requested_by: "user" });
    toast("Pipeline attached", "success");
    navigate(`products/${productId}/releases/${releaseId}`);
  } catch (e) {
    const detail = e.data?.violations ? "\n• " + e.data.violations.join("\n• ") : "";
    toast(e.message + detail, "error");
  }
}

async function detachPipeline(productId, releaseId, pipelineId) {
  try {
    await api.detachPipeline(productId, releaseId, pipelineId);
    toast("Pipeline detached", "success");
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
      <div><h1>Compliance</h1><div class="sub">Release admission rules and audit events</div></div>
      <button class="btn btn-primary" onclick="showCreateRule()">+ New Rule</button>
    </div>

    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><h2>Release Admission Rules</h2></div>
      ${rules.length === 0
        ? `<div class="empty-state"><div class="empty-icon">🛡</div><p>No rules defined. Pipelines can be attached to any release.</p></div>`
        : `<div class="table-wrap"><table>
          <thead><tr><th>Description</th><th>Scope</th><th>Min Rating</th><th>Actions</th></tr></thead>
          <tbody>${rules.map(r => `
            <tr>
              <td>${r.description||"—"}</td>
              <td><code style="font-size:12px">${r.scope}</code></td>
              <td>${ratingBadge(r.min_rating)}</td>
              <td><button class="btn btn-danger btn-sm" onclick="deleteRule('${r.id}')">Disable</button></td>
            </tr>`).join("")}
          </tbody></table></div>`
      }
    </div>

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
  `);
});

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
    navigate("compliance");
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

function showCreateWebhook() {
  openModal("New Webhook",
    `<div class="form-group"><label>Name *</label>
       <input id="wh-name" class="form-control" placeholder="e.g. GitHub Push Trigger"></div>
     <div class="form-group"><label>Pipeline ID *</label>
       <input id="wh-pipeline" class="form-control" placeholder="pipeline ID"></div>
     <div class="form-group"><label>Description</label>
       <input id="wh-desc" class="form-control" placeholder="When is this triggered?"></div>`,
    async () => {
      const name = el("wh-name").value.trim();
      const pipelineId = el("wh-pipeline").value.trim();
      if (!name || !pipelineId) throw new Error("Name and Pipeline ID are required");
      const result = await api.createWebhook({
        name, pipeline_id: pipelineId,
        description: el("wh-desc").value.trim(),
      });
      closeModal();
      openModal("Webhook Created — Save Your Token",
        `<p style="margin-bottom:12px;color:var(--gray-600)">This token will not be shown again. Copy it now.</p>
         <input class="form-control" value="${result.token}" readonly style="font-family:monospace;font-size:13px">`,
        () => { closeModal(); navigate("webhooks"); }, "Done"
      );
    },
    "Create"
  );
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

router.register("admin", async (hash, parts) => {
  const tab = parts[1] || "users";
  setBreadcrumb({ label: "Administration" });
  setContent(loading());

  const [users, groups, roles] = await Promise.all([
    api.getUsers().catch(() => []),
    api.getGroups().catch(() => []),
    api.getRoles().catch(() => []),
  ]);

  const tabs = [
    { id: "users",  label: `Users (${users.length})` },
    { id: "groups", label: `Groups (${groups.length})` },
    { id: "roles",  label: `Roles (${roles.length})` },
    { id: "ldap",   label: "LDAP" },
  ];

  const tabBar = `<div class="tab-bar">
    ${tabs.map(t => `<button class="tab-btn${tab === t.id ? " active" : ""}"
      onclick="navigate('admin/${t.id}')">${t.label}</button>`).join("")}
  </div>`;

  let panelHtml = "";

  if (tab === "users") {
    panelHtml = `
      <div class="page-header">
        <div><h1>Users</h1><div class="sub">Manage platform users and their personas</div></div>
        <button class="btn btn-primary" onclick="showCreateUser()">+ New User</button>
      </div>
      ${tabBar}
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
            </tbody></table></div></div>`
      }`;
  } else if (tab === "groups") {
    panelHtml = `
      <div class="page-header">
        <div><h1>Groups</h1><div class="sub">Organise users into teams for bulk access control</div></div>
        <button class="btn btn-primary" onclick="showCreateGroup()">+ New Group</button>
      </div>
      ${tabBar}
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
          </div>`
      }`;
  } else if (tab === "roles") {
    panelHtml = `
      <div class="page-header">
        <div><h1>Roles</h1><div class="sub">Permission bundles assigned to users and groups</div></div>
        <button class="btn btn-primary" onclick="showCreateRole()">+ New Role</button>
      </div>
      ${tabBar}
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
            </tbody></table></div></div>`
      }`;
  } else if (tab === "ldap") {
    panelHtml = `
      <div class="page-header">
        <div><h1>LDAP / Active Directory</h1><div class="sub">Configure directory integration for single sign-on</div></div>
      </div>
      ${tabBar}
      <div class="card">
        <div class="card-header"><h2>Connection Settings</h2></div>
        <div style="color:var(--gray-500);font-size:13px;margin-bottom:16px">
          These settings are read from environment variables at startup.
          To change them update your ConfigMap / environment and restart the pod.
        </div>
        <div class="detail-grid" style="margin-bottom:20px">
          <div class="detail-row"><span class="detail-label">LDAP_URL</span><code id="ldap-url-display" style="font-size:12px">Loading…</code></div>
          <div class="detail-row"><span class="detail-label">LDAP_BIND_DN</span><code id="ldap-bind-dn-display" style="font-size:12px">Loading…</code></div>
          <div class="detail-row"><span class="detail-label">LDAP_BASE_DN</span><code id="ldap-base-dn-display" style="font-size:12px">Loading…</code></div>
          <div class="detail-row"><span class="detail-label">LDAP_USER_SEARCH_BASE</span><code id="ldap-search-base-display" style="font-size:12px">Loading…</code></div>
        </div>
        <div class="card-header" style="margin-top:16px"><h2>Test Connection</h2></div>
        <div style="color:var(--gray-500);font-size:13px;margin-bottom:12px">
          Optionally provide credentials to test a full user bind, or leave blank to test service-account connectivity only.
        </div>
        <div class="grid grid-2" style="gap:12px;margin-bottom:12px">
          <div class="form-group"><label>Username (optional)</label><input id="ldap-test-user" class="form-control" placeholder="e.g. jdoe"></div>
          <div class="form-group"><label>Password (optional)</label><input id="ldap-test-pass" class="form-control" type="password" placeholder="••••••••"></div>
        </div>
        <button class="btn btn-primary" onclick="testLdapConnection()">Test Connection</button>
        <div id="ldap-test-result" style="margin-top:12px;font-size:13px"></div>
      </div>`;
  }

  setContent(panelHtml);
  if (tab === "ldap") loadLdapConfig();
});

router.register("admin/users", (hash, parts) => router.navigate("admin/users", false) || router.routes["admin"](hash, ["admin","users"]));
router.register("admin/groups", (hash, parts) => router.routes["admin"](hash, ["admin","groups"]));
router.register("admin/roles", (hash, parts) => router.routes["admin"](hash, ["admin","roles"]));
router.register("admin/ldap",  (hash, parts) => router.routes["admin"](hash, ["admin","ldap"]));

// user detail page
router.register("admin/users/:id", async (hash, parts) => {
  const userId = parts[2];
  setBreadcrumb({ label: "Administration", hash: "admin" }, { label: "User" });
  setContent(loading());

  const [user, bindings, roles] = await Promise.all([
    api.getUser(userId).catch(() => null),
    api.getUserBindings(userId).catch(() => []),
    api.getRoles().catch(() => []),
  ]);

  if (!user) { setContent(`<div class="card"><div class="empty-state"><p>User not found.</p></div></div>`); return; }

  const roleMap = Object.fromEntries(roles.map(r => [r.id, r.name]));

  setBreadcrumb(
    { label: "Administration", hash: "admin" },
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

function showEditTask(productId, pipelineId, stageId, taskId, name, desc, order, taskType, timeout, isRequired) {
  openModal("Edit Task",
    `<div class="form-group"><label>Name *</label><input id="et-name" class="form-control" value="${name}"></div>
     <div class="form-group"><label>Description</label><input id="et-desc" class="form-control" value="${desc}"></div>
     <div class="form-group"><label>On Error</label>
       <select id="et-err" class="form-control">
         <option value="fail"${taskType==="fail"?" selected":""}>Fail stage</option>
         <option value="warn"${taskType==="warn"?" selected":""}>Warn (continue with warning)</option>
         <option value="continue"${taskType==="continue"?" selected":""}>Continue (ignore error)</option>
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
         <strong style="font-size:11px;color:var(--gray-700)">Available context variables ($RW_* / os.environ)</strong>
         <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px">
           ${["RW_PIPELINE_RUN_ID","RW_PIPELINE_ID","RW_PIPELINE_NAME","RW_COMMIT_SHA","RW_ARTIFACT_ID","RW_TRIGGERED_BY","RW_GIT_REPO","RW_GIT_BRANCH","RW_STAGE_RUN_ID","RW_STAGE_ID","RW_STAGE_NAME","RW_TASK_RUN_ID","RW_TASK_ID","RW_TASK_NAME"].map(v =>
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
     </div>`,
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
        });
        closeModal(); toast("Stage created", "success");
        navigate(`products/${productId}/pipelines/${pipelineId}`);
      } catch (e) { modalError(e.message); }
    }
  );
}

function showEditStage(productId, pipelineId, stageId, name, runLang, containerImg, order, isProtected) {
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
     </div>`,
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

  // Layout constants
  const STAGE_W = 180;
  const TASK_H = 36;
  const TASK_PAD = 8;
  const STAGE_HEAD = 40;
  const STAGE_PAD_X = 20;
  const COL_GAP = 60;
  const ROW_TOP = 20;
  const CORNER = 6;
  const ARROW_W = 12;
  const COLORS = {
    stageHead: "#1e3a5f",
    stageFill: "#f0f4fa",
    stageBorder: "#c4d4e8",
    taskFill: "#ffffff",
    taskBorder: "#d1dff0",
    taskText: "#1e293b",
    taskType: "#64748b",
    arrowStroke: "#94a3b8",
    connectorLine: "#cbd5e1",
  };

  // Compute column positions
  const sorted = [...stages].sort((a, b) => a.order - b.order);
  let cols = []; // {x, stage, stageH}
  let x = STAGE_PAD_X;
  for (const stage of sorted) {
    const tasks = stage.tasks || [];
    const stageH = STAGE_HEAD + tasks.length * (TASK_H + TASK_PAD) + TASK_PAD;
    cols.push({ x, stage, stageH });
    x += STAGE_W + COL_GAP;
  }

  const totalW = x - COL_GAP + STAGE_PAD_X;
  const totalH = Math.max(...cols.map(c => c.stageH)) + ROW_TOP * 2;

  let el_arr = [];

  // Draw connector lines first (behind boxes)
  for (let i = 0; i < cols.length - 1; i++) {
    const cur = cols[i];
    const nxt = cols[i + 1];
    const cy = ROW_TOP + cur.stageH / 2;
    const x1 = cur.x + STAGE_W;
    const x2 = nxt.x;
    const mx = (x1 + x2) / 2;
    el_arr.push(`<path d="M${x1},${cy} C${mx},${cy} ${mx},${cy} ${x2},${cy}" stroke="${COLORS.arrowStroke}" stroke-width="2" fill="none" marker-end="url(#arrowhead-${pipelineId})"/>`);
  }

  // Draw stage boxes
  for (const { x: sx, stage, stageH } of cols) {
    const sy = ROW_TOP;
    // Stage card shadow
    el_arr.push(`<rect x="${sx+2}" y="${sy+2}" width="${STAGE_W}" height="${stageH}" rx="${CORNER}" fill="#00000015"/>`);
    // Stage card body
    el_arr.push(`<rect x="${sx}" y="${sy}" width="${STAGE_W}" height="${stageH}" rx="${CORNER}" fill="${COLORS.stageFill}" stroke="${COLORS.stageBorder}" stroke-width="1.5"/>`);
    // Clickable stage header — scrolls to stage-block in editor
    el_arr.push(`<g style="cursor:pointer" onclick="visualScrollToStage('${stage.id}')" title="Go to stage editor">`);
    el_arr.push(`<rect x="${sx}" y="${sy}" width="${STAGE_W}" height="${STAGE_HEAD}" rx="${CORNER}" fill="${COLORS.stageHead}"/>`);
    el_arr.push(`<rect x="${sx}" y="${sy+CORNER}" width="${STAGE_W}" height="${STAGE_HEAD - CORNER}" fill="${COLORS.stageHead}"/>`);
    const stageName = stage.name.length > 18 ? stage.name.slice(0, 16) + "…" : stage.name;
    el_arr.push(`<text x="${sx + STAGE_W/2}" y="${sy + 16}" text-anchor="middle" font-size="12" font-weight="700" fill="#ffffff" font-family="system-ui,sans-serif">#${stage.order} ${stageName}</text>`);
    const lang = stage.run_language || stage.container_image || "bash";
    el_arr.push(`<text x="${sx + STAGE_W/2}" y="${sy + 30}" text-anchor="middle" font-size="10" fill="#a8c4e8" font-family="system-ui,sans-serif">${lang.toUpperCase()}</text>`);
    el_arr.push(`</g>`);

    // Task rows
    const tasks = (stage.tasks || []).sort((a, b) => a.order - b.order);
    let ty = sy + STAGE_HEAD + TASK_PAD;
    for (const task of tasks) {
      // Clickable task row — scrolls to task row and opens script editor
      el_arr.push(`<g style="cursor:pointer" onclick="visualScrollToTask('${task.id}','${stage.id}')" title="Go to task editor">`);
      el_arr.push(`<rect x="${sx+TASK_PAD}" y="${ty}" width="${STAGE_W - TASK_PAD*2}" height="${TASK_H}" rx="4" fill="${COLORS.taskFill}" stroke="${COLORS.taskBorder}" stroke-width="1"/>`);
      el_arr.push(`<circle cx="${sx+TASK_PAD+10}" cy="${ty+TASK_H/2}" r="8" fill="#e2ebf6"/>`);
      el_arr.push(`<text x="${sx+TASK_PAD+10}" y="${ty+TASK_H/2+4}" text-anchor="middle" font-size="10" font-weight="700" fill="#1e3a5f" font-family="system-ui,sans-serif">${task.order}</text>`);
      const tName = task.name.length > 18 ? task.name.slice(0, 16) + "…" : task.name;
      el_arr.push(`<text x="${sx+TASK_PAD+24}" y="${ty+14}" font-size="11" font-weight="600" fill="${COLORS.taskText}" font-family="system-ui,sans-serif">${tName}</text>`);
      const tLang = task.run_language || "bash";
      const tErr = task.on_error === "fail" ? "● fail" : "● warn";
      const tErrColor = task.on_error === "fail" ? "#ef4444" : "#f59e0b";
      el_arr.push(`<text x="${sx+TASK_PAD+24}" y="${ty+26}" font-size="10" fill="${COLORS.taskType}" font-family="system-ui,sans-serif">${tLang}</text>`);
      el_arr.push(`<text x="${sx+STAGE_W-TASK_PAD-4}" y="${ty+26}" text-anchor="end" font-size="10" fill="${tErrColor}" font-family="system-ui,sans-serif">${tErr}</text>`);
      el_arr.push(`</g>`);
      ty += TASK_H + TASK_PAD;
    }

    if (tasks.length === 0) {
      el_arr.push(`<text x="${sx + STAGE_W/2}" y="${sy + STAGE_HEAD + 24}" text-anchor="middle" font-size="12" fill="#94a3b8" font-family="system-ui,sans-serif">No tasks</text>`);
    }
  }

  svg.innerHTML = `
    <defs>
      <marker id="arrowhead-${pipelineId}" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
        <polygon points="0 0, 10 3.5, 0 7" fill="${COLORS.arrowStroke}"/>
      </marker>
    </defs>
    ${el_arr.join("\n")}
  `;
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
  const authorName = (document.getElementById("git-author-name")||{}).value || "Release Wizard";
  const authorEmail = (document.getElementById("git-author-email")||{}).value || "rw@release-wizard.local";
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

function _renderPipelineRun(run, productId, pipelineId) {
  const stageRuns = (run.stage_runs || []).sort((a, b) => (a.stage_order || 0) - (b.stage_order || 0));

  // ── Visual flow graph ─────────────────────────────────────────────────
  const STAGE_W = 200;
  const COL_GAP = 50;
  const HEAD_H = 48;
  const TASK_H = 28;
  const TASK_PAD = 5;
  const PAD_X = 16;
  const PAD_Y = 16;
  const CORNER = 8;

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
  // Defs
  svgEls.push(`<defs>
    ${Object.entries({Succeeded:"#22c55e",Failed:"#ef4444",Running:"#3b82f6",Warning:"#f59e0b",Cancelled:"#94a3b8",Pending:"#e2e8f0"}).map(([s,c]) =>
      `<linearGradient id="rg-${s}" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="${c}33"/><stop offset="100%" stop-color="${c}11"/></linearGradient>`
    ).join("")}
    <marker id="run-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#cbd5e1"/>
    </marker>
  </defs>`);

  // Connector arrows
  for (let i = 0; i < svgCols.length - 1; i++) {
    const { x: ax, colH: ah } = svgCols[i];
    const { x: bx } = svgCols[i + 1];
    const cy2 = PAD_Y + ah / 2;
    const x1 = ax + STAGE_W, x2 = bx;
    const mx = (x1 + x2) / 2;
    svgEls.push(`<path d="M${x1},${cy2} C${mx},${cy2} ${mx},${cy2} ${x2},${cy2}" stroke="#cbd5e1" stroke-width="2" fill="none" marker-end="url(#run-arrow)"/>`);
  }

  // Stage columns
  for (const { sr, tasks, x: sx, colH } of svgCols) {
    const sy = PAD_Y;
    const sc = _statusColor(sr.status);
    // Card shadow
    svgEls.push(`<rect x="${sx+2}" y="${sy+2}" width="${STAGE_W}" height="${colH}" rx="${CORNER}" fill="#00000012"/>`);
    // Card fill
    svgEls.push(`<rect x="${sx}" y="${sy}" width="${STAGE_W}" height="${colH}" rx="${CORNER}" fill="url(#rg-${sr.status})" stroke="${sc}" stroke-width="2"/>`);
    // Header bar
    svgEls.push(`<rect x="${sx}" y="${sy}" width="${STAGE_W}" height="${HEAD_H}" rx="${CORNER}" fill="${sc}"/>`);
    svgEls.push(`<rect x="${sx}" y="${sy+CORNER}" width="${STAGE_W}" height="${HEAD_H-CORNER}" fill="${sc}"/>`);
    // Stage name
    const sName = (sr.stage_name || sr.stage_id || "Stage").slice(0, 20);
    svgEls.push(`<text x="${sx+STAGE_W/2}" y="${sy+19}" text-anchor="middle" font-size="12" font-weight="700" fill="#fff" font-family="system-ui,sans-serif">${sName}</text>`);
    // Status + duration
    const dur = fmtDuration(sr.started_at, sr.finished_at);
    svgEls.push(`<text x="${sx+STAGE_W/2}" y="${sy+35}" text-anchor="middle" font-size="10" fill="#ffffffcc" font-family="system-ui,sans-serif">${_statusIcon(sr.status)} ${sr.status} ${dur ? "· "+dur : ""}</text>`);
    // Clickable stage header
    svgEls.push(`<rect x="${sx}" y="${sy}" width="${STAGE_W}" height="${HEAD_H}" rx="${CORNER}" fill="transparent" style="cursor:pointer" onclick="document.getElementById('sr-${sr.id}')?.scrollIntoView({behavior:'smooth'})"/>`);

    // Task rows
    let ty = sy + HEAD_H + TASK_PAD;
    for (const tr of tasks) {
      const tc = _statusColor(tr.status);
      const tName = (tr.task_name || tr.task_id || "Task").slice(0, 22);
      // Task bg
      svgEls.push(`<rect x="${sx+6}" y="${ty}" width="${STAGE_W-12}" height="${TASK_H}" rx="4" fill="#ffffff" stroke="${tc}" stroke-width="1.5"/>`);
      // Status bar on left
      svgEls.push(`<rect x="${sx+6}" y="${ty}" width="4" height="${TASK_H}" rx="4" fill="${tc}"/>`);
      // Task name
      svgEls.push(`<text x="${sx+16}" y="${ty+11}" font-size="10" font-weight="600" fill="#1e293b" font-family="system-ui,sans-serif">${tName}</text>`);
      // Duration
      const tdur = fmtDuration(tr.started_at, tr.finished_at);
      svgEls.push(`<text x="${sx+16}" y="${ty+22}" font-size="9" fill="#64748b" font-family="system-ui,sans-serif">${_statusIcon(tr.status)} ${tr.status}${tdur ? " · "+tdur : ""}</text>`);
      // Clickable task row
      svgEls.push(`<rect x="${sx+6}" y="${ty}" width="${STAGE_W-12}" height="${TASK_H}" rx="4" fill="transparent" style="cursor:pointer" onclick="toggleLog('log-${tr.id}')"/>`);
      ty += TASK_H + TASK_PAD;
    }
    if (!tasks.length) {
      svgEls.push(`<text x="${sx+STAGE_W/2}" y="${sy+HEAD_H+24}" text-anchor="middle" font-size="11" fill="#94a3b8" font-family="system-ui,sans-serif">No tasks</text>`);
    }
  }

  const flowSvg = stageRuns.length
    ? `<svg width="${totalW}" height="${totalH}" style="display:block">${svgEls.join("")}</svg>`
    : `<p style="color:var(--gray-400);padding:16px">No stages to display.</p>`;

  // ── Runtime properties panel helper ──────────────────────────────────
  function _propsPanel(id, props) {
    const isEmpty = !props || Object.keys(props).length === 0;
    const json = isEmpty ? "{}" : JSON.stringify(props, null, 2);
    return `<button class="btn btn-secondary btn-sm" style="font-size:11px;padding:2px 8px" onclick="toggleLog('rtprop-${id}')">{ } Properties</button>
      <div id="rtprop-${id}" class="task-log-block">
        <pre style="background:var(--gray-50);border:1px solid var(--gray-200);border-radius:6px;padding:8px;font-size:12px;margin:6px 0 0;max-height:180px;overflow:auto">${json}</pre>
      </div>`;
  }

  // ── Stage detail cards ────────────────────────────────────────────────
  const stageDetails = stageRuns.map(sr => {
    const srProps = sr.runtime_properties || {};
    const taskRows = (sr.task_runs || []).map(tr => {
      const tc = _statusColor(tr.status);
      let outProps = {};
      if (tr.output_json) { try { outProps = JSON.parse(tr.output_json); } catch {} }
      return `
        <div class="task-run-row" style="border-left:3px solid ${tc}">
          <div style="display:flex;align-items:center;gap:8px;flex:1;flex-wrap:wrap">
            <span class="task-run-name">${tr.task_name || tr.task_id}</span>
            ${statusBadge(tr.status)}
            <span class="task-run-duration">${fmtDuration(tr.started_at, tr.finished_at)}</span>
            ${tr.return_code !== null && tr.return_code !== undefined
              ? `<code style="font-size:11px;color:var(--gray-400)">exit ${tr.return_code}</code>`
              : ""}
            ${_propsPanel(tr.id + "-out", outProps)}
            <button class="task-log-toggle" onclick="toggleLog('log-${tr.id}')">Logs</button>
          </div>
          <div id="log-${tr.id}" class="task-log-block">
            <div class="log-viewer"><pre style="margin:0;white-space:pre-wrap;font-size:12px">${tr.logs ? tr.logs.replace(/</g,"&lt;").replace(/>/g,"&gt;") : "(no logs)"}</pre></div>
          </div>
        </div>`;
    }).join("");

    const headerBg = { Succeeded: "#f0fdf4", Failed: "#fef2f2", Running: "#eff6ff", Warning: "#fffbeb", Cancelled: "#f8fafc" }[sr.status] || "var(--gray-50)";
    const borderColor = _statusColor(sr.status);
    return `
      <div id="sr-${sr.id}" class="card" style="margin-bottom:14px;border-left:4px solid ${borderColor}">
        <div class="card-header" style="background:${headerBg}">
          <h3 style="margin:0;font-size:15px">${_statusIcon(sr.status)} ${sr.stage_name || sr.stage_id}</h3>
          <div style="display:flex;align-items:center;gap:10px">
            ${statusBadge(sr.status)}
            <span style="font-size:12px;color:var(--gray-400)">${fmtDuration(sr.started_at, sr.finished_at)}</span>
            ${_propsPanel(sr.id + "-rt", srProps)}
          </div>
        </div>
        ${(sr.task_runs||[]).length === 0
          ? `<div style="padding:14px;color:var(--gray-400);font-size:13px">No tasks.</div>`
          : taskRows}
      </div>`;
  }).join("");

  const runColor = _statusColor(run.status);
  const ctxTabs = productId && pipelineId ? pipelineContextTabs(productId, pipelineId, "runs") : "";
  const pipelineProps = run.runtime_properties || {};

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
        ${_propsPanel(run.id + "-rt", pipelineProps)}
      </div>
    </div>

    ${ctxTabs}

    <!-- Overall progress bar -->
    <div style="height:6px;border-radius:3px;background:var(--gray-200);margin-bottom:16px;overflow:hidden">
      <div style="height:100%;border-radius:3px;background:${runColor};transition:width .4s;width:${
        run.status==="Succeeded"||run.status==="Warning"||run.status==="Failed" ? "100" :
        stageRuns.length ? Math.round(stageRuns.filter(s=>TERMINAL.has(s.status)).length/stageRuns.length*100) : 0
      }%"></div>
    </div>

    <!-- Visual flow -->
    <div class="card" style="margin-bottom:16px;overflow-x:auto">
      <div style="padding:8px 16px 4px">
        <div style="font-size:11px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:.06em">Pipeline Flow — click a stage or task to jump to details</div>
      </div>
      <div style="padding:8px 8px 12px;min-height:80px">${flowSvg}</div>
    </div>

    ${stageDetails || `<div class="card"><div class="empty-state"><div class="empty-icon">📋</div><p>No stages in this pipeline.</p></div></div>`}
  `;
}

function toggleLog(id) {
  const el2 = document.getElementById(id);
  if (el2) el2.classList.toggle("open");
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

    setBreadcrumb({ label: "Products", hash: "products" }, { label: "Pipeline Run" });
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
              <td style="display:flex;gap:4px">
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

// ── Docs page ──────────────────────────────────────────────────────────────
router.register("docs", () => {
  setBreadcrumb({ label: "Documentation" });
  setContent(`
    <div class="page-header">
      <div><h1>Documentation</h1><div class="sub">Release Wizard — usage guide and API reference</div></div>
      <a class="btn btn-primary btn-sm" href="/api/v1/docs/swagger" target="_blank">Open Swagger UI</a>
    </div>
    <div class="grid grid-2" style="margin-bottom:20px">
      <div class="card">
        <div class="card-header"><h2>Quick Start</h2></div>
        <ol style="padding-left:18px;line-height:2">
          <li>Create a <strong>Product</strong> — a top-level grouping.</li>
          <li>Define <strong>Environments</strong> (dev, qa, prod) and attach to products.</li>
          <li>Create <strong>Pipelines</strong> with <strong>Stages</strong> and <strong>Tasks</strong>.</li>
          <li>Create a <strong>Release</strong> and attach pipelines to it.</li>
          <li>Run the release — pipelines execute in agent sandboxes.</li>
        </ol>
      </div>
      <div class="card">
        <div class="card-header"><h2>Key Concepts</h2></div>
        <div class="detail-grid">
          <div class="detail-row"><span class="detail-label">Product</span><span class="detail-value">Top-level grouping for releases, pipelines, and apps</span></div>
          <div class="detail-row"><span class="detail-label">Environment</span><span class="detail-value">A deployment target (dev/qa/prod) shared across products</span></div>
          <div class="detail-row"><span class="detail-label">Pipeline</span><span class="detail-value">An ordered set of stages (CI or CD)</span></div>
          <div class="detail-row"><span class="detail-label">Stage</span><span class="detail-value">A group of tasks that run in a shared context</span></div>
          <div class="detail-row"><span class="detail-label">Task</span><span class="detail-value">A bash or python script sandboxed in an agent pod</span></div>
          <div class="detail-row"><span class="detail-label">Agent Pool</span><span class="detail-value">Sandboxed execution environment for task containers</span></div>
          <div class="detail-row"><span class="detail-label">Release</span><span class="detail-value">A versioned collection of pipelines ready to deploy</span></div>
          <div class="detail-row"><span class="detail-label">Compliance</span><span class="detail-value">Admission rules that gate pipeline attachment to releases</span></div>
        </div>
      </div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><h2>Task Script Contract</h2></div>
      <div style="padding:0 16px 16px">
        <p style="color:var(--gray-600);font-size:13px;margin-bottom:12px">Tasks run as non-root containers in an isolated sandbox. The following conventions apply:</p>
        <div class="grid grid-2">
          <div>
            <strong style="font-size:13px">Exit codes</strong>
            <table style="margin-top:8px;font-size:13px"><tbody>
              <tr><td style="padding:3px 12px 3px 0;color:var(--gray-500)">0</td><td>Succeeded</td></tr>
              <tr><td style="padding:3px 12px 3px 0;color:var(--gray-500)">1</td><td>Warning (if on_error=warn)</td></tr>
              <tr><td style="padding:3px 12px 3px 0;color:var(--gray-500)">2+</td><td>Failed</td></tr>
            </tbody></table>
          </div>
          <div>
            <strong style="font-size:13px">JSON output</strong>
            <p style="color:var(--gray-600);font-size:13px;margin-top:8px">Print a JSON object as the <strong>last line</strong> of stdout. It will be captured as the task's output and available to downstream tasks via <code>TASK_OUTPUT_&lt;TASK_ID&gt;</code>.</p>
          </div>
        </div>
        <div style="margin-top:16px">
          <strong style="font-size:13px">Example Bash task with output:</strong>
          <pre style="background:var(--gray-100);padding:12px;border-radius:6px;font-size:12px;margin-top:8px;overflow-x:auto">#!/bin/bash
VERSION=$(git rev-parse --short HEAD)
echo "Building version: $VERSION"
# ... build steps ...
echo '{"version":"'"$VERSION"'","artifact":"api:'"$VERSION"'"}'</pre>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-header"><h2>API Reference</h2></div>
      <p style="padding:0 16px;color:var(--gray-600);font-size:13px">Full interactive API documentation is available in the Swagger UI.</p>
      <div class="table-wrap" style="padding:0 16px 16px"><table>
        <thead><tr><th>Resource</th><th>Base Path</th><th>Methods</th></tr></thead>
        <tbody>
          ${[
            ["Products","/api/v1/products","GET POST PUT DELETE"],
            ["Environments","/api/v1/environments","GET POST PUT DELETE"],
            ["Pipelines","/api/v1/products/:id/pipelines","GET POST PUT DELETE"],
            ["Stages","/api/v1/products/:id/pipelines/:id/stages","GET POST PUT DELETE"],
            ["Tasks","/api/v1/products/:id/pipelines/:id/stages/:id/tasks","GET POST PUT DELETE"],
            ["Releases","/api/v1/products/:id/releases","GET POST PUT DELETE"],
            ["Runs","/api/v1/pipeline-runs · /api/v1/release-runs","GET POST PUT"],
            ["Agent Pools","/api/v1/agent-pools","GET POST DELETE"],
            ["Compliance","/api/v1/compliance/rules","GET POST DELETE"],
            ["Users","/api/v1/users","GET POST PATCH DELETE"],
            ["Groups","/api/v1/groups","GET POST PATCH DELETE"],
            ["Roles","/api/v1/roles","GET POST PATCH DELETE"],
          ].map(([r,p,m]) => `<tr><td><strong>${r}</strong></td><td><code style="font-size:12px">${p}</code></td><td style="color:var(--gray-500);font-size:12px">${m}</td></tr>`).join("")}
        </tbody>
      </table></div>
    </div>
  `);
});

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
