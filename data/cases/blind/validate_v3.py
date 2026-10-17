# -*- coding: utf-8 -*-
import json, re, sys
from collections import Counter
D = json.load(open('data/cases/blind/blind_cases_v3.json', encoding='utf-8'))
ERR = []
def err(cid, m): ERR.append(f'[{cid}] {m}')
BANNED = ['虚构','伪造','造假','虚增','占用','舞弊','虚假']
TOP = ['case_id','company_name','stock_code','penalty_decision_no','source_url','case_category','csrc_summary','industry',
       'audit_period','description','vouchers','contracts','invoices','bank_flows','ground_truth_findings']
CAT_RULES = {
 '虚增收入/提前确认': ['虚增收入','提前确认'],
 '少计费用或成本': ['少计','费用'],
 '资产减值不提或少提': ['减值'],
 '预计负债/担保/诉讼未确认': ['预计负债','担保','诉讼'],
 '资金占用经预付或其他应收': ['资金占用'],
 '无单据核销负债增利': ['核销负债'],
 '在建工程或存货虚增': ['在建工程','存货虚增'],
 '关联交易非关联化': ['关联交易非关联化'],
}
if len(D) != 16: err('ALL', f'case count {len(D)} != 16')
ids = [c['case_id'] for c in D]
exp_ids = [f'BLIND3_{i:03d}' for i in range(1,17)]
if ids != exp_ids: err('ALL', f'case ids {ids}')
total_f = 0; cats = set(); companies = Counter(c['company_name'] for c in D)
for k,v in companies.items():
    if v>1: err('ALL', f'duplicate company {k}')
