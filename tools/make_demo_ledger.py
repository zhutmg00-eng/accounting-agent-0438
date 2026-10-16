"""
生成「全量分析程序」演示账套（合成数据，明确标注，非真实企业）。

输出到 data/templates/demo_population/：
  演示账套_记账凭证.xlsx   约 600 张凭证 / 1,500+ 行分录（含制单人、复核人、附件张数）
  演示账套_增值税发票.csv
  演示账套_银行流水.csv

注入的已知异常（用于现场验证算子能否找回）：
  * 12 张周末/节假日记账            -> JE01
  * 8 张制单=复核 / 无复核人        -> JE04
  * 6 张无附件                      -> JE05
  * 5 张收入直接对应银行存款且无单据 -> JE07
  * 4 张引用不存在的单据号          -> JE10
  * 3 组同一对手方资金往返（体外循环）+ 1 组关联方接力 -> fund round-trips
其余金额按对数正态分布生成，整体应符合 Benford 定律。

用法：uv run python tools/make_demo_ledger.py   （固定随机种子，可复现）
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.plugins.audit_fraud_plugin.analytics import _is_offday  # noqa: E402

SEED = 20261028
OUT = Path(__file__).resolve().parent.parent / "data" / "templates" / "demo_population"
COMPANY = "星河精密制造有限公司（合成演示）"
CUSTOMERS = ["华东机电贸易有限公司", "北方装备集团有限公司", "南粤电子科技有限公司", "西部能源设备有限公司",
             "江城汽车零部件有限公司", "海岳工业自动化有限公司", "中原重工销售有限公司"]
VENDORS = ["申城钢材供应链有限公司", "鲁信轴承有限公司", "粤华包装材料有限公司", "京西物流有限公司"]
SHELL = ["瀚海商贸有限公司", "鼎丰咨询服务有限公司"]  # 关联/空壳对手方
PREPARERS = ["王敏", "陈静", "刘洋", "赵磊"]
CHECKERS = ["孙丽", "周强"]


def workday(rng: random.Random, start: date, end: date) -> date:
    while True:
        d = start + timedelta(days=rng.randint(0, (end - start).days))
        if not _is_offday(d):
            return d


def amount(rng: random.Random) -> float:
    return round(rng.lognormvariate(11.0, 2.0), 2)


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    start, end = date(2025, 1, 1), date(2025, 12, 31)
    rows, invoices, flows = [], [], []
    balance = 80_000_000.0
    vno = 0

    def add_voucher(d, lines, doc=None, preparer=None, checker=None, attach=1):
        nonlocal vno
        vno += 1
        vid = f"2025-记-{vno:04d}"
        preparer = preparer or rng.choice(PREPARERS)
        checker = rng.choice(CHECKERS) if checker is None else checker
        for code, name, dr, cr, summ in lines:
            rows.append({"凭证号": vid, "记账日期": d.isoformat(), "科目编码": code, "科目名称": name,
                         "借方金额": dr, "贷方金额": cr, "摘要": summ, "关联单据号": doc or "",
                         "制单人": preparer, "复核人": checker, "附件张数": attach})
        return vid

    def add_flow(tid, when, party, amt, remark):
        nonlocal balance
        balance += amt
        flows.append({"交易流水号": tid, "交易时间": when, "对手方户名": party,
                      "对手方账号": f"6222{rng.randint(10**11, 10**12 - 1)}", "交易金额": round(amt, 2),
                      "交易后余额": round(balance, 2), "附言": remark})

    # 1) 正常销售：凭证 + 发票 + 回款
    for i in range(260):
        d = workday(rng, start, end)
        net = amount(rng)
        tax = round(net * 0.13, 2)
        total = round(net + tax, 2)
        cust = rng.choice(CUSTOMERS)
        inv = f"FP2025{i + 1:05d}"
        add_voucher(d, [("1122", f"应收账款-{cust}", total, 0, "确认产品销售收入"),
                        ("6001", "主营业务收入-精密部件", 0, net, "确认产品销售收入"),
                        ("2221", "应交税费-应交增值税(销项税额)", 0, tax, "销项税额")], doc=inv)
        invoices.append({"发票号码": inv, "开票日期": d.isoformat(), "购买方名称": cust, "销售方名称": COMPANY,
                         "不含税金额": net, "税额": tax, "价税合计": total, "货物或劳务名称": "精密传动部件"})
        if rng.random() < 0.8:
            pay = d + timedelta(days=rng.randint(10, 60))
            if pay <= end:
                add_flow(f"BK{len(flows) + 1:06d}", f"{pay.isoformat()} {rng.randint(9, 16):02d}:{rng.randint(0, 59):02d}",
                         cust, total, "货款")

    # 2) 正常采购与费用
    for i in range(240):
        d = workday(rng, start, end)
        amt = amount(rng)
        ven = rng.choice(VENDORS)
        add_voucher(d, [("1403", "原材料", amt, 0, "采购原材料入库"),
                        ("2202", f"应付账款-{ven}", 0, amt, "采购原材料入库")], doc=None)
        if rng.random() < 0.7:
            pay = d + timedelta(days=rng.randint(15, 45))
            if pay <= end:
                add_flow(f"BK{len(flows) + 1:06d}", f"{pay.isoformat()} 10:{rng.randint(10, 59)}", ven, -amt, "支付材料款")

    # ---- 注入异常 ----
    weekend_days = [date(2025, 3, 8), date(2025, 4, 13), date(2025, 6, 21), date(2025, 7, 27), date(2025, 8, 16),
                    date(2025, 9, 14), date(2025, 10, 2), date(2025, 10, 5), date(2025, 11, 22), date(2025, 12, 6),
                    date(2025, 12, 27), date(2025, 12, 28)]
    for d in weekend_days:  # JE01
        a = amount(rng)
        add_voucher(d, [("6602", "管理费用-咨询费", a, 0, "支付咨询服务费"), ("1002", "银行存款", 0, a, "支付咨询服务费")])
    for k in range(8):  # JE04
        d = workday(rng, start, end)
        a = amount(rng)
        p = rng.choice(PREPARERS)
        add_voucher(d, [("1221", "其他应收款-员工借款", a, 0, "员工备用金"), ("1002", "银行存款", 0, a, "员工备用金")],
                    preparer=p, checker=p if k % 2 == 0 else "")
    for _ in range(6):  # JE05
        d = workday(rng, start, end)
        a = amount(rng)
        add_voucher(d, [("6601", "销售费用-市场推广", a, 0, "市场推广费"), ("1002", "银行存款", 0, a, "市场推广费")], attach=0)
    for k in range(5):  # JE07 收入直接对应银行存款、无单据，集中在期末
        d = date(2025, 12, 26 + k)
        a = float(rng.choice([3_000_000, 5_000_000, 8_000_000, 2_000_000, 6_000_000]))
        add_voucher(d, [("1002", "银行存款", a, 0, "收到货款"), ("6001", "主营业务收入-精密部件", 0, a, "收到货款")])
    for k in range(4):  # JE10 引用不存在单据
        d = workday(rng, date(2025, 11, 1), end)
        a = amount(rng) * 10
        add_voucher(d, [("1122", "应收账款-西部能源设备有限公司", round(a, 2), 0, "补记销售收入"),
                        ("6001", "主营业务收入-精密部件", 0, round(a, 2), "补记销售收入")], doc=f"FP2025X{k + 1:03d}")

    # 资金往返：同一对手方先流出后流入
    for k, (d, amt) in enumerate([(date(2025, 6, 10), 12_000_000.0), (date(2025, 9, 3), 18_500_000.0),
                                  (date(2025, 12, 1), 25_000_000.0)]):
        add_flow(f"BKRT{k + 1:02d}A", f"{d.isoformat()} 09:30", SHELL[0], -amt, "预付采购款")
        back = d + timedelta(days=rng.randint(5, 20))
        add_flow(f"BKRT{k + 1:02d}B", f"{back.isoformat()} 15:10", SHELL[0], round(amt * rng.uniform(0.97, 1.0), 2), "退回预付款")
    # 关联方接力（两个都为关联方合同对手方，需在平台上标注关联方合同才能识别；此处同时在附言中留痕）
    add_flow("BKRT04A", "2025-12-15 10:00", SHELL[1], -9_600_000.0, "支付咨询服务费")
    add_flow("BKRT04B", "2025-12-29 16:20", SHELL[0], 9_450_000.0, "往来款")

    rng.shuffle(rows)  # 打乱顺序避免按类型排列
    rows.sort(key=lambda r: (r["凭证号"]))
    pd.DataFrame(rows).to_excel(OUT / "演示账套_记账凭证.xlsx", index=False)
    for name, data in (("演示账套_增值税发票.csv", invoices), ("演示账套_银行流水.csv", sorted(flows, key=lambda f: f["交易时间"]))):
        with open(OUT / name, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)
    print(f"[demo] {vno} 张凭证 / {len(rows)} 行分录 / {len(invoices)} 张发票 / {len(flows)} 笔流水 -> {OUT}")


if __name__ == "__main__":
    main()
