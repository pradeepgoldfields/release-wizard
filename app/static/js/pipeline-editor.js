/**
 * pipeline-editor.js  — X6-based interactive pipeline canvas
 *
 * Exposes a single global:  PipelineEditor
 * Usage:
 *   const pe = new PipelineEditor("pe-container", { productId, pipelineId, onSave });
 *   pe.load(stages);          // stages = pipeline.stages from REST API
 *   pe.destroy();
 */

/* ── Constants ─────────────────────────────────────────────────────────────── */

const PE_ACCENT = [
  "#3b82f6","#8b5cf6","#10b981","#f59e0b",
  "#ef4444","#06b6d4","#f97316","#6366f1",
];

const PE_TYPE_COLOR = {
  "unit-test":"#3b82f6","integration-test":"#8b5cf6","e2e-test":"#6366f1",
  "build":"#f59e0b","docker-build":"#f97316","compile":"#eab308",
  "deploy":"#10b981","helm-deploy":"#059669","canary":"#34d399",
  "security-scan":"#ef4444","dast":"#dc2626","sast":"#f87171",
  "code-coverage":"#0ea5e9","lint":"#64748b","notify":"#a855f7",
  "python":"#3b82f6",
};

const PE_KIND_COLOR = { gate:"#f59e0b", approval:"#8b5cf6", script:"#94a3b8" };
const PE_KIND_ICON  = { gate:"⊘", approval:"✋", script:"⚙" };

const STAGE_NODE_W = 220;
const STAGE_NODE_HDR = 52;
const TASK_NODE_H  = 52;
const TASK_NODE_W  = 200;
const TASK_GAP     = 8;
const STAGE_PAD_X  = 10;
const STAGE_PAD_TOP = 8;
const STAGE_PAD_BOT = 12;
const SLOT_GAP     = 80;      // horizontal gap between stage columns
const PAR_ROW_GAP  = 16;      // vertical gap between parallel stage rows

/* ── Helpers ────────────────────────────────────────────────────────────────── */

function peAccent(stage, idx) {
  return stage.accent_color || PE_ACCENT[idx % PE_ACCENT.length];
}

function peTaskAccent(task) {
  const k = task.kind || "script";
  if (k !== "script") return PE_KIND_COLOR[k] || "#94a3b8";
  if (task.task_type) {
    for (const t of task.task_type.split(",")) {
      const c = PE_TYPE_COLOR[t.trim().toLowerCase()];
      if (c) return c;
    }
  }
  return "#94a3b8";
}

function peStageHeight(tasks) {
  const n = tasks.length;
  return STAGE_NODE_HDR + STAGE_PAD_TOP + n * (TASK_NODE_H + TASK_GAP) + STAGE_PAD_BOT;
}

/* ── Stage node HTML ─────────────────────────────────────────────────────────── */

function _stageNodeHtml(stage, tasks, accent) {
  const taskRows = tasks.map(t => {
    const ta   = peTaskAccent(t);
    const icon = PE_KIND_ICON[t.kind || "script"] || "⚙";
    const dot  = (t.on_error || "fail") === "warn" ? "#f59e0b" : "#ef4444";
    const name = t.name.length > 20 ? t.name.slice(0, 18) + "…" : t.name;
    const kindBadge = (t.kind && t.kind !== "script")
      ? `<span class="pe-task-badge" style="background:${ta}20;color:${ta}">${t.kind}</span>`
      : (t.task_type
          ? `<span class="pe-task-badge" style="background:${ta}20;color:${ta}">${t.task_type.split(",")[0].trim()}</span>`
          : "");
    const reqStar = t.is_required ? `<span style="color:#f59e0b;margin-left:2px">★</span>` : "";
    const parBadge = (t.execution_mode === "parallel")
      ? `<span class="pe-task-badge" style="background:#6366f115;color:#6366f1">⇉</span>` : "";
    return `
      <div class="pe-task-row" data-task-id="${t.id}" data-stage-id="${stage.id}">
        <span class="pe-task-accent-bar" style="background:${ta}"></span>
        <span class="pe-task-icon" style="color:${ta}">${icon}</span>
        <span class="pe-task-name">${name}${reqStar}</span>
        <span class="pe-task-meta">${parBadge}${kindBadge}</span>
        <span class="pe-task-dot" style="background:${dot}30;border:1.5px solid ${dot}"></span>
      </div>`;
  }).join("");

  const emptyRow = tasks.length === 0
    ? `<div class="pe-task-empty">No tasks — click + to add</div>` : "";

  const execBadge = (stage.execution_mode === "parallel")
    ? `<span class="pe-stage-badge pe-stage-parallel">⇉ parallel</span>` : "";
  const protBadge = stage.is_protected
    ? `<span class="pe-stage-badge pe-stage-prot">🔒</span>` : "";
  const entryBadge = (stage.entry_gate || {}).enabled
    ? `<span class="pe-stage-badge pe-stage-gate">⊘ entry</span>` : "";
  const exitBadge = (stage.exit_gate || {}).enabled
    ? `<span class="pe-stage-badge pe-stage-exit">✓ exit</span>` : "";

  const stageName = stage.name.length > 20 ? stage.name.slice(0, 18) + "…" : stage.name;

  return `
    <div class="pe-stage-node" data-stage-id="${stage.id}">
      <div class="pe-stage-accent" style="background:linear-gradient(90deg,${accent},${accent}aa)"></div>
      <div class="pe-stage-header">
        <span class="pe-stage-order" style="background:${accent}22;color:${accent}">${stage.order}</span>
        <span class="pe-stage-name">${stageName}</span>
        <div class="pe-stage-badges">${execBadge}${protBadge}${entryBadge}${exitBadge}</div>
      </div>
      <div class="pe-task-list">
        ${taskRows}${emptyRow}
      </div>
    </div>`;
}

