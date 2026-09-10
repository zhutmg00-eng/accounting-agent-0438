"""
PDF Report Exporter using ReportLab.
Generates printable, executive-level Audit Finding & Risk Penetration Reports
with clear Execution Mode identification and Three-Layer Evidence Trail (Issue 5).
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from src.core.schemas import AnalysisReportResult, ExecutionMode


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
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#1F497D"),
        alignment=1, # Center
        spaceAfter=12
    )
    h2_style = ParagraphStyle(
        name="DocH2",
        fontName=font_name,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1F497D"),
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        name="DocBody",
        fontName=font_name,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#262626")
    )
    body_bold = ParagraphStyle(
        name="DocBodyBold",
        fontName=font_name,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1F497D")
    )
    badge_style = ParagraphStyle(
        name="BadgeStyle",
        fontName=font_name,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#B91C1C")
    )

    story = []

    # Title
    story.append(Paragraph(f"数智审计与舞弊穿透报告 - {report.company_name}", title_style))
    
    # Mode badge
    mode_str = "🟢 实时在线推理 (DeepSeek-V3)" if report.execution_mode in (ExecutionMode.ONLINE, ExecutionMode.STRICT_ONLINE) and not report.fallback_occurred else "🟡 离线确定性模拟演示 (Demo Mode)"
    story.append(Paragraph(
        f"<b>综合风险评级:</b> {report.overall_risk_rating.value} | "
        f"<b>Beneish M-Score:</b> {report.beneish_m_score or 'N/A'} | "
        f"<b>执行模式:</b> {mode_str}", 
        body_style
    ))
    story.append(Spacer(1, 8))

    # Executive Summary Box
    story.append(Paragraph("一、管理层与评审专家摘要 (Executive Summary)", h2_style))
    story.append(Paragraph(report.executive_summary, body_style))
    story.append(Spacer(1, 8))

    # Risk Findings Section with Evidence Trail
    story.append(Paragraph("二、重点风险清单与三层证据链 (Risk Findings & Evidence Trail)", h2_style))
    
    table_data = [
        [
            Paragraph("<b>发现项/等级</b>", body_bold),
            Paragraph("<b>涉案金额</b>", body_bold),
            Paragraph("<b>【确定性事实】与【模型推断】</b>", body_bold),
            Paragraph("<b>待人工复核/审计建议</b>", body_bold)
        ]
    ]

    for f in report.findings:
        col1 = f"<b>{f.finding_id}</b><br/>{f.title}<br/><i>[{f.risk_level.value}]</i>"
        col2 = f"¥{f.impact_amount:,.2f}"
        
        evidence_text = f"<b>[客观事实]</b>: {f.rule_evidence or f.suspected_mechanism}<br/><b>[模型研判]</b>: {f.model_explanation or f.accounting_standard}"
        remedy_text = f"<b>[人工复核]</b>: {f.human_verification_flag}<br/><b>[建议程序]</b>: {f.suggested_procedure}"

        table_data.append([
            Paragraph(col1, body_style),
            Paragraph(col2, body_style),
            Paragraph(evidence_text, body_style),
            Paragraph(remedy_text, body_style)
        ])

    if len(table_data) > 1:
        t = Table(table_data, colWidths=[120, 75, 200, 130])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F2F5F9")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1F497D")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("各项业财勾稽完全吻合，未检出重大错报或舞弊风险点。", body_style))

    story.append(Spacer(1, 10))

    # Workpapers Section
    story.append(Paragraph("三、抽查与实质性测试底稿索引 (Workpaper Index)", h2_style))
    for wp in report.workpapers:
        story.append(Paragraph(
            f"<b>底稿编号:</b> {wp.workpaper_id} - {wp.title} | "
            f"<b>核查金额:</b> ¥{wp.total_audited_amount:,.2f} | <b>异常:</b> ¥{wp.abnormal_amount:,.2f}",
            body_bold
        ))
        story.append(Paragraph(f"<b>综合意见:</b> {wp.audit_opinion_summary}", body_style))
        story.append(Spacer(1, 4))

    doc.build(story)
    return output_path
