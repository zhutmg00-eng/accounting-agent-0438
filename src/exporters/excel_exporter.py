"""
Excel Exporter for Standardized Audit Workpapers (.xlsx).
Enhanced with Execution Mode badge and Three-Layer Evidence Traceability (Issue 5).
"""

from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from src.core.schemas import AnalysisReportResult, AuditWorkpaper, ExecutionMode


def export_workpaper_to_excel(report: AnalysisReportResult, output_path: Path) -> Path:
    """Export Audit Workpapers to a beautifully styled Excel workbook with evidence trail."""
    wb = openpyxl.Workbook()
    
    # Sheet 1: Summary Dashboard
    ws_summary = wb.active
    ws_summary.title = "审计总览与风险矩阵"
    ws_summary.views.sheetView[0].showGridLines = True

    # Styling
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="微软雅黑", size=16, bold=True, color="1F497D")
    bold_font = Font(name="微软雅黑", size=10, bold=True)
    normal_font = Font(name="微软雅黑", size=10)
    border_thin = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9")
    )

    # Title
    ws_summary["A1"] = f"{report.company_name} - 数智审计穿透与风险研判底稿"
    ws_summary["A1"].font = title_font
    ws_summary.merge_cells("A1:H1")

    # Meta & Execution Mode
    mode_text = "🟢 实时在线推理 (DeepSeek-V3)" if report.execution_mode in (ExecutionMode.ONLINE, ExecutionMode.STRICT_ONLINE) and not report.fallback_occurred else "🟡 离线确定性模拟 (Demo Mode)"
    ws_summary["A3"] = "被审计单位:"
    ws_summary["B3"] = report.company_name
    ws_summary["C3"] = "综合风险评级:"
    ws_summary["D3"] = report.overall_risk_rating.value
    ws_summary["E3"] = "Beneish M-Score:"
    ws_summary["F3"] = str(report.beneish_m_score if report.beneish_m_score is not None else "N/A")
    ws_summary["G3"] = "执行模式:"
    ws_summary["H3"] = mode_text
    for cell in ["A3", "C3", "E3", "G3"]:
        ws_summary[cell].font = bold_font

    # Executive Summary
    ws_summary["A5"] = "管理层与主审评委摘要:"
    ws_summary["A5"].font = bold_font
    ws_summary["A6"] = report.executive_summary
    ws_summary["A6"].font = normal_font
    ws_summary.merge_cells("A6:H7")
    ws_summary["A6"].alignment = Alignment(wrap_text=True, vertical="top")

    # Risk Findings Table with Evidence Traceability
    ws_summary["A9"] = "重点风险发现清单与三层证据链 (Risk Findings & Evidence Trail)"
    ws_summary["A9"].font = Font(name="微软雅黑", size=12, bold=True, color="C00000")

    headers_finding = ["编号", "风险发现项", "风险等级", "涉案金额(元)", "确定性客观事实(规则发现)", "大模型准则深度研判", "待人工复核/审计程序", "依据准则"]
    for col_idx, h in enumerate(headers_finding, start=1):
        c = ws_summary.cell(row=10, column=col_idx, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")

    current_row = 11
    for f in report.findings:
        ws_summary.cell(row=current_row, column=1, value=f.finding_id).font = normal_font
        ws_summary.cell(row=current_row, column=2, value=f.title).font = bold_font
        ws_summary.cell(row=current_row, column=3, value=f.risk_level.value).font = bold_font
        ws_summary.cell(row=current_row, column=4, value=f.impact_amount).font = normal_font
        ws_summary.cell(row=current_row, column=5, value=f.rule_evidence or f.suspected_mechanism).font = normal_font
        ws_summary.cell(row=current_row, column=6, value=f.model_explanation or f.suspected_mechanism).font = normal_font
        ws_summary.cell(row=current_row, column=7, value=f.human_verification_flag or f.suggested_procedure).font = normal_font
        ws_summary.cell(row=current_row, column=8, value=f.accounting_standard).font = normal_font
        
        for col_idx in range(1, 9):
            ws_summary.cell(row=current_row, column=col_idx).border = border_thin
            ws_summary.cell(row=current_row, column=col_idx).alignment = Alignment(wrap_text=True, vertical="top")
        current_row += 1

    # Individual Workpaper Sheets
    for wp_idx, wp in enumerate(report.workpapers, start=1):
        sheet_name = f"底稿_{wp.workpaper_id}"[:30]
        ws_wp = wb.create_sheet(title=sheet_name)
        ws_wp.views.sheetView[0].showGridLines = True

        ws_wp["A1"] = wp.title
        ws_wp["A1"].font = title_font
        ws_wp.merge_cells("A1:H1")

        ws_wp["A3"] = "底稿编号:"
        ws_wp["B3"] = wp.workpaper_id
        ws_wp["C3"] = "编制人:"
        ws_wp["D3"] = wp.prepared_by
        ws_wp["E3"] = "核查日期:"
        ws_wp["F3"] = wp.review_date

        headers_wp = ["凭证号", "记账日期", "业务摘要", "账面金额(元)", "核实确认金额(元)", "差异金额(元)", "审计结论", "数据来源与追溯"]
        for col_idx, h in enumerate(headers_wp, start=1):
            c = ws_wp.cell(row=5, column=col_idx, value=h)
            c.fill = header_fill
            c.font = header_font
            c.alignment = Alignment(horizontal="center", vertical="center")

        r_idx = 6
        for r in wp.rows:
            ws_wp.cell(row=r_idx, column=1, value=r.voucher_no).font = normal_font
            ws_wp.cell(row=r_idx, column=2, value=r.date).font = normal_font
            ws_wp.cell(row=r_idx, column=3, value=r.summary).font = normal_font
            ws_wp.cell(row=r_idx, column=4, value=r.ledger_amount).font = normal_font
            ws_wp.cell(row=r_idx, column=5, value=r.verified_amount).font = normal_font
            ws_wp.cell(row=r_idx, column=6, value=r.discrepancy).font = normal_font
            ws_wp.cell(row=r_idx, column=7, value=r.audit_conclusion).font = normal_font
            ws_wp.cell(row=r_idx, column=8, value=r.evidence_trace or r.source_file or "标准凭证库").font = normal_font

            for col_idx in range(1, 9):
                ws_wp.cell(row=r_idx, column=col_idx).border = border_thin
            r_idx += 1

        # Summary footer
        ws_wp.cell(row=r_idx + 1, column=1, value="底稿综合意见:").font = bold_font
        ws_wp.cell(row=r_idx + 1, column=2, value=wp.audit_opinion_summary).font = normal_font
        ws_wp.merge_cells(start_row=r_idx + 1, start_column=2, end_row=r_idx + 2, end_column=8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
