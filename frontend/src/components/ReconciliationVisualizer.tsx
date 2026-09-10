import React, { useState } from 'react'
import { Layers, AlertTriangle, CheckCircle2, ArrowRightLeft, FileSpreadsheet, Receipt, Landmark, HelpCircle } from 'lucide-react'
import { AccountingVoucher, InvoiceItem, BankFlowRecord } from '../types'

interface ReconciliationVisualizerProps {
  currentCase: any
  reconData: {
    discrepancies: any[]
    total_discrepancies_count: number
    total_audited_amount: number
    total_abnormal_amount: number
    reconciliation_clean: boolean
  } | null
}

export const ReconciliationVisualizer: React.FC<ReconciliationVisualizerProps> = ({
  currentCase,
  reconData
}) => {
  const [activeTab, setActiveTab] = useState<'discrepancies' | 'vouchers' | 'invoices' | 'bank_flows'>('discrepancies')

  const vouchers: AccountingVoucher[] = currentCase?.vouchers || []
  const invoices: InvoiceItem[] = currentCase?.invoices || []
  const bankFlows: BankFlowRecord[] = currentCase?.bank_flows || []
  const discrepancies = reconData?.discrepancies || []

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Executive Summary Header */}
      <div className="glass-panel rounded-2xl p-6 border border-white/10 relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 mb-1">
              <Layers className="w-4 h-4" />
              <span>三单业财闭环穿透核对飞轮 (Tripartite Reconciliation)</span>
            </div>
            <h2 className="text-xl font-bold text-white">
              {currentCase?.company_name} · 业务凭证 ⟷ 税务发票 ⟷ 资金流水 闭环勾稽
            </h2>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <span className="text-[11px] text-slate-400 block font-mono">勾稽核对状态</span>
              <span className={`text-sm font-bold font-mono px-3 py-1 rounded-md inline-block mt-0.5 ${
                reconData?.reconciliation_clean
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-rose-500/20 text-rose-300 border border-rose-500/30 glow-crimson'
              }`}>
                {reconData?.reconciliation_clean ? '三单勾稽一致 (CLEAN)' : `检出 ${reconData?.total_discrepancies_count || 0} 处重大勾稽断裂`}
              </span>
            </div>
          </div>
        </div>

        {/* 3 Key Entity Counts */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-cyan-500/20 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-cyan-500/10 flex items-center justify-center border border-cyan-500/30">
              <FileSpreadsheet className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <div className="text-xs text-slate-400 font-mono">记账凭证 (Vouchers)</div>
              <div className="text-lg font-bold font-mono text-white">{vouchers.length} 笔入账</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-purple-500/20 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center border border-purple-500/30">
              <Receipt className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <div className="text-xs text-slate-400 font-mono">税务发票 (Invoices)</div>
              <div className="text-lg font-bold font-mono text-white">{invoices.length} 张单据</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-blue-500/20 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center border border-blue-500/30">
              <Landmark className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <div className="text-xs text-slate-400 font-mono">银行流水 (Bank Flows)</div>
              <div className="text-lg font-bold font-mono text-white">{bankFlows.length} 笔收支</div>
            </div>
          </div>
        </div>
      </div>

      {/* Discrepancies Alert Table */}
      <div className="glass-panel rounded-2xl p-6 border border-white/10 space-y-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <span>三单勾稽穿透断裂与造假疑点明细 ({discrepancies.length})</span>
          </h3>
          <span className="text-xs font-mono text-rose-400">
            涉及异常金额合计: ¥{(reconData?.total_abnormal_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
          </span>
        </div>

        {discrepancies.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2 opacity-80" />
            该案例业财三单高度吻合，记账金额、发票税额与银行回执无勾稽差异。
          </div>
        ) : (
          <div className="space-y-3">
            {discrepancies.map((d, i) => (
              <div
                key={i}
                className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 hover:border-rose-500/60 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1 max-w-3xl">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[11px] font-bold font-mono bg-rose-500/20 text-rose-300 border border-rose-500/40">
                      {d.type}
                    </span>
                    {d.voucher_id && (
                      <span className="text-xs font-mono text-cyan-300 bg-slate-900 px-2 py-0.5 rounded border border-white/10">
                        凭证: {d.voucher_id}
                      </span>
                    )}
                    {d.doc_id && (
                      <span className="text-xs font-mono text-purple-300 bg-slate-900 px-2 py-0.5 rounded border border-white/10">
                        单据: {d.doc_id}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed font-mono pt-1">
                    {d.detail}
                  </p>
                </div>

                <div className="text-right flex-shrink-0">
                  <span className="text-[11px] text-slate-400 block font-mono">异动金额</span>
                  <span className="text-sm font-bold font-mono text-rose-400">
                    ¥{Number(d.amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Raw Entity Inspection Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Vouchers Inspection */}
        <div className="glass-panel rounded-2xl p-4 border border-white/10 space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-white border-b border-white/10 pb-2">
            <span className="flex items-center gap-1.5 text-cyan-300">
              <FileSpreadsheet className="w-4 h-4" />
              <span>记账凭证明细</span>
            </span>
            <span className="font-mono text-slate-400">{vouchers.length} 条</span>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {vouchers.map((v, idx) => {
              const debit = v.entries.reduce((acc, e) => acc + (e.debit || 0), 0)
              const credit = v.entries.reduce((acc, e) => acc + (e.credit || 0), 0)
              const isBalanced = Math.abs(debit - credit) < 0.01
              return (
                <div key={idx} className="p-3 rounded-lg bg-slate-900/70 border border-white/5 text-xs space-y-1.5 font-mono">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-cyan-400">{v.voucher_id}</span>
                    <span className="text-slate-400 text-[11px]">{v.voucher_date}</span>
                  </div>
                  <div className="text-slate-300 truncate">{v.entries[0]?.summary || '业务记账'}</div>
                  <div className="flex items-center justify-between pt-1 border-t border-white/5 text-[11px]">
                    <span className="text-slate-400">金额: ¥{debit.toLocaleString('zh-CN')}</span>
                    <span className={isBalanced ? 'text-emerald-400' : 'text-rose-400 font-bold'}>
                      {isBalanced ? '借贷平衡' : '借贷不平'}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Invoices Inspection */}
        <div className="glass-panel rounded-2xl p-4 border border-white/10 space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-white border-b border-white/10 pb-2">
            <span className="flex items-center gap-1.5 text-purple-300">
              <Receipt className="w-4 h-4" />
              <span>税务发票清单</span>
            </span>
            <span className="font-mono text-slate-400">{invoices.length} 张</span>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {invoices.map((inv, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-slate-900/70 border border-white/5 text-xs space-y-1.5 font-mono">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-purple-400">{inv.invoice_no}</span>
                  <span className="text-slate-400 text-[11px]">{inv.invoice_date}</span>
                </div>
                <div className="text-slate-300 truncate">客户/销售方: {inv.customer_or_vendor}</div>
                <div className="flex items-center justify-between pt-1 border-t border-white/5 text-[11px]">
                  <span className="text-slate-400">价税合计</span>
                  <span className="text-slate-200 font-bold">¥{inv.total_amount.toLocaleString('zh-CN')}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bank Flows Inspection */}
        <div className="glass-panel rounded-2xl p-4 border border-white/10 space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-white border-b border-white/10 pb-2">
            <span className="flex items-center gap-1.5 text-blue-300">
              <Landmark className="w-4 h-4" />
              <span>银行对账单流水</span>
            </span>
            <span className="font-mono text-slate-400">{bankFlows.length} 笔</span>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {bankFlows.map((b, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-slate-900/70 border border-white/5 text-xs space-y-1.5 font-mono">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-blue-400">{b.transaction_id}</span>
                  <span className="text-slate-400 text-[11px]">{b.transaction_time}</span>
                </div>
                <div className="text-slate-300 truncate">对手方: {b.counterparty_name}</div>
                <div className="flex items-center justify-between pt-1 border-t border-white/5 text-[11px]">
                  <span className="text-slate-400 truncate max-w-[120px]">{b.remark || '无附言'}</span>
                  <span className={`font-bold ${b.amount < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                    ¥{b.amount.toLocaleString('zh-CN')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