/* ═══════════════════════════════════════════════════════════════════════════════
   PipelineEditor class
   ═══════════════════════════════════════════════════════════════════════════════ */

class PipelineEditor {
  /**
   * @param {string} containerId   id of the mount <div>
   * @param {object} opts
   *   opts.productId   {string}
   *   opts.pipelineId  {string}
   *   opts.onEditStage (stageId) => void
   *   opts.onEditTask  (taskId, stageId) => void
   *   opts.onAddTask   (stageId) => void
   *   opts.onAddStage  () => void
   *   opts.onReorderStage (stageId, newOrder) => Promise
   *   opts.onDeleteStage  (stageId) => void
   *   opts.readOnly    {boolean}
   */
  constructor(containerId, opts = {}) {
    this._containerId = containerId;
    this._opts = opts;
    this._graph = null;
    this._stages = [];
    this._nodeMap = {};   // stageId → X6 node
    this._mounted = false;
  }

  /* ── Public API ─────────────────────────────────────────────────────────── */

  load(stages) {
    this._stages = stages || [];
    if (!this._mounted) {
      this._mount();
    }
    this._render();
  }

  reload(stages) {
    this._stages = stages || [];
    this._render();
  }

  destroy() {
    if (this._graph) {
      this._graph.dispose();
      this._graph = null;
    }
    this._mounted = false;
    this._nodeMap = {};
    const el = document.getElementById(this._containerId);
    if (el) el.innerHTML = "";
  }

  /* ── Mount: build DOM scaffold + X6 Graph ──────────────────────────────── */

