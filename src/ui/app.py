"""
Streamlit Web Demonstration Prototype for 2026年北京市大学生数智会计创新应用竞赛.
DeepSeek-AuditMind: 复杂业财融合与数智舞弊穿透智能体.
Implements:
- Issue 1: Focus on core audit & fraud penetration mainline (5-minute closed loop)
- Issue 2: Excel / CSV financial data upload with field-level validation and sample templates
- Issue 3: Strict separation between STRICT_ONLINE, ONLINE, and MOCK modes (no silent fallback)
- Issue 4: Rigorous field-level & amount-level benchmark scorecard
- Issue 5: Three-layer structured evidence traceability (Deterministic facts, LLM reasoning, CPA verification)
- Issue 6: One-click live competition presentation support
"""

import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path
import sys

# Ensure root path is in sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.config import settings
from src.core.schemas import (
    AccountingCaseData, RiskLevel, ExecutionMode, AnalysisReportResult
)
from src.core.llm_adapter import DeepSeekLLMAdapter, DeepSeekAPIError
from src.core.harness import AccountingAgentHarness
from src.benchmark.test_cases import get_benchmark_cases
from src.benchmark.benchmark_runner import run_benchmark_suite
from src.exporters.excel_exporter import export_workpaper_to_excel
from src.exporters.pdf_exporter import export_report_to_pdf
from src.exporters.json_exporter import export_report_to_json
from src.ui.dashboard_view import render_data_anomaly_dashboard
from src.data_loader.file_importer import (
    parse_vouchers_file, parse_invoices_file, parse_bank_flows_file,
    generate_sample_templates
)

