"""Renders audit reports as PDF.

Uses fpdf2 (pure Python, works on Windows and in the UBI container).
WeasyPrint is kept as an optional fallback for HTML-based release reports
and requires GTK/Pango (available in the UBI container only).
"""

from datetime import UTC, datetime
from pathlib import Path

from flask import current_app, render_template


# ── Confidence badge colours ──────────────────────────────────────────────────

_CONF_COLOR = {
    "confirmed": (22, 163, 74),    # green
    "partial":   (234, 88, 12),    # orange
    "manual":    (124, 58, 237),   # purple
    "not_met":   (220, 38, 38),    # red
}
_CONF_LABEL = {
    "confirmed": "CONFIRMED",
    "partial":   "PARTIAL",
    "manual":    "MANUAL REVIEW",
    "not_met":   "NOT MET",
}


# ── fpdf2 audit PDF ───────────────────────────────────────────────────────────

def export_audit_report_pdf(report: dict) -> bytes:
    """Render an ISAE/ACF audit report dict to PDF bytes using fpdf2.

    Works on Windows and inside the UBI container — no native libs required.
    """
    from fpdf import FPDF

    framework    = report.get("framework", "Audit")
    pipeline     = report.get("pipeline_name", "—")
    run_id       = report.get("run_id", "—")
    run_status   = report.get("run_status", "—")
    generated_at = report.get("generated_at", datetime.now(UTC).isoformat())
    overall      = report.get("overall_rating", "")
    summary      = report.get("summary", {})

    # ── Normalise groups ──────────────────────────────────────────────────────
    # ISAE returns "categories" dict; ACF returns "domains" dict.
    groups: list[dict] = []
    if report.get("categories"):
        for key, cat in report["categories"].items():
            groups.append({
                "group_name": cat.get("label") or key,
                "controls": cat.get("controls", []),
            })
    elif report.get("domains"):
        for domain_name, dom in report["domains"].items():
            groups.append({
                "group_name": domain_name,
                "controls": dom.get("controls", []),
            })
    else:
        controls = report.get("controls", [])
        if controls:
            groups = [{"group_name": "Controls", "controls": controls}]

    # ── Build PDF ─────────────────────────────────────────────────────────────
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # Header bar
    pdf.set_fill_color(26, 58, 92)
    pdf.rect(0, 0, 210, 28, style="F")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(8)
    pdf.cell(0, 8, "Compliance Audit Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, framework, ln=True, align="C")
    pdf.set_y(32)

    # Meta row
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5, f"Pipeline: {pipeline}   |   Run: {run_id}   |   Status: {run_status}   |   Overall: {overall}", ln=True)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f"Generated: {generated_at}", ln=True)
    pdf.ln(4)

    # Summary scorecard
    total     = summary.get("total", 0)
    confirmed = summary.get("confirmed", 0)
    partial   = summary.get("partial", 0)
    not_met   = summary.get("not_met", 0)
    manual    = summary.get("manual", 0)

    _scorecard(pdf, [
        ("Total Controls", str(total),     (26, 58, 92)),
        ("Confirmed",      str(confirmed),  (22, 163, 74)),
        ("Partial",        str(partial),    (234, 88, 12)),
        ("Not Met",        str(not_met),    (220, 38, 38)),
        ("Manual Review",  str(manual),     (124, 58, 237)),
    ])
    pdf.ln(6)

    # Control groups
    for group in groups:
        group_name = group.get("group_name", "")
        controls   = group.get("controls", [])
        if not controls:
            continue

        # Group header
        pdf.set_fill_color(236, 240, 248)
        pdf.set_text_color(26, 58, 92)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, f"  {group_name}", ln=True, fill=True)
        pdf.ln(2)

        for ctrl in controls:
            _render_control(pdf, ctrl)

        pdf.ln(3)

    # Footer
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(0, 6, f"Conduit  |  {generated_at}  |  {framework}", ln=True, align="C")

    return bytes(pdf.output())


# ── Control renderer ──────────────────────────────────────────────────────────