  _mount() {
    const container = document.getElementById(this._containerId);
    if (!container) return;

    container.innerHTML = `
      <div class="pe-toolbar" id="pe-toolbar-${this._containerId}">
        <div class="pe-toolbar-left">
          <button class="pe-btn pe-btn-primary" id="pe-add-stage-${this._containerId}">
            <span>＋</span> Add Stage
          </button>
          <span class="pe-toolbar-sep"></span>
          <button class="pe-btn pe-btn-ghost" id="pe-fit-${this._containerId}" title="Fit view">⊞ Fit</button>
          <button class="pe-btn pe-btn-ghost" id="pe-zoom-in-${this._containerId}" title="Zoom in">＋</button>
          <button class="pe-btn pe-btn-ghost" id="pe-zoom-out-${this._containerId}" title="Zoom out">－</button>
        </div>
        <div class="pe-toolbar-right">
          <span class="pe-hint">Click a stage or task to edit • Drag stages to reorder</span>
        </div>
      </div>
      <div class="pe-canvas-wrap">
        <div id="pe-x6-${this._containerId}" class="pe-x6-mount"></div>
        <div class="pe-minimap-wrap" id="pe-mm-${this._containerId}"></div>
      </div>`;

    // Check X6 is loaded
    if (typeof window.X6 === "undefined") {
      this._renderFallback(container);
      return;
    }

    const { Graph } = window.X6;

    // Register HTML node shape for X6 v1 if not already registered
    if (!Graph.nodeRegistry || !Graph.nodeRegistry.get("pe-html-node")) {
      try {
        Graph.registerNode("pe-html-node", {
          inherit: "rect",
          attrs: {
            body: { fill: "transparent", stroke: "transparent", strokeWidth: 0 },
            foreignObject: { width: "100%", height: "100%", x: 0, y: 0 },
          },
        }, true);
      } catch (ex) { /* already registered */ }
    }

    const mountEl = document.getElementById(`pe-x6-${this._containerId}`);

    this._graph = new Graph({
      container: mountEl,
      width:  mountEl.offsetWidth  || 900,
      height: mountEl.offsetHeight || 560,
      background: { color: "#0f172a" },
      grid: { size: 20, visible: true, type: "dot", args: [{ color: "#1e293b", thickness: 1 }] },
      panning: true,
      mousewheel: { enabled: true, zoomAtMousePosition: true, modifiers: "ctrl", minScale: 0.25, maxScale: 2.5 },
      connecting: { enabled: false },
      selecting: { enabled: true, rubberband: false },
      snapline: true,
      resizing: false,
      rotating: false,
    });

    // Toolbar buttons
    const btnAddStage = document.getElementById(`pe-add-stage-${this._containerId}`);
    if (btnAddStage) btnAddStage.onclick = () => this._opts.onAddStage && this._opts.onAddStage();

    const btnFit = document.getElementById(`pe-fit-${this._containerId}`);
    if (btnFit) btnFit.onclick = () => this._graph.zoomToFit({ padding: 40 });

    const btnZoomIn  = document.getElementById(`pe-zoom-in-${this._containerId}`);
    if (btnZoomIn)  btnZoomIn.onclick  = () => this._graph.zoom(0.15);

    const btnZoomOut = document.getElementById(`pe-zoom-out-${this._containerId}`);
    if (btnZoomOut) btnZoomOut.onclick = () => this._graph.zoom(-0.15);

    // Node click events — listen on the DOM directly since X6 v1 HTML rendering
    // injects a foreignObject; we delegate from the canvas container instead
    mountEl.addEventListener("click", (e) => {
      const taskRow  = e.target.closest && e.target.closest(".pe-task-row");
      const stageHdr = e.target.closest && e.target.closest(".pe-stage-header");
      if (taskRow) {
        e.stopPropagation();
        const tid = taskRow.dataset.taskId;
        const sid = taskRow.dataset.stageId;
        if (tid && sid && this._opts.onEditTask) this._opts.onEditTask(tid, sid);
        return;
      }
      if (stageHdr) {
        e.stopPropagation();
        const sid = stageHdr.closest(".pe-stage-node") && stageHdr.closest(".pe-stage-node").dataset.stageId;
        if (sid && this._opts.onEditStage) this._opts.onEditStage(sid);
      }
    });

    // Node moved → persist reorder
    this._graph.on("node:moved", ({ node }) => {
      this._onNodeMoved(node);
    });

    // Auto-resize when container resizes
    if (window.ResizeObserver) {
      new ResizeObserver(() => {
        if (this._graph && mountEl.offsetWidth > 0) {
          this._graph.resize(mountEl.offsetWidth, mountEl.offsetHeight);
        }
      }).observe(mountEl);
    }

    this._mounted = true;
  }

  /* ── Fallback (X6 not loaded) ───────────────────────────────────────────── */

  _renderFallback(container) {
    container.innerHTML += `<div class="pe-load-error">
      X6 graph library could not be loaded. Check your network connection and reload.
    </div>`;
    this._mounted = true;  // prevent re-mount loops
  }

  /* ── Render all stages as X6 nodes ─────────────────────────────────────── */

