/**
 * pipeline-editor.js  — JointJS-based interactive pipeline canvas
 *
 * Exposes globals:  PipelineEditor, PipelineSidePanel
 * Usage:
 *   const pe = new PipelineEditor("pe-container", { ...opts });
 *   pe.load(stages);
 *   pe.destroy();
 */

/* ── Constants ─────────────────────────────────────────────────────────────── */

const PE_ACCENT = [
  "#3b82f6","#8b5cf6","#10b981","#f59e0b",
  "#ef4444","#06b6d4","#f97316","#6366f1",
];

const PE_TYPE_COLOR = {
  "unit-test":"#3b82f6","integration-test":"#8b5cf6","e2e-test":"#6366f1",
  "test-gen":"#7c3aed","code-coverage":"#0ea5e9",
  "build":"#f59e0b","docker-build":"#f97316","compile":"#eab308",
  "dockerfile":"#f97316","dependency-update":"#fb923c",
  "deploy":"#10b981","helm-deploy":"#059669","canary":"#34d399",
  "blue-green":"#2dd4bf","rollback":"#f43f5e","argocd":"#6366f1",
  "terraform":"#8b5cf6","ansible":"#e11d48","kubectl":"#0ea5e9",
  "security-scan":"#ef4444","dast":"#dc2626","sast":"#f87171",
  "sca":"#fb7185","secret-scan":"#f43f5e","iac-scan":"#e879f9",
  "cve-triage":"#fbbf24","sbom":"#a78bfa","api-fuzzing":"#dc2626",
  "auth-testing":"#f87171","owasp-top10":"#ef4444",
  "lint":"#64748b","code-gen":"#38bdf8","refactor":"#818cf8",
  "code-review":"#c084fc","diff-analysis":"#a78bfa",
  "style-check":"#94a3b8","complexity-analysis":"#8b5cf6",
  "security-pattern-review":"#f87171","pr-comment":"#c084fc",
  "change-summary":"#818cf8",
  "git-commit":"#34d399","git-push":"#10b981","git-tag":"#059669",
  "branch-management":"#6ee7b7","changelog-gen":"#a7f3d0",
  "conventional-commits":"#34d399","release-cut":"#10b981",
  "requirements-analysis":"#fcd34d","acceptance-criteria":"#fbbf24",
  "user-story":"#f59e0b","bdd":"#fde68a","gherkin":"#fef3c7",
  "stakeholder-report":"#f59e0b","gap-analysis":"#fcd34d","process-mapping":"#fbbf24",
  "pipeline-coordination":"#818cf8","dependency-resolution":"#6366f1",
  "workflow-decision":"#8b5cf6","gate-evaluation":"#f59e0b",
  "approval-routing":"#a855f7","stage-scheduling":"#7c3aed",
  "notify":"#a855f7","python":"#3b82f6",
};

const PE_KIND_COLOR = { gate:"#f59e0b", approval:"#8b5cf6", script:"#94a3b8" };
const PE_KIND_ICON  = { gate:"⊘", approval:"✋", script:"⚙" };

const STAGE_NODE_W  = 300;
const STAGE_NODE_HDR = 68;
const TASK_NODE_H   = 64;
const TASK_GAP      = 10;
const STAGE_PAD_X   = 12;
const STAGE_PAD_TOP = 10;
const STAGE_PAD_BOT = 16;
const SLOT_GAP      = 100;
const PAR_ROW_GAP   = 20;

/* ── Helpers ────────────────────────────────────────────────────────────────── */

function _peIsLight(hex) {
  const c = hex.replace("#", "");
  const r = parseInt(c.substring(0,2),16);
  const g = parseInt(c.substring(2,4),16);
  const b = parseInt(c.substring(4,6),16);
  return (r*299 + g*587 + b*114)/1000 > 128;
}

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
  return STAGE_NODE_HDR + STAGE_PAD_TOP + n*(TASK_NODE_H+TASK_GAP) + STAGE_PAD_BOT;
}

/* ── JointJS custom shapes (defined once at module scope) ───────────────────── */

function _peEnsureShapes() {
  if (typeof joint === "undefined") return;
  if (joint.shapes.app && joint.shapes.app.StageNode) return;  // already defined

  if (!joint.shapes.app) joint.shapes.app = {};

  // Shared markup for an HTML foreignObject node
  const htmlMarkup = [
    { tagName: "rect",          selector: "body" },
    { tagName: "foreignObject", selector: "fo"   },
  ];

  joint.shapes.app.StageNode = joint.dia.Element.define(
    "app.StageNode",
    {
      attrs: {
        body: { fill: "transparent", stroke: "transparent", strokeWidth: 0, rx: 10, ry: 10 },
        fo:   { x: 0, y: 0, overflow: "visible" },
      },
    },
    { markup: htmlMarkup }
  );

  joint.shapes.app.ContainerNode = joint.dia.Element.define(
    "app.ContainerNode",
    {
      attrs: {
        body: {
          fill: "#eff6ff", stroke: "#93c5fd", strokeWidth: 2,
          strokeDasharray: "6 4", rx: 14, ry: 14,
        },
        fo: { x: 0, y: 0, overflow: "visible" },
      },
    },
    { markup: htmlMarkup }
  );
}

/* ── Stage node HTML ─────────────────────────────────────────────────────────── */