def _render_control(pdf, ctrl: dict) -> None:
    ctrl_id    = ctrl.get("id", "")
    title      = ctrl.get("title", "")
    desc       = ctrl.get("description", "")
    confidence = ctrl.get("confidence", "not_met")
    dim_score  = ctrl.get("dim_score", 0)
    evidences  = ctrl.get("evidences", [])   # list of human-readable strings
    artifacts  = ctrl.get("artifacts", [])   # list of structured task dicts

    r, g, b    = _CONF_COLOR.get(confidence, (150, 150, 150))
    badge      = _CONF_LABEL.get(confidence, confidence.upper())

    # Control title line
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 30, 30)
    id_w = 22
    pdf.cell(id_w, 6, ctrl_id, ln=False)

    # Title — remaining width minus badge width
    badge_w = 38
    title_w = 180 - id_w - badge_w
    title_text = title[:72] + ("…" if len(title) > 72 else "")
    pdf.cell(title_w, 6, title_text, ln=False)

    # Confidence badge (right-aligned)
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(badge_w, 6, badge, ln=True, fill=True, align="C")

    # Description (light grey, wrapped manually)
    if desc:
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(110, 110, 110)
        desc_short = desc[:180] + ("…" if len(desc) > 180 else "")
        pdf.multi_cell(0, 4, desc_short)

    # Maturity score indicator
    if dim_score:
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 4, f"  Maturity dimension score: {dim_score}/3", ln=True)

    # Evidence lines (strings from _score_control)
    if evidences:
        for ev in evidences[:4]:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(60, 60, 60)
            line = f"  • {ev}"
            if len(line) > 120:
                line = line[:117] + "…"
            pdf.cell(0, 5, line, ln=True)

    # Artifact task details
    if artifacts:
        for art in artifacts[:3]:
            task_name  = art.get("task_name", "")
            stage_name = art.get("stage_name", "")
            status     = art.get("status", "")
            task_type  = art.get("task_type", "")
            icon = "✓" if status in ("Succeeded", "Warning") else "✗"

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(80, 80, 80)
            task_line = f"    {icon} {task_name}  [{stage_name} · {task_type} · {status}]"
            if len(task_line) > 120:
                task_line = task_line[:117] + "…"
            pdf.cell(0, 5, task_line, ln=True)

            # Log snippets
            for snip in art.get("log_snippets", [])[:2]:
                pdf.set_font("Courier", "", 7)
                pdf.set_text_color(120, 120, 120)
                snip_line = f"        {snip.strip()}"
                if len(snip_line) > 130:
                    snip_line = snip_line[:127] + "…"
                pdf.cell(0, 4, snip_line, ln=True)

    if not evidences and not artifacts:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(170, 170, 170)
        pdf.cell(0, 5, "  No evidence found in this pipeline run", ln=True)

    # Divider
    pdf.set_draw_color(220, 220, 220)
    pdf.line(15, pdf.get_y() + 1, 195, pdf.get_y() + 1)
    pdf.ln(4)


# ── Scorecard ─────────────────────────────────────────────────────────────────

def _scorecard(pdf, items: list[tuple]) -> None:
    """Render a row of stat boxes: [(label, value, (r,g,b)), ...]"""
    n    = len(items)
    w    = 180 // n
    x0   = pdf.get_x()
    y0   = pdf.get_y()

    for label, value, color in items:
        r, g, b = color
        # Box background
        pdf.set_fill_color(r, g, b)
        pdf.rect(pdf.get_x(), y0, w - 2, 18, style="F")
        # Value
        pdf.set_xy(pdf.get_x(), y0 + 1)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(w - 2, 8, value, ln=False, align="C")
        # Label
        pdf.set_xy(pdf.get_x() - (w - 2), y0 + 10)
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(w - 2, 5, label, ln=False, align="C")
        pdf.set_xy(pdf.get_x(), y0)

    pdf.set_y(y0 + 20)
    pdf.set_text_color(30, 30, 30)


# ── WeasyPrint release report PDF (container only) ────────────────────────────

def export_release_report_pdf(report: dict) -> bytes:
    """Render a release audit report to PDF using WeasyPrint (UBI container only).

    Raises RuntimeError with a helpful message if GTK/Pango libs are missing.
    """
    try:
        from weasyprint import HTML
    except OSError as exc:
        raise RuntimeError(
            "WeasyPrint system libraries (GTK/Pango) are not available on this host. "
            "PDF export is supported inside the UBI container. "
            f"Original error: {exc}"
        ) from exc

    html_content = render_template("audit_report.html", report=report)
    return HTML(string=html_content).write_pdf()


def save_audit_pdf(release_id: str, pdf_bytes: bytes) -> str:
    """Persist PDF to the configured storage path and return the file path."""
    storage_path = Path(current_app.config["AUDIT_STORAGE_PATH"])
    storage_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename  = f"{release_id}_{timestamp}.pdf"
    file_path = storage_path / filename

    file_path.write_bytes(pdf_bytes)
    return str(file_path)
