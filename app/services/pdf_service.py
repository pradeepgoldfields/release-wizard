"""Renders audit reports as PDF using ReportLab.

ReportLab is pure Python, supports full Unicode, and works on Windows
and inside the UBI container without native libraries.
"""

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from flask import current_app, render_template

# ── Colour palette ────────────────────────────────────────────────────────────

_CONF_COLOR = {
    "confirmed": (22 / 255, 163 / 255, 74 / 255),
    "partial": (234 / 255, 88 / 255, 12 / 255),
    "manual": (124 / 255, 58 / 255, 237 / 255),
    "not_met": (220 / 255, 38 / 255, 38 / 255),
}
_CONF_LABEL = {
    "confirmed": "CONFIRMED",
    "partial": "PARTIAL",
    "manual": "MANUAL REVIEW",
    "not_met": "NOT MET",
}

# ── Helper: RGB tuple for ReportLab (0–1 range) ───────────────────────────────

_HEADER_BG = (26 / 255, 58 / 255, 92 / 255)
_HEADER_FG = (1.0, 1.0, 1.0)
_GROUP_BG = (236 / 255, 240 / 255, 248 / 255)
_GROUP_FG = (26 / 255, 58 / 255, 92 / 255)
_META_FG = (80 / 255, 80 / 255, 80 / 255)
_BODY_FG = (30 / 255, 30 / 255, 30 / 255)
_LIGHT_FG = (110 / 255, 110 / 255, 110 / 255)
_DIM_FG = (130 / 255, 130 / 255, 130 / 255)
_EV_FG = (60 / 255, 60 / 255, 60 / 255)
_TASK_FG = (80 / 255, 80 / 255, 80 / 255)
_LOG_FG = (120 / 255, 120 / 255, 120 / 255)
_DIVIDER = (220 / 255, 220 / 255, 220 / 255)
_NONE_FG = (170 / 255, 170 / 255, 170 / 255)
_WHITE = (1.0, 1.0, 1.0)


# ── Main export function ──────────────────────────────────────────────────────