function _stageNodeHtml(stage, tasks, accent) {
  const taskRows = tasks.map(t => {
    const ta   = peTaskAccent(t);
    const icon = PE_KIND_ICON[t.kind || "script"] || "⚙";
    const dot  = (t.on_error||"fail")==="warn" ? "#f59e0b" : "#ef4444";
    const name = t.name.length > 20 ? t.name.slice(0,18)+"…" : t.name;
    const kindBadge = (t.kind && t.kind !== "script")
      ? `<span class="pe-task-badge" style="background:${ta}20;color:${ta}">${t.kind}</span>`
      : (t.task_type
          ? `<span class="pe-task-badge" style="background:${ta}20;color:${ta}">${t.task_type.split(",")[0].trim()}</span>`
          : "");
    const reqStar  = t.is_required ? `<span style="color:#f59e0b;margin-left:2px">★</span>` : "";
    const parBadge = (t.execution_mode==="parallel")
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

  const execBadge  = (stage.execution_mode==="parallel")
    ? `<span class="pe-stage-badge pe-stage-parallel">⇉ parallel</span>` : "";
  const protBadge  = stage.is_protected
    ? `<span class="pe-stage-badge pe-stage-prot">🔒</span>` : "";
  const entryBadge = (stage.entry_gate||{}).enabled
    ? `<span class="pe-stage-badge pe-stage-gate">⊘ entry</span>` : "";
  const exitBadge  = (stage.exit_gate||{}).enabled
    ? `<span class="pe-stage-badge pe-stage-exit">✓ exit</span>` : "";

  const stageName = stage.name.length > 20 ? stage.name.slice(0,18)+"…" : stage.name;

  return `
    <div class="pe-stage-node" data-stage-id="${stage.id}">
      <div class="pe-stage-accent" style="background:linear-gradient(90deg,${accent},${accent}aa)"></div>
      <div class="pe-stage-header">
        <span class="pe-stage-order" style="background:${accent}22;color:${accent}">${stage.order}</span>
        <span class="pe-stage-name">${stageName}</span>
        <div class="pe-stage-badges">${execBadge}${protBadge}${entryBadge}${exitBadge}</div>
        <button class="pe-stage-info-btn" title="Edit stage properties">✎</button>
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
   * @param {string} containerId
   * @param {object} opts
   *   opts.onEditPipeline () => void
   *   opts.onEditStage    (stageId) => void
   *   opts.onEditTask     (taskId, stageId) => void
   *   opts.onAddTask      (stageId) => void
   *   opts.onAddStage     () => void
   *   opts.onReorderStage (stageId, newOrder) => Promise
   *   opts.onDeleteStage  (stageId) => void
   *   opts.onColorChange  (color) => void
   *   opts.pipelineName   {string}
   *   opts.accentColor    {string}
   *   opts.readOnly       {boolean}
   */
  constructor(containerId, opts = {}) {
    this._containerId = containerId;
    this._opts  = opts;
    this._graph = null;   // joint.dia.Graph
    this._paper = null;   // joint.dia.Paper
    this._stages  = [];
    this._nodeMap = {};   // stageId → Element
    this._mounted = false;
    this._pipelineContainerNodeId = null;
    this._pipelineContainerLabel  = "Pipeline";
    // pan state
    this._panOrigin = null;
    this._panTranslate = { tx: 0, ty: 0 };
    this._isFullscreen = false;
  }

  /* ── Public API ─────────────────────────────────────────────────────────── */

  load(stages) {
    this._stages = stages || [];
    if (!this._mounted) this._mount();
    this._render();
  }

  reload(stages) {
    this._stages = stages || [];
    this._render();
  }

  destroy() {
    if (this._paper) { this._paper.remove(); this._paper = null; }
    if (this._graph) { this._graph.resetCells([]); this._graph = null; }
    this._mounted = false;
    this._nodeMap = {};
    const el = document.getElementById(this._containerId);
    if (el) el.innerHTML = "";
  }

  /* ── Mount: build DOM scaffold + JointJS Graph/Paper ─────────────────────── */

  _mount() {
    const container = document.getElementById(this._containerId);
    if (!container) return;

    const readOnly = !!this._opts.readOnly;

    container.innerHTML = `
      <div class="pe-toolbar" id="pe-toolbar-${this._containerId}">
        <div class="pe-toolbar-left">
          ${readOnly ? "" : `<button class="pe-btn pe-btn-primary" id="pe-add-stage-${this._containerId}"><span>＋</span> Add Stage</button>
          <span class="pe-toolbar-sep"></span>`}
          <button class="pe-btn pe-btn-ghost" id="pe-fit-${this._containerId}" title="Fit view">⊞ Fit</button>
          <button class="pe-btn pe-btn-ghost" id="pe-zoom-in-${this._containerId}" title="Zoom in">＋</button>
          <button class="pe-btn pe-btn-ghost" id="pe-zoom-out-${this._containerId}" title="Zoom out">－</button>
        </div>
        <div class="pe-toolbar-right">
          <span class="pe-hint">${readOnly ? "Click stage or task to highlight YAML" : "Click a stage or task to edit • Drag stages to reorder"}</span>
          <span class="pe-toolbar-sep"></span>
          <button class="pe-btn pe-btn-ghost" id="pe-fullscreen-${this._containerId}" title="Fill page (F)">⛶ Fill page</button>
          <span class="pe-toolbar-sep"></span>
          <div class="pe-theme-picker" id="pe-theme-picker-${this._containerId}">
            <button class="pe-btn pe-btn-ghost pe-theme-btn" id="pe-theme-btn-${this._containerId}" title="Canvas theme">🎨</button>
            <div class="pe-theme-menu" id="pe-theme-menu-${this._containerId}">
              <div class="pe-theme-label">Canvas Theme</div>
              <button class="pe-theme-opt selected" data-bg="#0f172a" data-grid="#1e293b" data-node="#1e293b" data-border="#334155" data-text="#f1f5f9" title="Dark (default)"><span class="pe-theme-swatch" style="background:#0f172a;border-color:#334155"></span>Dark</button>
              <button class="pe-theme-opt" data-bg="#1a1a2e" data-grid="#16213e" data-node="#16213e" data-border="#0f3460" data-text="#e2e8f0" title="Midnight"><span class="pe-theme-swatch" style="background:#1a1a2e;border-color:#0f3460"></span>Midnight</button>
              <button class="pe-theme-opt" data-bg="#0d1117" data-grid="#161b22" data-node="#161b22" data-border="#30363d" data-text="#e6edf3" title="GitHub Dark"><span class="pe-theme-swatch" style="background:#0d1117;border-color:#30363d"></span>GitHub Dark</button>
              <button class="pe-theme-opt" data-bg="#111827" data-grid="#1f2937" data-node="#1f2937" data-border="#374151" data-text="#f9fafb" title="Slate"><span class="pe-theme-swatch" style="background:#111827;border-color:#374151"></span>Slate</button>
              <button class="pe-theme-opt" data-bg="#f8fafc" data-grid="#e2e8f0" data-node="#ffffff" data-border="#cbd5e1" data-text="#0f172a" title="Light"><span class="pe-theme-swatch" style="background:#f8fafc;border-color:#cbd5e1"></span>Light</button>
              <button class="pe-theme-opt" data-bg="#fafaf9" data-grid="#e7e5e4" data-node="#ffffff" data-border="#d6d3d1" data-text="#1c1917" title="Warm"><span class="pe-theme-swatch" style="background:#fafaf9;border-color:#d6d3d1"></span>Warm</button>
              <button class="pe-theme-opt" data-bg="#052e16" data-grid="#14532d" data-node="#166534" data-border="#15803d" data-text="#f0fdf4" title="Forest"><span class="pe-theme-swatch" style="background:#052e16;border-color:#15803d"></span>Forest</button>
              <button class="pe-theme-opt" data-bg="#1e1b4b" data-grid="#312e81" data-node="#3730a3" data-border="#4338ca" data-text="#eef2ff" title="Indigo"><span class="pe-theme-swatch" style="background:#1e1b4b;border-color:#4338ca"></span>Indigo</button>
              <button class="pe-theme-opt" data-bg="#e0f2fe" data-grid="#bae6fd" data-node="#ffffff" data-border="#7dd3fc" data-text="#0c4a6e" title="Sky Blue"><span class="pe-theme-swatch" style="background:#e0f2fe;border-color:#7dd3fc"></span>Sky Blue</button>
            </div>
          </div>
        </div>
      </div>
      <div class="pe-canvas-wrap" style="position:relative">
        <div id="pe-jj-${this._containerId}" class="pe-jj-mount"></div>
      </div>`;

    if (typeof joint === "undefined") {
      console.error("[PE] joint is undefined!");
      this._renderFallback(container);
      return;
    }

    console.log("[PE] joint loaded, version:", joint.version, "shapes.app:", !!joint.shapes.app);
    _peEnsureShapes();
    console.log("[PE] shapes defined, StageNode:", !!joint.shapes.app.StageNode);

    const mountEl = document.getElementById(`pe-jj-${this._containerId}`);
    const initW   = mountEl.offsetWidth  || 900;
    const initH   = mountEl.offsetHeight || 400;

    this._graph = new joint.dia.Graph({}, { cellNamespace: joint.shapes });

    this._paper = new joint.dia.Paper({
      el:     mountEl,
      model:  this._graph,
      width:  initW,
      height: initH,
      background: { color: "#0f172a" },
      gridSize: 1,
      drawGrid: false,
      interactive: (view) => {
        if (readOnly) return false;
        const movable = view.model.prop("movable");
        if (movable === false) return false;
        return { elementMove: true, addLinkFromMagnet: false };
      },
      defaultConnector: { name: "rounded", args: { radius: 6 } },
      defaultRouter:    { name: "orthogonal" },
    });

    // ── Toolbar wiring ────────────────────────────────────────────────────────
    const outer = container.closest(".pe-canvas-outer") || container.parentElement;

    const btnAddStage = document.getElementById(`pe-add-stage-${this._containerId}`);
    if (btnAddStage) btnAddStage.onclick = () => this._opts.onAddStage && this._opts.onAddStage();

    const btnFit = document.getElementById(`pe-fit-${this._containerId}`);
    if (btnFit) btnFit.onclick = () => {
      this._paper.scaleContentToFit({ padding: 40, maxScaleX: 1, maxScaleY: 1 });
      // reset translate so centred
      this._panTranslate = { tx: 0, ty: 0 };
    };

    const btnZoomIn  = document.getElementById(`pe-zoom-in-${this._containerId}`);
    if (btnZoomIn)  btnZoomIn.onclick  = () => this._zoom(1.15);

    const btnZoomOut = document.getElementById(`pe-zoom-out-${this._containerId}`);
    if (btnZoomOut) btnZoomOut.onclick = () => this._zoom(1/1.15);

    const btnFs = document.getElementById(`pe-fullscreen-${this._containerId}`);
    if (btnFs && outer) {
      btnFs.onclick = () => this._toggleFullscreen(outer, btnFs);
      document.addEventListener("keydown", (e) => {
        if (e.key === "F" && !e.ctrlKey && !e.metaKey && !e.altKey &&
            document.activeElement &&
            !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName)) {
          this._toggleFullscreen(outer, btnFs);
        }
        if (e.key === "Escape" && this._isFullscreen) {
          this._exitFullscreen(outer, btnFs);
        }
      });
    }

    // ── Theme picker ──────────────────────────────────────────────────────────
    const themeBtn  = document.getElementById(`pe-theme-btn-${this._containerId}`);
    const themeMenu = document.getElementById(`pe-theme-menu-${this._containerId}`);
    if (themeBtn && themeMenu) {
      themeBtn.onclick = (e) => { e.stopPropagation(); themeMenu.classList.toggle("open"); };
      themeMenu.querySelectorAll(".pe-theme-opt").forEach(opt => {
        opt.onclick = () => {
          this._applyTheme(opt.dataset, outer || container.parentElement);
          themeMenu.querySelectorAll(".pe-theme-opt").forEach(o => o.classList.remove("selected"));
          opt.classList.add("selected");
          themeMenu.classList.remove("open");
        };
      });
      document.addEventListener("click", (e) => {
        if (!e.target.closest(`#pe-theme-picker-${this._containerId}`)) {
          themeMenu.classList.remove("open");
        }
      });
    }

    // ── DOM click delegation (works through foreignObject) ────────────────────
    mountEl.addEventListener("click", (e) => {
      const plHdr    = e.target.closest && e.target.closest("[data-pe-pipeline-hdr]");
      const taskRow  = e.target.closest && e.target.closest(".pe-task-row");
      const infoBtn  = e.target.closest && e.target.closest(".pe-stage-info-btn");
      const stageHdr = e.target.closest && e.target.closest(".pe-stage-header");

      if (plHdr) {
        e.stopPropagation();
        if (!readOnly && this._opts.onEditPipeline) this._opts.onEditPipeline();
        return;
      }
      if (taskRow) {
        e.stopPropagation();
        const tid = taskRow.dataset.taskId;
        const sid = taskRow.dataset.stageId;
        if (tid && sid) {
          if (this._opts.onEditTask) this._opts.onEditTask(tid, sid);
          else this._showTaskProps(tid, sid);
        }
        return;
      }
      if (infoBtn) {
        e.stopPropagation();
        const sn = infoBtn.closest(".pe-stage-node");
        const sid = sn && sn.dataset.stageId;
        if (sid) {
          if (this._opts.onEditStage) this._opts.onEditStage(sid);
          else this._showStageProps(sid);
        }
        return;
      }
      if (stageHdr) {
        e.stopPropagation();
        const sn = stageHdr.closest(".pe-stage-node");
        const sid = sn && sn.dataset.stageId;
        if (sid) {
          if (this._opts.onEditStage) this._opts.onEditStage(sid);
          else this._showStageProps(sid);
        }
        return;
      }
      this._closeProps();
    });

    // ── Pan (blank drag) ──────────────────────────────────────────────────────
    this._paper.on("blank:pointerdown", (evt) => {
      this._panOrigin = { x: evt.clientX, y: evt.clientY,
                          tx: this._panTranslate.tx, ty: this._panTranslate.ty };
    });
    this._paper.on("blank:pointermove", (evt) => {
      if (!this._panOrigin) return;
      const dx = evt.clientX - this._panOrigin.x;
      const dy = evt.clientY - this._panOrigin.y;
      const tx = this._panOrigin.tx + dx;
      const ty = this._panOrigin.ty + dy;
      this._paper.translate(tx, ty);
      this._panTranslate = { tx, ty };
    });
    this._paper.on("blank:pointerup", () => { this._panOrigin = null; });

    // ── Wheel: pinch/ctrl = zoom, two-finger scroll = pan ────────────────────
    mountEl.addEventListener("wheel", (e) => {
      e.preventDefault();
      if (e.ctrlKey) {
        // Pinch-to-zoom or ctrl+scroll → zoom (deltaY scaled for sensitivity)
        const factor = 1 - Math.sign(e.deltaY) * Math.min(Math.abs(e.deltaY) * 0.003, 0.1);
        const scale  = this._paper.scale();
        const newS   = Math.max(0.25, Math.min(2.5, scale.sx * factor));
        const rect   = mountEl.getBoundingClientRect();
        this._paper.scale(newS, newS, e.clientX - rect.left, e.clientY - rect.top);
      } else {
        // Two-finger trackpad scroll → pan
        const t = this._paper.translate();
        this._paper.translate(t.tx - e.deltaX, t.ty - e.deltaY);
        this._panTranslate = this._paper.translate();
      }
    }, { passive: false });

    // ── Drag constraint: keep stage nodes inside container ────────────────────
    this._paper.on("element:pointermove", (view) => {
      if (!view.model.prop("movable")) return;
      const stageId = view.model.prop("custom/stageId");
      if (!stageId) return;
      const contId = this._pipelineContainerNodeId;
      if (!contId) return;
      const contEl = this._graph.getCell(contId);
      if (!contEl) return;

      const CONT_PAD_X = 28, CONT_PAD_Y = 14, CONT_HDR_H = 32;
      const cp = contEl.position();
      const cs = contEl.size();
      const ns = view.model.size();
      const np = view.model.position();

      const minX = cp.x + CONT_PAD_X;
      const minY = cp.y + CONT_HDR_H + CONT_PAD_Y;
      const maxX = cp.x + cs.width  - CONT_PAD_X - ns.width;
      const maxY = cp.y + cs.height - CONT_PAD_Y - ns.height;

      const cx = Math.max(minX, Math.min(maxX, np.x));
      const cy = Math.max(minY, Math.min(maxY, np.y));
      if (cx !== np.x || cy !== np.y) view.model.position(cx, cy);
    });

    // ── Drag end: reorder + resize container ──────────────────────────────────
    this._paper.on("element:pointerup", (view) => {
      if (!view.model.prop("custom/stageId")) return;
      this._onNodeMoved(view.model);
      this._resizeContainer();
    });

    // ── ResizeObserver ────────────────────────────────────────────────────────
    if (window.ResizeObserver) {
      new ResizeObserver(() => {
        if (this._paper && mountEl.offsetWidth > 0) {
          this._paper.setDimensions(mountEl.offsetWidth, mountEl.offsetHeight);
        }
      }).observe(mountEl);
    }

    // ── Restore saved theme ───────────────────────────────────────────────────
    try {
      const saved = localStorage.getItem("pe-theme");
      if (saved) {
        const t = JSON.parse(saved);
        this._applyTheme(t, outer);
        if (themeMenu) {
          themeMenu.querySelectorAll(".pe-theme-opt").forEach(o => {
            o.classList.toggle("selected", o.dataset.bg === t.bg);
          });
        }
      }
    } catch {}

    this._mounted = true;
  }

  /* ── Zoom helper ─────────────────────────────────────────────────────────── */
  _zoom(factor) {
    if (!this._paper) return;
    const s = this._paper.scale();
    const newS = Math.max(0.25, Math.min(2.5, s.sx * factor));
    this._paper.scale(newS, newS);
  }

  /* ── Theme application ───────────────────────────────────────────────────── */

  _applyTheme({ bg, grid, node, border, text }, outer) {
    if (this._paper) this._paper.drawBackground({ color: bg });
    if (outer) outer.style.background = bg;

    const styleId = `pe-theme-style-${this._containerId}`;
    let styleEl = document.getElementById(styleId);
    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = styleId;
      document.head.appendChild(styleEl);
    }
    const isLight = _peIsLight(bg);
    const taskBg  = isLight ? "#f8fafc" : "#0f172a";
    styleEl.textContent = `
      #pe-container-${this._containerId} .pe-stage-node { background:${node} !important; border-color:${border} !important; }
      #pe-container-${this._containerId} .pe-stage-name { color:${text} !important; }
      #pe-container-${this._containerId} .pe-task-row   { background:${taskBg} !important; border-color:${border} !important; }
      #pe-container-${this._containerId} .pe-task-name  { color:${isLight?"#1e293b":"#e2e8f0"} !important; }
      #pe-container-${this._containerId} .pe-toolbar    { background:${bg} !important; border-bottom-color:${border} !important; }
      #pe-container-${this._containerId} .pe-canvas-wrap{ background:${bg}; }
    `;
    try { localStorage.setItem("pe-theme", JSON.stringify({ bg, grid, node, border, text })); } catch {}
  }

  /* ── Fullscreen ──────────────────────────────────────────────────────────── */

  _toggleFullscreen(outer, btn) {
    const mountEl = document.getElementById(`pe-jj-${this._containerId}`);
    if (!mountEl) return;

    if (this._isFullscreen) {
      this._exitFullscreen(outer, btn);
      return;
    }
    this._isFullscreen = true;
    btn.textContent = "⛶ Exit fullscreen";
    btn.title = "Exit fullscreen (Esc)";

    // Apply current canvas background to the fullscreen mount
    const bg = this._paper ? this._paper.options.background?.color || "#0f172a" : "#0f172a";
    mountEl.style.background = bg;
    mountEl.classList.add("pe-jj-fullscreen");

    // Floating toolbar overlay inside fullscreen
    const floatId = `pe-fs-toolbar-${this._containerId}`;
    document.getElementById(floatId)?.remove();
    const floatBar = document.createElement("div");
    floatBar.id = floatId;
    floatBar.style.cssText = `
      position:fixed;top:12px;right:16px;z-index:10002;
      display:flex;gap:6px;align-items:center;
      background:#0f172acc;border:1px solid #334155;
      border-radius:8px;padding:5px 8px;backdrop-filter:blur(4px);
    `;
    floatBar.innerHTML = `
      <button class="pe-btn pe-btn-ghost" id="pe-fs-zin-${this._containerId}" title="Zoom in">＋</button>
      <button class="pe-btn pe-btn-ghost" id="pe-fs-zout-${this._containerId}" title="Zoom out">－</button>
      <button class="pe-btn pe-btn-ghost" id="pe-fs-fit-${this._containerId}" title="Fit">⊞ Fit</button>
      <span style="width:1px;height:18px;background:#334155;margin:0 2px"></span>
      <button class="pe-btn pe-btn-ghost" id="pe-fs-exit-${this._containerId}" title="Exit fullscreen (Esc)">⛶ Exit</button>
    `;
    document.body.appendChild(floatBar);

    floatBar.querySelector(`#pe-fs-zin-${this._containerId}`).onclick  = () => this._zoom(1.15);
    floatBar.querySelector(`#pe-fs-zout-${this._containerId}`).onclick = () => this._zoom(1/1.15);
    floatBar.querySelector(`#pe-fs-fit-${this._containerId}`).onclick  = () => {
      if (this._paper) this._paper.scaleContentToFit({ padding: 60 });
    };
    floatBar.querySelector(`#pe-fs-exit-${this._containerId}`).onclick = () => this._exitFullscreen(outer, btn);

    // Resize paper to fill viewport and scale up nodes to fill the space
    const resize = () => {
      if (!this._paper) return;
      const w = window.innerWidth;
      const h = window.innerHeight;
      this._paper.setDimensions(w, h);
      this._paper.scaleContentToFit({ padding: 60, minScaleX: 0.5, minScaleY: 0.5, maxScaleX: 4, maxScaleY: 4 });
    };
    requestAnimationFrame(() => { resize(); requestAnimationFrame(resize); });
  }

  _exitFullscreen(outer, btn) {
    const mountEl = document.getElementById(`pe-jj-${this._containerId}`);
    this._isFullscreen = false;
    btn.textContent = "⛶ Fill page";
    btn.title = "Fill page (F)";
    if (mountEl) {
      mountEl.classList.remove("pe-jj-fullscreen");
      mountEl.style.background = "";
    }
    document.getElementById(`pe-fs-toolbar-${this._containerId}`)?.remove();
    setTimeout(() => this._sizeCanvasToFit(Object.values(this._nodeMap)), 60);
  }

  _resizePaper() {
    const mountEl = document.getElementById(`pe-jj-${this._containerId}`);
    if (this._paper && mountEl) {
      const wrap = mountEl.parentElement;
      const w = wrap ? wrap.clientWidth  : mountEl.offsetWidth;
      const h = wrap ? wrap.clientHeight : mountEl.offsetHeight;
      if (w > 0 && h > 0) this._paper.setDimensions(w, h);
    }
  }

  /* ── Fallback ────────────────────────────────────────────────────────────── */

  _renderFallback(container) {
    container.innerHTML += `<div class="pe-load-error">
      JointJS graph library could not be loaded. Check your network connection and reload.
    </div>`;
    this._mounted = true;
  }

  /* ── Render all stages ───────────────────────────────────────────────────── */

  _render() {
    if (!this._graph || !this._paper) return;

    console.log("[PE] _render called, stages:", this._stages.length);

    this._graph.resetCells([]);
    this._nodeMap = {};
    this._pipelineContainerNodeId = null;

    const sorted = [...this._stages].sort((a, b) => a.order - b.order);
    console.log("[PE] sorted stages:", sorted.map(s => s.name));

    // Group into slots
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

    // Pre-compute slot heights
    const slotHeights = slots.map(slot => {
      if (slot.type === "sequential") {
        const tasks = (slot.stage.tasks||[]).slice().sort((a,b)=>a.order-b.order);
        return Math.max(peStageHeight(tasks), STAGE_NODE_HDR+STAGE_PAD_TOP+STAGE_PAD_BOT+30);
      }
      let h = 0;
      slot.stages.forEach((s, idx) => {
        const tasks = (s.tasks||[]).slice().sort((a,b)=>a.order-b.order);
        const nH = Math.max(peStageHeight(tasks), STAGE_NODE_HDR+STAGE_PAD_TOP+STAGE_PAD_BOT+30);
        h += nH + (idx > 0 ? PAR_ROW_GAP : 0);
      });
      return h;
    });

    const contentW = slots.length * STAGE_NODE_W + Math.max(0, slots.length-1) * SLOT_GAP;
    const MARGIN   = 40;

    const mountEl = document.getElementById(`pe-jj-${this._containerId}`);
    const viewW   = (mountEl && mountEl.offsetWidth > 100)
      ? mountEl.offsetWidth
      : (this._paper.options.width || 900);

    const offsetX = Math.max(MARGIN, Math.round((viewW - contentW) / 2));
    const baseY   = MARGIN;

    let curX = offsetX;
    const elements = [];
    const links    = [];
    let prevIds    = [];
    // Track node bounding boxes for anchor alignment: { id -> {y, h} }
    const nodeBBox = {};

    slots.forEach((slot, si) => {
      if (slot.type === "sequential") {
        const s      = slot.stage;
        const tasks  = (s.tasks||[]).slice().sort((a,b)=>a.order-b.order);
        const accent = peAccent(s, sorted.indexOf(s));
        const nH     = slotHeights[si];
        const nodeId = `stage-${s.id}`;

        const el = this._createStageNode(s, tasks, accent, curX, baseY, STAGE_NODE_W, nH, nodeId);
        elements.push(el);
        this._nodeMap[s.id] = el;
        nodeBBox[nodeId] = { y: baseY, h: nH, x: curX, w: STAGE_NODE_W };

        prevIds.forEach(pid => links.push(this._createLink(pid, nodeId, false, nodeBBox[pid], nodeBBox[nodeId])));
        prevIds = [nodeId];
        curX += STAGE_NODE_W + SLOT_GAP;

      } else {
        const group = slot.stages;
        let rowY    = baseY;
        const curIds = [];

        group.forEach(s => {
          const tasks  = (s.tasks||[]).slice().sort((a,b)=>a.order-b.order);
          const accent = peAccent(s, sorted.indexOf(s));
          const nH     = Math.max(peStageHeight(tasks), STAGE_NODE_HDR+STAGE_PAD_TOP+STAGE_PAD_BOT+30);
          const nodeId = `stage-${s.id}`;

          const el = this._createStageNode(s, tasks, accent, curX, rowY, STAGE_NODE_W, nH, nodeId);
          elements.push(el);
          this._nodeMap[s.id] = el;
          curIds.push(nodeId);
          nodeBBox[nodeId] = { y: rowY, h: nH, x: curX, w: STAGE_NODE_W };

          prevIds.forEach(pid => links.push(this._createLink(pid, nodeId, true, nodeBBox[pid], nodeBBox[nodeId])));
          rowY += nH + PAR_ROW_GAP;
        });

        prevIds = curIds;
        curX += STAGE_NODE_W + SLOT_GAP;
      }
    });

    // ── Pipeline container background ──────────────────────────────────────
    let contEl = null;
    if (elements.length) {
      let minX = Infinity, minY = Infinity, maxNX = 0, maxNY = 0;
      elements.forEach(el => {
        const p = el.position();
        const s = el.size();
        minX  = Math.min(minX,  p.x);
        minY  = Math.min(minY,  p.y);
        maxNX = Math.max(maxNX, p.x + s.width);
        maxNY = Math.max(maxNY, p.y + s.height);
      });
      const CONT_PAD_X = 28, CONT_PAD_Y = 14, CONT_HDR_H = 32;
      const contX = minX - CONT_PAD_X;
      const contY = minY - CONT_PAD_Y - CONT_HDR_H;
      const contW = (maxNX - minX) + CONT_PAD_X * 2;
      const contH = (maxNY - minY) + CONT_PAD_Y * 2 + CONT_HDR_H;
      const contId = `pe-pipeline-container-${this._containerId}`;

      contEl = new joint.shapes.app.ContainerNode({
        id: contId,
        position: { x: contX, y: contY },
        size:     { width: contW, height: contH },
        z: -2,
        attrs: {
          body: { width: contW, height: contH },
          fo:   { width: contW, height: contH },
        },
        prop: { movable: false },
      });
      this._pipelineContainerNodeId  = contId;
      this._pipelineContainerLabel   = (this._opts && this._opts.pipelineName) || "Pipeline";
    }

    // Add all cells in one batch
    const allCells = contEl
      ? [contEl, ...elements, ...links]
      : [...elements, ...links];
    console.log("[PE] addCells:", allCells.length, "elements:", elements.length, "links:", links.length);
    this._graph.addCells(allCells);

    // ── Inject HTML into foreignObjects after JointJS renders SVG ────────────
    const injectHtml = () => {
      console.log("[PE] injectHtml fired, graph cells:", this._graph.getCells().length);
      // Container node label
      if (this._pipelineContainerNodeId) {
        const contCell = this._graph.getCell(this._pipelineContainerNodeId);
        const view = contCell && this._paper.findViewByModel(contCell);
        if (view) {
          const fo = view.el.querySelector("foreignObject");
          if (fo) {
            const CONT_HDR_H = 32;
            const canEdit    = !this._opts.readOnly;
            const label      = this._pipelineContainerLabel;
            fo.innerHTML = `<div xmlns="http://www.w3.org/1999/xhtml"
              style="width:100%;height:100%;overflow:hidden;box-sizing:border-box;border-radius:14px">
              <div data-pe-pipeline-hdr="1"
                style="padding:6px 14px;display:flex;align-items:center;gap:8px;height:${CONT_HDR_H}px;${canEdit?"cursor:pointer;":""}">
                <span style="font-size:13px;color:#3b82f6">⬡</span>
                <span style="font-size:12px;font-weight:700;color:#1d4ed8;letter-spacing:0.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${label}</span>
                ${canEdit ? `<span style="margin-left:auto;font-size:11px;color:#3b82f6;opacity:0.7;user-select:none">✎</span>` : ""}
              </div>
            </div>`;
          }
        }
      }

      // Stage nodes
      elements.forEach(el => {
        const html = el.prop("peHtml");
        if (!html) return;
        const view = this._paper.findViewByModel(el);
        if (!view) return;
        const fo = view.el.querySelector("foreignObject");
        if (!fo) return;
        fo.innerHTML = `<div xmlns="http://www.w3.org/1999/xhtml"
          style="width:100%;height:100%;overflow:hidden;">${html}</div>`;
      });

      // Size canvas to fit
      this._sizeCanvasToFit(elements);

      // Apply saved pipeline accent colour
      const savedColor = (() => { try { return localStorage.getItem(`pe-pl-color-${this._containerId}`); } catch { return null; } })();
      const color = savedColor || this._opts.accentColor || null;
      if (color) this._applyPipelineColor(color, false);
    };

    // Inject HTML: use render:done + a deduplication guard to avoid double-inject
    let _injected = false;
    const _injectOnce = () => { if (_injected) return; _injected = true; injectHtml(); };
    this._paper.once("render:done", _injectOnce);
    setTimeout(_injectOnce, 80);  // fallback if render:done already fired
  }

  /* ── Size canvas to content ──────────────────────────────────────────────── */

  _sizeCanvasToFit(elements) {
    if (!this._paper) return;
    try {
      const allEls = this._graph.getElements();
      if (!allEls.length) return;
      let maxX = 0, maxY = 0;
      allEls.forEach(el => {
        const p = el.position();
        const s = el.size();
        maxX = Math.max(maxX, p.x + s.width);
        maxY = Math.max(maxY, p.y + s.height);
      });
      const mountEl   = document.getElementById(`pe-jj-${this._containerId}`);
      if (!mountEl) return;
      const viewportW = mountEl.parentElement ? mountEl.parentElement.offsetWidth : 0;
      const paddedW   = Math.max(maxX + 80, viewportW || 0);
      const paddedH   = maxY + 80;

      mountEl.style.width     = paddedW + "px";
      mountEl.style.height    = paddedH + "px";
      mountEl.style.minWidth  = paddedW + "px";
      mountEl.style.minHeight = paddedH + "px";

      this._paper.setDimensions(paddedW, paddedH);

      if (mountEl.parentElement) {
        mountEl.parentElement.scrollLeft = 0;
        mountEl.parentElement.scrollTop  = 0;
      }
    } catch {}
  }

  /* ── Create a JointJS stage element ──────────────────────────────────────── */

  _createStageNode(stage, tasks, accent, x, y, w, h, nodeId) {
    const html = _stageNodeHtml(stage, tasks, accent);
    const el   = new joint.shapes.app.StageNode({
      id:       nodeId,
      position: { x, y },
      size:     { width: w, height: h },
      z: 1,
      attrs: {
        body: { width: w, height: h },
        fo:   { width: w, height: h },
      },
      prop: { movable: !this._opts.readOnly },
    });
    el.prop("custom/stageId", stage.id);
    el.prop("peHtml", html);
    return el;
  }

  /* ── Create a JointJS link (edge) between two element IDs ────────────────── */

  _createLink(sourceId, targetId, isParallel = false, srcBBox = null, tgtBBox = null) {
    const color = isParallel ? "#6366f1" : "#475569";

    // For parallel links: use explicit vertices to draw a clean elbow:
    //   source right-centre → midgap at source Y → midgap at target Y → target left-centre
    // This avoids the orthogonal router collapsing the vertical segment when
    // source and target share the same exit Y.
    let vertices = [];
    let router = { name: "orthogonal" };
    if (isParallel && srcBBox && tgtBBox) {
      const srcMidY = srcBBox.y + srcBBox.h / 2;
      const tgtMidY = tgtBBox.y + tgtBBox.h / 2;
      const midX    = srcBBox.x + srcBBox.w + (tgtBBox.x - (srcBBox.x + srcBBox.w)) / 2;
      vertices = [
        { x: midX, y: srcMidY },
        { x: midX, y: tgtMidY },
      ];
      router = { name: "normal" };
    }

    return new joint.shapes.standard.Link({
      source: { id: sourceId, anchor: { name: "right" } },
      target: { id: targetId, anchor: { name: "left"  } },
      vertices,
      router,
      connector: { name: "rounded", args: { radius: 6 } },
      z: -1,
      attrs: {
        line: {
          stroke:            color,
          strokeWidth:       2,
          "stroke-dasharray": "5 4",
          targetMarker: {
            type: "path",
            d:    "M 8 -4 0 0 8 4 Z",
            fill: color,
            "stroke-width": 0,
          },
        },
      },
    });
  }

  /* ── Apply pipeline container accent colour ──────────────────────────────── */

  _applyPipelineColor(color, persist = true) {
    this._pipelineColor = color;
    if (this._graph && this._pipelineContainerNodeId) {
      const contEl = this._graph.getCell(this._pipelineContainerNodeId);
      if (contEl) {
        contEl.attr("body/stroke", color);
        contEl.attr("body/fill",   color + "18");
        const view = this._paper.findViewByModel(contEl);
        if (view) {
          const labelEl = view.el.querySelector("[style*='font-weight:700']");
          if (labelEl) labelEl.style.color = color;
          const iconEl  = view.el.querySelector("[style*='font-size:13px']");
          if (iconEl)  iconEl.style.color  = color;
        }
      }
    }
    if (persist) {
      try { localStorage.setItem(`pe-pl-color-${this._containerId}`, color); } catch {}
      if (this._opts.onColorChange) this._opts.onColorChange(color);
    }
  }

  /* ── Handle drag end → reorder ───────────────────────────────────────────── */

  _onNodeMoved(element) {
    const stageEls = this._graph.getElements()
      .filter(el => el.prop("custom/stageId"))
      .sort((a, b) => a.position().x - b.position().x);

    stageEls.forEach((el, idx) => {
      const sid = el.prop("custom/stageId");
      if (this._opts.onReorderStage) this._opts.onReorderStage(sid, idx + 1);
    });
  }

  /* ── Resize container to wrap all stage nodes ────────────────────────────── */

  _resizeContainer() {
    if (!this._graph || !this._pipelineContainerNodeId) return;
    const contEl = this._graph.getCell(this._pipelineContainerNodeId);
    if (!contEl) return;

    const stageEls = this._graph.getElements().filter(el => el.prop("custom/stageId"));
    if (!stageEls.length) return;

    const CONT_PAD_X = 28, CONT_PAD_Y = 14, CONT_HDR_H = 32;
    let minX = Infinity, minY = Infinity, maxX = 0, maxY = 0;
    stageEls.forEach(el => {
      const p = el.position();
      const s = el.size();
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x + s.width);
      maxY = Math.max(maxY, p.y + s.height);
    });

    const newX = minX - CONT_PAD_X;
    const newY = minY - CONT_PAD_Y - CONT_HDR_H;
    const newW = (maxX - minX) + CONT_PAD_X * 2;
    const newH = (maxY - minY) + CONT_PAD_Y * 2 + CONT_HDR_H;

    contEl.position(newX, newY);
    contEl.resize(newW, newH);
    contEl.attr("body/width",  newW);
    contEl.attr("body/height", newH);
    contEl.attr("fo/width",    newW);
    contEl.attr("fo/height",   newH);
  }

  /* ── Properties panel helpers ────────────────────────────────────────────── */

  _openProps(titleText, bodyHtml, footHtml) {
    const panelId = "pe-props-panel";
    let panel = document.getElementById(panelId);
    if (!panel) {
      panel = document.createElement("div");
      panel.id = panelId;
      panel.className = "pe-side-panel";
      panel.innerHTML = `
        <div class="pe-sp-overlay" id="pe-props-overlay"></div>
        <div class="pe-sp-drawer" id="pe-props-drawer">
          <div class="pe-sp-head">
            <span id="pe-props-panel-title" class="pe-sp-title">Properties</span>
            <button class="pe-sp-close" id="pe-props-panel-close">×</button>
          </div>
          <div class="pe-sp-body" id="pe-props-panel-body"></div>
          <div class="pe-sp-foot" id="pe-props-panel-foot" style="display:none"></div>
        </div>`;
      document.body.appendChild(panel);
      document.getElementById("pe-props-overlay").onclick     = () => this._closeProps();
      document.getElementById("pe-props-panel-close").onclick = () => this._closeProps();
    }
    document.getElementById("pe-props-panel-title").textContent = titleText;
    document.getElementById("pe-props-panel-body").innerHTML    = bodyHtml;
    const foot = document.getElementById("pe-props-panel-foot");
    if (footHtml) { foot.innerHTML = footHtml; foot.style.display = ""; }
    else          { foot.innerHTML = ""; foot.style.display = "none"; }
    panel.classList.add("open");
  }

  _closeProps() {
    const panel = document.getElementById("pe-props-panel");
    if (panel) panel.classList.remove("open");
  }

  _propBadge(text, color) {
    return `<span class="pe-prop-badge pe-prop-badge-${color}">${text}</span>`;
  }
  _propRow(label, valueHtml) {
    return `<div class="pe-prop-row"><span class="pe-prop-label">${label}</span><span class="pe-prop-value">${valueHtml}</span></div>`;
  }
  _propRowMono(label, value) {
    if (!value) return "";
    return `<div class="pe-prop-row"><span class="pe-prop-label">${label}</span><span class="pe-prop-value mono">${value.replace(/</g,"&lt;")}</span></div>`;
  }

  _showStageProps(stageId) {
    const stage = this._stages.find(s => s.id === stageId);
    if (!stage) return;
    const accent = peAccent(stage, this._stages.indexOf(stage));
    const tasks  = (stage.tasks||[]).slice().sort((a,b)=>a.order-b.order);
    const execMode  = stage.execution_mode || "sequential";
    const execBadge = execMode === "parallel"
      ? this._propBadge("⇉ parallel","indigo")
      : this._propBadge("→ sequential","slate");
    const condMap    = {always:"always",on_success:"on success",on_failure:"on failure",on_warning:"on warning"};
    const condColors = {always:"slate",on_success:"green",on_failure:"red",on_warning:"amber"};
    const cond       = stage.run_condition || "always";
    const condBadge  = this._propBadge(condMap[cond]||cond, condColors[cond]||"slate");
    const protBadge  = stage.is_protected ? this._propBadge("🔒 protected","amber") : "";
    const eg = stage.entry_gate||{}, xg = stage.exit_gate||{};
    let gateRows = "";
    if (eg.enabled||xg.enabled) {
      gateRows = `<hr class="pe-prop-divider"><div class="pe-prop-section">Gates</div>`;
      if (eg.enabled) gateRows += this._propRow("Entry gate", this._propBadge("⊘ enabled","amber"));
      if (xg.enabled) gateRows += this._propRow("Exit gate",  this._propBadge("✓ enabled","green"));
    }
    const accentDot = `<span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:${accent};vertical-align:middle;margin-right:4px"></span>${accent}`;
    const bodyHtml = `
      <div class="pe-props-object-name" style="border-left:3px solid ${accent};padding-left:8px">${stage.name}</div>
      ${this._propRow("Order", `<b style="color:#f1f5f9">#${stage.order}</b>`)}
      ${this._propRow("Execution", execBadge)}
      ${this._propRow("Run condition", condBadge)}
      ${protBadge ? this._propRow("Protection", protBadge) : ""}
      ${this._propRow("Accent", accentDot)}
      ${stage.container_image ? this._propRow("Container", `<code style="font-size:11px;color:#a5f3fc;background:#0f172a;padding:2px 5px;border-radius:4px">${stage.container_image}</code>`) : ""}
      ${stage.run_language    ? this._propRow("Language", stage.run_language) : ""}
      <hr class="pe-prop-divider">
      <div class="pe-prop-section">Tasks (${tasks.length})</div>
      ${tasks.map(t => {
        const ta = peTaskAccent(t);
        const k  = t.kind||"script";
        return `<div style="display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:1px solid #1e293b">
          <span style="color:${ta};font-size:13px">${PE_KIND_ICON[k]||"⚙"}</span>
          <span style="font-size:12px;color:#cbd5e1;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t.name}</span>
          <span style="font-size:10px;color:${ta};font-weight:700">${k!=="script"?k:(t.task_type||"")}</span>
        </div>`;
      }).join("")}
      ${gateRows}`;
    const footHtml = this._opts.readOnly ? "" : `
      <button class="pe-btn pe-btn-primary" style="flex:1;justify-content:center" onclick="window._pePropsEditStage&&window._pePropsEditStage('${stageId}')">✏ Edit Stage</button>
      <button class="pe-btn pe-btn-ghost"   style="flex:1;justify-content:center" onclick="window._pePropsAddTask&&window._pePropsAddTask('${stageId}')">＋ Add Task</button>`;
    window._pePropsEditStage = (sid) => { this._closeProps(); setTimeout(()=>{ if(this._opts.onEditStage) this._opts.onEditStage(sid); },50); };
    window._pePropsAddTask   = (sid) => { this._closeProps(); setTimeout(()=>{ if(this._opts.onAddTask)   this._opts.onAddTask(sid);   },50); };
    this._openProps("Stage Properties", bodyHtml, footHtml);
  }

  _showTaskProps(taskId, stageId) {
    const stage = this._stages.find(s => s.id === stageId);
    if (!stage) return;
    const task = (stage.tasks||[]).find(t => t.id === taskId);
    if (!task) return;
    const ta   = peTaskAccent(task);
    const kind = task.kind||"script";
    const kindBadge  = this._propBadge(`${PE_KIND_ICON[kind]||"⚙"} ${kind}`, {gate:"amber",approval:"purple",script:"slate"}[kind]||"slate");
    const condColors = {always:"slate",on_success:"green",on_failure:"red",on_warning:"amber"};
    const condMap    = {always:"always",on_success:"on success",on_failure:"on failure",on_warning:"on warning"};
    const cond       = task.run_condition||"always";
    const condBadge  = this._propBadge(condMap[cond]||cond, condColors[cond]||"slate");
    const errBadge   = this._propBadge(task.on_error||"fail", {fail:"red",warn:"amber",continue:"slate"}[task.on_error]||"red");
    const execBadge  = (task.execution_mode==="parallel") ? this._propBadge("⇉ parallel","indigo") : this._propBadge("→ sequential","slate");
    const reqBadge   = task.is_required ? this._propBadge("★ required","amber") : this._propBadge("optional","slate");
    let kindSpecific = "";
    if (kind === "gate") {
      kindSpecific = `<hr class="pe-prop-divider"><div class="pe-prop-section">Gate</div>
        ${this._propRow("Language", task.gate_language||"bash")}
        ${task.gate_script ? this._propRowMono("Script", task.gate_script.slice(0,200)+(task.gate_script.length>200?"\n…":"")) : ""}`;
    } else if (kind === "approval") {
      const approvers = (typeof task.approval_approvers==="string" ? JSON.parse(task.approval_approvers||"[]") : task.approval_approvers)||[];
      kindSpecific = `<hr class="pe-prop-divider"><div class="pe-prop-section">Approval</div>
        ${this._propRow("Required count", task.approval_required_count===0?"all":String(task.approval_required_count))}
        ${task.approval_timeout ? this._propRow("Timeout", task.approval_timeout+"s") : ""}
        <div class="pe-prop-row"><span class="pe-prop-label">Approvers</span><div style="margin-top:3px">${approvers.map(a=>`<div style="font-size:12px;color:#cbd5e1;padding:2px 0"><span style="font-size:10px;color:#a78bfa;font-weight:700;background:#8b5cf222;padding:1px 5px;border-radius:4px">${a.type}</span> ${a.ref}</div>`).join("")||"<span style='color:#475569;font-size:11px'>none configured</span>"}</div></div>`;
    } else {
      kindSpecific = `${this._propRow("Language", task.run_language||"bash")}
        ${task.run_code ? this._propRowMono("Script", task.run_code.slice(0,200)+(task.run_code.length>200?"\n…":"")) : ""}`;
    }
    const bodyHtml = `
      <div class="pe-props-object-name" style="border-left:3px solid ${ta};padding-left:8px">${task.name}</div>
      ${task.description ? `<div style="font-size:12px;color:#64748b;line-height:1.5;margin-bottom:4px">${task.description}</div>` : ""}
      ${this._propRow("Kind", kindBadge)}
      ${this._propRow("Execution", execBadge)}
      ${this._propRow("Run condition", condBadge)}
      ${this._propRow("On error", errBadge)}
      ${this._propRow("Required", reqBadge)}
      ${this._propRow("Timeout", (task.timeout||300)+"s")}
      ${kindSpecific}`;
    const footHtml = this._opts.readOnly ? "" : `
      <button class="pe-btn pe-btn-primary" style="flex:1;justify-content:center" onclick="window._pePropsEditTask&&window._pePropsEditTask('${taskId}','${stageId}')">✏ Edit Task</button>`;
    window._pePropsEditTask = (tid, sid) => { this._closeProps(); setTimeout(()=>{ if(this._opts.onEditTask) this._opts.onEditTask(tid,sid); },50); };
    this._openProps("Task Properties", bodyHtml, footHtml);
  }
}

/* ── Side Panel ──────────────────────────────────────────────────────────────── */

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
      this._el      = document.getElementById("pe-side-panel");
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
          <button class="pe-btn pe-btn-ghost"   id="pe-sp-cancel">Cancel</button>
          <button class="pe-btn pe-btn-primary"  id="pe-sp-save">Save Changes</button>
        </div>
        <div class="pe-sp-error" id="pe-sp-error" style="display:none"></div>
      </div>`;
    document.body.appendChild(el);
    this._el      = el;
    this._titleEl = el.querySelector("#pe-sp-title");
    this._bodyEl  = el.querySelector("#pe-sp-body");
    this._saveBtn = el.querySelector("#pe-sp-save");
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
    setTimeout(() => {
      const inp = this._bodyEl.querySelector("input,select,textarea");
      if (inp) inp.focus();
    }, 220);
  }

  close() { this._el && this._el.classList.remove("open"); }

  error(msg) {
    const e = document.getElementById("pe-sp-error");
    if (!e) return;
    e.textContent   = msg;
    e.style.display = msg ? "block" : "none";
  }

  clearError() { this.error(""); }

  setSaving(saving) {
    if (this._saveBtn) {
      this._saveBtn.disabled    = saving;
      this._saveBtn.textContent = saving ? "Saving…" : (this._saveBtn._label || "Save Changes");
    }
  }
}

/* ── Globals ─────────────────────────────────────────────────────────────────── */
window.PipelineEditor    = PipelineEditor;
window.PipelineSidePanel = PipelineSidePanel;
