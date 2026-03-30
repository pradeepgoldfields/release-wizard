/* API client — thin wrapper over fetch */

const BASE = "/api/v1";

// ── JWT token storage ────────────────────────────────────────────────────────
const auth = {
  getToken: () => localStorage.getItem("rw_token"),
  setToken: (t) => localStorage.setItem("rw_token", t),
  clearToken: () => localStorage.removeItem("rw_token"),
  isLoggedIn: () => !!localStorage.getItem("rw_token"),
};

async function request(method, path, body) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  const token = auth.getToken();
  if (token) opts.headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(BASE + path, opts);
  if (res.status === 204) return null;
  if (res.status === 401) {
    // Token expired or invalid — force re-login
    auth.clearToken();
    if (typeof showLoginPage === "function") showLoginPage();
    throw Object.assign(new Error("Session expired"), { code: "UNAUTHENTICATED" });
  }
  const json = await res.json();
  if (!res.ok) throw Object.assign(new Error(json.error || "Request failed"), { data: json });
  return json;
}

const api = {
  // Auth
  login: (data) => request("POST", "/auth/login", data),
  logout: () => request("POST", "/auth/logout"),
  me: () => request("GET", "/auth/me"),
  changePassword: (userId, data) => request("PATCH", `/users/${userId}/password`, data),

  // Products
  getProducts: () => request("GET", "/products"),
  createProduct: (data) => request("POST", "/products", data),
  getProduct: (id) => request("GET", `/products/${id}`),
  updateProduct: (id, data) => request("PUT", `/products/${id}`, data),
  deleteProduct: (id) => request("DELETE", `/products/${id}`),

  // Environments (top-level)
  getEnvironments: () => request("GET", "/environments"),
  createEnvironment: (data) => request("POST", "/environments", data),
  getEnvironment: (id) => request("GET", `/environments/${id}`),
  updateEnvironment: (id, data) => request("PUT", `/environments/${id}`, data),
  deleteEnvironment: (id) => request("DELETE", `/environments/${id}`),

  // Product ↔ Environment attachment
  getProductEnvironments: (pid) => request("GET", `/products/${pid}/environments`),
  attachEnvironment: (pid, data) => request("POST", `/products/${pid}/environments`, data),
  detachEnvironment: (pid, eid) => request("DELETE", `/products/${pid}/environments/${eid}`),

  // Applications
  getApplications: (pid) => request("GET", `/products/${pid}/applications`),
  createApplication: (pid, data) => request("POST", `/products/${pid}/applications`, data),
  updateApplication: (pid, aid, data) => request("PUT", `/products/${pid}/applications/${aid}`, data),
  deleteApplication: (pid, aid) => request("DELETE", `/products/${pid}/applications/${aid}`),

  // Pipelines
  getPipelines: (pid) => request("GET", `/products/${pid}/pipelines`),
  createPipeline: (pid, data) => request("POST", `/products/${pid}/pipelines`, data),
  getPipeline: (pid, plid) => request("GET", `/products/${pid}/pipelines/${plid}`),
  updatePipeline: (pid, plid, data) => request("PUT", `/products/${pid}/pipelines/${plid}`, data),
  deletePipeline: (pid, plid) => request("DELETE", `/products/${pid}/pipelines/${plid}`),
  updateCompliance: (pid, plid, data) => request("POST", `/products/${pid}/pipelines/${plid}/compliance`, data),

  // Stages
  createStage: (pid, plid, data) => request("POST", `/products/${pid}/pipelines/${plid}/stages`, data),
  updateStage: (pid, plid, sid, data) => request("PUT", `/products/${pid}/pipelines/${plid}/stages/${sid}`, data),
  deleteStage: (pid, plid, sid) => request("DELETE", `/products/${pid}/pipelines/${plid}/stages/${sid}`),

  // Stage Tasks
  getTasks: (pid, plid, sid) => request("GET", `/products/${pid}/pipelines/${plid}/stages/${sid}/tasks`),
  createTask: (pid, plid, sid, data) => request("POST", `/products/${pid}/pipelines/${plid}/stages/${sid}/tasks`, data),
  getTask: (pid, plid, sid, tid) => request("GET", `/products/${pid}/pipelines/${plid}/stages/${sid}/tasks/${tid}`),
  updateTask: (pid, plid, sid, tid, data) => request("PUT", `/products/${pid}/pipelines/${plid}/stages/${sid}/tasks/${tid}`, data),
  deleteTask: (pid, plid, sid, tid) => request("DELETE", `/products/${pid}/pipelines/${plid}/stages/${sid}/tasks/${tid}`),
  runTask: (pid, plid, sid, tid, data) => request("POST", `/products/${pid}/pipelines/${plid}/stages/${sid}/tasks/${tid}/run`, data),
  listTaskRuns: (pid, plid, sid, tid) => request("GET", `/products/${pid}/pipelines/${plid}/stages/${sid}/tasks/${tid}/runs`),
  getTaskRun: (runId) => request("GET", `/task-runs/${runId}`),

  // Agent Pools
  getAgentPools: () => request("GET", "/agent-pools"),
  createAgentPool: (data) => request("POST", "/agent-pools", data),
  deleteAgentPool: (id) => request("DELETE", `/agent-pools/${id}`),

  // Pipeline runs
  getPipelineRuns: (plid) => request("GET", `/pipelines/${plid}/runs`),
  createPipelineRun: (plid, data) => request("POST", `/pipelines/${plid}/runs`, data),
  getPipelineRun: (id) => request("GET", `/pipeline-runs/${id}`),
  updatePipelineRun: (id, data) => request("PATCH", `/pipeline-runs/${id}`, data),

  // Releases
  getReleases: (pid) => request("GET", `/products/${pid}/releases`),
  createRelease: (pid, data) => request("POST", `/products/${pid}/releases`, data),
  getRelease: (pid, rid) => request("GET", `/products/${pid}/releases/${rid}`),
  updateRelease: (pid, rid, data) => request("PUT", `/products/${pid}/releases/${rid}`, data),
  deleteRelease: (pid, rid) => request("DELETE", `/products/${pid}/releases/${rid}`),
  attachPipeline: (pid, rid, data) => request("POST", `/products/${pid}/releases/${rid}/pipelines`, data),
  detachPipeline: (pid, rid, plid) => request("DELETE", `/products/${pid}/releases/${rid}/pipelines/${plid}`),
  getAuditReport: (pid, rid) => request("GET", `/products/${pid}/releases/${rid}/audit`),

  // Release application groups
  getReleaseAppGroups: (pid, rid) => request("GET", `/products/${pid}/releases/${rid}/application-groups`),
  addReleaseAppGroup: (pid, rid, data) => request("POST", `/products/${pid}/releases/${rid}/application-groups`, data),
  removeReleaseAppGroup: (pid, rid, gid) => request("DELETE", `/products/${pid}/releases/${rid}/application-groups/${gid}`),

  // Release runs
  getReleaseRuns: (rid) => request("GET", `/releases/${rid}/runs`),
  createReleaseRun: (rid, data) => request("POST", `/releases/${rid}/runs`, data),
  getReleaseRun: (id) => request("GET", `/release-runs/${id}`),
  updateReleaseRun: (id, data) => request("PATCH", `/release-runs/${id}`, data),

  // Users
  getUsers: () => request("GET", "/users"),
  createUser: (data) => request("POST", "/users", data),
  getUser: (id) => request("GET", `/users/${id}`),
  updateUser: (id, data) => request("PATCH", `/users/${id}`, data),
  deleteUser: (id) => request("DELETE", `/users/${id}`),
  getUserBindings: (id) => request("GET", `/users/${id}/bindings`),
  addUserBinding: (id, data) => request("POST", `/users/${id}/bindings`, data),
  removeUserBinding: (userId, bindingId) => request("DELETE", `/users/${userId}/bindings/${bindingId}`),
  getUserPermissions: (id, scope) => request("GET", `/users/${id}/permissions?scope=${scope || "organization"}`),

  // Groups
  getGroups: () => request("GET", "/groups"),
  createGroup: (data) => request("POST", "/groups", data),
  getGroup: (id) => request("GET", `/groups/${id}`),
  updateGroup: (id, data) => request("PATCH", `/groups/${id}`, data),
  deleteGroup: (id) => request("DELETE", `/groups/${id}`),
  addGroupMember: (groupId, userId) => request("POST", `/groups/${groupId}/members/${userId}`),
  removeGroupMember: (groupId, userId) => request("DELETE", `/groups/${groupId}/members/${userId}`),

  // Roles
  getRoles: () => request("GET", "/roles"),
  createRole: (data) => request("POST", "/roles", data),
  getRole: (id) => request("GET", `/roles/${id}`),
  updateRole: (id, data) => request("PATCH", `/roles/${id}`, data),
  deleteRole: (id) => request("DELETE", `/roles/${id}`),

  // Plugins
  getPlugins: () => request("GET", "/plugins"),
  getPlugin: (id) => request("GET", `/plugins/${id}`),
  uploadPlugin: (data) => request("POST", "/plugins", data),
  togglePlugin: (id) => request("PATCH", `/plugins/${id}/toggle`),
  deletePlugin: (id) => request("DELETE", `/plugins/${id}`),
  getPluginConfigs: (id) => request("GET", `/plugins/${id}/configs`),
  createPluginConfig: (id, data) => request("POST", `/plugins/${id}/configs`, data),
  updatePluginConfig: (id, cfgId, data) => request("PUT", `/plugins/${id}/configs/${cfgId}`, data),
  deletePluginConfig: (id, cfgId) => request("DELETE", `/plugins/${id}/configs/${cfgId}`),

  // YAML import
  importPipelineYaml: (pid, plid, yamlText) => {
    const token = auth.getToken();
    const headers = { "Content-Type": "text/yaml" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(`${BASE}/products/${pid}/pipelines/${plid}/import`, {
      method: "POST", headers, body: yamlText,
    }).then(async r => {
      if (r.status === 401) { auth.clearToken(); if (typeof showLoginPage === "function") showLoginPage(); throw new Error("Session expired"); }
      const j = await r.json();
      if (!r.ok) throw Object.assign(new Error(j.error || "Import failed"), { data: j });
      return j;
    });
  },

  // Git sync
  gitPullPipeline: (pid, plid) => request("POST", `/products/${pid}/pipelines/${plid}/git/pull`),
  gitPushPipeline: (pid, plid, data) => request("POST", `/products/${pid}/pipelines/${plid}/git/push`, data),

  // LDAP
  getLdapConfig: () => request("GET", "/auth/ldap/config"),
  testLdap: (data) => request("POST", "/auth/ldap/test", data),

  // Compliance
  getComplianceRules: () => request("GET", "/compliance/rules"),
  createComplianceRule: (data) => request("POST", "/compliance/rules", data),
  deleteComplianceRule: (id) => request("DELETE", `/compliance/rules/${id}`),
  getAuditEvents: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request("GET", `/compliance/audit-events${qs ? "?" + qs : ""}`);
  },

  // Webhooks
  listWebhooks: () => request("GET", "/webhooks"),
  createWebhook: (data) => request("POST", "/webhooks", data),
  updateWebhook: (id, data) => request("PUT", `/webhooks/${id}`, data),
  deleteWebhook: (id) => request("DELETE", `/webhooks/${id}`),
  getWebhookDeliveries: (id) => request("GET", `/webhooks/${id}/deliveries`),

  // Vault
  listSecrets: () => request("GET", "/vault"),
  createSecret: (data) => request("POST", "/vault", data),
  revealSecret: (id) => request("POST", `/vault/${id}/reveal`),
  updateSecret: (id, data) => request("PUT", `/vault/${id}`, data),
  deleteSecret: (id) => request("DELETE", `/vault/${id}`),
};
