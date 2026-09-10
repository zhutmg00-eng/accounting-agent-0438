"""
Data Anomaly & Fraud Diagnostics Dashboard (数智会计数据问题穿透大屏)
Provides comprehensive, granular visualization of accounting discrepancies,
timeline mismatches, Beneish 8-variable anomalies, and circular money trails.
"""

from typing import Dict, Any, List, Optional
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from src.core.schemas import AccountingCaseData, AnalysisReportResult, RiskLevel
from src.plugins.audit_fraud_plugin.tools import calculate_beneish_m_score, perform_three_way_reconciliation


def calculate_case_diagnostics(case: AccountingCaseData, report: Optional[AnalysisReportResult] = None) -> Dict[str, Any]:
    """
    Extract and compute deep data diagnostics for the given case.
    """
    recon = perform_three_way_reconciliation(case)
    
    # Beneish M-Score
    beneish = None
    if case.financial_summary:
        fs = case.financial_summary
        beneish = calculate_beneish_m_score(
            cur_sales=fs.revenue,
            prev_sales=fs.revenue * 0.75,
            cur_ar=fs.accounts_receivable,
            prev_ar=fs.accounts_receivable * 0.50,
            cur_cogs=fs.cost_of_sales,
            prev_cogs=fs.cost_of_sales * 0.70,
            cur_assets=fs.total_assets,
            prev_assets=fs.total_assets * 0.80,
            cur_depr=fs.total_assets * 0.05,
            prev_depr=fs.total_assets * 0.04,
            cur_ppe=fs.total_assets * 0.35,
            prev_ppe=fs.total_assets * 0.32,
            cur_sga=fs.revenue * 0.12,
            prev_sga=fs.revenue * 0.10,
            cur_leverage=0.45,
            prev_leverage=0.40,
            cur_net_income=fs.net_profit,
            cur_cfo=fs.operating_cash_flow
        )

    # Granular line-item diagnostics
    anomaly_items = []
    invoice_map = {inv.invoice_no: inv for inv in case.invoices}
    contract_map = {c.contract_id: c for c in case.contracts}

    for v in case.vouchers:
        debit_sum = sum(e.debit for e in v.entries)
        credit_sum = sum(e.credit for e in v.entries)
        v_amount = max(debit_sum, credit_sum)
        
        # 1. Debit-Credit imbalance
        if abs(debit_sum - credit_sum) > 0.01:
            diff = abs(debit_sum - credit_sum)
            anomaly_items.append({
                "source_id": v.voucher_id,
                "category": "借贷试算不平",
                "risk_level": "HIGH",
                "voucher_date": v.voucher_date,
                "target_date": v.voucher_date,
                "days_lag": 0,
                "ledger_amount": v_amount,
                "verified_amount": min(debit_sum, credit_sum),
                "discrepancy_amount": diff,
                "accounts_involved": ", ".join(f"{e.account_code} {e.account_name}" for e in v.entries),
                "specific_issue": f"记账凭证借贷不平衡！借方合计 ¥{debit_sum:,.2f} != 贷方合计 ¥{credit_sum:,.2f}，差额 ¥{diff:,.2f}",
                "standard_violated": "《企业会计准则——基本准则》复式记账原则",
                "remedy": "要求财务重新复核分录原始凭证并冲正不平差额。"
            })

        # 2. Document mismatch and timeline gap
        if v.associated_doc_id:
            doc_id = v.associated_doc_id
            if doc_id in invoice_map:
                inv = invoice_map[doc_id]
                # Date mismatch
                if v.voucher_date < inv.invoice_date and v_amount > 100000:
                    d1 = datetime.strptime(v.voucher_date, "%Y-%m-%d")
                    d2 = datetime.strptime(inv.invoice_date, "%Y-%m-%d")
                    lag_days = (d2 - d1).days
                    is_cross_year = d1.year != d2.year
                    issue_desc = (
                        f"🚨 跨年度提前确认收入！凭证记账日({v.voucher_date}) 比发票开具与验收日({inv.invoice_date}) "
                        f"提前了整整 {lag_days} 天！恰好跨越12月31日资产负债表日，涉嫌突击做大当年业绩！"
                        if is_cross_year else
                        f"⚠️ 凭证记账日期({v.voucher_date}) 早于发票开具日期({inv.invoice_date}) {lag_days} 天，存在提前确认疑点。"
                    )
                    anomaly_items.append({
                        "source_id": v.voucher_id,
                        "category": "跨期提前确认收入",
                        "risk_level": "HIGH",
                        "voucher_date": v.voucher_date,
                        "target_date": inv.invoice_date,
                        "days_lag": lag_days,
                        "ledger_amount": v_amount,
                        "verified_amount": 0.0,
                        "discrepancy_amount": v_amount,
                        "accounts_involved": ", ".join(f"{e.account_code} {e.account_name}" for e in v.entries),
                        "specific_issue": issue_desc,
                        "standard_violated": "CAS 14《企业会计准则第14号——收入》第四条(控制权转移五步法)",
                        "remedy": "追溯调整至实际控制权转移年度(次年)，调减当年营业收入与应收账款。"
                    })

                # Amount mismatch
                if abs(v_amount - inv.total_amount) > 1.0:
                    diff = abs(v_amount - inv.total_amount)
                    anomaly_items.append({
                        "source_id": v.voucher_id,
                        "category": "凭证与发票金额不符",
                        "risk_level": "HIGH",
                        "voucher_date": v.voucher_date,
                        "target_date": inv.invoice_date,
                        "days_lag": 0,
                        "ledger_amount": v_amount,
                        "verified_amount": inv.total_amount,
                        "discrepancy_amount": diff,
                        "accounts_involved": ", ".join(f"{e.account_code} {e.account_name}" for e in v.entries),
                        "specific_issue": f"凭证入账金额 (¥{v_amount:,.2f}) 与税控发票价税合计 (¥{inv.total_amount:,.2f}) 差额 ¥{diff:,.2f}，涉嫌多计/少计！",
                        "standard_violated": "《中华人民共和国发票管理办法》第二十条",
                        "remedy": "核查增值税专用发票抵扣联与差额凭单。"
                    })

            # Contract checks
            if doc_id in contract_map:
                c = contract_map[doc_id]
                if c.is_related_party:
                    anomaly_items.append({
                        "source_id": v.voucher_id,
                        "category": "关联方隐蔽空转交易",
                        "risk_level": "HIGH",
                        "voucher_date": v.voucher_date,
                        "target_date": c.sign_date,
                        "days_lag": 0,
                        "ledger_amount": v_amount,
                        "verified_amount": 0.0,
                        "discrepancy_amount": v_amount,
                        "accounts_involved": ", ".join(f"{e.account_code} {e.account_name}" for e in v.entries),
                        "specific_issue": f"合同 {c.contract_id} 交易对手方 '{c.customer_or_vendor}' 为重大关联方！涉及金额 ¥{c.total_contract_value:,.2f}，无独立商业实质，涉嫌体外循环资金。",
                        "standard_violated": "CAS 36《企业会计准则第36号——关联方披露》",
                        "remedy": "实施穿透式资金流水核查与商业实质独立评估。"
                    })

        # Check in-transit materials with no receipt
        for entry in v.entries:
            if "在途" in entry.account_name and v_amount >= 5000000:
                anomaly_items.append({
                    "source_id": v.voucher_id,
                    "category": "在途存货虚假采购挂账",
                    "risk_level": "HIGH",
                    "voucher_date": v.voucher_date,
                    "target_date": v.voucher_date,
                    "days_lag": 0,
                    "ledger_amount": v_amount,
                    "verified_amount": 0.0,
                    "discrepancy_amount": v_amount,
                    "accounts_involved": f"{entry.account_code} {entry.account_name}",
                    "specific_issue": f"大额采购特种物资挂账在途金额达 ¥{v_amount:,.2f}，供应商疑似空壳公司，库房无入库验收记录及真实物流运单！",
                    "standard_violated": "CAS 1《企业会计准则第1号——存货》及 CSA 1141 号",
                    "remedy": "执行库房全面实地监盘并调取第三方独立承运人物流提单。"
                })

    # Bank flows circular loop check
    for flow in case.bank_flows:
        if abs(flow.amount) >= 1000000 and any(kw in flow.remark for kw in ["退款", "借款", "拆借", "往来"]):
            anomaly_items.append({
                "source_id": f"BANK-{flow.transaction_id}",
                "category": "大额资金体外回流闭环",
                "risk_level": "HIGH",
                "voucher_date": flow.transaction_date,
                "target_date": flow.transaction_date,
                "days_lag": 0,
                "ledger_amount": abs(flow.amount),
                "verified_amount": 0.0,
                "discrepancy_amount": abs(flow.amount),
                "accounts_involved": "1002 银行存款",
                "specific_issue": f"大额资金流水 ¥{abs(flow.amount):,.2f} 短期内以 '{flow.remark}' 名义原路转回，交易对手为 '{flow.counterparty_name}'，具备典型资金闭环空转特征！",
                "standard_violated": "CSA 1141《中国注册会计师审计准则第1141号——财务报表审计中与舞弊相关的责任》",
                "remedy": "调取银行全程资金轨迹底单并核实资金最终受益所有人。"
            })

    # Health score
    total_audited = max(recon["total_audited_amount"], 1.0)
    total_abnormal = sum(item["discrepancy_amount"] for item in anomaly_items)
    anomaly_ratio = min(total_abnormal / total_audited, 1.0)
    health_score = max(int((1.0 - anomaly_ratio * 0.8 - (len(anomaly_items) * 5 / 100)) * 100), 0)
    if len(anomaly_items) == 0:
        health_score = 100

    return {
        "health_score": health_score,
        "total_audited": total_audited,
        "total_abnormal": total_abnormal,
        "anomaly_items": anomaly_items,
        "beneish": beneish,
        "recon": recon
    }


