import json, re
cases=json.load(open('/workspace/work/blind_set_v2/blind_cases_v2.json',encoding='utf-8'))
bad=re.compile('虚构|伪造|造假|虚增|占用|舞弊|虚假')
err=[]
for c in cases:
    vids={v['voucher_id'] for v in c['vouchers']}
    if len(vids)!=len(c['vouchers']): err.append((c['case_id'],'dup voucher'))
    if not 4<=len(c['vouchers'])<=14: err.append((c['case_id'],'voucher count',len(c['vouchers'])))
    for v in c['vouchers']:
        d=round(sum(e['debit'] for e in v['entries']),2); cr=round(sum(e['credit'] for e in v['entries']),2)
        if abs(d-cr)>0.005: err.append((c['case_id'],v['voucher_id'],'unbalanced',d,cr))
        for e in v['entries']:
            if bad.search(e['summary']): err.append((c['case_id'],v['voucher_id'],'leak',e['summary']))
    for i in c['invoices']:
        if abs(i['amount_without_tax']+i['tax_amount']-i['total_amount'])>0.005: err.append((c['case_id'],i['invoice_no'],'inv'))
    prev=None
    for fl in c['bank_flows']:
        if bad.search(fl['remark']): err.append((c['case_id'],'leak flow'))
        if prev is not None and abs(prev+fl['amount']-fl['balance_after'])>0.005: err.append((c['case_id'],fl['transaction_id'],'bal'))
        prev=fl['balance_after']
        if fl['balance_after']<0: err.append((c['case_id'],fl['transaction_id'],'neg'))
    for k in c['contracts']:
        if bad.search(k['payment_terms']+k['delivery_condition']): err.append((c['case_id'],'leak contract'))
    if bad.search(c['description']): err.append((c['case_id'],'leak desc'))
    for f in c['ground_truth_findings']:
        for x in f['expected_vouchers']:
            if x not in vids: err.append((c['case_id'],'missing voucher',x))
    print(c['case_id'],c['company_name'],len(c['vouchers']),'V',len(c['contracts']),'C',len(c['invoices']),'I',len(c['bank_flows']),'F',
          [(f['expected_amount']) for f in c['ground_truth_findings']])
checks={('BLIND2_001',0):('1123','debit'),('BLIND2_002',0):('6001','credit'),('BLIND2_002',1):('6601','debit'),('BLIND2_002',2):('6401','debit'),
 ('BLIND2_003',0):('6701','credit'),('BLIND2_004',0):('6301','credit'),('BLIND2_005',0):('1123','debit'),('BLIND2_006',0):('1604','debit'),
 ('BLIND2_006',1):('6603','credit'),('BLIND2_007',0):('1121','debit'),('BLIND2_007',1):('1123','debit'),('BLIND2_008',0):('6601','debit'),
 ('BLIND2_008',1):('530101','debit'),('BLIND2_009',0):('6001','credit'),('BLIND2_009',1):('1123','debit'),('BLIND2_010',0):('6001','credit'),('BLIND2_010',1):('6001','credit')}
cm={c['case_id']:c for c in cases}
for (cid,i),(acct,side) in checks.items():
    c=cm[cid]; f=c['ground_truth_findings'][i]
    s=round(sum(e[side] for v in c['vouchers'] if v['voucher_id'] in f['expected_vouchers'] for e in v['entries'] if e['account_code']==acct),2)
    print(cid,i,acct,s,f['expected_amount'],'OK' if abs(s-f['expected_amount'])<0.01 else 'DIFF')
# cost checks
for cid,vs,exp in [('BLIND2_002',['GY-2018-12-071','GY-2018-12-078','GY-2018-12-085'],20003200),('BLIND2_009',['SW-2021-06-018','SW-2021-12-021'],448237000),('BLIND2_010',['HG-2020-06-018','HG-2020-12-044'],59451300)]:
    s=round(sum(e['debit'] for v in cm[cid]['vouchers'] if v['voucher_id'] in vs for e in v['entries'] if e['account_code']=='6401'),2); print(cid,'cost',s,exp)
print('errors',err)
