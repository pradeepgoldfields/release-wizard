/**
 * pipeline-run-canvas.js — JointJS-based live pipeline run visualiser
 *
 * Renders stage-run + task-run status onto a JointJS canvas, with:
 *  - Status-coloured node headers and task rows
 *  - Animated pulse ring on Running nodes
 *  - Click-to-scroll to detail cards below the canvas
 *  - Incremental update() method for live polling (no full re-render)
 *
 * Usage:
 *   const rc = new PipelineRunCanvas("prc-container", { runId });
 *   rc.load(runData, pipelineStages);   // initial render
 *   rc.update(newRunData);              // on each poll tick
 *   rc.destroy();
 */

/* ── Status colour map ────────────────────────────────────────────────────── */
const PRC_STATUS = {
  Succeeded:        { bg: "#052e16", border: "#16a34a", text: "#4ade80", dot: "#22c55e", badge: "#166534" },
  Failed:           { bg: "#2d0a0a", border: "#dc2626", text: "#f87171", dot: "#ef4444", badge: "#991b1b" },
  Running:          { bg: "#0c1a3a", border: "#3b82f6", text: "#60a5fa", dot: "#3b82f6", badge: "#1d4ed8" },
  Warning:          { bg: "#2d1f00", border: "#f59e0b", text: "#fbbf24", dot: "#f59e0b", badge: "#92400e" },
  Cancelled:        { bg: "#1a1a1a", border: "#475569", text: "#94a3b8", dot: "#64748b", badge: "#334155" },
  Pending:          { bg: "#0f172a", border: "#334155", text: "#64748b", dot: "#475569", badge: "#1e293b" },
  AwaitingApproval: { bg: "#1e0a3a", border: "#7c3aed", text: "#a78bfa", dot: "#8b5cf6", badge: "#5b21b6" },
  Skipped:          { bg: "#0f172a", border: "#1e293b", text: "#475569", dot: "#334155", badge: "#1e293b" },
};

function _prcStatus(s) {
  return PRC_STATUS[s] || PRC_STATUS.Pending;
}

/* ── Constants ────────────────────────────────────────────────────────────── */
const PRC_NODE_W   = 240;
const PRC_HDR_H    = 58;
const PRC_TASK_H   = 46;
const PRC_TASK_GAP = 6;
const PRC_PAD_TOP  = 8;
const PRC_PAD_BOT  = 10;
const PRC_SLOT_GAP = 80;
const PRC_PAR_GAP  = 16;

function _prcNodeHeight(tasks) {
  return PRC_HDR_H + PRC_PAD_TOP + tasks.length * (PRC_TASK_H + PRC_TASK_GAP) + PRC_PAD_BOT;
}

