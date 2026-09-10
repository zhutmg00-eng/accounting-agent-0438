"""
Streamlit Web Demonstration Prototype for 2026年北京市大学生数智会计创新应用竞赛.
Supports DeepSeek API / Mock mode, live multi-agent execution, interactive workpapers, and report exports.
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
from src.core.schemas import AccountingCaseData, RiskLevel
from src.core.llm_adapter import DeepSeekLLMAdapter
from src.core.harness import AccountingAgentHarness
from src.benchmark.test_cases import get_benchmark_cases
from src.benchmark.benchmark_runner import run_benchmark_suite
from src.exporters.excel_exporter import export_workpaper_to_excel
from src.exporters.pdf_exporter import export_report_to_pdf
from src.exporters.json_exporter import export_report_to_json
from src.ui.dashboard_view import render_data_anomaly_dashboard

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
        margin-bottom: 5px;
    }
    .sub-header {
        font-size: 14px;
        color: #595959;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #F8F9FA;
        border-left: 5px solid #1F497D;
        padding: 15px;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .risk-high {
        background-color: #FFEBEE;
        border-left: 5px solid #D32F2F;
        padding: 12px;
        border-radius: 4px;
        margin-bottom: 10px;
    }
    .risk-clean {
        background-color: #E8F5E9;
        border-left: 5px solid #388E3C;
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


init_session_state()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/accounting.png", width=64)
    st.markdown("### ⚙️ 模型与系统配置")
    
    use_mock = st.toggle("使用离线智能评测引擎 (Mock/Demo)", value=True, help="无需联网或 API Key，使用内置确定性财税算法与 CoT 推理链。")
    api_key = st.text_input("DeepSeek API Key", value=settings.api_key if not use_mock else "", type="password", disabled=use_mock)
    api_base = st.text_input("API Base URL", value=settings.api_base, disabled=use_mock)
    model_name = st.selectbox("推理模型", ["deepseek-chat", "deepseek-reasoner", "qwen-max", "glm-4"], index=0, disabled=use_mock)
    
    # Update harness LLM adapter if changed
    llm_adapter = DeepSeekLLMAdapter(api_key=api_key, api_base=api_base, model_name=model_name, use_mock=use_mock)
    st.session_state.harness.llm = llm_adapter

    st.markdown("---")
    st.markdown("### 🧩 智能体插件选择 (Plugin)")
    plugins_meta = st.session_state.harness.registry.list_plugins()
    plugin_options = {p["name"]: p["id"] for p in plugins_meta}
    selected_plugin_name = st.selectbox("选择业务插件", list(plugin_options.keys()))
    selected_plugin_id = plugin_options[selected_plugin_name]

    st.markdown("---")
    st.markdown("### 📁 测试案例选择")
    cases = get_benchmark_cases()
    case_names = [f"{c.case_id} - {c.company_name}" for c in cases]
    selected_case_idx = st.selectbox("预置实战案例", range(len(cases)), format_func=lambda i: case_names[i])
    selected_case = cases[selected_case_idx]

    st.caption("2026年北京市大学生数智会计创新应用竞赛")


# ----------------- MAIN CONTENT -----------------
st.markdown('<div class="main-header">⚖️ DeepSeek-AuditMind: 复杂业财融合与舞弊穿透智能体</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">当前执行插件: <b>{selected_plugin_name}</b> | 核心引擎: <b>{"离线高精度规则引擎" if use_mock else model_name}</b></div>', unsafe_allow_html=True)

tab_dashboard, tab_agent, tab_workpaper, tab_benchmark, tab_export = st.tabs([
    "🎯 数据问题穿透大屏 (Anomaly Dashboard)",
    "🔍 智能体穿透研判 (Live Execution)", 
    "📋 标准审计底稿 (Workpapers)", 
    "📊 评测基座与评分卡 (Benchmark Harness)", 
    "💾 结构化成果导出 (Export)"
])

# ----------------- TAB 0: DATA ANOMALY DASHBOARD -----------------
with tab_dashboard:
    render_data_anomaly_dashboard(selected_case, st.session_state.current_report)

# ----------------- TAB 1: LIVE AGENT EXECUTION -----------------
with tab_agent:
    st.markdown(f"#### 🏢 案例基本信息: {selected_case.company_name}")
    col_info1, col_info2, col_info3 = st.columns([1, 1, 2])
    with col_info1:
        st.write(f"**所属行业:** {selected_case.industry}")
        st.write(f"**核算/审计期间:** {selected_case.audit_period}")
    with col_info2:
        st.write(f"**抽样凭证数:** {len(selected_case.vouchers)} 张")
        st.write(f"**关联单据数:** {len(selected_case.contracts) + len(selected_case.invoices) + len(selected_case.bank_flows)} 份")
    with col_info3:
        st.info(f"**业务背景简述:** {selected_case.description}")

    # Run Button
    if st.button("🚀 启动数智智能体穿透核查", type="primary", use_container_width=True):
        with st.status("🤖 DeepSeek Multi-Agent 正在协同穿透执行中...", expanded=True) as status:
            st.write("1️⃣ [业财数据治理智能体] 正在清洗凭证、提取分录并执行三单勾稽比对...")
            st.write("2️⃣ [财务计算算子] 正在计算 Beneish M-Score 8变量指标与借贷平衡...")
            st.write("3️⃣ [审计推理智能体] 正在依据 CSA 1141 与 CAS 14 准则构建 CoT 证据链...")
            st.write("4️⃣ [确定性校验卫士] 正在校验数字一致性并生成标准化审计底稿...")
            
            report = st.session_state.harness.run_case(selected_case, plugin_id=selected_plugin_id)
            st.session_state.current_report = report
            status.update(label="✅ 智能体穿透核查完成！", state="complete", expanded=False)

    # Display Results if Available
    if st.session_state.current_report and st.session_state.current_report.case_id == selected_case.case_id:
        rep = st.session_state.current_report
        
        st.markdown("---")
        st.markdown("### 📊 智能体研判核心指标看板")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            risk_color = "red" if rep.overall_risk_rating == RiskLevel.HIGH else ("orange" if rep.overall_risk_rating == RiskLevel.MEDIUM else "green")
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
            st.metric("Token消耗", f"{rep.token_usage.get('total', 0)}")

        st.markdown("#### 📝 管理层与主审评委摘要")
        st.success(rep.executive_summary)

        st.markdown("#### 🚨 重点风险发现与准则穿透依据 (Risk Findings)")
        if not rep.findings:
            st.info("🎉 未发现重大异常风险，各项业财勾稽指标与财务数据均符合会计准则要求。")
        else:
            for f in rep.findings:
                risk_style = "risk-high" if f.risk_level == RiskLevel.HIGH else "risk-clean"
                with st.expander(f"【{f.finding_id}】{f.title} ({f.risk_level.value} - 涉嫌金额: ¥{f.impact_amount:,.2f})", expanded=True):
                    st.markdown(f"**📖 依据会计/审计准则:** `{f.accounting_standard}`")
                    st.markdown(f"**🔍 疑点手法剖析:** {f.suspected_mechanism}")
                    
                    st.markdown("**⛓️ 结构化证据链条 (Evidence Trail):**")
                    for ev in f.evidences:
                        st.markdown(f"- 📌 **[{ev.evidence_type}]** 单据源: `{ev.source_ref}` ➔ {ev.detail}")
                    
                    st.markdown(f"**💡 建议执行的实质性审计程序:** `{f.suggested_procedure}`")


# ----------------- TAB 2: AUDIT WORKPAPERS -----------------
with tab_workpaper:
    if not st.session_state.current_report:
        st.info("👈 请先在第一个标签页点击【启动数智智能体穿透核查】生成审计底稿。")
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
                df_rows = pd.DataFrame([r.model_dump() for r in wp.rows])
                df_rows.columns = ["凭证号", "记账日期", "业务摘要", "账面金额(元)", "核实确认金额(元)", "差异金额(元)", "审计核查结论"]
                st.dataframe(df_rows, use_container_width=True)

            st.caption(f"**底稿综合意见:** {wp.audit_opinion_summary}")
            st.markdown("---")


# ----------------- TAB 3: BENCHMARK HARNESS -----------------
with tab_benchmark:
    st.markdown("### 📊 智能体评测基座 (DeepSeek Evaluation Harness)")
    st.write("自动化对 4 个实战案例进行端到端测试，考核指标包括：查准率(Precision)、查全率(Recall)、F1-Score、JSON结构合规率与零算术幻觉率。")

    if st.button("⚡ 运行全套自动化评测基准 (Run Benchmark Suite)", type="primary"):
        with st.spinner("正在逐一评测基准数据集..."):
            summary = run_benchmark_suite(st.session_state.harness, plugin_id=selected_plugin_id)
            st.session_state.benchmark_summary = summary

    if st.session_state.benchmark_summary:
        b_sum = st.session_state.benchmark_summary
        
        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("评测通过率", f"{b_sum.passed_cases}/{b_sum.total_cases} ({b_sum.passed_cases/b_sum.total_cases:.0%})")
        b2.metric("平均 F1-Score", f"{b_sum.mean_f1_score:.4f}")
        b3.metric("平均查全率(Recall)", f"{b_sum.mean_recall:.1%}")
        b4.metric("零算术幻觉达标率", f"{b_sum.math_accuracy_rate:.0%}")
        b5.metric("平均端到端耗时", f"{b_sum.mean_latency:.3f} s")

        st.markdown("#### 🏆 案例详细评分卡 (Case Scorecard)")
        df_bench = pd.DataFrame([
            {
                "案例编号": s.case_id,
                "企业名称": s.case_name,
                "查准率(P)": f"{s.precision:.1%}",
                "查全率(R)": f"{s.recall:.1%}",
                "F1-Score": f"{s.f1_score:.2f}",
                "JSON合规": "✓ 100%" if s.json_schema_valid else "✗",
                "零算术幻觉": "✓ 100%" if s.math_accuracy_rate == 1.0 else "✗",
                "耗时(s)": f"{s.latency_seconds:.3f}",
                "考核状态": "✅ PASSED" if s.passed else "❌ FAILED"
            }
            for s in b_sum.case_scores
        ])
        st.dataframe(df_bench, use_container_width=True)


# ----------------- TAB 4: EXPORT ARTIFACTS -----------------
with tab_export:
    if not st.session_state.current_report:
        st.info("👈 请先运行案例生成结构化报告后即可在此处一键导出。")
    else:
        rep = st.session_state.current_report
        st.markdown("### 💾 竞赛成果文件一键导出")
        st.write("满足比赛硬性要求：输出结构化结果（JSON / Excel底稿 / PDF报告），可供评审专家现场查阅。")

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