EXCL = '康美药业 康得新 辅仁药业 宜华生活 金正大 胜通 东方金钰 同济堂 瑞幸 索菱 科融环境 亚太药业 抚顺特钢 獐子岛 广州浪奇 雏鹰农牧 万福生科 延安必康 华泽钴镍 凯迪生态 三圣 金亚科技 欣泰电气 雅百特 风神轮胎 贵州茅台 福耀玻璃 中国移动 泽达易盛 紫晶存储 郑州华晶 锦州港 美尚生态 柏堡龙 易见股份 凯乐科技 荣联科技 罗普特 海天味业 长江电力 伊利股份 美的集团 贵州百灵 北特科技 德豪润达 如意毛纺 凯伦建材 林州重机 德威新材 华铭智能 吴中医药 弘高创意 宁德时代 中国神华 恒瑞医药 海康威视 万华化学 格力电器'.split()
for c in D:
    cid = c['case_id']; fraud = int(cid[-3:]) <= 10
    for k in TOP:
        if k not in c: err(cid, f'missing field {k}')
    for x in EXCL:
        if x in c['company_name']: err(cid, f'excluded company {x}')
    # banned words
    texts = [('description', c['description'])]
    for v in c['vouchers']:
        for e in v['entries']: texts.append((v['voucher_id']+'摘要', e['summary']))
    for b in c['bank_flows']: texts.append((b['transaction_id']+'备注', b['remark']))
    for ct in c['contracts']:
        texts.append((ct['contract_id']+'付款条款', ct['payment_terms'])); texts.append((ct['contract_id']+'交付条件', ct['delivery_condition']))
    for where, t in texts:
        for w in BANNED:
            if w in t: err(cid, f'banned word "{w}" in {where}: {t}')
    # vouchers
    if not (6 <= len(c['vouchers']) <= 14): err(cid, f'voucher count {len(c["vouchers"])}')
    vmap = {}
    for v in c['vouchers']:
        if v['voucher_id'] in vmap: err(cid, f'dup voucher {v["voucher_id"]}')
        vmap[v['voucher_id']] = v
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v['voucher_date']): err(cid, f'bad date {v["voucher_id"]}')
        if not isinstance(v['attachments_count'], int): err(cid, f'attachments not int {v["voucher_id"]}')
        dr = sum(e['debit'] for e in v['entries']); cr = sum(e['credit'] for e in v['entries'])
        if abs(dr-cr) > 0.005: err(cid, f'unbalanced {v["voucher_id"]} dr={dr} cr={cr}')
        if len(v['entries']) < 2: err(cid, f'<2 entries {v["voucher_id"]}')
        for e in v['entries']:
            if not re.fullmatch(r'\d{4}', e['account_code']): err(cid, f'bad acct {e["account_code"]}')
            if e['debit'] < 0 or e['credit'] < 0 or (e['debit'] and e['credit']) or (not e['debit'] and not e['credit']):
                err(cid, f'entry amount issue {v["voucher_id"]} {e}')
    inv_nos = {i['invoice_no'] for i in c['invoices']}
    for v in c['vouchers']:
        if v['associated_doc_id'] and v['associated_doc_id'] not in inv_nos: err(cid, f'{v["voucher_id"]} doc {v["associated_doc_id"]} not in invoices')
    # invoices
    for i in c['invoices']:
        if abs(i['amount_without_tax'] + i['tax_amount'] - i['total_amount']) > 0.005: err(cid, f'invoice {i["invoice_no"]} sum mismatch')
    # bank flows
    bf = c['bank_flows']
    times = [b['transaction_time'] for b in bf]
    if times != sorted(times): err(cid, 'bank flows not sorted')
    for b in bf:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', b['transaction_time']): err(cid, f'bad time {b["transaction_id"]}')
        if b['balance_after'] < 0: err(cid, f'negative balance {b["transaction_id"]}')
        if '***' not in b['counterparty_account']: err(cid, f'account not masked {b["transaction_id"]}')
    for a, b in zip(bf, bf[1:]):
        if abs(a['balance_after'] + b['amount'] - b['balance_after']) > 0.005: err(cid, f'balance break at {b["transaction_id"]}')
    # findings
    gf = c['ground_truth_findings']
    if fraud:
        if not (1 <= len(gf) <= 3): err(cid, f'finding count {len(gf)}')
        if not c['penalty_decision_no'] or not c['csrc_summary'] or not c['source_url']: err(cid, 'fraud case missing decision info')
    else:
        if gf: err(cid, 'compliant case has findings')
        if c['penalty_decision_no'] or c['csrc_summary']: err(cid, 'compliant case should have empty decision/summary')
    total_f += len(gf)
    for name, kws in CAT_RULES.items():
        if fraud and any(k in c['case_category'] for k in kws): cats.add(name)
    for f in gf:
        if f['expected_risk_level'] not in ('HIGH','MEDIUM'): err(cid, 'bad risk level')
        for vid in f['expected_vouchers']:
            if vid not in vmap: err(cid, f'expected voucher {vid} missing')
        m = re.search(r'科目(\d{4}).*?(借方|贷方)', f['amount_basis'])
        if not m: err(cid, f'amount_basis unparsable: {f["amount_basis"]}'); continue
        acct, side = m.group(1), m.group(2)
        s = 0.0
        for vid in f['expected_vouchers']:
            for e in vmap.get(vid, {'entries': []})['entries']:
                if e['account_code'] == acct: s += e['debit'] if side == '借方' else e['credit']
        if abs(s - f['expected_amount']) >= 0.01: err(cid, f'expected_amount {f["expected_amount"]} != recomputed {s:.2f} ({acct}{side})')
        if s == 0: err(cid, 'expected amount zero')
    # fraud vouchers must not be all vouchers
    if fraud:
        fv = {vid for f in gf for vid in f['expected_vouchers']}
        if len(fv) >= len(vmap): err(cid, 'all vouchers are fraud vouchers')
if not (18 <= total_f <= 22): err('ALL', f'total findings {total_f} not in 18-22')
if len(cats) < 6: err('ALL', f'only {len(cats)} fraud categories: {cats}')
print('total findings:', total_f); print('categories covered:', len(cats), sorted(cats))
if ERR:
    print(f'ERRORS: {len(ERR)}'); [print(' ', e) for e in ERR]; sys.exit(1)
print('VALIDATION PASSED: 0 errors')