/* ── Stage node HTML ─────────────────────────────────────────────────────── */
function _prcStageHtml(sr, accent) {
  const sc = _prcStatus(sr.status);
  const statusIcon = {
    Succeeded: "✓", Failed: "✗", Running: "⟳", Warning: "⚠",
    Cancelled: "⊘", Pending: "○", AwaitingApproval: "✋", Skipped: "↷"
  }[sr.status] || "○";

  const pulseCls = sr.status === "Running" ? " prc-pulse" : "";

  const taskRows = (sr.task_runs || []).map(tr => {
    const tc    = _prcStatus(tr.status);
    const tName = (tr.task_name || "Task").length > 22
      ? (tr.task_name || "Task").slice(0, 20) + "…"
      : (tr.task_name || "Task");
    const tIcon = {
      Succeeded: "✓", Failed: "✗", Running: "⟳", Warning: "⚠",
      Cancelled: "⊘", AwaitingApproval: "✋", Skipped: "↷"
    }[tr.status] || "○";
    const dur = tr.started_at && tr.finished_at
      ? _prcFmtDur(tr.started_at, tr.finished_at)
      : (tr.status === "Running" ? "running…" : "");

    return `<div class="prc-task-row" data-task-run-id="${tr.id}"
        style="border-left:3px solid ${tc.dot};background:#f0f9ff;border-bottom:1px solid #dbeafe"
        onclick="event.stopPropagation();window.prcOpenDrawer&&prcOpenDrawer('${sr.id}','${tr.id}')">
      <span style="font-size:13px;color:${tc.dot};flex-shrink:0">${tIcon}</span>
      <span style="font-size:11px;font-weight:600;color:#1e293b;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${tName}</span>
      <span style="font-size:10px;color:${sc.badge === "#1e293b" ? "#64748b" : sc.text};background:${tc.dot}18;border:1px solid ${tc.dot}50;padding:1px 5px;border-radius:4px;white-space:nowrap">${tr.status}</span>
      ${dur ? `<span style="font-size:10px;color:#94a3b8;white-space:nowrap;margin-left:3px">${dur}</span>` : ""}
    </div>`;
  }).join("");

  const dur = sr.started_at && sr.finished_at
    ? _prcFmtDur(sr.started_at, sr.finished_at)
    : (sr.status === "Running" ? "running…" : "");

  return `
    <div class="prc-stage-node${pulseCls}" data-stage-run-id="${sr.id}"
      style="background:#eff6ff;border:3px solid ${accent};border-radius:10px;width:100%;height:100%;
             display:flex;flex-direction:column;overflow:hidden;box-shadow:0 2px 12px ${accent}30;cursor:pointer"
      onclick="window.prcOpenDrawer&&prcOpenDrawer('${sr.id}')">
      <!-- Accent top bar -->
      <div style="height:4px;background:${accent};flex-shrink:0"></div>
      <!-- Header -->
      <div style="padding:8px 10px 6px;display:flex;align-items:center;gap:7px;flex-shrink:0;border-bottom:2px solid ${accent}40;background:#dbeafe80">
        <span style="font-size:16px;color:${sc.dot};flex-shrink:0">${statusIcon}</span>
        <span style="font-size:13px;font-weight:700;color:#0f172a;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${
          (sr.stage_name || "Stage").length > 18 ? (sr.stage_name || "Stage").slice(0, 16) + "…" : (sr.stage_name || "Stage")
        }</span>
        <span style="font-size:10px;color:${sc.dot};background:${sc.dot}18;border:1px solid ${sc.dot}50;padding:2px 6px;border-radius:6px;font-weight:700;white-space:nowrap">${sr.status}</span>
        ${dur ? `<span style="font-size:10px;color:#64748b;white-space:nowrap">${dur}</span>` : ""}
      </div>
      <!-- Task rows -->
      <div style="flex:1;overflow:hidden;display:flex;flex-direction:column">
        ${taskRows || `<div style="padding:8px 10px;color:#94a3b8;font-size:11px">No tasks</div>`}
      </div>
    </div>`;
}

function _prcFmtDur(start, end) {
  if (!start || !end) return "";
  const s = Math.round((new Date(end) - new Date(start)) / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60), sec = s % 60;
  return sec ? `${m}m ${sec}s` : `${m}m`;
}