def export_audit_report_pdf(report: dict) -> bytes:
    """Render an ISAE/ACF audit report dict to PDF bytes using ReportLab.

    Works on Windows and inside the UBI container — no native libs required.
    """
    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.lib.enums import TA_CENTER  # noqa: PLC0415
    from reportlab.lib.pagesizes import A4  # noqa: PLC0415
    from reportlab.lib.styles import ParagraphStyle  # noqa: PLC0415
    from reportlab.lib.units import mm  # noqa: PLC0415
    from reportlab.platypus import (  # noqa: PLC0415
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    framework = report.get("framework", "Audit")
    pipeline = report.get("pipeline_name", "—")
    run_id = report.get("run_id", "—")
    run_status = report.get("run_status", "—")
    generated_at = report.get("generated_at", datetime.now(UTC).isoformat())
    overall = report.get("overall_rating", "")
    summary = report.get("summary", {})

    # Normalise groups (ISAE: "categories", ACF: "domains", fallback: "controls")
    groups: list[dict] = []
    if report.get("categories"):
        for key, cat in report["categories"].items():
            groups.append(
                {"group_name": cat.get("label") or key, "controls": cat.get("controls", [])}
            )
    elif report.get("domains"):
        for domain_name, dom in report["domains"].items():
            groups.append({"group_name": domain_name, "controls": dom.get("controls", [])})
    else:
        controls = report.get("controls", [])
        if controls:
            groups = [{"group_name": "Controls", "controls": controls}]

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    # ── Styles ────────────────────────────────────────────────────────────────
    def _style(name, **kw) -> ParagraphStyle:
        defaults = dict(
            fontName="Helvetica", fontSize=9, leading=12, textColor=colors.black, spaceAfter=2
        )
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    s_title = _style(
        "title", fontName="Helvetica-Bold", fontSize=16, textColor=colors.white, alignment=TA_CENTER
    )
    s_sub = _style("sub", fontSize=9, textColor=colors.white, alignment=TA_CENTER)
    s_meta = _style("meta", fontSize=8, textColor=colors.Color(*_META_FG))
    s_gen = _style(
        "gen", fontName="Helvetica-Oblique", fontSize=7, textColor=colors.Color(*_META_FG)
    )
    s_group = _style(
        "group", fontName="Helvetica-Bold", fontSize=10, textColor=colors.Color(*_GROUP_FG)
    )
    s_ctrl_id = _style(
        "ctrl_id", fontName="Helvetica-Bold", fontSize=9, textColor=colors.Color(*_BODY_FG)
    )
    s_ctrl_title = _style(
        "ctrl_title", fontName="Helvetica-Bold", fontSize=9, textColor=colors.Color(*_BODY_FG)
    )
    s_desc = _style("desc", fontSize=8, textColor=colors.Color(*_LIGHT_FG))
    s_dim = _style(
        "dim", fontName="Helvetica-Oblique", fontSize=7, textColor=colors.Color(*_DIM_FG)
    )
    s_ev = _style("ev", fontSize=8, textColor=colors.Color(*_EV_FG))
    s_task = _style("task", fontSize=8, textColor=colors.Color(*_TASK_FG))
    s_log = _style("log", fontName="Courier", fontSize=7, textColor=colors.Color(*_LOG_FG))
    s_none = _style(
        "none", fontName="Helvetica-Oblique", fontSize=8, textColor=colors.Color(*_NONE_FG)
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    header_data = [[Paragraph("Compliance Audit Report", s_title)], [Paragraph(framework, s_sub)]]
    header_table = Table(header_data, colWidths=[180 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.Color(*_HEADER_BG)),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))

    # ── Meta line ─────────────────────────────────────────────────────────────
    story.append(
        Paragraph(
            f"Pipeline: {pipeline} &nbsp; | &nbsp; Run: {run_id} &nbsp; | &nbsp; Status: {run_status} &nbsp; | &nbsp; Overall: {overall}",
            s_meta,
        )
    )
    story.append(Paragraph(f"Generated: {generated_at}", s_gen))
    story.append(Spacer(1, 4 * mm))

    # ── Scorecard ─────────────────────────────────────────────────────────────
    total = summary.get("total", 0)
    confirmed = summary.get("confirmed", 0)
    partial = summary.get("partial", 0)
    not_met = summary.get("not_met", 0)
    manual = summary.get("manual", 0)

    scorecard_items = [
        ("Total Controls", str(total), _HEADER_BG),
        ("Confirmed", str(confirmed), (22 / 255, 163 / 255, 74 / 255)),
        ("Partial", str(partial), (234 / 255, 88 / 255, 12 / 255)),
        ("Not Met", str(not_met), (220 / 255, 38 / 255, 38 / 255)),
        ("Manual Review", str(manual), (124 / 255, 58 / 255, 237 / 255)),
    ]
    _s_val = _style(
        "sc_val",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    _s_lbl = _style("sc_lbl", fontSize=7, textColor=colors.white, alignment=TA_CENTER)

    sc_cells = [
        [Paragraph(v, _s_val) for _, v, _ in scorecard_items],
        [Paragraph(lbl, _s_lbl) for lbl, _, _ in scorecard_items],
    ]
    col_w = 180 * mm / len(scorecard_items)
    sc_table = Table(sc_cells, colWidths=[col_w] * len(scorecard_items))
    sc_styles = [
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]
    for col, (_, _, rgb) in enumerate(scorecard_items):
        sc_styles.append(("BACKGROUND", (col, 0), (col, -1), colors.Color(*rgb)))
    sc_table.setStyle(TableStyle(sc_styles))
    story.append(sc_table)
    story.append(Spacer(1, 6 * mm))

    # ── Control groups ────────────────────────────────────────────────────────
    for group in groups:
        group_name = group.get("group_name", "")
        controls = group.get("controls", [])
        if not controls:
            continue

        # Group header band
        gh_table = Table([[Paragraph(f"  {group_name}", s_group)]], colWidths=[180 * mm])
        gh_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.Color(*_GROUP_BG)),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(gh_table)
        story.append(Spacer(1, 2 * mm))

        for ctrl in controls:
            _render_control_rl(
                story, ctrl, s_ctrl_id, s_ctrl_title, s_desc, s_dim, s_ev, s_task, s_log, s_none
            )

        story.append(Spacer(1, 3 * mm))

    # ── Footer ────────────────────────────────────────────────────────────────
    s_footer = _style(
        "footer",
        fontName="Helvetica-Oblique",
        fontSize=7,
        textColor=colors.Color(*_NONE_FG),
        alignment=TA_CENTER,
    )
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.Color(*_DIVIDER)))
    story.append(Paragraph(f"Conduit  |  {generated_at}  |  {framework}", s_footer))

    doc.build(story)
    return buf.getvalue()


