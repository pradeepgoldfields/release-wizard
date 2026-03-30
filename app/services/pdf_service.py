"""Renders audit reports as PDF using WeasyPrint + Jinja2 templates.

WeasyPrint requires GTK/Pango system libraries (available in the UBI container).
On Windows the import is deferred; PDF export will raise a clear error locally
rather than preventing the app from starting.
"""

from datetime import UTC, datetime
from pathlib import Path

from flask import current_app, render_template

TEMPLATE_NAME = "audit_report.html"


def export_audit_report_pdf(report: dict) -> bytes:
    """Render the audit report dict to a PDF and return raw bytes.

    Requires GTK/Pango libraries — available inside the UBI container but not
    on Windows. Raises RuntimeError with a helpful message if libraries are absent.
    """
    try:
        from weasyprint import HTML
    except OSError as exc:
        raise RuntimeError(
            "WeasyPrint system libraries (GTK/Pango) are not available on this host. "
            "PDF export is supported inside the UBI container. "
            f"Original error: {exc}"
        ) from exc

    html_content = render_template(TEMPLATE_NAME, report=report)
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes


def save_audit_pdf(release_id: str, pdf_bytes: bytes) -> str:
    """Persist PDF to the configured storage path and return the file path."""
    storage_path = Path(current_app.config["AUDIT_STORAGE_PATH"])
    storage_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{release_id}_{timestamp}.pdf"
    file_path = storage_path / filename

    file_path.write_bytes(pdf_bytes)
    return str(file_path)