/* ── Ensure JointJS shape defined once ──────────────────────────────────── */
function _prcEnsureShapes() {
  if (window._prcShapesDefined) return;
  window._prcShapesDefined = true;

  if (typeof joint === "undefined") return;

  joint.shapes.prc = joint.shapes.prc || {};

  joint.shapes.prc.StageNode = joint.dia.Element.define(
    "prc.StageNode",
    {
      attrs: {
        root:  { pointerEvents: "visiblePainted" },
        body:  { fill: "transparent", stroke: "transparent", strokeWidth: 0, rx: 10, ry: 10 },
        fo:    { overflow: "visible" },
      },
    },
    {
      markup: [
        { tagName: "rect",          selector: "body" },
        { tagName: "foreignObject", selector: "fo"   },
      ],
    },
    {}
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   PipelineRunCanvas class
   ═══════════════════════════════════════════════════════════════════════════ */

class PipelineRunCanvas {
  constructor(containerId) {
    this._containerId = containerId;
    this._graph       = null;
    this._paper       = null;
    this._mounted     = false;
    this._nodeMap     = {};   // stageRunId → JointJS element id
    this._elemMap     = {};   // JointJS element id → element instance
    this._runData     = null;
    this._stages      = [];

    this._isFullscreen = false;

    // Pan state
    this._panning  = false;
    this._panStart = { x: 0, y: 0 };
    this._panOrig  = { x: 0, y: 0 };
    this._scale    = 1;
  }

  /* ── Public API ─────────────────────────────────────────────────────────── */

  load(runData, pipelineStages) {
    this._runData = runData;
    this._stages  = pipelineStages || [];
    if (!this._mounted) this._mount();
    this._render();
  }

  update(newRunData) {
    this._runData = newRunData;
    this._refreshNodes();
  }

  destroy() {
    if (this._paper) { this._paper.remove(); this._paper = null; }
    if (this._graph) { this._graph.clear();  this._graph = null; }
    this._mounted = false;
    this._nodeMap = {};
    this._elemMap = {};
    const el = document.getElementById(this._containerId);
    if (el) el.innerHTML = "";
  }

  /* ── Mount ──────────────────────────────────────────────────────────────── */

  _mount() {
    const container = document.getElementById(this._containerId);
    if (!container) return;

    const mountId = `prc-jj-${this._containerId}`;
    container.innerHTML = `
      <div class="prc-toolbar" id="prc-tb-${this._containerId}">
        <span class="prc-toolbar-label">⬡ Pipeline Run — click a stage or task for details</span>
        <div style="display:flex;gap:6px">
          <button class="pe-btn pe-btn-ghost" id="prc-fit-${this._containerId}" title="Fit view">⊞ Fit</button>
          <button class="pe-btn pe-btn-ghost" id="prc-zin-${this._containerId}">＋</button>
          <button class="pe-btn pe-btn-ghost" id="prc-zout-${this._containerId}">－</button>
          <button class="pe-btn pe-btn-ghost" id="prc-fs-${this._containerId}" title="Full page">⛶</button>
        </div>
      </div>
      <div class="prc-canvas-wrap">
        <div id="${mountId}" class="prc-jj-mount"></div>
      </div>`;

    if (typeof joint === "undefined") {
      container.innerHTML += `<div style="color:#ef4444;padding:16px;font-size:13px">JointJS library not loaded.</div>`;
      this._mounted = true;
      return;
    }

    _prcEnsureShapes();

    const mountEl = document.getElementById(mountId);
    const W = mountEl.offsetWidth  || 900;
    const H = mountEl.offsetHeight || 400;

    this._graph = new joint.dia.Graph({}, { cellNamespace: joint.shapes });

    this._paper = new joint.dia.Paper({
      el:            mountEl,
      model:         this._graph,
      width:         W,
      height:        H,
      background:    { color: "#ffffff" },
      gridSize:      20,
      drawGrid:      { name: "dot", args: { color: "#e2e8f0", thickness: 1 } },
      interactive:   false,   // nodes are not draggable in run canvas
      cellViewNamespace: joint.shapes,
    });

    /* ── Manual pan ──────────────────────────────────────────────────────── */
    this._paper.on("blank:pointerdown", (evt, x, y) => {
      this._panning  = true;
      this._panStart = { x: evt.clientX, y: evt.clientY };
      const t = this._paper.translate();
      this._panOrig  = { x: t.tx, y: t.ty };
      mountEl.style.cursor = "grabbing";
    });

    const onMove = (evt) => {
      if (!this._panning) return;
      const dx = evt.clientX - this._panStart.x;
      const dy = evt.clientY - this._panStart.y;
      this._paper.translate(this._panOrig.x + dx, this._panOrig.y + dy);
    };
    const onUp = () => {
      if (!this._panning) return;
      this._panning = false;
      mountEl.style.cursor = "";
    };
    mountEl.addEventListener("pointermove", onMove);
    mountEl.addEventListener("pointerup",   onUp);

    /* ── Wheel: pinch/ctrl = zoom, two-finger scroll = pan ──────────────── */
    mountEl.addEventListener("wheel", (evt) => {
      evt.preventDefault();
      if (evt.ctrlKey) {
        // Pinch-to-zoom or ctrl+scroll → zoom
        const factor   = 1 - Math.sign(evt.deltaY) * Math.min(Math.abs(evt.deltaY) * 0.003, 0.1);
        const newScale = Math.min(2.5, Math.max(0.2, this._scale * factor));
        if (newScale === this._scale) return;
        const rect = mountEl.getBoundingClientRect();
        this._scale = newScale;
        this._paper.scale(newScale, newScale, evt.clientX - rect.left, evt.clientY - rect.top);
      } else {
        // Two-finger trackpad scroll → pan
        const t = this._paper.translate();
        this._paper.translate(t.tx - evt.deltaX, t.ty - evt.deltaY);
        this._panOrig = this._paper.translate();
      }
    }, { passive: false });

    /* ── Toolbar buttons ─────────────────────────────────────────────────── */
    document.getElementById(`prc-fit-${this._containerId}`).onclick = () => {
      this._scale = 1;
      this._paper.scaleContentToFit({ padding: 40 });
      const s = this._paper.scale();
      this._scale = s.sx;
    };
    document.getElementById(`prc-zin-${this._containerId}`).onclick = () => {
      this._scale = Math.min(2.5, this._scale + 0.15);
      this._paper.scale(this._scale, this._scale);
    };
    document.getElementById(`prc-zout-${this._containerId}`).onclick = () => {
      this._scale = Math.max(0.2, this._scale - 0.15);
      this._paper.scale(this._scale, this._scale);
    };
    document.getElementById(`prc-fs-${this._containerId}`).onclick = () => {
      this._toggleFullscreen();
    };

    /* ── Esc exits fullscreen ────────────────────────────────────────────── */
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this._isFullscreen) this._exitFullscreen();
    });

    /* ── Resize observer ─────────────────────────────────────────────────── */
    if (window.ResizeObserver) {
      new ResizeObserver(() => {
        if (this._paper && mountEl.offsetWidth > 0)
          this._paper.setDimensions(mountEl.offsetWidth, mountEl.offsetHeight);
      }).observe(mountEl);
    }

    this._mounted = true;
  }

  /* ── Fullscreen ─────────────────────────────────────────────────────────── */

  _toggleFullscreen() {
    if (this._isFullscreen) { this._exitFullscreen(); return; }
    this._isFullscreen = true;

    const mountEl = document.getElementById(`prc-jj-${this._containerId}`);
    if (!mountEl) return;
    mountEl.classList.add("prc-jj-fullscreen");

    // Update button label
    const fsBtn = document.getElementById(`prc-fs-${this._containerId}`);
    if (fsBtn) fsBtn.textContent = "✕ Exit";

    // Floating exit toolbar
    const tb = document.createElement("div");
    tb.id = `prc-fs-tb-${this._containerId}`;
    tb.style.cssText = `position:fixed;top:14px;right:18px;z-index:10003;display:flex;gap:6px`;
    tb.innerHTML = `
      <button class="pe-btn pe-btn-ghost" style="background:#1e293b;color:#e2e8f0;border:1px solid #334155"
        onclick="document.getElementById('prc-fit-${this._containerId}').click()">⊞ Fit</button>
      <button class="pe-btn pe-btn-ghost" style="background:#1e293b;color:#e2e8f0;border:1px solid #334155"
        onclick="document.getElementById('prc-zin-${this._containerId}').click()">＋</button>
      <button class="pe-btn pe-btn-ghost" style="background:#1e293b;color:#e2e8f0;border:1px solid #334155"
        onclick="document.getElementById('prc-zout-${this._containerId}').click()">－</button>
      <button class="pe-btn pe-btn-ghost" style="background:#1e293b;color:#e2e8f0;border:1px solid #334155"
        onclick="document.getElementById('prc-fs-${this._containerId}').click()">✕ Exit</button>`;
    document.body.appendChild(tb);

    // Resize paper to fill screen
    requestAnimationFrame(() => {
      if (!this._paper) return;
      const w = window.innerWidth, h = window.innerHeight;
      this._paper.setDimensions(w, h);
      this._paper.scaleContentToFit({ padding: 60 });
      const s = this._paper.scale();
      this._scale = s.sx;
    });
  }

  _exitFullscreen() {
    this._isFullscreen = false;
    const mountEl = document.getElementById(`prc-jj-${this._containerId}`);
    if (mountEl) mountEl.classList.remove("prc-jj-fullscreen");

    const fsBtn = document.getElementById(`prc-fs-${this._containerId}`);
    if (fsBtn) fsBtn.textContent = "⛶";

    const tb = document.getElementById(`prc-fs-tb-${this._containerId}`);
    if (tb) tb.remove();

    // Restore paper dimensions
    requestAnimationFrame(() => {
      if (!this._paper) return;
      const mountEl2 = document.getElementById(`prc-jj-${this._containerId}`);
      if (mountEl2) {
        this._paper.setDimensions(mountEl2.offsetWidth || 900, mountEl2.offsetHeight || 400);
        this._paper.scaleContentToFit({ padding: 40 });
        const s = this._paper.scale();
        this._scale = s.sx;
      }
    });
  }

  /* ── Render ──────────────────────────────────────────────────────────────── */

  _render() {
    if (!this._graph || !this._runData) return;
    this._graph.clear();
    this._nodeMap = {};
    this._elemMap = {};

    const stageRuns = (this._runData.stage_runs || [])
      .slice()
      .sort((a, b) => (a.stage_order || 0) - (b.stage_order || 0));

    // Build accent map from pipeline stage definitions
    const accentMap = {};
    (this._stages || []).forEach(s => { accentMap[s.id] = s.accent_color; });

    // Group stage runs into sequential/parallel slots
    const slots = [];
    let i = 0;
    while (i < stageRuns.length) {
      const execMode = this._getExecMode(stageRuns[i]);
      if (execMode === "parallel") {
        const grp = [];
        while (i < stageRuns.length && this._getExecMode(stageRuns[i]) === "parallel") {
          grp.push(stageRuns[i++]);
        }
        slots.push({ type: "parallel", stageRuns: grp });
      } else {
        slots.push({ type: "sequential", sr: stageRuns[i++] });
      }
    }

    let curX = 40;
    const baseY = 40;
    const elements  = [];
    const links     = [];
    let prevElemIds = [];

    slots.forEach(slot => {
      if (slot.type === "sequential") {
        const sr     = slot.sr;
        const accent = accentMap[sr.stage_id] || _prcStatus(sr.status).dot;
        const nH     = Math.max(_prcNodeHeight(sr.task_runs || []), PRC_HDR_H + PRC_PAD_TOP + PRC_PAD_BOT + 20);
        const el     = this._makeNode(sr, accent, curX, baseY, PRC_NODE_W, nH);
        elements.push(el);
        this._nodeMap[sr.id]     = el.id;
        this._elemMap[el.id]     = el;
        prevElemIds.forEach(pid => links.push(this._makeLink(pid, el.id, false)));
        prevElemIds = [el.id];
        curX += PRC_NODE_W + PRC_SLOT_GAP;
      } else {
        const curElemIds = [];
        let rowY = baseY;
        slot.stageRuns.forEach(sr => {
          const accent = accentMap[sr.stage_id] || _prcStatus(sr.status).dot;
          const nH     = Math.max(_prcNodeHeight(sr.task_runs || []), PRC_HDR_H + PRC_PAD_TOP + PRC_PAD_BOT + 20);
          const el     = this._makeNode(sr, accent, curX, rowY, PRC_NODE_W, nH);
          elements.push(el);
          this._nodeMap[sr.id]   = el.id;
          this._elemMap[el.id]   = el;
          curElemIds.push(el.id);
          prevElemIds.forEach(pid => links.push(this._makeLink(pid, el.id, true)));
          rowY += nH + PRC_PAR_GAP;
        });
        prevElemIds = curElemIds;
        curX += PRC_NODE_W + PRC_SLOT_GAP;
      }
    });

    this._graph.addCells([...elements, ...links]);

    // Inject HTML into foreignObjects
    const injectHtml = () => {
      elements.forEach(el => {
        const html = el.prop("prcHtml");
        if (!html) return;
        const view = this._paper.findViewByModel(el);
        if (!view) return;
        const fo = view.el.querySelector("foreignObject");
        if (!fo) return;
        const ns = "http://www.w3.org/1999/xhtml";
        let body = fo.querySelector("div");
        if (!body) {
          body = document.createElementNS(ns, "div");
          body.setAttribute("xmlns", ns);
          body.style.cssText = "width:100%;height:100%;overflow:hidden;";
          fo.appendChild(body);
        }
        body.innerHTML = html;
      });
    };

    let _injected = false;
    const _injectOnce = () => { if (_injected) return; _injected = true; injectHtml(); };
    this._paper.once("render:done", _injectOnce);
    setTimeout(_injectOnce, 80);

    // Size the canvas to fit all nodes
    setTimeout(() => {
      if (!this._graph) return;
      const allCells = this._graph.getElements();
      if (!allCells.length) return;
      let maxX = 0, maxY = 0;
      allCells.forEach(el => {
        const p = el.position(), s = el.size();
        maxX = Math.max(maxX, p.x + s.width);
        maxY = Math.max(maxY, p.y + s.height);
      });
      const w = maxX + 80, h = maxY + 80;
      const mountEl = document.getElementById(`prc-jj-${this._containerId}`);
      if (mountEl) {
        mountEl.style.width    = w + "px";
        mountEl.style.height   = h + "px";
        mountEl.style.minWidth  = w + "px";
        mountEl.style.minHeight = h + "px";
        this._paper.setDimensions(w, h);
        if (mountEl.parentElement) {
          mountEl.parentElement.scrollLeft = 0;
          mountEl.parentElement.scrollTop  = 0;
        }
      }
    }, 80);
  }

  /* ── Incremental update (polling) ────────────────────────────────────────── */

  _refreshNodes() {
    if (!this._graph || !this._runData) return;
    const stageRuns = this._runData.stage_runs || [];
    const accentMap = {};
    (this._stages || []).forEach(s => { accentMap[s.id] = s.accent_color; });

    stageRuns.forEach(sr => {
      const elemId = this._nodeMap[sr.id];
      if (!elemId) return;
      const el = this._graph.getCell(elemId);
      if (!el) return;
      const view = this._paper.findViewByModel(el);
      if (!view) return;
      const fo = view.el.querySelector("foreignObject");
      if (!fo) return;
      const body = fo.querySelector("div");
      if (!body) return;
      const accent = accentMap[sr.stage_id] || _prcStatus(sr.status).dot;
      body.innerHTML = _prcStageHtml(sr, accent);
    });
  }

  /* ── Element / link factories ─────────────────────────────────────────────── */

  _makeNode(sr, accent, x, y, w, h) {
    const el = new joint.shapes.prc.StageNode({
      position: { x, y },
      size:     { width: w, height: h },
      z:        1,
      attrs: {
        body: { width: w, height: h },
        fo:   { width: w, height: h, x: 0, y: 0 },
      },
    });
    el.prop("prcHtml",    _prcStageHtml(sr, accent));
    el.prop("stageRunId", sr.id);
    return el;
  }

  _makeLink(sourceId, targetId, isParallel) {
    const color = isParallel ? "#4f46e5" : "#334155";
    return new joint.shapes.standard.Link({
      source: { id: sourceId, anchor: { name: "right"  } },
      target: { id: targetId, anchor: { name: "left"   } },
      z:      -1,
      router:    { name: "manhattan", args: { padding: 10 } },
      connector: { name: "rounded",   args: { radius: 6 } },
      attrs: {
        line: {
          stroke:               color,
          strokeWidth:          2,
          "stroke-dasharray":   "5 4",
          targetMarker: {
            type:   "path",
            d:      "M 10 -5 0 0 10 5 z",
            fill:   color,
            stroke: "none",
          },
        },
      },
    });
  }

  _getExecMode(sr) {
    const stageDef = (this._stages || []).find(s => s.id === sr.stage_id);
    return (stageDef && stageDef.execution_mode) || "sequential";
  }
}

