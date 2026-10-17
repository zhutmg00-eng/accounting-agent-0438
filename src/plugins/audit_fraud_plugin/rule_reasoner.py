"""
确定性规则推理器：把各算子的结构化结果直接组装成发现项与底稿。

* 离线模式（MOCK）下取代原来"解析提示词 + 按公司名/背景关键词套模板"的启发式引擎——
  本模块不含任何公司名称或案例背景关键词，只依据算子输出的异常类型与会计科目口径。
* 在线模式下作为"补位"：模型没有覆盖到的确定性异常，以确定性发现项补入报告。

每条发现项的金额都注明口径（amount_basis），风险等级按 CSA 1221 实际执行的重要性划分：
金额 ≥ 实际执行的重要性 → HIGH；低于它但高于明显微小错报临界值 → MEDIUM；否则 LOW。
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Tuple

from src.core.schemas import AccountingCaseData, EvidenceItem, RiskFinding, RiskLevel
from src.plugins.audit_fraud_plugin.substantive import component_amount, primary_voucher_family

RECON_FAMILIES: Dict[str, Tuple[str, str, str, str]] = {
    "单据缺失或虚构/伪造业务单据": (
        "记账凭证引用的业务单据在合同、发票、流水中均不存在",
        "CSA 1141 舞弊风险；CAS 14 收入确认（交易真实性）", "auto",
        "向客户/供应商函证交易与余额，调取出入库、物流与验收原件，核实单据是否真实存在"),
    "大额业务单据缺失发票及银行流水(三单勾稽缺失)": (
        "大额业务仅有合同与凭证、缺少发票和资金流水支持",
        "CAS 14 收入确认；CSA 1301 审计证据", "revenue",
        "检查发票开具与认证记录、银行收付款回单，函证交易对手"),
    "凭证与合同金额不符": (
        "记账金额与合同约定金额不一致",
        "CAS 14 交易价格；CSA 1301 审计证据", "diff",
        "取得合同变更/补充协议，复核计价与结算单"),
    "凭证与发票金额不符": (
        "记账金额与发票价税合计不一致", "CSA 1301 审计证据；增值税发票管理", "diff",
        "核对发票原件与税务系统记录，复核差异原因"),
    "凭证与银行流水金额不符": (
        "记账金额与银行流水金额不一致", "CSA 1312 函证；CSA 1301 审计证据", "diff",
        "获取银行对账单原件并函证，复核差异"),
    "凭证开具早于发票日期(疑似跨期提前确认收入)": (
        "收入记账日期早于发票开具日期，存在跨期确认风险", "CAS 14 第十三条 控制权转移时点", "revenue",
        "执行截止测试：核对发货、签收、验收单日期与记账期间"),
    "关联方隐蔽重大交易未做专项披露": (
        "与关联方的重大交易需穿透商业实质并核查披露", "CAS 36 关联方披露", "voucher",
        "获取关联方清单与股权穿透，核查交易定价公允性与披露完整性"),
    "大额资金异常往来与体外循环/造假嫌疑": (
        "大额资金往来的附言显示拆借、过桥或存单等非经营性特征", "CSA 1141 舞弊风险；CAS 22 金融工具", "flow",
        "函证银行账户与存单，追踪资金最终流向"),
    "借贷不平衡": (
        "记账凭证借贷不平衡", "《会计基础工作规范》；CSA 1141", "diff",
        "调取原始凭证与总账，核实记账差错或篡改"),
}


def _level(amount: float, mat: Dict[str, Any], floor: RiskLevel = RiskLevel.LOW) -> RiskLevel:
    pm = mat.get("performance_materiality") or 0.0
    trivial = mat.get("clearly_trivial_threshold") or 0.0
    lvl = RiskLevel.HIGH if amount >= pm else (RiskLevel.MEDIUM if amount >= trivial else RiskLevel.LOW)
    order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
    return order[max(order.index(lvl), order.index(floor))]


def _ev(kind: str, ref: str, detail: str, source_file: str = "") -> EvidenceItem:
    return EvidenceItem(evidence_type=kind, source_ref=ref, detail=detail, source_file=source_file)


def build_rule_findings(case: AccountingCaseData, tool_results: Dict[str, Any],
                        include_recon: bool = True, skip_ids: set = frozenset()) -> List[RiskFinding]:
    """把算子结果变成发现项。``skip_ids``：在线模式中模型已覆盖的单据号，不再重复补位。"""
    sp = tool_results.get("substantive") or {}
    mat = sp.get("materiality") or {}
    vouchers = {v.voucher_id: v for v in case.vouchers}
    out: List[RiskFinding] = []
    substantive_covered_vids = set()

    def add(title, level, std, amount, basis, mechanism, evidences, procedure, rule, covered_vids=()):
        refs = " ".join(e.source_ref for e in evidences)
        if skip_ids and any(i and i in refs for i in skip_ids):
            return
        substantive_covered_vids.update(covered_vids)
        out.append(RiskFinding(
            finding_id=f"RF-R{len(out) + 1:02d}", title=title, risk_level=level, accounting_standard=std,
            impact_amount=round(amount, 2), suspected_mechanism=mechanism, evidences=evidences,
            suggested_procedure=procedure, rule_evidence=f"{rule}（金额口径：{basis}）",
            model_explanation="由确定性算子生成，未经大模型",
            human_verification_flag="确定性程序检出，结论由注册会计师复核确认",
        ))

    # ---- 1. 专项实质性程序
    bb = sp.get("book_to_bank") or {}
    nb = [x for x in bb.get("book_without_bank", []) if x["direction"] == "收款"]
    if nb:
        by_basis: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
        for x in nb:
            v = vouchers.get(x["voucher_id"])
            sub_k = "利息或理财收入" if (v and any("利息" in (e.summary or "") or "6051" in (e.account_code or "") or "6603" in (e.account_code or "") for e in v.entries)) else "银行存款收款"
            by_basis.setdefault(sub_k, []).append(x)
        for sub_k, grp in by_basis.items():
            amt = sum(x["amount"] for x in grp)
            vids = [x["voucher_id"] for x in grp]
            add(f"银行存款账面{sub_k}在银行对账单中无对应流水（有账无流）", _level(amt, mat, RiskLevel.MEDIUM),
                "CSA 1312 函证；CAS 22 金融工具；CSA 1141 舞弊风险", amt, "银行存款借方",
                "银行存款日记账记录的收款无法在对账单中找到同金额、同期间的流水，可能存在虚构回款或虚增货币资金",
                [_ev("账实核对", f"凭证[{x['voucher_id']}]", f"{x['date']} 收款 ¥{x['amount']:,.2f}，对账单无对应流水；{x['summary']}") for x in grp[:15]],
                "向开户行独立函证余额与发生额，现场打印对账单，核对网银流水", "银企账实核对算子", covered_vids=vids)
    rs = bb.get("restricted_cash_signals") or []
    if rs:
        amt = sum(x["amount"] for x in rs if x["source"] == "合同") or max((x["amount"] for x in rs), default=0.0)
        add("货币资金存在质押、担保、存单或资金归集等受限线索，需核查披露", RiskLevel.MEDIUM,
            "CAS 22 金融工具列报；CAS 36 关联方披露；上市公司监管指引第 8 号", amt, "合同/流水金额",
            "定期存单质押担保或资金归集会使账面货币资金不可自由支配，若未披露将误导报表使用者",
            [_ev("受限资金线索", f"{'合同' if x['source'] == '合同' else '流水'}[{x['id']}]", f"{x['party']}：{x['detail']}") for x in rs[:10]],
            "向银行函证存单是否质押、冻结或用于担保，检查担保合同与董事会决议", "银企账实核对算子")

    b2b = sp.get("back_to_back") or {}
    pairs = b2b.get("pairs") or []
    if pairs:
        amt = sum(p["revenue"] for p in pairs)
        strong = b2b.get("strong_pairs", 0)
        vids = [p["sale_voucher"] for p in pairs] + [p["purchase_voucher"] for p in pairs]
        add("短期购销配对、毛利极低" + ("且货权不实际移转，疑似无商业实质贸易" if strong else "，需判断总额法/净额法"),
            _level(amt, mat, RiskLevel.MEDIUM if strong else RiskLevel.LOW),
            "CAS 14 第五条 商业实质；CAS 14 第三十四条 主要责任人与代理人", amt, "主营/其他业务收入贷方（不含税）",
            "采购入库与对外销售在数日内配对完成、几乎无毛利" + ("，合同约定货权转移/仓单转移/自提而不移库，企业未承担存货风险" if strong else ""),
            [_ev("购销配对", f"凭证[{p['sale_voucher']}] ↔ 凭证[{p['purchase_voucher']}]",
                 f"{p['sale_date']} 售予 {p['customer']} ¥{p['revenue']:,.2f}；{p['purchase_date']} 购自 {p['supplier']} ¥{p['cost']:,.2f}；毛利率 {p['gross_margin']:.2%}；{p['terms']}") for p in pairs[:10]],
            "检查货权凭证、物流与仓储记录，判断企业是否承担存货风险和定价权；必要时按净额法调整", "背靠背贸易算子", covered_vids=vids)

    cc = sp.get("cutoff_and_cost") or {}
    cut = cc.get("cutoff_items") or []
    if cut:
        cut_groups: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
        for x in cut:
            g_key = x["contract_id"] if any(k in (x.get("contract_condition") or "") for k in ("解除", "终止", "审定结算", "结算审定")) else "DEFAULT_CUTOFF"
            cut_groups.setdefault(g_key, []).append(x)
        for g_key, grp in cut_groups.items():
            amt = sum(x["revenue"] for x in grp)
            strong = any(x["risk"] == "HIGH" for x in grp)
            vids = [x["voucher_id"] for x in grp]
            evs = []
            for x in grp[:10]:
                evs.append(_ev("截止测试", f"凭证[{x['voucher_id']}] 合同[{x['contract_id']}]",
                               f"{x['date']} 确认 ¥{x['revenue']:,.2f}；合同条款：{x['contract_condition']}；入账依据：{x['recognition_evidence']}"))
                for b in x["post_period_work_payments"][:3]:
                    evs.append(_ev("期后付款", f"流水[{b['transaction_id']}]", f"{b['time']} {b['remark']} ¥{abs(b['amount']):,.2f}"))
            add("合同未达控制权转移条件或已解除/审定结算，违规提前或多确认收入" + ("（存在期后施工付款或零回款反证）" if strong else ""),
                _level(amt, mat, RiskLevel.MEDIUM), "CAS 14 第四条、第十三条 控制权转移时点", amt,
                "主营/其他业务收入贷方（不含税）",
                "履约义务在资产负债表日尚未完成或合同基础已变更，收入被提前或超额确认至本期",
                evs, "取得终验/吊装/排期/结算报告与验收日期，检查期后安装、施工支出与回款，执行截止测试", "截止与成本配比算子", covered_vids=vids)
    gaps = cc.get("cost_gaps") or []
    if gaps:
        amt = sum(g["goods_shipped_balance"] - g["cost_carried"] for g in gaps)
        vids = [v for g in gaps for v in g["vouchers"]]
        add("已确认收入的合同，其发出商品未结转营业成本", _level(amt, mat, RiskLevel.MEDIUM),
            "CAS 14 第三十五条 收入与成本配比；CAS 1 存货", amt, "发出商品借方余额（应结转未结转）",
            "收入已确认而对应发出商品仍挂账，营业成本少计、利润虚增",
            [_ev("成本配比", " ".join(f"凭证[{v}]" for v in g["vouchers"][:6]) + f" 单据[{g['doc']}]",
                 f"收入 ¥{g['revenue']:,.2f}，发出商品余额 ¥{g['goods_shipped_balance']:,.2f}，已结转成本 ¥{g['cost_carried']:,.2f}") for g in gaps[:10]],
            "盘点发出商品，复核成本结转计算表与收入确认清单的对应关系", "截止与成本配比算子", covered_vids=vids)

    tp = sp.get("third_party_and_prepay") or {}
    third = tp.get("third_party_receipts") or []
    if third:
        amt = sum(x["amount"] for x in third)
        vids = [x["voucher_id"] for x in third]
        add("应收账款由非客户的第三方代为回款", _level(amt, mat, RiskLevel.MEDIUM),
            "CSA 1141 舞弊风险；CAS 14 收入真实性；CAS 36 关联方", amt, "应收账款贷方（对应银行收款）",
            "回款付款方与账面客户不一致或附言为代付，可能是体外资金回流粉饰回款",
            [_ev("第三方回款", f"凭证[{x['voucher_id']}] 流水[{x['transaction_id']}]",
                 f"账面客户 {x['customer_on_books']}，实际付款方 {x['actual_payer']}，¥{x['amount']:,.2f}，附言：{x['remark']}") for x in third[:10]],
            "取得代付协议与三方确认，穿透付款方与公司及客户的关系", "第三方回款与预付算子", covered_vids=vids)
    pp = tp.get("prepayments") or []
    if pp:
        amt = sum(x["outstanding"] for x in pp)
        rel = any(x["related_party"] for x in pp)
        vids = [v for x in pp for v in x["vouchers"]]
        add("大额预付款项期内未结转" + ("且付给关联方，疑似非经营性资金占用" if rel else "，供应商无进项发票"),
            _level(amt, mat, RiskLevel.MEDIUM if rel else RiskLevel.LOW),
            "CAS 36 关联方披露；CSA 1141 舞弊风险", amt, "预付账款借方余额（期内未结转部分）",
            "以预付采购款名义流出的资金长期未形成存货或资产，可能被关联方占用或延迟结转",
            [_ev("预付款", " ".join(f"凭证[{v}]" for v in x["vouchers"][:6]),
                 f"{x['party']}：预付 ¥{x['paid']:,.2f}，已结转 ¥{x['settled']:,.2f}，余额 ¥{x['outstanding']:,.2f}{'（关联方）' if x['related_party'] else ''}") for x in pp[:10]],
            "函证预付余额，检查采购合同履行与到货情况，穿透收款方股权", "第三方回款与预付算子", covered_vids=vids)

    # ---- 2. 职业判断类算子
    jd = sp.get("judgment") or {}
    J = [
        ("expense_completeness", "已发生费用未计入当期损益或异常冲减成本费用",
         "《企业会计准则——基本准则》第九条 权责发生制；CAS 1 存货；CAS 9 职工薪酬；CAS 17 借款费用", RiskLevel.MEDIUM,
         "已发生服务费挂账资产、期末违规将成本/费用转入存货/预付/在建工程、冲回已计提薪酬或将本期费用推迟至期后入账，少计当期成本费用、虚增利润",
         "取得服务验收/结算单、投料与成本结转计算表，复核费用归属期与资本化条件，冲回违规冲减分录", "费用完整性算子"),
        ("impairment", "资产减值准备期末冲回或逾期/违约应收款未单项计提减值",
         "CAS 8 资产减值；CAS 22 预期信用损失与单项计提", RiskLevel.MEDIUM,
         "期末无依据冲回减值准备直接增加利润；或已逾期违约、停止拨付及长期未收回的应收/预付未单项足额计提减值",
         "复核减值测试模型与冲回依据，对逾期及违约客户实施单项信用风险评估并补提坏账准备", "减值判断算子"),
        ("liability_writeoff", "应付款项无资金流动直接核销转入损益或冲减成本",
         "CAS 22 第十二条 金融负债终止确认", RiskLevel.MEDIUM,
         "借记应付账款/其他应付款、贷记营业外收入或主营业务成本，无付款也无债权人豁免文件，属于无依据核销负债虚增利润",
         "取得债权人豁免函或法院文书，独立函证债权人，检查期后是否仍有付款", "负债核销算子"),
        ("related_reclass", "关联方资金占用重分类或无商业实质购销/保理业务",
         "CAS 36 关联方披露；CAS 1 存货；CAS 14 收入商业实质；上市公司监管指引第 8 号", RiskLevel.MEDIUM,
         "期末预付转其他应收形成资金占用，或开展无实物流转/无对价支付的存货采购、关联销售及无放款本金的保理利息确认",
         "函证交易对手并实地监盘存货，核查保理放款本金流水，穿透交易对手股权与实际控制人关系", "商业实质与关联方算子"),
        ("provisions", "或有事项（诉讼/担保/赔偿）未足额确认预计负债或违规确认追偿资产",
         "CAS 13 或有事项第四条、第七条", RiskLevel.MEDIUM,
         "存在败诉判决、裁决或担保义务而未确认预计负债，或在确认预计负债时将尚未基本确定的追偿款挂账其他应收款以抵减损失",
         "查阅诉讼与担保台账、法院判决书及律师询证函，冲回未基本确定的追偿资产并补提预计负债", "或有事项算子"),
    ]
    for key, base_title, std, floor, mech, proc, rule in J:
        items = (jd.get(key) or {}).get("items", [])
        if key == "liability_writeoff":
            items = [x for x in items if x.get("weak_support") or x.get("year_end")]
        if not items:
            continue
        by_kind: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
        for x in items:
            by_kind.setdefault(x.get("kind", base_title), []).append(x)
        for kind_name, k_items in by_kind.items():
            amt = sum(x["amount"] for x in k_items)
            lvl = _level(amt, mat, floor)
            vids = []
            evs = []
            for x in k_items[:10]:
                v_list = x.get("vouchers") or ([x["voucher_id"]] if x.get("voucher_id") else [])
                vids.extend(v_list)
                ref_str = " ".join(f"凭证[{v}]" for v in v_list) if v_list else f"{x.get('source', '')}[{x.get('id', '')}]"
                evs.append(_ev(kind_name, ref_str, x["detail"]))
            title = f"{base_title}：{kind_name}" if len(by_kind) > 1 else base_title
            add(title, lvl, std, amt, k_items[0]["amount_basis"], mech, evs, proc, rule, covered_vids=vids)

    # ---- 3. 三单勾稽算子
    if include_recon:
        groups: "OrderedDict[Tuple[str, str], List[Dict[str, Any]]]" = OrderedDict()
        for d in (tool_results.get("reconciliation") or {}).get("discrepancies", []):
            dtype = d.get("type", "")
            vid = str(d.get("voucher_id", ""))
            if dtype in ("凭证与合同金额不符", "大额业务单据缺失发票及银行流水(三单勾稽缺失)", "凭证开具早于发票日期(疑似跨期提前确认收入)") and vid in substantive_covered_vids:
                continue
            v = vouchers.get(vid)
            sub_fam = primary_voucher_family(v) if (dtype == "单据缺失或虚构/伪造业务单据" and v is not None) else "default"
            groups.setdefault((dtype, sub_fam), []).append(d)

        for (dtype, sub_fam), items in groups.items():
            title, std, fam, proc = RECON_FAMILIES.get(
                dtype, (dtype, "CSA 1141 舞弊风险", "voucher", "实施进一步实质性程序"))
            if fam == "auto":
                fam = sub_fam if sub_fam != "default" else "revenue"
                if fam == "bills":
                    title = "记账凭证引用的应收票据/背书单据在真实台账中不存在"
                elif fam == "cash_in" and len(groups) > 1:
                    title = "记账凭证引用的银行回单/存款单据在银行流水中不存在"
            amount, basis_set, evs = 0.0, set(), []
            for d in items:
                vid = str(d.get("voucher_id", ""))
                v = vouchers.get(vid)
                if fam == "diff" or v is None:
                    a, b = float(d.get("amount", 0.0)), ("差异额" if fam == "diff" else "流水金额")
                else:
                    a, b = component_amount(v, fam)
                amount += a
                basis_set.add(b)
                ref = f"凭证[{vid}]" if v is not None else (f"流水[{vid.replace('BANK-', '')}]" if vid.startswith("BANK-") else vid)
                if d.get("doc_id"):
                    ref += f" 单据[{d['doc_id']}]"
                if v is not None and case.invoices:
                    v_line_amts = {e.debit or e.credit for e in v.entries if (e.debit or e.credit)}
                    for inv in case.invoices:
                        if any(abs(inv.total_amount - la) <= max(la * 0.001, 1.0) for la in v_line_amts):
                            ref += f" 发票[{inv.invoice_no}]"
                evs.append(_ev("勾稽比对", ref, d.get("detail", ""), "业财勾稽核查结果"))
            is_estimate = any(
                vouchers.get(str(d.get("voucher_id", ""))) and any("跌价准备" in (e.account_name or "") or "预计负债" in (e.account_name or "") for e in vouchers[str(d.get("voucher_id", ""))].entries)
                for d in items
            )
            if is_estimate and amount < (mat.get("overall_materiality") or float("inf")):
                level = RiskLevel.MEDIUM
            else:
                level = _level(amount, mat)
            add(title, level, std, amount, "、".join(sorted(basis_set)),
                f"{len(items)} 处{dtype}", evs[:15], proc, "三单勾稽算子")

    return out


def offline_report_json(case: AccountingCaseData, tool_results: Dict[str, Any]) -> Dict[str, Any]:
    """离线模式的报告骨架：发现项由 build_rule_findings 生成（在 parse_and_verify 中加入）。"""
    findings = build_rule_findings(case, tool_results)
    mat = (tool_results.get("substantive") or {}).get("materiality") or {}
    sig = [f for f in findings if f.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM)]
    if any(f.risk_level == RiskLevel.HIGH for f in findings):
        rating = "HIGH"
    elif sig:
        rating = "MEDIUM"
    elif findings:
        rating = "LOW"
    else:
        rating = "CLEAN"
    distinct: List[float] = []
    for f in sig:
        if not any(abs(f.impact_amount - a) <= max(a * 0.001, 1.0) for a in distinct):
            distinct.append(f.impact_amount)
    total = sum(distinct)
    summary = (
        f"【离线确定性模式】{case.company_name}：确定性程序检出 {len(findings)} 类异常，"
        f"其中达到重要性的 {len(sig)} 类，去重后涉及金额 ¥{total:,.2f}（实际执行的重要性 ¥{mat.get('performance_materiality', 0):,.2f}）。"
        if findings else
        f"【离线确定性模式】{case.company_name}：三单勾稽、银企核对、截止与配比、第三方回款、背靠背贸易、职业判断算子及全量分录测试均未检出达到明显微小临界值的异常。"
    )
    return {"executive_summary": summary, "overall_risk_rating": rating, "risk_findings": [], "workpapers": [],
            "_rule_findings": findings}
