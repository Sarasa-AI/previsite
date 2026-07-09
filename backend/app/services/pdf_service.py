"""Clinical patient report PDF generation using ReportLab."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.intake import ClinicalSummary, MedicalOverview

PLACEHOLDER = "ثبت نشده"
EMPTY = "—"

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
FONT_REGULAR = "Vazirmatn"
FONT_BOLD = "Vazirmatn-Bold"
_FONTS_REGISTERED = False


def _register_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, FONT_DIR / "Vazirmatn-Regular.ttf"))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, FONT_DIR / "Vazirmatn-Bold.ttf"))
    pdfmetrics.registerFontFamily(FONT_REGULAR, normal=FONT_REGULAR, bold=FONT_BOLD)
    _FONTS_REGISTERED = True


def reshape_persian_text(text: str) -> str:
    if not text:
        return text
    return get_display(arabic_reshaper.reshape(text))


def _pdf_text(value: str) -> str:
    return reshape_persian_text(escape(value))


def _safe_text(value: str | None, *, placeholder: str = PLACEHOLDER) -> str:
    text = (value or "").strip()
    return _pdf_text(text) if text else reshape_persian_text(escape(placeholder))


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Heading1"],
            fontName=FONT_REGULAR,
            fontSize=16,
            leading=20,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
        ),
        "section": ParagraphStyle(
            "SectionTitle",
            parent=base["Heading2"],
            fontName=FONT_REGULAR,
            fontSize=12,
            leading=16,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#0f766e"),
        ),
        "body": ParagraphStyle(
            "BodyText",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=14,
            wordWrap="CJK",
        ),
        "label": ParagraphStyle(
            "LabelText",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748b"),
        ),
        "mono": ParagraphStyle(
            "MonoText",
            parent=base["Code"],
            fontName=FONT_REGULAR,
            fontSize=8,
            leading=11,
            wordWrap="CJK",
        ),
        "highlight": ParagraphStyle(
            "HighlightText",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=14,
            wordWrap="CJK",
            backColor=colors.HexColor("#fef3c7"),
            borderPadding=6,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=12,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=12,
            wordWrap="CJK",
        ),
    }


def _section_title(styles: dict[str, ParagraphStyle], text: str) -> Paragraph:
    return Paragraph(escape(text), styles["section"])


def _text_block(styles: dict[str, ParagraphStyle], label: str, value: str | None) -> list:
    return [
        Paragraph(f"<b>{escape(label)}</b>", styles["label"]),
        Paragraph(_safe_text(value), styles["body"]),
        Spacer(1, 0.15 * cm),
    ]


def _bullet_list(styles: dict[str, ParagraphStyle], items: list[str]) -> Paragraph:
    if not items:
        return Paragraph(_safe_text(None), styles["body"])
    bullets = "<br/>".join(f"• {_safe_text(item, placeholder=EMPTY)}" for item in items)
    return Paragraph(bullets, styles["body"])


def _paragraph_table(
    styles: dict[str, ParagraphStyle],
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float],
) -> Table:
    header_cells = [Paragraph(escape(h), styles["table_header"]) for h in headers]
    body_rows = [
        [Paragraph(_safe_text(cell, placeholder=EMPTY), styles["table_cell"]) for cell in row]
        for row in rows
    ]
    table = Table([header_cells, *body_rows], colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _highlight_box(styles: dict[str, ParagraphStyle], text: str | None) -> Table:
    content = Paragraph(_safe_text(text), styles["highlight"])
    table = Table([[content]], colWidths=[17 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#f59e0b")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _build_header(styles: dict[str, ParagraphStyle], session_data: dict[str, Any]) -> list:
    clinic_name = session_data.get("clinic_name") or "PreVisit MVP"
    patient_name = session_data.get("patient_name") or EMPTY
    report_date = session_data.get("report_date") or EMPTY
    session_id = session_data.get("session_id") or EMPTY

    return [
        Paragraph(f"<b>{_pdf_text(str(clinic_name))}</b>", styles["title"]),
        Paragraph(
            f"Patient: <b>{_pdf_text(str(patient_name))}</b> &nbsp;|&nbsp; "
            f"Date: {_pdf_text(str(report_date))} &nbsp;|&nbsp; "
            f"Session ID: {_pdf_text(str(session_id))}",
            styles["subtitle"],
        ),
        Spacer(1, 0.4 * cm),
    ]


def _build_clinical_summary_section(
    styles: dict[str, ParagraphStyle],
    clinical_summary: ClinicalSummary | None,
) -> list:
    flowables: list = [_section_title(styles, "Chief Complaint & HPI Summary")]

    if not clinical_summary:
        flowables.append(Paragraph(_safe_text(None), styles["body"]))
        flowables.append(Spacer(1, 0.2 * cm))
        return flowables

    flowables.extend(_text_block(styles, "Chief Complaint (CC)", clinical_summary.chief_complaint))
    flowables.extend(_text_block(styles, "HPI Narrative Summary", clinical_summary.hpi_summary))
    return flowables


def _build_clinical_data_section(
    styles: dict[str, ParagraphStyle],
    clinical_summary: ClinicalSummary | None,
) -> list:
    flowables: list = [_section_title(styles, "Clinical Data")]

    positives = clinical_summary.pertinent_positives if clinical_summary else []
    negatives = clinical_summary.pertinent_negatives if clinical_summary else []
    red_flags = clinical_summary.red_flags if clinical_summary else []

    flowables.append(Paragraph("<b>Positives</b>", styles["label"]))
    flowables.append(_bullet_list(styles, positives))
    flowables.append(Spacer(1, 0.15 * cm))

    flowables.append(Paragraph("<b>Negatives</b>", styles["label"]))
    flowables.append(_bullet_list(styles, negatives))
    flowables.append(Spacer(1, 0.15 * cm))

    flowables.append(Paragraph("<b>Red Flags</b>", styles["label"]))
    flowables.append(_bullet_list(styles, red_flags))
    flowables.append(Spacer(1, 0.2 * cm))

    return flowables


def _build_medical_overview_section(
    styles: dict[str, ParagraphStyle],
    medical_overview: MedicalOverview,
) -> list:
    flowables: list = [_section_title(styles, "Medical Overview")]

    flowables.extend(_text_block(styles, "Allergies", medical_overview.allergies))
    flowables.extend(_text_block(styles, "Surgical History", medical_overview.surgical_history))
    flowables.extend(_text_block(styles, "Family History", medical_overview.family_history))

    if medical_overview.chronic_conditions:
        rows = [
            [condition.name, condition.duration or EMPTY]
            for condition in medical_overview.chronic_conditions
        ]
        flowables.append(Paragraph("<b>Chronic Conditions</b>", styles["label"]))
        flowables.append(
            _paragraph_table(
                styles,
                ["Condition", "Duration"],
                rows,
                [10 * cm, 7 * cm],
            )
        )
        flowables.append(Spacer(1, 0.2 * cm))
    else:
        flowables.extend(_text_block(styles, "Chronic Conditions", None))

    return flowables


def _build_medications_section(
    styles: dict[str, ParagraphStyle],
    medical_overview: MedicalOverview,
) -> list:
    flowables: list = [_section_title(styles, "Current Medications")]

    if not medical_overview.current_medications:
        flowables.append(Paragraph(_safe_text(None), styles["body"]))
        flowables.append(Spacer(1, 0.2 * cm))
        return flowables

    rows = [
        [
            med.name or EMPTY,
            med.amount or EMPTY,
            med.frequency or EMPTY,
        ]
        for med in medical_overview.current_medications
    ]
    flowables.append(
        _paragraph_table(
            styles,
            ["Name", "Amount", "Frequency"],
            rows,
            [7 * cm, 5 * cm, 5 * cm],
        )
    )
    flowables.append(Spacer(1, 0.2 * cm))
    return flowables


def _build_lab_results_section(
    styles: dict[str, ParagraphStyle],
    medical_overview: MedicalOverview,
) -> list:
    flowables: list = [_section_title(styles, "Lab Results")]

    if not medical_overview.lab_results:
        flowables.append(Paragraph(_safe_text(None), styles["body"]))
        flowables.append(Spacer(1, 0.2 * cm))
        return flowables

    rows = [
        [lab.name or EMPTY, lab.extracted_data or EMPTY]
        for lab in medical_overview.lab_results
    ]
    flowables.append(
        _paragraph_table(
            styles,
            ["Test", "Extracted Values (OCR)"],
            rows,
            [5 * cm, 12 * cm],
        )
    )
    flowables.append(Spacer(1, 0.2 * cm))
    return flowables


def _build_patient_questions_section(
    styles: dict[str, ParagraphStyle],
    medical_overview: MedicalOverview,
) -> list:
    flowables: list = [_section_title(styles, "Patient Questions & Notes")]
    flowables.append(_highlight_box(styles, medical_overview.patient_questions))
    flowables.append(Spacer(1, 0.2 * cm))
    return flowables


def generate_patient_report_pdf(session_data: dict, medical_overview: MedicalOverview) -> bytes:
    """Generate a printable clinical patient report PDF."""
    _register_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Patient Report {session_data.get('session_id', '')}",
    )

    styles = _build_styles()
    clinical_summary: ClinicalSummary | None = session_data.get("clinical_summary")

    flowables: list = []
    flowables.extend(_build_header(styles, session_data))
    flowables.extend(_build_clinical_summary_section(styles, clinical_summary))
    flowables.extend(_build_clinical_data_section(styles, clinical_summary))
    flowables.extend(_build_medical_overview_section(styles, medical_overview))
    flowables.extend(_build_medications_section(styles, medical_overview))
    flowables.extend(_build_lab_results_section(styles, medical_overview))
    flowables.extend(_build_patient_questions_section(styles, medical_overview))

    doc.build(flowables)
    return buffer.getvalue()
