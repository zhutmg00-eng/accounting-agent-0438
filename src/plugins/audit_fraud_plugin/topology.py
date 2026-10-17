"""
资金拓扑与业财单据链（供前端"穿透"页渲染），全部由确定性算子从案例数据生成，不读取真值字段。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from src.core.schemas import AccountingCaseData
from src.plugins.audit_fraud_plugin.analytics import detect_fund_round_trips
from src.plugins.audit_fraud_plugin.judgment import judgment_ids
from src.plugins.audit_fraud_plugin.substantive import run_substantive_procedures, voucher_total, _same_party
from src.plugins.audit_fraud_plugin.tools import perform_three_way_reconciliation


def _d(s: str):
    try:
        return datetime.strptime((s or "")[:10], "%Y-%m-%d")
    except ValueError:
        return None


def build_topology(case: AccountingCaseData, max_parties: int = 8) -> Dict[str, Any]:
    rt = detect_fund_round_trips(case)
    recon = perform_three_way_reconciliation(case)
    sp = run_substantive_procedures(case)

    flagged_flows = {l["out_id"] for l in rt["loops"]} | {l["in_id"] for l in rt["loops"]}
    flagged_flows |= {str(d.get("voucher_id", "")).replace("BANK-", "") for d in recon["discrepancies"]
                      if str(d.get("voucher_id", "")).startswith("BANK-")}
    flagged_flows |= {x["transaction_id"] for x in sp["third_party_and_prepay"]["third_party_receipts"]}
    flagged_flows |= {x["id"] for x in sp["book_to_bank"]["restricted_cash_signals"] if x["source"] == "流水"}
    for x in sp["cutoff_and_cost"]["cutoff_items"]:
        flagged_flows |= {b["transaction_id"] for b in x["post_period_work_payments"]}

    by_party: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"in": 0.0, "out": 0.0, "n": 0, "flagged": 0.0, "flows": []})
    for b in case.bank_flows:
        k = b.counterparty_name or "（未知对手方）"
        p = by_party[k]
        p["in" if b.amount > 0 else "out"] += abs(b.amount)
        p["n"] += 1
        p["flows"].append(b.transaction_id)
        if b.transaction_id in flagged_flows:
            p["flagged"] += abs(b.amount)
    related = {c.customer_or_vendor for c in case.contracts if c.is_related_party}
    ranked = sorted(by_party.items(), key=lambda kv: (kv[1]["flagged"] > 0, kv[1]["in"] + kv[1]["out"]), reverse=True)
    parties = [{
        "name": k, "inflow": round(v["in"], 2), "outflow": round(v["out"], 2), "count": v["n"],
        "flagged_amount": round(v["flagged"], 2), "related_party": any(_same_party(k, r) and k for r in related),
        "flows": v["flows"][:6],
    } for k, v in ranked[:max_parties]]

    # 业财单据链：算子指向的凭证，逐张检查 合同 → 发票 → 凭证 → 流水 是否连得上
    contracts = {c.contract_id: c for c in case.contracts}
    invoices = {i.invoice_no: i for i in case.invoices}
    flows = {b.transaction_id: b for b in case.bank_flows}
    focus: List[str] = []
    for d in recon["discrepancies"]:
        vid = str(d.get("voucher_id", ""))
        if not vid.startswith("BANK-") and vid not in focus:
            focus.append(vid)
    for x in sp["book_to_bank"]["book_without_bank"]:
        focus.append(x["voucher_id"])
    for p in sp["back_to_back"]["pairs"]:
        focus += [p["sale_voucher"], p["purchase_voucher"]]
    for x in sp["cutoff_and_cost"]["cutoff_items"]:
        focus.append(x["voucher_id"])
    for g in sp["cutoff_and_cost"].get("cost_gaps", []):
        focus.extend(g.get("vouchers", []))
    for x in sp["third_party_and_prepay"]["third_party_receipts"]:
        focus.append(x["voucher_id"])
    for x in sp["third_party_and_prepay"].get("prepayments", []):
        focus.extend(x.get("vouchers", []))
    # 纳入职业判断类算子标记的凭证（v2.5 补齐）
    for jid in sorted(judgment_ids(sp.get("judgment") or {})):
        focus.append(jid)

    seen, chains = set(), []
    vmap = {v.voucher_id: v for v in case.vouchers}
    for vid in focus:
        if vid in seen or vid not in vmap:
            continue
        seen.add(vid)
        v = vmap[vid]
        amt = voucher_total(v)
        doc = v.associated_doc_id
        c = contracts.get(doc)
        inv = invoices.get(doc)
        fl = flows.get(doc)
        party = (c.customer_or_vendor if c else "") or next((e.account_name.split("-", 1)[1] for e in v.entries if "-" in e.account_name), "")
        if c is None and party:
            c = next((x for x in case.contracts if _same_party(x.customer_or_vendor, party)), None)
        if inv is None:
            inv = next((i for i in case.invoices if party and (_same_party(i.buyer_name, party) or _same_party(i.seller_name, party))
                        and any(abs(i.total_amount - a) <= max(a * 0.001, 1) for a in [amt] + [e.debit or e.credit for e in v.entries])), None)
        if fl is None:
            vd = _d(v.voucher_date)
            fl = next((b for b in case.bank_flows
                       if any(abs(abs(b.amount) - a) <= max(a * 0.001, 1) for a in [amt] + [e.debit or e.credit for e in v.entries if e.debit or e.credit])
                       and (not vd or not _d(b.transaction_time) or abs((_d(b.transaction_time) - vd).days) <= 30)), None)
        chains.append({
            "voucher_id": vid, "date": v.voucher_date, "amount": round(amt, 2), "party": party,
            "contract": c.contract_id if c else None,
            "invoice": inv.invoice_no if inv else None,
            "bank_flow": fl.transaction_id if fl else None,
            "doc_ref": doc,
            "doc_ref_exists": (doc in contracts or doc in invoices or doc in flows) if doc else None,
        })
        if len(chains) >= 12:
            break
    return {
        "company": case.company_name,
        "has_bank_flows": bool(case.bank_flows),
        "parties": parties,
        "loops": rt["loops"],
        "loop_amount": rt.get("loop_amount", 0.0),
        "third_party_receipts": sp["third_party_and_prepay"]["third_party_receipts"],
        "restricted_cash_signals": sp["book_to_bank"]["restricted_cash_signals"],
        "chains": chains,
        "method": "资金拓扑来自银行流水按对手方汇总；红色为确定性算子标记的流水（资金往返、异常附言、第三方代付、受限资金、期后施工付款）。单据链逐张检查算子指向的凭证能否连到合同、发票与流水。",
    }