  _render() {
    if (!this._graph) return;
    this._graph.clearCells();
    this._nodeMap = {};

    const sorted = [...this._stages].sort((a, b) => a.order - b.order);

    // Group into slots: sequential | parallel run
    const slots = [];
    let i = 0;
    while (i < sorted.length) {
      if ((sorted[i].execution_mode || "sequential") === "parallel") {
        const grp = [];
        while (i < sorted.length && (sorted[i].execution_mode || "sequential") === "parallel") {
          grp.push(sorted[i++]);
        }
        slots.push({ type: "parallel", stages: grp });
      } else {
        slots.push({ type: "sequential", stage: sorted[i++] });
      }
    }

    let curX = 40;
    const baseY = 40;

    const nodes = [];
    const edges = [];
    // Track last slot's node IDs for edge drawing
    let prevNodeIds = [];   // node IDs to connect FROM (right anchors)

    slots.forEach((slot, si) => {
      if (slot.type === "sequential") {
        const s      = slot.stage;
        const tasks  = (s.tasks || []).slice().sort((a, b) => a.order - b.order);
        const accent = peAccent(s, sorted.indexOf(s));
        const nH     = Math.max(peStageHeight(tasks), STAGE_NODE_HDR + STAGE_PAD_TOP + STAGE_PAD_BOT + 30);
        const nodeId = `stage-${s.id}`;

        const node = this._createStageNode(s, tasks, accent, curX, baseY, STAGE_NODE_W, nH);
        nodes.push(node);
        this._nodeMap[s.id] = node;

        // Connect from all previous slot nodes to this one
        prevNodeIds.forEach(pid => edges.push(this._createEdgeById(pid, nodeId, false)));
        prevNodeIds = [nodeId];
        curX += STAGE_NODE_W + SLOT_GAP;

      } else {
        // parallel group — stack vertically
        const group  = slot.stages;
        let rowY     = baseY;
        const curNodeIds = [];

        group.forEach(s => {
          const tasks  = (s.tasks || []).slice().sort((a, b) => a.order - b.order);
          const accent = peAccent(s, sorted.indexOf(s));
          const nH     = Math.max(peStageHeight(tasks), STAGE_NODE_HDR + STAGE_PAD_TOP + STAGE_PAD_BOT + 30);
          const nodeId = `stage-${s.id}`;

          const node = this._createStageNode(s, tasks, accent, curX, rowY, STAGE_NODE_W, nH);
          nodes.push(node);
          this._nodeMap[s.id] = node;
          curNodeIds.push(nodeId);

          // Connect from all previous nodes to each parallel node
          prevNodeIds.forEach(pid => edges.push(this._createEdgeById(pid, nodeId, true)));
          rowY += nH + PAR_ROW_GAP;
        });

        prevNodeIds = curNodeIds;
        curX += STAGE_NODE_W + SLOT_GAP;
      }
    });

    this._graph.addNodes(nodes);
    if (edges.length) this._graph.addEdges(edges);

    // Inject HTML into each node's foreignObject after X6 has rendered SVG
    setTimeout(() => {
      nodes.forEach(nodeDef => {
        if (!nodeDef._peHtml) return;
        const svgNode = this._graph.findViewByCell(nodeDef.id);
        if (!svgNode) return;
        const fo = svgNode.container.querySelector("foreignObject");
        if (!fo) return;
        // Create an XHTML div inside the foreignObject
        const ns  = "http://www.w3.org/1999/xhtml";
        let body  = fo.querySelector("body,div");
        if (!body) {
          body = document.createElementNS(ns, "div");
          body.setAttribute("xmlns", ns);
          body.style.cssText = "width:100%;height:100%;overflow:hidden;";
          fo.appendChild(body);
        }
        body.innerHTML = nodeDef._peHtml;
      });
    }, 20);

    // Fit view after paint
    setTimeout(() => {
      if (this._graph) this._graph.zoomToFit({ padding: 40, maxScale: 1.2 });
    }, 80);
  }

  /* ── Create one X6 HTML node for a stage (X6 v1 foreignObject) ─────────── */

  _createStageNode(stage, tasks, accent, x, y, w, h) {
    if (!this._graph) return null;
    const htmlContent = _stageNodeHtml(stage, tasks, accent);
    // Encode HTML for SVG foreignObject (no XML-escaping needed for innerHTML trick)
    // Use X6 v1 "rect" shape with custom markup using foreignObject
    return {
      id:    `stage-${stage.id}`,
      shape: "rect",
      x, y,
      width:  w,
      height: h,
      data:   { stageId: stage.id },
      markup: [
        { tagName: "rect",          selector: "body" },
        { tagName: "foreignObject", selector: "fo"   },
      ],
      attrs: {
        body: {
          width:  w,
          height: h,
          fill:   "transparent",
          stroke: "transparent",
          strokeWidth: 0,
          rx: 10,
          ry: 10,
        },
        fo: {
          width:    w,
          height:   h,
          x:        0,
          y:        0,
          overflow: "visible",
        },
      },
      // X6 v1 doesn't have built-in foreignObject innerHTML; we do it post-render
      _peHtml: htmlContent,
      movable: !this._opts.readOnly,
    };
  }

  /* ── Create one X6 edge between two node IDs ────────────────────────────── */