/* ── CSS animation for Running nodes ─────────────────────────────────────────── */
(function _injectPrcStyles() {
  if (document.getElementById("prc-styles")) return;
  const s = document.createElement("style");
  s.id = "prc-styles";
  s.textContent = `
    @keyframes prc-pulse-ring {
      0%   { box-shadow: 0 0 0 0 #3b82f640; }
      70%  { box-shadow: 0 0 0 8px #3b82f600; }
      100% { box-shadow: 0 0 0 0 #3b82f600; }
    }
    .prc-stage-node.prc-pulse { animation: prc-pulse-ring 1.8s ease-out infinite; }
    .prc-task-row {
      display: flex; align-items: center; gap: 6px;
      padding: 6px 8px 6px 10px; cursor: pointer;
      transition: background 0.12s;
    }
    .prc-task-row:hover { filter: brightness(1.15); }
    .prc-toolbar {
      display: flex; align-items: center; justify-content: space-between;
      padding: 7px 12px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;
      flex-shrink: 0;
    }
    .prc-toolbar-label {
      font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.03em;
    }
    .prc-canvas-wrap {
      flex: 1; overflow-x: auto; overflow-y: auto; position: relative;
    }
    .prc-canvas-wrap::-webkit-scrollbar { height: 8px; width: 8px; }
    .prc-canvas-wrap::-webkit-scrollbar-track { background: #f1f5f9; }
    .prc-canvas-wrap::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
    .prc-jj-mount { width: 100%; height: 100%; min-width: 600px; min-height: 300px; }
    .prc-jj-mount.prc-jj-fullscreen {
      position: fixed !important; inset: 0 !important; z-index: 9999 !important;
      width: 100vw !important; height: 100vh !important;
      min-width: unset !important; min-height: unset !important;
      background: #0f172a;
    }
    .prc-outer {
      display: flex; flex-direction: row;
      border-radius: 10px; overflow: hidden;
      border: 1px solid #e2e8f0; background: #ffffff;
      box-shadow: 0 4px 24px #00000015;
      height: calc(100vh - 180px); min-height: 400px;
    }
    .prc-canvas-col {
      flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden;
    }
    /* ── Run drawer ── */
    .prc-drawer {
      width: 0; flex-shrink: 0; overflow: hidden;
      transition: width 0.25s ease;
      display: flex; flex-direction: column;
      border-left: 1px solid #e2e8f0; background: #ffffff;
    }
    .prc-drawer.open { width: 480px; }
    .prc-drawer-hdr {
      display: flex; align-items: center; justify-content: space-between;
      padding: 12px 16px; border-bottom: 1px solid #e2e8f0; flex-shrink: 0;
      background: #f8fafc;
    }
    .prc-drawer-hdr-title { font-size: 14px; font-weight: 700; color: #0f172a; }
    .prc-drawer-hdr-sub { font-size: 11px; color: #64748b; margin-top: 2px; }
    .prc-drawer-close {
      width: 28px; height: 28px; border-radius: 6px; border: none; background: #f1f5f9;
      color: #64748b; font-size: 16px; cursor: pointer; display: flex;
      align-items: center; justify-content: center; flex-shrink: 0;
    }
    .prc-drawer-close:hover { background: #e2e8f0; color: #0f172a; }
    .prc-drawer-body {
      flex: 1; overflow-y: auto; padding: 0;
    }
    .prc-drawer-section {
      border-bottom: 1px solid #f1f5f9; padding: 14px 16px;
    }
    .prc-drawer-section-title {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .06em; color: #94a3b8; margin-bottom: 10px;
    }
    .prc-task-item {
      border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px;
      overflow: hidden;
    }
    .prc-task-item-hdr {
      display: flex; align-items: center; gap: 8px; padding: 10px 12px;
      cursor: pointer; background: #f8fafc; border-bottom: 1px solid transparent;
    }
    .prc-task-item-hdr:hover { background: #f1f5f9; }
    .prc-task-item-hdr.active { background: #eff6ff; border-bottom: 1px solid #bfdbfe; }
    .prc-task-item-body { display: none; }
    .prc-task-item-body.open { display: block; }
    .prc-log-area {
      background: #0f172a; color: #e2e8f0; font-family: monospace;
      font-size: 12px; padding: 14px 16px; white-space: pre-wrap;
      word-break: break-all; max-height: 400px; overflow-y: auto;
      line-height: 1.6;
    }
    .prc-log-area::-webkit-scrollbar { width: 6px; }
    .prc-log-area::-webkit-scrollbar-track { background: #1e293b; }
    .prc-log-area::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
    .prc-approval-panel {
      background: linear-gradient(135deg,#f5f3ff,#eff6ff);
      border-top: 2px solid #7c3aed; padding: 14px 16px;
    }
    .prc-ctx-tabs { display: flex; gap: 0; border-bottom: 1px solid #e2e8f0; padding: 0 12px; }
    .prc-ctx-tab {
      padding: 8px 14px; font-size: 12px; font-weight: 500; color: #64748b;
      border: none; background: none; cursor: pointer;
      border-bottom: 2px solid transparent; margin-bottom: -1px;
    }
    .prc-ctx-tab.active { color: #3b82f6; border-bottom-color: #3b82f6; font-weight: 600; }
    .prc-ctx-pane { display: none; padding: 12px 16px; }
    .prc-ctx-pane.active { display: block; }
    .prc-ctx-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .prc-ctx-table td { padding: 4px 8px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
    .prc-ctx-table td:first-child { font-family: monospace; color: #6366f1; width: 45%; word-break: break-all; }
    .prc-ctx-table td:last-child { color: #334155; word-break: break-all; }
    .prc-gate-banner {
      padding: 8px 14px; font-size: 12px; font-weight: 600;
      display: flex; align-items: center; gap: 10px;
    }
  `;
  document.head.appendChild(s);
})();

window.PipelineRunCanvas = PipelineRunCanvas;
