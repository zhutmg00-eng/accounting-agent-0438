import React, { useState } from 'react'
import {
  Panel,
  Surface,
  Status,
  StatusMark,
  Chip,
  DataTable,
  Th,
  Td,
  TdNum,
  EmptyState,
  cn,
  type Tone
} from '../ui/primitives'
import { useAnimatedNumber, Reveal } from '../ui/motion'

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

type ReconTab = 'discrepancies' | 'vouchers' | 'invoices' | 'bank_flows'

/**
 * Beat 2 "穿透": the three documents of one transaction set (合同 / 发票 / 凭证)
 * either close or they do not.
 *
 * The screen is about one number, the amount that fails to close. Matched rows
 * stay quiet on the tone ladder; only the breaks and the missing counterparts
 * carry a status hue, and only as a small mark next to the figure.
 */
export const ReconciliationVisualizer: React.FC<ReconciliationVisualizerProps> = ({
  currentCase,
  reconData
}) => {
  const [activeTab, setActiveTab] = useState<ReconTab>('discrepancies')

  const vouchers = currentCase?.vouchers || []
  const invoices = currentCase?.invoices || []
  const bankFlows = currentCase?.bank_flows || []
  const discrepancies: any[] = reconData?.discrepancies || []

  /* --------------------------------------------------------------------- */
  /* Figures                                                                */
  /* --------------------------------------------------------------------- */

  const abnormalTotal = Number(reconData?.total_abnormal_amount || 0)
  const breakCount = reconData?.total_discrepancies_count || discrepancies.length
  const isClean = Boolean(reconData?.reconciliation_clean)
  const recordTotal = vouchers.length + invoices.length + bankFlows.length
  const displayedAbnormal = useAnimatedNumber(abnormalTotal)

  const money = (v: unknown) =>
    Number(v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  const breakTone: Tone = !reconData ? 'neutral' : isClean ? 'clear' : 'critical'

  const conclusion = !reconData
    ? '本案例尚未执行三单勾稽'
    : isClean
      ? '三单闭合，未发现勾稽断裂'
      : '三单未闭合，发现勾稽断裂'

  const basis = !reconData
    ? '在【审计指挥舱】点击「启动穿透」或在工作台调用 perform_three_way_reconciliation 算子后，本页会给出逐条差异证据。'
    : isClean
      ? `已核对记账凭证 ${vouchers.length} 笔、税务发票 ${invoices.length} 张、银行流水 ${bankFlows.length} 笔，记账金额、发票税额与银行回执相互印证。`
      : `已核对业务记录 ${recordTotal} 条，检出 ${breakCount} 处断裂。断裂明细与本页异常金额一一对应，可直接作为底稿索引。`

  /* --------------------------------------------------------------------- */
  /* Raw record inspection                                                  */
  /* --------------------------------------------------------------------- */

  const tabs: { id: ReconTab; label: string; count: number }[] = [
    { id: 'discrepancies', label: '勾稽断裂明细', count: breakCount },
    { id: 'vouchers', label: '记账凭证', count: vouchers.length },
    { id: 'invoices', label: '税务发票', count: invoices.length },
    { id: 'bank_flows', label: '银行流水', count: bankFlows.length }
  ]

  const renderDiscrepancyRows = () => {
    if (discrepancies.length === 0) {
      return (
        <tr>
          <Td colSpan={4} className="p-0">
            <EmptyState
              title={reconData ? '本案例未检出勾稽断裂' : '尚未执行勾稽核对'}
              body={
                reconData
                  ? '记账金额、发票税额与银行回执三向吻合。可以继续做凭证抽样或转向资金体外拓扑核查。'
                  : '先在工作台调用三单穿透勾稽算子，差异证据会逐条落到这张表上。'
              }
            />
          </Td>
        </tr>
      )
    }

    return discrepancies.map((d: any, i: number) => (
      <tr key={i}>
        <Td>
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <StatusMark tone="critical" />
            <span className="text-small font-medium text-fg">{d.type || '勾稽异常'}</span>
          </span>
        </Td>
        <Td className="text-fg-muted">
          <span className="tabular-nums">{d.voucher_id || d.doc_id || '未关联单号'}</span>
        </Td>
        <Td className="max-w-[38ch] text-fg-muted">{d.detail}</Td>
        <TdNum className="font-medium text-risk-critical">¥{money(d.amount)}</TdNum>
      </tr>
    ))
  }

  const renderVoucherRows = () =>
    vouchers.map((v: any, idx: number) => {
      const debit = v.entries.reduce((acc: number, e: any) => acc + (e.debit || 0), 0)
      const credit = v.entries.reduce((acc: number, e: any) => acc + (e.credit || 0), 0)
      const isBalanced = Math.abs(debit - credit) < 0.01
      return (
        <tr key={idx}>
          <Td>
            <span className="tabular-nums text-small font-medium text-fg">{v.voucher_id}</span>
          </Td>
          <Td className="tabular-nums text-fg-muted">{v.voucher_date}</Td>
          <Td className="max-w-[32ch] text-fg-muted">{v.entries[0]?.summary || '业务记账'}</Td>
          <TdNum>¥{debit.toLocaleString('zh-CN')}</TdNum>
          <Td>
            <Status tone={isBalanced ? 'neutral' : 'critical'}>
              {isBalanced ? '借贷平衡' : '借贷不平'}
            </Status>
          </Td>
        </tr>
      )
    })

  const renderInvoiceRows = () =>
    invoices.map((inv: any, idx: number) => (
      <tr key={idx}>
        <Td>
          <span className="tabular-nums text-small font-medium text-fg">{inv.invoice_no}</span>
        </Td>
        <Td className="tabular-nums text-fg-muted">{inv.invoice_date}</Td>
        <Td className="max-w-[32ch] text-fg-muted">
          <div>{inv.buyer_name || inv.seller_name || '—'}</div>
          {inv.goods_or_service ? <div className="text-label text-fg-faint">{inv.goods_or_service}</div> : null}
        </Td>
        <TdNum>¥{Number(inv.total_amount || 0).toLocaleString('zh-CN')}</TdNum>
      </tr>
    ))

  const renderBankFlowRows = () =>
    bankFlows.map((b: any, idx: number) => (
      <tr key={idx}>
        <Td>
          <span className="tabular-nums text-small font-medium text-fg">{b.transaction_id}</span>
        </Td>
        <Td className="tabular-nums text-fg-muted">{b.transaction_time}</Td>
        <Td className="max-w-[32ch] text-fg-muted">
          {b.counterparty_name}
          <span className="ml-2 text-label text-fg-faint">{b.remark || '无附言'}</span>
        </Td>
        <TdNum className={b.amount < 0 ? 'text-risk-critical' : 'text-fg'}>
          ¥{Number(b.amount || 0).toLocaleString('zh-CN')}
        </TdNum>
      </tr>
    ))

  const columnCount = activeTab === 'discrepancies' || activeTab === 'vouchers' ? 5 : 4
  const visibleRows =
    activeTab === 'discrepancies'
      ? discrepancies.length
      : activeTab === 'vouchers'
        ? vouchers.length
        : activeTab === 'invoices'
          ? invoices.length
          : bankFlows.length

  return (
    <div className="flex-1 overflow-y-auto bg-field">
      <div className="mx-auto max-w-[80rem] space-y-8 px-6 py-8">
        {/* ---------------------------------------------------------------- */}
        {/* The one number: what fails to close.                             */}
        {/* ---------------------------------------------------------------- */}
        <Reveal index={0}>
          <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
            <div className="min-w-0">
              <h2 className="text-title font-semibold text-fg">
                {currentCase?.company_name || '未选定案例'}
                <span className="ml-3 text-body font-normal text-fg">
                  业务凭证 ⟷ 税务发票 ⟷ 资金流水闭环勾稽
                </span>
              </h2>
              <div className="mt-5 text-label text-fg-muted">勾稽差异金额</div>
              <div
                className={cn(
                  'mt-1 tabular-nums text-display font-semibold',
                  reconData && !isClean ? 'text-risk-critical' : 'text-fg'
                )}
                aria-label="三单勾稽差异金额合计"
              >
                ¥{money(displayedAbnormal)}
              </div>
            </div>

            <div className="flex flex-col items-start gap-3 sm:items-end">
              <Chip tone={breakTone} filled={Boolean(reconData) && !isClean}>
                {!reconData
                  ? '待核验'
                  : isClean
                    ? '三单勾稽一致'
                    : `检出 ${breakCount} 处勾稽断裂`}
              </Chip>
              <span className="text-body text-fg">
                已核对 <span className="tabular-nums text-fg">{recordTotal}</span> 条业务记录
              </span>
            </div>
          </header>
        </Reveal>

        {/* ---------------------------------------------------------------- */}
        {/* The verdict, on the one lit surface of this screen.              */}
        {/* ---------------------------------------------------------------- */}
        <Reveal index={1}>
          <Surface paper className="px-6 py-6" aria-label="勾稽结论">
            <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
              <div className="min-w-0 max-w-[34ch]">
                <div className="text-label text-ink-muted">勾稽结论</div>
                <p className="mt-2 text-title font-semibold text-ink">{conclusion}</p>
              </div>

              <div className="text-right">
                <div className="text-label text-ink-muted">
                  {reconData ? (isClean ? '待复核断裂' : '差异条目') : '差异条目'}
                </div>
                <div
                  className={cn(
                    'mt-1 tabular-nums text-title font-semibold',
                    reconData && !isClean ? 'text-risk-critical' : 'text-ink'
                  )}
                >
                  {reconData ? breakCount : '---'}
                  <span className="ml-1.5 text-small font-medium text-ink-muted">处</span>
                </div>
                <div className="mt-3 text-label text-ink-muted">差异金额</div>
                <div className="mt-1 tabular-nums text-body font-semibold text-ink">
                  ¥{money(abnormalTotal)}
                </div>
              </div>
            </div>

            <p className="mt-5 max-w-[75ch] bg-paper-deep px-3 py-2 text-small text-ink-muted">{basis}</p>
          </Surface>
        </Reveal>

        {/* ---------------------------------------------------------------- */}
        {/* Evidence: one real table, four views over it.                    */}
        {/* ---------------------------------------------------------------- */}
        <Reveal index={2}>
          <Panel
            title="穿透证据台账"
            note="断裂明细与三类原始单据共用一张台账，切换视图不丢失上下文。"
            meta={<span className="tabular-nums">当前视图 {visibleRows} 条</span>}
            bare
          >
            <div className="scroll-x flex items-center gap-1 bg-field-sunken px-5 py-2">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setActiveTab(t.id)}
                  aria-pressed={activeTab === t.id}
                  className={cn(
                    'press flex items-center gap-2 px-3 py-2 text-small',
                    activeTab === t.id
                      ? 'bg-field-raised2 font-medium text-fg'
                      : 'text-fg-muted hover:bg-field-raised hover:text-fg'
                  )}
                >
                  <span>{t.label}</span>
                  <span className="tabular-nums text-label text-fg-faint">{t.count}</span>
                </button>
              ))}
            </div>

            <DataTable>
              <thead>
                {activeTab === 'discrepancies' ? (
                  <tr>
                    <Th>断裂类型</Th>
                    <Th>关联单号</Th>
                    <Th>证据说明</Th>
                    <Th className="text-right">异动金额</Th>
                  </tr>
                ) : activeTab === 'vouchers' ? (
                  <tr>
                    <Th>凭证号</Th>
                    <Th>记账日期</Th>
                    <Th>摘要</Th>
                    <Th className="text-right">借方金额</Th>
                    <Th>借贷校验</Th>
                  </tr>
                ) : activeTab === 'invoices' ? (
                  <tr>
                    <Th>发票号</Th>
                    <Th>开票日期</Th>
                    <Th>客户 / 销售方</Th>
                    <Th className="text-right">价税合计</Th>
                  </tr>
                ) : (
                  <tr>
                    <Th>交易号</Th>
                    <Th>交易时间</Th>
                    <Th>对手方</Th>
                    <Th className="text-right">发生额</Th>
                  </tr>
                )}
              </thead>
              <tbody>
                {activeTab === 'discrepancies'
                  ? renderDiscrepancyRows()
                  : activeTab === 'vouchers'
                    ? renderVoucherRows()
                    : activeTab === 'invoices'
                      ? renderInvoiceRows()
                      : renderBankFlowRows()}
              </tbody>
            </DataTable>
          </Panel>
        </Reveal>
      </div>
    </div>
  )
}