# ── Control renderer ──────────────────────────────────────────────────────────


def _render_control_rl(
    story, ctrl: dict, s_id, s_title, s_desc, s_dim, s_ev, s_task, s_log, s_none
) -> None:
    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.lib.enums import TA_CENTER  # noqa: PLC0415
    from reportlab.lib.styles import ParagraphStyle  # noqa: PLC0415
    from reportlab.lib.units import mm  # noqa: PLC0415
    from reportlab.platypus import HRFlowable, Paragraph, Table, TableStyle  # noqa: PLC0415

    ctrl_id = ctrl.get("id", "")
    title = ctrl.get("title", "")
    desc = ctrl.get("description", "")
    confidence = ctrl.get("confidence", "not_met")
    dim_score = ctrl.get("dim_score", 0)
    evidences = ctrl.get("evidences", [])
    artifacts = ctrl.get("artifacts", [])

    rgb = _CONF_COLOR.get(confidence, (0.6, 0.6, 0.6))
    badge = _CONF_LABEL.get(confidence, confidence.upper())

    # Title row: [ID | Title | Badge]
    _s_badge = ParagraphStyle(
        "badge", fontName="Helvetica-Bold", fontSize=7, textColor=colors.white, alignment=TA_CENTER
    )
    title_row = Table(
        [[Paragraph(ctrl_id, s_id), Paragraph(title[:100], s_title), Paragraph(badge, _s_badge)]],
        colWidths=[22 * mm, 130 * mm, 28 * mm],
    )
    title_row.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (2, 0), (2, 0), colors.Color(*rgb)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(title_row)

    if desc:
        story.append(Paragraph(desc[:220] + ("..." if len(desc) > 220 else ""), s_desc))

    if dim_score:
        story.append(Paragraph(f"Maturity dimension score: {dim_score}/3", s_dim))

    for ev in evidences[:4]:
        story.append(Paragraph(f"  \u2022 {ev[:120]}", s_ev))

    for art in artifacts[:3]:
        task_name = art.get("task_name", "")
        stage_name = art.get("stage_name", "")
        status = art.get("status", "")
        task_type = art.get("task_type", "")
        icon = "\u2713" if status in ("Succeeded", "Warning") else "\u2717"
        story.append(
            Paragraph(
                f"    {icon} {task_name}  [{stage_name} \u00b7 {task_type} \u00b7 {status}]", s_task
            )
        )
        for snip in art.get("log_snippets", [])[:2]:
            story.append(Paragraph(f"        {snip.strip()[:100]}", s_log))

    if not evidences and not artifacts:
        story.append(Paragraph("  No evidence found in this pipeline run", s_none))

    story.append(
        HRFlowable(width="100%", thickness=0.3, color=colors.Color(*_DIVIDER), spaceAfter=3 * mm)
    )


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
    filename = f"{release_id}_{timestamp}.pdf"
    file_path = storage_path / filename

    file_path.write_bytes(pdf_bytes)
    return str(file_path)
