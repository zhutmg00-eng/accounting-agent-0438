"""
合成盲测基准（Synthetic Blind Benchmark）。

与 28 例案例库互补：案例库的真值由同一团队与检测规则一起编写，存在"自己出题自己答"的
循环风险。本模块用**独立的随机生成器**造账套：每个账套随机注入若干异常（正例），同时
注入"近似但不该报"的干扰项（负例），真值只来自生成器的注入记录。

约束（防止过拟合检测规则）：
* 本文件**不导入**任何检测代码（analytics / tools / plugin），生成逻辑只依据审计常识；
* 节假日按国务院办公厅公布的全部法定节假日安排生成（含清明、劳动节、端午、中秋），
  而不是检测器内置的表；
* 随机种子与案例库无关，每次评测可换种子复跑。

评测：逐条规则计算凭证/流水级 Precision、Recall；Benford 按账套级二分类计算准确率。

用法：uv run python -m src.benchmark.blind_synthetic --seeds 20 --out output/blind_synthetic_report.json
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from src.core.schemas import (
    AccountingCaseData, AccountingVoucher, BankFlowRecord, InvoiceItem, JournalEntryLine,
)

# 2024 年全部法定节假日放假日期（国办发明电〔2023〕7 号）——独立于检测器
HOLIDAYS_2024 = (
    [date(2024, 1, 1)]
    + [date(2024, 2, 10) + timedelta(days=i) for i in range(8)]   # 春节
    + [date(2024, 4, 4) + timedelta(days=i) for i in range(3)]    # 清明
    + [date(2024, 5, 1) + timedelta(days=i) for i in range(5)]    # 劳动节
    + [date(2024, 6, 10)]                                         # 端午
    + [date(2024, 9, 15) + timedelta(days=i) for i in range(3)]   # 中秋
    + [date(2024, 10, 1) + timedelta(days=i) for i in range(7)]   # 国庆
)
# 调休上班的周末（这些周末记账不应被视为异常）
MAKEUP_WORKDAYS_2024 = [date(2024, 2, 4), date(2024, 2, 18), date(2024, 4, 7), date(2024, 4, 28),
                        date(2024, 5, 11), date(2024, 9, 14), date(2024, 9, 29), date(2024, 10, 12)]
YEAR = 2024


def _is_offday(d: date) -> bool:
    if d in MAKEUP_WORKDAYS_2024:
        return False
    return d.weekday() >= 5 or d in HOLIDAYS_2024


def _workday(rng: random.Random, lo: date = date(YEAR, 1, 2), hi: date = date(YEAR, 12, 20)) -> date:
    while True:
        d = lo + timedelta(days=rng.randint(0, (hi - lo).days))
        if not _is_offday(d):
            return d


def _amount(rng: random.Random) -> float:
    a = round(rng.lognormvariate(11.0, 2.0), 2)
    # 正常账务尽量不出现 10 万整倍数，避免与"整数金额"标识混淆
    if a >= 100_000 and abs(a % 100_000) < 0.005:
        a += 37.21
    return max(a, 12.34)


class Ledger:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.seed = seed
        self.vouchers: List[AccountingVoucher] = []
        self.invoices: List[InvoiceItem] = []
        self.flows: List[BankFlowRecord] = []
        self.truth: Dict[str, Set[str]] = defaultdict(set)   # label -> ids that SHOULD be flagged
        self.decoys: Dict[str, Set[str]] = defaultdict(set)  # label -> ids that should NOT be flagged
        self._n = 0
        self._balance = 50_000_000.0

    def voucher(self, d: date, lines, doc=None, preparer=None, checker="__auto__", attach=1) -> str:
        self._n += 1
        vid = f"S{self.seed}-V{self._n:04d}"
        preparer = preparer or self.rng.choice(["甲", "乙", "丙"])
        if checker == "__auto__":
            checker = self.rng.choice([p for p in ["丁", "戊"] if p != preparer])
        self.vouchers.append(AccountingVoucher(
            voucher_id=vid, voucher_date=d.isoformat(), preparer=preparer, checker=checker,
            attachments_count=attach, associated_doc_id=doc,
            entries=[JournalEntryLine(account_code=c, account_name=n, debit=dr, credit=cr, summary=s)
                     for c, n, dr, cr, s in lines]))
        return vid

    def flow(self, when: datetime, party: str, amt: float, remark: str) -> str:
        tid = f"S{self.seed}-B{len(self.flows) + 1:04d}"
        self._balance += amt
        self.flows.append(BankFlowRecord(
            transaction_id=tid, transaction_time=when.strftime("%Y-%m-%d %H:%M"), counterparty_name=party,
            counterparty_account="6222****0000", amount=round(amt, 2), balance_after=round(self._balance, 2),
            remark=remark))
        return tid

    def sale(self, d: date, amt: float) -> Tuple[str, str]:
        inv = f"S{self.seed}-INV{len(self.invoices) + 1:04d}"
        cust = self.rng.choice(["客户A有限公司", "客户B有限公司", "客户C有限公司", "客户D有限公司"])
        tax = round(amt * 0.13, 2)
        self.invoices.append(InvoiceItem(invoice_no=inv, invoice_date=d.isoformat(), buyer_name=cust,
                                         seller_name="被审计单位", amount_without_tax=amt, tax_amount=tax,
                                         total_amount=round(amt + tax, 2), goods_or_service="产品"))
        vid = self.voucher(d, [("1122", f"应收账款-{cust}", round(amt + tax, 2), 0, "销售商品"),
                               ("6001", "主营业务收入", 0, amt, "销售商品"),
                               ("2221", "应交税费-销项税额", 0, tax, "销售商品")], doc=inv)
        return vid, inv


def build_ledger(seed: int, size: int = 200, fabricate_amounts: bool = False) -> Tuple[AccountingCaseData, Ledger]:
    L = Ledger(seed)
    rng = L.rng
    # ---- 正常业务 ----
    for _ in range(size):
        d = _workday(rng)
        kind = rng.random()
        if kind < 0.45:
            amt = float(rng.randint(1, 9)) * 10 ** rng.randint(3, 6) + rng.random() if fabricate_amounts else _amount(rng)
            L.sale(d, round(amt, 2))
        elif kind < 0.85:
            amt = float(rng.randint(1, 9)) * 10 ** rng.randint(3, 6) + rng.random() if fabricate_amounts else _amount(rng)
            amt = round(amt, 2)
            L.voucher(d, [("1403", "原材料", amt, 0, "采购入库"), ("2202", "应付账款", 0, amt, "采购入库")])
        else:
            amt = _amount(rng)
            L.voucher(d, [("6602", "管理费用", amt, 0, "日常费用"), ("1002", "银行存款", 0, amt, "日常费用")])
        if rng.random() < 0.4:
            party = rng.choice(["客户A有限公司", "客户B有限公司", "供应商E有限公司", "供应商F有限公司"])
            sign = 1 if "客户" in party else -1
            L.flow(datetime(d.year, d.month, d.day, rng.randint(9, 16), rng.randint(0, 59)), party,
                   sign * _amount(rng), "货款")

    # ---- 注入异常（正例）与干扰项（负例），数量随机 ----
    def k(lo=1, hi=4):
        return rng.randint(lo, hi)

    # 非工作日记账：含小长假与普通周末；调休上班的周末为负例
    offdays = [d for d in (date(YEAR, 1, 1) + timedelta(days=i) for i in range(366)) if d.year == YEAR and _is_offday(d)]
    for _ in range(k()):
        d = rng.choice(offdays)
        a = _amount(rng)
        L.truth["offday_posting"].add(L.voucher(d, [("6602", "管理费用", a, 0, "费用报销"), ("1002", "银行存款", 0, a, "费用报销")]))
    for d in rng.sample(MAKEUP_WORKDAYS_2024, k(1, 2)):
        a = _amount(rng)
        L.decoys["offday_posting"].add(L.voucher(d, [("6602", "管理费用", a, 0, "费用报销"), ("1002", "银行存款", 0, a, "费用报销")]))

    # 职责分离：制单=复核 或 空复核为正例；不同人复核为负例（基础业务已覆盖）
    for i in range(k()):
        d = _workday(rng)
        a = _amount(rng)
        p = rng.choice(["甲", "乙", "丙"])
        L.truth["segregation_of_duties"].add(L.voucher(
            d, [("1221", "其他应收款", a, 0, "备用金"), ("1002", "银行存款", 0, a, "备用金")],
            preparer=p, checker=p if i % 2 == 0 else ""))

    # 无附件
    for _ in range(k()):
        d = _workday(rng)
        a = _amount(rng)
        L.truth["no_attachment"].add(L.voucher(d, [("6601", "销售费用", a, 0, "推广费"), ("1002", "银行存款", 0, a, "推广费")], attach=0))

    # 引用不存在的单据（正例）；引用真实发票的正常凭证为负例（基础销售已覆盖）
    for i in range(k()):
        d = _workday(rng)
        a = round(_amount(rng) * 5, 2)
        L.truth["phantom_document"].add(L.voucher(
            d, [("1122", "应收账款-客户E有限公司", a, 0, "销售商品"), ("6001", "主营业务收入", 0, a, "销售商品")],
            doc=f"S{seed}-INVX{i:03d}"))

    # 收入直接对应货币资金且无单据（正例）；有发票的现销为负例
    for _ in range(k()):
        d = _workday(rng)
        a = _amount(rng)
        L.truth["revenue_cash_no_doc"].add(L.voucher(d, [("1002", "银行存款", a, 0, "收到货款"), ("6001", "主营业务收入", 0, a, "收到货款")]))
    for _ in range(k(1, 2)):
        d = _workday(rng)
        a = _amount(rng)
        inv = f"S{seed}-INVC{len(L.invoices):04d}"
        L.invoices.append(InvoiceItem(invoice_no=inv, invoice_date=d.isoformat(), buyer_name="现销客户", seller_name="被审计单位",
                                      amount_without_tax=a, tax_amount=0, total_amount=a, goods_or_service="产品"))
        L.decoys["revenue_cash_no_doc"].add(L.voucher(d, [("1002", "银行存款", a, 0, "现销"), ("6001", "主营业务收入", 0, a, "现销")], doc=inv))

    # 资金往返：同一对手方 3–25 天内流出又流回、金额差 ≤5% 为正例；
    # 干扰：60 天后才流回、或金额只回来 60%
    for i in range(k()):
        d = _workday(rng, hi=date(YEAR, 11, 30))
        amt = round(rng.uniform(1e6, 5e7), 2)
        party = f"往来单位{seed}-{i}有限公司"
        o = L.flow(datetime(d.year, d.month, d.day, 10, 0), party, -amt, "预付款")
        back = d + timedelta(days=rng.randint(3, 25))
        n = L.flow(datetime(back.year, back.month, back.day, 15, 0), party, round(amt * rng.uniform(0.96, 1.0), 2), "退回")
        L.truth["round_trip"].add(f"{o}->{n}")
    for i in range(k(1, 2)):
        d = _workday(rng, hi=date(YEAR, 9, 30))
        amt = round(rng.uniform(1e6, 5e7), 2)
        party = f"干扰单位{seed}-{i}有限公司"
        o = L.flow(datetime(d.year, d.month, d.day, 10, 0), party, -amt, "预付款")
        if i % 2 == 0:
            back = d + timedelta(days=60)
            n = L.flow(datetime(back.year, back.month, back.day, 15, 0), party, amt, "退回")
        else:
            back = d + timedelta(days=10)
            n = L.flow(datetime(back.year, back.month, back.day, 15, 0), party, round(amt * 0.6, 2), "部分退回")
        L.decoys["round_trip"].add(f"{o}->{n}")

    case = AccountingCaseData(
        case_id=f"BLIND_SYN_{seed}", company_name=f"合成盲测账套 {seed}", description="synthetic blind ledger",
        audit_period=f"{YEAR}年度", vouchers=L.vouchers, invoices=L.invoices, bank_flows=L.flows,
    )
    return case, L


RULE_OF_LABEL = {
    "offday_posting": "JE01",
    "segregation_of_duties": "JE04",
    "no_attachment": "JE05",
    "revenue_cash_no_doc": "JE07",
    "phantom_document": "JE10",
}


def evaluate(seeds: List[int], size: int = 200) -> Dict[str, Any]:
    # Detection code is imported only here, at evaluation time.
    from src.plugins.audit_fraud_plugin.analytics import (
        journal_entry_testing, detect_fund_round_trips, benford_first_digit_test,
    )
    tally = defaultdict(lambda: {"tp": 0, "fn": 0, "fp_decoy": 0, "decoys": 0, "fp_other": 0})
    misses: Dict[str, List[str]] = defaultdict(list)
    benford = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    for seed in seeds:
        case, L = build_ledger(seed, size=size)
        je = journal_entry_testing(case, top_n=10_000)
        by_rule: Dict[str, Set[str]] = defaultdict(set)
        for f in je["flagged"]:
            for r in f["rules"]:
                by_rule[r].add(f["voucher_id"])
        for label, rule in RULE_OF_LABEL.items():
            flagged = by_rule.get(rule, set())
            t = tally[label]
            t["tp"] += len(L.truth[label] & flagged)
            missed = L.truth[label] - flagged
            t["fn"] += len(missed)
            if missed:
                vmap = {v.voucher_id: v.voucher_date for v in case.vouchers}
                misses[label].extend(f"{m}({vmap.get(m, '')})" for m in sorted(missed))
            t["decoys"] += len(L.decoys[label])
            t["fp_decoy"] += len(L.decoys[label] & flagged)
            injected = set().union(*L.truth.values(), *L.decoys.values())
            t["fp_other"] += len(flagged - L.truth[label] - injected)
        rt = detect_fund_round_trips(case)
        found = {f"{l['out_id']}->{l['in_id']}" for l in rt["loops"]}
        t = tally["round_trip"]
        t["tp"] += len(L.truth["round_trip"] & found)
        t["fn"] += len(L.truth["round_trip"] - found)
        t["decoys"] += len(L.decoys["round_trip"])
        t["fp_decoy"] += len(L.decoys["round_trip"] & found)
        t["fp_other"] += len(found - L.truth["round_trip"] - L.decoys["round_trip"])
        # Benford：同一种子分别生成"自然金额"与"人为编造金额"两套账，检验能否区分
        for fabricated in (False, True):
            c2, _ = build_ledger(seed + 100_000, size=max(size, 300), fabricate_amounts=fabricated)
            res = benford_first_digit_test(c2)
            flagged = res.get("applicable") and not res.get("conforms")
            key = ("tp" if flagged else "fn") if fabricated else ("fp" if flagged else "tn")
            benford[key] += 1

    rules = {}
    for label, t in tally.items():
        flagged_total = t["tp"] + t["fp_decoy"] + t["fp_other"]
        rules[label] = {
            "rule": RULE_OF_LABEL.get(label, "round_trip"),
            "recall": round(t["tp"] / max(t["tp"] + t["fn"], 1), 4),
            "precision": round(t["tp"] / max(flagged_total, 1), 4),
            "decoy_false_positive_rate": round(t["fp_decoy"] / max(t["decoys"], 1), 4) if t["decoys"] else None,
            **t,
            "sample_misses": misses.get(label, [])[:8],
        }
    n = len(seeds)
    return {
        "seeds": seeds,
        "ledgers": n,
        "ledger_size_base_vouchers": size,
        "rules": rules,
        "benford": {**benford, "accuracy": round((benford["tp"] + benford["tn"]) / max(2 * n, 1), 4)},
        "protocol": "生成器独立于检测代码；真值仅来自注入记录；负例为调休上班周末、有发票现销、60 天后回款/仅回款 60% 的资金往来。",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--start", type=int, default=7001)
    ap.add_argument("--size", type=int, default=200)
    ap.add_argument("--out", type=str, default="output/blind_synthetic_report.json")
    args = ap.parse_args()
    seeds = list(range(args.start, args.start + args.seeds))
    rep = evaluate(seeds, size=args.size)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    for label, r in rep["rules"].items():
        print(f"{label:24s} {r['rule']:10s} recall={r['recall']:.3f} precision={r['precision']:.3f} decoyFP={r['decoy_false_positive_rate']}")
    print("benford", rep["benford"])


if __name__ == "__main__":
    main()