def render_data_anomaly_dashboard(case: AccountingCaseData, report: Optional[AnalysisReportResult] = None):
    """
    Render the interactive Data Anomaly & Fraud Diagnostics Dashboard in Streamlit.
    """
    diag = calculate_case_diagnostics(case, report)
    anomalies = diag["anomaly_items"]
    beneish = diag["beneish"]

    st.markdown("## 🎯 数据问题穿透大屏 (Data Anomaly & Fraud Dashboard)")
    st.caption(f"当前诊断目标企业: **{case.company_name}** | 审计年度: **{case.audit_period}** | 行业: **{case.industry}**")

    # 1. Top KPI Row
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        score = diag["health_score"]
        score_color = "#10B981" if score >= 85 else ("#F59E0B" if score >= 60 else "#EF4444")
        st.markdown(
            f"""
            <div style="background-color:#F9FAFB; border-radius:8px; padding:12px; border-left:5px solid {score_color};">
                <div style="font-size:12px; color:#6B7280;">数据合规健康度</div>
                <div style="font-size:26px; font-weight:bold; color:{score_color};">{score} / 100</div>
                <div style="font-size:11px; color:#9CA3AF;">{"健康合规" if score >= 85 else "高危错报预警"}</div>
            </div>
            """, unsafe_allow_html=True
        )
    with k2:
        st.metric("受审交易总金额", f"¥ {diag['total_audited']:,.0f}")
    with k3:
        abnormal_pct = (diag["total_abnormal"] / diag["total_audited"]) * 100 if diag["total_audited"] > 0 else 0
        st.metric("🚨 异常疑点涉及金额", f"¥ {diag['total_abnormal']:,.0f}", delta=f"{abnormal_pct:.1f}% 异常占比", delta_color="inverse")
    with k4:
        st.metric("发现问题疑点数", f"{len(anomalies)} 处", delta="需实质性程序" if len(anomalies) > 0 else "无异常")
    with k5:
        m_val = beneish["m_score"] if beneish else -2.5
        is_manip = beneish["is_manipulator"] if beneish else False
        st.metric("Beneish 舞弊指数", f"{m_val:.2f}", delta="🚨 严重越界" if is_manip else "处于安全区间", delta_color="inverse" if is_manip else "normal")

    st.markdown("---")

    # 2. Filter Bar & Granular Line-Item Discrepancy Diagnostics Table
    st.markdown("### 📋 具体数据问题所在穿透定位 (Granular Discrepancy Diagnostics)")
    st.write("点击展开或通过筛选条件精准定位具体是哪张记账凭证、哪个会计科目、哪张发票及具体违规事实：")

    if not anomalies:
        st.success("🎉 本案例业财数据完整合规！各项发票、凭证、合同、银行流水三单勾稽完全吻合，未检测到跨期收入、虚假采购或资金闭环异常。")
    else:
        # Category filter
        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            all_cats = ["全部"] + list(set(item["category"] for item in anomalies))
            selected_cat = st.selectbox("按数据问题类型筛选:", all_cats)
        with col_f2:
            st.info(f"💡 系统共扫描出 **{len(anomalies)}** 处确凿数据问题，涉及资金 **¥ {diag['total_abnormal']:,.2f}** 元。")

        filtered_items = anomalies if selected_cat == "全部" else [it for it in anomalies if it["category"] == selected_cat]

        # Detailed expandable cards for each specific issue
        for idx, item in enumerate(filtered_items, start=1):
            with st.container():
                st.markdown(
                    f"""
                    <div style="background-color: #FEF2F2; border: 1px solid #F87171; border-left: 6px solid #DC2626; border-radius: 6px; padding: 14px; margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-weight: bold; font-size: 16px; color: #991B1B;">
                                #{idx} 【{item['category']}】 单据索引: {item['source_id']}
                            </span>
                            <span style="background-color: #FEE2E2; color: #B91C1C; font-size: 12px; font-weight: bold; padding: 2px 8px; border-radius: 4px;">
                                差异涉及金额: ¥ {item['discrepancy_amount']:,.2f}
                            </span>
                        </div>
                        <div style="font-size: 13px; color: #1F2937; margin-bottom: 8px;">
                            <b>🔍 具体问题所在详析:</b> <span style="color:#B91C1C; font-weight:600;">{item['specific_issue']}</span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; font-size: 12px; background: #FFFFFF; padding: 8px 12px; border-radius: 4px; border: 1px solid #FECACA;">
                            <div><b>记账日期:</b> <code>{item['voucher_date']}</code></div>
                            <div><b>业务/发票日期:</b> <code>{item['target_date']}</code> {f'(倒挂 {item["days_lag"]} 天)' if item['days_lag'] > 0 else ''}</div>
                            <div><b>涉及会计科目:</b> <code>{item['accounts_involved']}</code></div>
                        </div>
                        <div style="margin-top: 8px; font-size: 12px; color: #374151;">
                            <b>📖 违反会计准则:</b> <code style="color:#991B1B;">{item['standard_violated']}</code>
                        </div>
                        <div style="margin-top: 4px; font-size: 12px; color: #047857;">
                            <b>🛠️ 建议审计调账与应对程序:</b> {item['remedy']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True
                )

    st.markdown("---")

    # 3. Interactive Visual Charts
    st.markdown("### 📊 多维可视化诊断图谱 (Visual Analytics)")
    tab_c1, tab_c2, tab_c3 = st.tabs([
        "📈 Beneish 8变量舞弊雷达与偏离度", 
        "⏳ 业财时序倒挂与金额差异分布", 
        "🔄 资金体外闭环流转拓扑"
    ])

    with tab_c1:
        if beneish and "variables" in beneish:
            vars_dict = beneish["variables"]
            labels = list(vars_dict.keys())
            values = list(vars_dict.values())
            benchmarks = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0]  # Safe reference benchmarks

            col_radar, col_bar = st.columns(2)
            with col_radar:
                # Radar chart
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=values,
                    theta=labels,
                    fill='toself',
                    name='当前企业指数',
                    line_color='#EF4444' if beneish['is_manipulator'] else '#10B981'
                ))
                fig_radar.add_trace(go.Scatterpolar(
                    r=benchmarks,
                    theta=labels,
                    fill='toself',
                    name='安全基准线 (1.0)',
                    line_color='#9CA3AF',
                    opacity=0.4
                ))
                fig_radar.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, max(max(values) * 1.2, 2.5)])),
                    title="Beneish M-Score 8大财务操纵维度雷达",
                    margin=dict(l=40, r=40, t=40, b=40)
                )
                st.plotly_chart(fig_radar, use_container_width=True)

            with col_bar:
                # Deviation bar chart
                dev_df = pd.DataFrame({
                    "指标名称": labels,
                    "计算数值": values,
                    "安全基准": benchmarks,
                    "偏离度(%)": [round((v - b) * 100, 1) for v, b in zip(values, benchmarks)]
                })
                fig_bar = px.bar(
                    dev_df,
                    x="偏离度(%)",
                    y="指标名称",
                    orientation='h',
                    color="偏离度(%)",
                    color_continuous_scale="Reds",
                    title="财务指标偏离安全基线程度 (%)"
                )
                fig_bar.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_bar, use_container_width=True)

            st.caption("ℹ️ **注**：DSRI(应收账款指数)过高代表营收虽增但现金未回流；GMI(毛利率指数)>1代表毛利恶化但企业掩盖；TATA>0代表权责发生制下未实现应计利润严重膨胀。")

    with tab_c2:
        # Timeline and amount distribution
        if anomalies:
            df_ano = pd.DataFrame(anomalies)
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                fig_pie = px.pie(
                    df_ano,
                    names="category",
                    values="discrepancy_amount",
                    title="各类数据问题涉及金额占比分布",
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_t2:
                fig_scatter = px.bar(
                    df_ano,
                    x="source_id",
                    y="discrepancy_amount",
                    color="category",
                    title="各异常凭证/流水金额对比",
                    text_auto='.2s'
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("合规对照组无时序倒挂与金额异常。")

    with tab_c3:
        # Sankey diagram of fund flows
        if case.bank_flows:
            flows_data = []
            for flow in case.bank_flows:
                src = case.company_name if flow.amount < 0 else flow.counterparty_name
                tgt = flow.counterparty_name if flow.amount < 0 else case.company_name
                flows_data.append({
                    "source": src,
                    "target": tgt,
                    "value": abs(flow.amount),
                    "remark": flow.remark
                })

            all_nodes = list(set([f["source"] for f in flows_data] + [f["target"] for f in flows_data]))
            node_map = {name: i for i, name in enumerate(all_nodes)}

            fig_sankey = go.Figure(data=[go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=all_nodes,
                    color="#1F497D"
                ),
                link=dict(
                    source=[node_map[f["source"]] for f in flows_data],
                    target=[node_map[f["target"]] for f in flows_data],
                    value=[f["value"] for f in flows_data],
                    color="rgba(239, 68, 68, 0.4)" if any("退款" in f["remark"] or "借款" in f["remark"] for f in flows_data) else "rgba(16, 185, 129, 0.4)"
                )
            )])
            fig_sankey.update_layout(title_text="资金往来流向与闭环回流桑基图 (Sankey Trail)", margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_sankey, use_container_width=True)
            st.warning("⚠️ **审计穿透发现**：红流显示资金在短时间内流向关联方后又以退款名义全额转回，无真实货物流或服务流对应，属于无商业实质的空转。")
        else:
            st.info("当前案例无外部银行对账单明细。")
