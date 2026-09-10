"""
PDF Report Exporter using ReportLab.
Generates printable, executive-level Audit Finding & Risk Penetration Reports.
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from src.core.schemas import AnalysisReportResult


def export_report_to_pdf(report: AnalysisReportResult, output_path: Path) -> Path:
    """Generate structured PDF audit report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    # Try registering Chinese font from Windows Fonts directory
    font_name = "Helvetica"
    win_fonts = [
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\msyh.ttf",
        "C:\\Windows\\Fonts\\simhei.ttf",
        "C:\\Windows\\Fonts\\simsun.ttc"
    ]
    for wf in win_fonts:
        if os.path.exists(wf):
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", wf))
                font_name = "ChineseFont"
                break
            except Exception:
                pass

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="DocTitle",
        fontName=font_name,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1F497D"),
        alignment=1, # Center
        spaceAfter=15
    )
    h2_style = ParagraphStyle(
        name="DocH2",
        fontName=font_name,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1F497D"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        name="DocBody",
        fontName=font_name,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#262626")
    )
    body_bold = ParagraphStyle(
        name="DocBodyBold",
        fontName=font_name,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1F497D")
    )

    story = []

    # Title
    story.append(Paragraph(f"数智审计与舞弊穿透报告 - {report.company_name}", title_style))
    story.append(Paragraph(f"<b>综合风险评级:</b> {report.overall_risk_rating.value} | <b>执行插件:</b> {report.plugin_name} | <b>Beneish M-Score:</b> {report.beneish_m_score or 'N/A'}", body_style))
    story.append(Spacer(1, 10))

    # Executive Summary Box
    story.append(Paragraph("一、管理层与评审专家摘要 (Executive Summary)", h2_style))
    story.append(Paragraph(report.executive_summary, body_style))
    story.append(Spacer(1, 10))

    # Risk Findings Section
    story.append(Paragraph("二、重点风险与舞弊疑点清单 (Risk Findings)", h2_style))
    
    table_data = [
        [
            Paragraph("<b>编号/等级</b>", body_bold),
            Paragraph("<b>风险发现项与准则依据</b>", body_bold),
            Paragraph("<b>影响金额(元)</b>", body_bold),
            Paragraph("<b>证据链与建议程序</b>", body_bold)
        ]
    ]

    for f in report.findings:
        evidence_texts = "<br/>".join([f"• [{e.source_ref}] {e.detail}" for e in f.evidences])
        desc_text = f"<b>{f.title}</b><br/><i>依据: {f.accounting_standard}</i><br/>手法: {f.suspected_mechanism}"
        proc_text = f"<b>证据:</b><br/>{evidence_texts}<br/><b>建议程序:</b> {f.suggested_procedure}"
        
        table_data.append([
            Paragraph(f"<b>{f.finding_id}</b><br/>[{f.risk_level.value}]", body_style),
            Paragraph(desc_text, body_style),
            Paragraph(f"{f.impact_amount:,.2f}", body_style),
            Paragraph(proc_text, body_style)
        ])

    col_widths = [70, 160, 80, 210]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Workpapers Section
    if report.workpapers:
        story.append(Paragraph("三、实质性审计工作底稿概要 (Workpapers)", h2_style))
        for wp in report.workpapers:
            story.append(Paragraph(f"<b>底稿索引:</b> {wp.workpaper_id} - {wp.title} (抽样 {wp.sample_count} 笔, 异常金额: {wp.abnormal_amount:,.2f}元)", body_style))
            story.append(Paragraph(f"<b>底稿意见:</b> {wp.audit_opinion_summary}", body_style))
            story.append(Spacer(1, 4))

    doc.build(story)
    return output_path