  _createEdgeById(sourceNodeId, targetNodeId, isParallel = false) {
    const color = isParallel ? "#6366f1" : "#475569";
    return {
      shape: "edge",
      source: { cell: sourceNodeId, anchor: { name: "right" } },
      target: { cell: targetNodeId, anchor: { name: "left"  } },
      router:    { name: "er", args: { offset: 20, direction: "H" } },
      connector: { name: "rounded", args: { radius: 6 } },
      attrs: {
        line: {
          stroke:          color,
          strokeWidth:     2,
          strokeDasharray: "5 4",
          targetMarker:    { name: "block", width: 8, height: 6, fill: color },
        },
      },
      zIndex: -1,
    };
  }

  /* ── Handle node drag-end → reorder via API ─────────────────────────────── */

  _onNodeMoved(node) {
    // Re-derive order from left-to-right X positions of all stage nodes
    const allNodes = this._graph.getNodes();
    const sorted = allNodes
      .filter(n => { const d = n.getData(); return d && d.stageId; })
      .sort((a, b) => a.getPosition().x - b.getPosition().x);

    sorted.forEach((n, idx) => {
      const sid = n.getData().stageId;
      if (this._opts.onReorderStage) {
        this._opts.onReorderStage(sid, idx + 1);
      }
    });
  }
}

/* ── Side Panel ─────────────────────────────────────────────────────────────
   PipelineSidePanel — slide-in editor that replaces modal dialogs for
   stage and task editing.
   ─────────────────────────────────────────────────────────────────────────── */

class PipelineSidePanel {
  constructor() {
    this._el = null;
    this._bodyEl = null;
    this._titleEl = null;
    this._onConfirm = null;
    this._ensureDom();
  }

  _ensureDom() {
    if (document.getElementById("pe-side-panel")) {
      this._el = document.getElementById("pe-side-panel");
      this._titleEl = document.getElementById("pe-sp-title");
      this._bodyEl  = document.getElementById("pe-sp-body");
      this._saveBtn = document.getElementById("pe-sp-save");
      return;
    }
    const el = document.createElement("div");
    el.id = "pe-side-panel";
    el.className = "pe-side-panel";
    el.innerHTML = `
      <div class="pe-sp-overlay" id="pe-sp-overlay"></div>
      <div class="pe-sp-drawer" id="pe-sp-drawer">
        <div class="pe-sp-head">
          <span id="pe-sp-title" class="pe-sp-title">Edit</span>
          <button class="pe-sp-close" id="pe-sp-close">×</button>
        </div>
        <div class="pe-sp-body" id="pe-sp-body"></div>
        <div class="pe-sp-foot">
          <button class="pe-btn pe-btn-ghost" id="pe-sp-cancel">Cancel</button>
          <button class="pe-btn pe-btn-primary" id="pe-sp-save">Save Changes</button>
        </div>
        <div class="pe-sp-error" id="pe-sp-error" style="display:none"></div>
      </div>`;
    document.body.appendChild(el);
    this._el       = el;
    this._titleEl  = el.querySelector("#pe-sp-title");
    this._bodyEl   = el.querySelector("#pe-sp-body");
    this._saveBtn  = el.querySelector("#pe-sp-save");
    el.querySelector("#pe-sp-close").onclick   = () => this.close();
    el.querySelector("#pe-sp-cancel").onclick  = () => this.close();
    el.querySelector("#pe-sp-overlay").onclick = () => this.close();
    this._saveBtn.onclick = () => this._onConfirm && this._onConfirm();
  }

  open(title, bodyHtml, onConfirm, saveBtnLabel = "Save Changes") {
    this._ensureDom();
    this._titleEl.textContent = title;
    this._bodyEl.innerHTML    = bodyHtml;
    this._onConfirm           = onConfirm;
    this._saveBtn.textContent = saveBtnLabel;
    this.clearError();
    this._el.classList.add("open");
    // Focus first input
    setTimeout(() => {
      const inp = this._bodyEl.querySelector("input,select,textarea");
      if (inp) inp.focus();
    }, 220);
  }

  close() {
    this._el && this._el.classList.remove("open");
  }

  error(msg) {
    const e = document.getElementById("pe-sp-error");
    if (!e) return;
    e.textContent = msg;
    e.style.display = msg ? "block" : "none";
  }

  clearError() {
    this.error("");
  }

  setSaving(saving) {
    if (this._saveBtn) {
      this._saveBtn.disabled    = saving;
      this._saveBtn.textContent = saving ? "Saving…" : (this._saveBtn._label || "Save Changes");
    }
  }
}

/* ── Export globals ─────────────────────────────────────────────────────────── */
window.PipelineEditor    = PipelineEditor;
window.PipelineSidePanel = PipelineSidePanel;