# Page configuration
st.set_page_config(
    page_title="DeepSeek-AuditMind | 数智会计创新应用竞赛",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 26px;
        font-weight: 700;
        color: #1F497D;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 14px;
        color: #595959;
        margin-bottom: 16px;
    }
    .mode-badge-online {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
        border: 1px solid #31C48D;
    }
    .mode-badge-mock {
        background-color: #FEF08A;
        color: #854D0E;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
        border: 1px solid #FACC15;
    }
    .risk-high {
        background-color: #FFEBEE;
        border-left: 5px solid #D32F2F;
        padding: 12px;
        border-radius: 4px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    if "harness" not in st.session_state:
        st.session_state.harness = AccountingAgentHarness()
    if "current_report" not in st.session_state:
        st.session_state.current_report = None
    if "benchmark_summary" not in st.session_state:
        st.session_state.benchmark_summary = None
    if "uploaded_case" not in st.session_state:
        st.session_state.uploaded_case = None


init_session_state()

# Ensure templates exist
templates_dir = Path("data/templates")
if not (templates_dir / "企业记账凭证模板.xlsx").exists():
    generate_sample_templates(templates_dir)

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/accounting.png", width=64)
    st.markdown("### ⚙️ 运行与推理引擎配置")
    
    mode_choice = st.radio(
        "选择运行模式:",
        ["🟡 离线确定性演示 (Mock/Demo)", "🟢 DeepSeek 在线分析 (Online)", "🔴 严格在线模式 (Strict-Online)"],
        index=0,
        help="【严格在线模式】：若 API 连接失败立即报错中断，绝不静默降级，确保真实性。\n【离线确定性演示】：内置规则引擎与算子，无需 API Key。"
    )

    if "Strict-Online" in mode_choice:
        current_mode = ExecutionMode.STRICT_ONLINE
        use_mock = False
    elif "Online" in mode_choice:
        current_mode = ExecutionMode.ONLINE
        use_mock = False
    else:
        current_mode = ExecutionMode.MOCK
        use_mock = True

    api_key = st.text_input("DeepSeek API Key", value=settings.api_key if not use_mock else "", type="password", disabled=use_mock)
    api_base = st.text_input("API Base URL", value=settings.api_base, disabled=use_mock)
    model_name = st.selectbox("推理模型", ["deepseek-chat", "deepseek-reasoner", "qwen-max"], index=0, disabled=use_mock)

    # Initialize or update LLM adapter
    llm_adapter = DeepSeekLLMAdapter(
        api_key=api_key,
        api_base=api_base,
        model_name=model_name,
        mode=current_mode
    )
    st.session_state.harness.llm = llm_adapter

    st.markdown("---")
    st.markdown("### 📁 数据源与真实案例选择")
    data_source_mode = st.radio("数据来源:", ["真实资本市场实战案例 (28例)", "上传本地财务文件 (Excel/CSV)"])

    if data_source_mode == "真实资本市场实战案例 (28例)":
        from src.benchmark.test_cases import get_case_categories
        categories = ["全部舞弊与合规大类 (All 28 Cases)"] + get_case_categories()
        selected_cat = st.selectbox("📂 案例类型分类筛选:", categories)
        
        filtered_cases = get_benchmark_cases(selected_cat if selected_cat != "全部舞弊与合规大类 (All 28 Cases)" else None)
        case_labels = [f"[{c.stock_code or '标杆'}] {c.company_name} ({c.case_category})" for c in filtered_cases]
        selected_case_idx = st.selectbox("🎯 选择实战案例:", range(len(filtered_cases)), format_func=lambda i: case_labels[i])
        active_case = filtered_cases[selected_case_idx]
    else:
        cases = get_benchmark_cases()
        active_case = st.session_state.uploaded_case if st.session_state.uploaded_case else cases[0]

    st.markdown("---")
    with st.expander("🧩 扩展功能区 (管理会计 CVP)", expanded=False):
        st.caption("管理会计插件可执行量本利敏感性分析，保留为评委答辩扩展模块。")
        st.write("已就绪算子: `calculate_breakeven_point`, `calc_target_profit_volume`")

    st.caption("2026年北京市大学生数智会计创新应用竞赛")


# ----------------- MAIN CONTENT HEADER -----------------
mode_badge = '<span class="mode-badge-online">🟢 真实在线推理模式 (DeepSeek-V3)</span>' if not use_mock else '<span class="mode-badge-mock">🟡 离线确定性演示模式 (Demo Mode)</span>'

st.markdown('<div class="main-header">⚖️ DeepSeek-AuditMind: 复杂业财融合与舞弊穿透智能体</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-header">当前执行模式: {mode_badge} | 核心业务主线: <b>数智审计与舞弊穿透 (包含 28 个真实资本市场案例)</b></div>',
    unsafe_allow_html=True
)

# Five Core Mainline Tabs
tab_data, tab_agent, tab_dashboard, tab_workpaper, tab_benchmark, tab_export = st.tabs([
    "📁 数据导入与案例预览 (Data)",
    "🔍 智能体穿透研判 (Live Execution)", 
    "🎯 数据问题穿透大屏 (Anomaly Dashboard)",
    "📋 标准审计底稿 (Workpapers)", 
    "📊 评测基座与评分卡 (Benchmark Harness)", 
    "💾 结构化成果导出 (Export)"
])

# ----------------- TAB 0: DATA INGESTION & PREVIEW -----------------
with tab_data:
    if "真实资本市场" in data_source_mode:
        st.markdown(f"### 🏢 案例基本信息: **{active_case.company_name}** ({active_case.stock_code or '非上市'})")
        if active_case.penalty_decision_no:
            st.markdown(f"🏛️ **官方行政监管文号 / 审计报告依据:** `{active_case.penalty_decision_no}`")
        if active_case.csrc_summary:
            st.info(f"📋 **中国证监会官方查明事实认定:** {active_case.csrc_summary}")

        c_i1, c_i2, c_i3 = st.columns([1, 1, 2])
        with c_i1:
            st.write(f"**所属行业:** {active_case.industry}")
            st.write(f"**审计核算期间:** {active_case.audit_period}")
            st.write(f"**舞弊分类:** {active_case.case_category}")
        with c_i2:
            st.write(f"**抽查凭证样本数:** {len(active_case.vouchers)} 张")
            st.write(f"**单据与流水数:** {len(active_case.contracts) + len(active_case.invoices) + len(active_case.bank_flows)} 份")
            if active_case.ground_truth_findings:
                st.write(f"**涉案涉嫌金额:** ¥{sum(gt.expected_amount for gt in active_case.ground_truth_findings):,.2f}")
        with c_i3:
            st.warning(f"**案件背景简述:** {active_case.description}")

        st.markdown("#### 📑 凭证分录抽查明细预览")
        v_rows = []
        for v in active_case.vouchers:
            for e in v.entries:
                v_rows.append({
                    "凭证号": v.voucher_id,
                    "记账日期": v.voucher_date,
                    "科目代码": e.account_code,
                    "科目名称": e.account_name,
                    "借方金额(元)": e.debit,
                    "贷方金额(元)": e.credit,
                    "摘要": e.summary,
                    "关联单据": v.associated_doc_id or "无"
                })
        if v_rows:
            st.dataframe(pd.DataFrame(v_rows), use_container_width=True)

    else:
        st.markdown("### 📤 上传真实财务数据 (Excel / CSV)")
        st.write("系统支持解析记账凭证表、增值税发票清单及银行流水，提供字段级精确校验。")

        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            with open(templates_dir / "企业记账凭证模板.xlsx", "rb") as f:
                st.download_button("📥 下载凭证导入模板 (.xlsx)", data=f.read(), file_name="企业记账凭证模板.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with col_t2:
            with open(templates_dir / "增值税发票清单模板.csv", "rb") as f:
                st.download_button("📥 下载发票清单模板 (.csv)", data=f.read(), file_name="增值税发票清单模板.csv", mime="text/csv")
        with col_t3:
            with open(templates_dir / "银行对账单明细模板.csv", "rb") as f:
                st.download_button("📥 下载银行流水模板 (.csv)", data=f.read(), file_name="银行对账单明细模板.csv", mime="text/csv")

        st.markdown("---")
        up_col1, up_col2, up_col3 = st.columns(3)
        with up_col1:
            voucher_file = st.file_uploader("1. 上传记账凭证表 (.xlsx / .csv)", type=["xlsx", "csv"])
        with up_col2:
            invoice_file = st.file_uploader("2. 上传发票清单 (.csv / .xlsx)", type=["csv", "xlsx"])
        with up_col3:
            bank_file = st.file_uploader("3. 上传银行对账单 (.csv / .xlsx)", type=["csv", "xlsx"])

        new_vouchers = []
        new_invoices = []
        new_bank_flows = []
        has_error = False

        if voucher_file:
            v_list, v_val = parse_vouchers_file(voucher_file, filename=voucher_file.name)
            if v_val.is_valid:
                st.success(f"✅ 凭证表解析成功: {v_val.summary}")
                new_vouchers = v_list
            else:
                has_error = True
                for err in v_val.errors:
                    st.error(f"❌ 凭证校验错误: {err}")

        if invoice_file:
            i_list, i_val = parse_invoices_file(invoice_file, filename=invoice_file.name)
            if i_val.is_valid:
                st.success(f"✅ 发票清单解析成功: {i_val.summary}")
                new_invoices = i_list
            else:
                has_error = True
                for err in i_val.errors:
                    st.error(f"❌ 发票校验错误: {err}")

        if bank_file:
            b_list, b_val = parse_bank_flows_file(bank_file, filename=bank_file.name)
            if b_val.is_valid:
                st.success(f"✅ 银行流水解析成功: {b_val.summary}")
                new_bank_flows = b_list
            else:
                has_error = True
                for err in b_val.errors:
                    st.error(f"❌ 流水校验错误: {err}")

        if new_vouchers and not has_error:
            custom_case = AccountingCaseData(
                case_id="UPLOADED_CUSTOM_001",
                company_name="用户自主导入审计目标公司",
                industry="自主上传自定义企业",
                audit_period="2025年度",
                description="由用户现场上传的外部财务总账、发票明细及银行对账单数据集。",
                vouchers=new_vouchers,
                invoices=new_invoices,
                bank_flows=new_bank_flows
            )
            st.session_state.uploaded_case = custom_case
            active_case = custom_case
            st.info("🎉 上传数据已成功装载至审计执行引擎！请切换至【🔍 智能体穿透研判】启动分析。")


# ----------------- TAB 1: LIVE AGENT EXECUTION -----------------
with tab_agent:
    st.markdown(f"#### 🚀 正在审计: **{active_case.company_name}** ({active_case.case_id})")

    # Run Button
    if st.button("🚀 启动数智智能体穿透核查 (Run AuditMind Agent)", type="primary", use_container_width=True):
        with st.status("🤖 DeepSeek Multi-Agent 正在协同穿透核查中...", expanded=True) as status:
            st.write("1️⃣ [业财数据治理智能体] 正在提取凭证分录并执行三单勾稽客观比对...")
            st.write("2️⃣ [确定性审计算子] 正在计算 Beneish M-Score 8变量指标与借贷平衡...")
            st.write(f"3️⃣ [审计推理智能体] 正在通过 {st.session_state.harness.llm.mode.value.upper()} 模式调用大模型准则推断...")
            st.write("4️⃣ [确定性校验卫士] 正在校验数字一致性并构建三层证据链...")
            
            try:
                report = st.session_state.harness.run_case(active_case, plugin_id="audit_fraud_detection")
                st.session_state.current_report = report
                status.update(label="✅ 智能体穿透核查顺利完成！", state="complete", expanded=False)
            except DeepSeekAPIError as err:
                status.update(label="❌ 严格在线模式执行失败！", state="error", expanded=True)
                st.error(f"🚨 **DeepSeek API 严格在线调用异常**: {str(err)}")
                st.warning("⚠️ 严格在线模式已禁止自动降级为 Mock，请检查网络连接、API Key 或在侧边栏切换至【离线确定性演示模式】。")
            except Exception as e:
                status.update(label="❌ 执行异常！", state="error", expanded=True)
                st.error(f"执行发生错误: {str(e)}")

    # Display Results if Available
    if st.session_state.current_report and st.session_state.current_report.case_id == active_case.case_id:
        rep = st.session_state.current_report
        
        st.markdown("---")
        st.markdown("### 📊 智能体研判核心指标看板")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("综合风险评级", rep.overall_risk_rating.value, delta="高危预警" if rep.overall_risk_rating == RiskLevel.HIGH else "合规正常")
        with c2:
            m_score_display = f"{rep.beneish_m_score:.2f}" if rep.beneish_m_score is not None else "N/A"
            st.metric("Beneish M-Score", m_score_display, help="高于 -1.78 表示财务舞弊概率极高")
        with c3:
            total_impact = sum(f.impact_amount for f in rep.findings)
            st.metric("疑点涉及金额", f"¥ {total_impact:,.0f}")
        with c4:
            st.metric("执行耗时", f"{rep.execution_time_seconds:.3f} s")
        with c5:
            st.metric("运行模式", rep.execution_mode.value.upper(), delta="在线真实" if rep.execution_mode != ExecutionMode.MOCK and not rep.fallback_occurred else "离线模拟")

        st.markdown("#### 📝 管理层与主审评委摘要")
        st.success(rep.executive_summary)

        st.markdown("#### 🚨 重点风险发现清单与三层证据链 (Three-Layer Evidence Trail)")
        if not rep.findings:
            st.info("🎉 各项业财单据匹配高度吻合，未检出重大错报或舞弊迹象。")
        else:
            for f in rep.findings:
                with st.expander(f"【{f.finding_id}】{f.title} ({f.risk_level.value} - 涉及金额: ¥{f.impact_amount:,.2f})", expanded=True):
                    st.markdown(f"**📖 依据会计/审计准则:** `{f.accounting_standard}`")
                    
                    # Three Evidence Layers
                    st.markdown(f"**1️⃣ 【确定性事实 (规则计算)】:** `{f.rule_evidence or f.suspected_mechanism}`")
                    st.markdown(f"**2️⃣ 【DeepSeek 大模型深度研判】:** {f.model_explanation or f.suspected_mechanism}")
                    st.markdown(f"**3️⃣ 【待注册会计师现场核实程序】:** `{f.human_verification_flag or f.suggested_procedure}`")
                    
                    st.markdown("**⛓️ 关联原始单据索引:**")
                    for ev in f.evidences:
                        st.markdown(f"- 📌 `[{ev.evidence_type}]` 单据引用: **{ev.source_ref}** | 来源文件: `{ev.source_file or '标准凭证库'}`")


# ----------------- TAB 2: ANOMALY DASHBOARD -----------------
with tab_dashboard:
    render_data_anomaly_dashboard(active_case, st.session_state.current_report)


# ----------------- TAB 3: AUDIT WORKPAPERS -----------------
with tab_workpaper:
    if not st.session_state.current_report or st.session_state.current_report.case_id != active_case.case_id:
        st.info("👈 请先在【智能体穿透研判】标签页点击启动核查以生成审计工作底稿。")
    else:
        rep = st.session_state.current_report
        st.markdown(f"### 📋 {rep.company_name} - 审计工作底稿库")
        
        for wp in rep.workpapers:
            st.markdown(f"#### 底稿索引: `{wp.workpaper_id}` - {wp.title}")
            col_w1, col_w2, col_w3 = st.columns(3)
            col_w1.write(f"**编制人:** {wp.prepared_by}")
            col_w2.write(f"**核查业务总额:** ¥{wp.total_audited_amount:,.2f}")
            col_w3.write(f"**确认异常金额:** ¥{wp.abnormal_amount:,.2f}")

            if wp.rows:
                df_rows = pd.DataFrame([
                    {
                        "凭证号": r.voucher_no,
                        "记账日期": r.date,
                        "业务摘要": r.summary,
                        "账面金额(元)": r.ledger_amount,
                        "核实确认金额(元)": r.verified_amount,
                        "差异金额(元)": r.discrepancy,
                        "审计结论": r.audit_conclusion,
                        "证据溯源索引": r.evidence_trace or r.source_file or "业务单据库"
                    }
                    for r in wp.rows
                ])
                st.dataframe(df_rows, use_container_width=True)

            st.caption(f"**底稿综合意见:** {wp.audit_opinion_summary}")
            st.markdown("---")


# ----------------- TAB 4: BENCHMARK HARNESS -----------------
with tab_benchmark:
    st.markdown("### 📊 智能体评测基座 (DeepSeek Evaluation Harness)")
    st.write("执行严格字段级与金额级（误差≤1%）基准测试，考核指标包括：查准率、查全率、金额准确率、类型命中率及零误报率。")

    if st.button("⚡ 运行全套严格评测基准 (Run Rigorous Benchmark Suite)", type="primary"):
        with st.spinner("正在逐一评测基准数据集..."):
            summary = run_benchmark_suite(st.session_state.harness, plugin_id="audit_fraud_detection")
            st.session_state.benchmark_summary = summary

    if st.session_state.benchmark_summary:
        b_sum = st.session_state.benchmark_summary
        
        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("评测通过率", f"{b_sum.passed_cases}/{b_sum.total_cases} ({b_sum.passed_cases/b_sum.total_cases:.0%})")
        b2.metric("平均 F1-Score", f"{b_sum.mean_f1_score:.2f}")
        b3.metric("金额精准率 (≤1%)", f"{b_sum.mean_amount_accuracy:.1%}")
        b4.metric("类型命中率", f"{b_sum.mean_type_accuracy:.1%}")
        b5.metric("对照组误报率", f"{b_sum.false_positive_rate:.1%}")

        st.markdown("#### 🏆 字段级与金额级详细评分卡 (Rigorous Scorecard)")
        df_bench = pd.DataFrame([
            {
                "案例编号": s.case_id,
                "企业名称": s.case_name,
                "类型命中": f"{s.type_accuracy_rate:.1%}",
                "金额精准度": f"{s.amount_accuracy_rate:.1%}",
                "证据溯源": f"{s.evidence_hit_rate:.1%}",
                "F1-Score": f"{s.f1_score:.2f}",
                "误报数": s.false_positive_count,
                "耗时(s)": f"{s.latency_seconds:.3f}",
                "考核状态": "✅ PASSED" if s.passed else "❌ FAILED"
            }
            for s in b_sum.case_scores
        ])
        st.dataframe(df_bench, use_container_width=True)


# ----------------- TAB 5: EXPORT ARTIFACTS -----------------
with tab_export:
    if not st.session_state.current_report:
        st.info("👈 请先运行案例生成结构化报告后即可在此处一键导出。")
    else:
        rep = st.session_state.current_report
        st.markdown("### 💾 竞赛成果文件一键导出")
        st.write("满足比赛硬性要求：输出结构化结果（JSON / 包含三层证据链的 Excel底稿 / PDF报告），供现场评委即时下载。")

        out_dir = settings.output_dir
        excel_path = out_dir / f"{rep.company_name}_审计底稿.xlsx"
        pdf_path = out_dir / f"{rep.company_name}_审计报告.pdf"
        json_path = out_dir / f"{rep.company_name}_结构化数据.json"

        export_workpaper_to_excel(rep, excel_path)
        export_report_to_pdf(rep, pdf_path)
        export_report_to_json(rep, json_path)

        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            with open(excel_path, "rb") as f:
                st.download_button(
                    "📊 下载标准审计底稿 (Excel .xlsx)",
                    data=f.read(),
                    file_name=f"{rep.company_name}_标准审计工作底稿.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        with col_d2:
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "📄 下载审计穿透报告 (PDF .pdf)",
                    data=f.read(),
                    file_name=f"{rep.company_name}_数智审计穿透报告.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        with col_d3:
            with open(json_path, "rb") as f:
                st.download_button(
                    "⚙️ 下载结构化结果 (JSON .json)",
                    data=f.read(),
                    file_name=f"{rep.company_name}_结构化数据.json",
                    mime="application/json",
                    use_container_width=True
                )
