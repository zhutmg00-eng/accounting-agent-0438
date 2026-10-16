import json
from decimal import Decimal
cases=json.load(open('/workspace/work/blind_set/blind_cases.json',encoding='utf-8'))
req=["case_id","company_name","stock_code","penalty_decision_no","source_url","case_category","csrc_summary","industry","audit_period","description","vouchers","contracts","invoices","bank_flows","ground_truth_findings"]
bad=0; nv=0
for c in cases:
    for k in req: assert k in c,(c['case_id'],k)
    vids=set()
    for v in c['vouchers']:
        nv+=1
        assert v['voucher_id'] not in vids,(c['case_id'],v['voucher_id']); vids.add(v['voucher_id'])
        dr=sum(Decimal(str(e['debit'])) for e in v['entries']); cr=sum(Decimal(str(e['credit'])) for e in v['entries'])
        if dr!=cr or dr==0: bad+=1; print('UNBAL',c['case_id'],v['voucher_id'],dr,cr)
    bids=[b['transaction_id'] for b in c['bank_flows']]; assert len(set(bids))==len(bids),c['case_id']
    for i in range(1,len(c['bank_flows'])):
        a=c['bank_flows'][i-1]; b=c['bank_flows'][i]
        assert abs(Decimal(str(a['balance_after']))+Decimal(str(b['amount']))-Decimal(str(b['balance_after'])))<Decimal('0.005'),(c['case_id'],b['transaction_id'])
    for inv in c['invoices']:
        assert abs(Decimal(str(inv['amount_without_tax']))+Decimal(str(inv['tax_amount']))-Decimal(str(inv['total_amount'])))<Decimal('0.005')
    for f in c['ground_truth_findings']:
        for x in f['expected_vouchers']: assert x in vids or x in bids,(c['case_id'],x)
    txt=json.dumps(c,ensure_ascii=False)
    for w in ['虚构','伪造','造假']:
        assert w not in txt,(c['case_id'],w)
    print(c['case_id'],c['company_name'],'凭证',len(c['vouchers']),'流水',len(c['bank_flows']),'发现',len(c['ground_truth_findings']))
print('cases',len(cases),'vouchers',nv,'unbalanced',bad)
