import React, { useState } from 'react'
import { AnalysisReportResult, WorkpaperData, CpaApprovalReceipt } from '../types'
import {
  Btn,
  DataTable,
  EmptyState,
  Panel,
  Status,
  Td,
  TdNum,
  Th,
  cn
} from '../ui/primitives'
import { Reveal } from '../ui/motion'

interface WorkpaperTableProps {
  report: AnalysisReportResult | null
  currentCase: any
  onRunAudit?: () => void
  isRunning?: boolean
}

const money = (value: unknown) =>
  `¥${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`

/**
 * Beat 4 - 存证. The workpaper is the lit sheet.
 *
 * This is where the direction pays off: the audit workpaper is literally the
 * paper, one bright artifact on a continuous dark field. Everything on the
 * sheet is ink; everything around it stays in the room.
 */
export const WorkpaperTable: React.FC<WorkpaperTableProps> = ({
  report,
  currentCase,
  onRunAudit,
  isRunning
}) => {
  const [downloading, setDownloading] = useState<string | null>(null)

  const [cpaReceipt, setCpaReceipt] = useState<CpaApprovalReceipt | null>(null)
  const [signing, setSigning] = useState(false)
  const [auditorName, setAuditorName] = useState('')
  const [certNo, setCertNo] = useState('')
  const [opinionType, setOpinionType] = useState('保留意见/拟追加外部银行函证')
  const [findingDispositions, setFindingDispositions] = useState<Record<string, string>>({})

  const handleSignOff = async () => {
    if (!report) return
    setSigning(true)
    try {
      const resp = await fetch('/api/compliance/cpa-approval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: report.case_id,
          auditor_name: auditorName,
          cert_no: certNo,
          opinion_type: opinionType,
          audit_firm: '数智会计联合审计项目组',
          professional_skepticism_notes:
            '已秉持职业怀疑态度，全面复核确定性算子三单倒挂天数与Beneish操纵指数，认可智能体证据链，拟针对可疑关联方实施外部独立银行函证。',
          compliance_confirmed: true
        })
      })
      if (resp.ok) {
        const receipt = await resp.json()
        setCpaReceipt(receipt)
      }
    } catch (e) {
      console.error('Sign-off failed', e)
    } finally {
      setSigning(false)
    }
  }

  if (!report || !report.workpapers || report.workpapers.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto">
        <Reveal index={0}>
          <EmptyState
            title="尚未生成受审企业审计工作底稿"
            body={`底稿由业财三单比对、Beneish 八因子刚性测算与准则定性共同合成。当前选定案例【${
              currentCase?.company_name || '未选定'
            }】尚未执行穿透研判。`}
            action={
              onRunAudit ? (
                <Btn variant="primary" size="lg" disabled={isRunning} onClick={onRunAudit}>
                  {isRunning ? '正在生成审计工作底稿…' : '立即对当前案例一键生成底稿'}
                </Btn>
              ) : undefined
            }
          />
        </Reveal>
      </div>
    )
  }

  const wp: WorkpaperData = report.workpapers[0]

  const handleExport = async (format: 'excel' | 'pdf' | 'json') => {
    setDownloading(format)
    try {
      const resp = await fetch(`/api/export/${format}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // 现场签署的注会信息与逐条发现复核意见随导出请求一并提交，写入 Excel/PDF 底稿
        body: JSON.stringify(
          cpaReceipt
            ? { ...report, cpa_signoff: { ...cpaReceipt, finding_dispositions: findingDispositions } }
            : report
        )
      })

      if (resp.ok) {
        const blob = await resp.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `AuditMind_${report.company_name}_${format.toUpperCase()}.${
          format === 'excel' ? 'xlsx' : format
        }`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      }
    } catch (e) {
      console.error('Export failed', e)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Who prepared it, and the one action that takes it out of the room. */}
      <Reveal index={0} className="px-5 pt-6 pb-5 sm:px-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="text-label text-fg-muted">
              注册会计师标准审计工作底稿 · {wp.workpaper_id}
            </div>
            <h2 className="mt-2 text-title font-semibold text-fg">
              {wp.title} · {report.company_name}
            </h2>
            <p className="mt-2 text-body text-fg">
              编制人 {wp.prepared_by} · 复核日期 {wp.review_date} · 抽样样本量 {wp.sample_count} 笔
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <Btn
              variant="primary"
              size="md"
              disabled={downloading === 'excel'}
              onClick={() => handleExport('excel')}
            >
              {downloading === 'excel' ? '正在导出…' : '导出 Excel 底稿 (.xlsx)'}
            </Btn>
            <Btn
              variant="quiet"
              size="md"
              disabled={downloading === 'pdf'}
              onClick={() => handleExport('pdf')}
            >
              {downloading === 'pdf' ? '正在排版…' : '导出 PDF 报告 (.pdf)'}
            </Btn>
            <Btn
              variant="quiet"
              size="md"
              disabled={downloading === 'json'}
              onClick={() => handleExport('json')}
            >
              {downloading === 'json' ? '正在打包…' : '导出 JSON 数据包'}
            </Btn>
          </div>
        </div>
      </Reveal>

      {/* The lit sheet: this is the one bright surface on the screen. */}
      <Reveal index={1} className="px-5 sm:px-6">
        <Panel paper bare>
          <div className="px-6 pt-6 pb-5">
            <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-5">
              <div>
                <div className="text-label text-ink-muted">审计调整（差异）金额合计</div>
                <div className="mt-1 text-display font-semibold tabular-nums text-risk-critical">
                  {money(wp.abnormal_amount)}
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-x-10 gap-y-4 sm:grid-cols-3">
                <div>
                  <dt className="text-label text-ink-muted">核查样本</dt>
                  <dd className="mt-1 text-body font-medium tabular-nums text-ink">
                    {wp.rows.length} 笔
                  </dd>
                </div>
                <div>
                  <dt className="text-label text-ink-muted">审定金额合计</dt>
                  <dd className="mt-1 text-body font-medium tabular-nums text-ink">
                    {money(wp.total_audited_amount)}
                  </dd>
                </div>
                <div>
                  <dt className="text-label text-ink-muted">底稿编号</dt>
                  <dd className="mt-1 text-body font-medium tabular-nums text-ink">
                    {wp.workpaper_id}
                  </dd>
                </div>
              </dl>
            </div>
            <p className="mt-5 bg-paper-deep px-4 py-3 text-body text-ink">
              <span className="text-label text-ink-muted">底稿复核综合意见 · </span>
              {wp.audit_opinion_summary}
            </p>
          </div>

          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 px-6 pb-3">
            <h2 className="text-title font-semibold text-ink">核查样本明细</h2>
            <span className="text-small text-ink-muted">
              账面与审定逐笔对照，差异超过 ¥0.01 记为异常
            </span>
          </div>

          <DataTable>
            <thead>
              <tr>
                <Th className="border-black/10 bg-transparent text-ink-muted">凭证号</Th>
                <Th className="border-black/10 bg-transparent text-ink-muted">业务日期</Th>
                <Th className="border-black/10 bg-transparent text-ink-muted">摘要</Th>
                <Th className="border-black/10 bg-transparent text-right text-ink-muted">
                  账面金额
                </Th>
                <Th className="border-black/10 bg-transparent text-right text-ink-muted">
                  审定金额
                </Th>
                <Th className="border-black/10 bg-transparent text-right text-ink-muted">
                  差异金额
                </Th>
                <Th className="border-black/10 bg-transparent text-ink-muted">审计结论</Th>
                <Th className="border-black/10 bg-transparent text-ink-muted">佐证底单</Th>
              </tr>
            </thead>
            <tbody>
              {wp.rows.map((r, i) => {
                const hasDiscrepancy = Math.abs(Number(r.discrepancy || 0)) > 0.01
                return (
                  <tr key={i} className="hover:bg-black/[0.03]">
                    <Td className="border-black/10 tabular-nums text-ink">{r.voucher_no}</Td>
                    <Td className="border-black/10 tabular-nums text-ink-muted">{r.date}</Td>
                    <Td className="border-black/10 max-w-xs truncate text-ink" title={r.summary}>
                      {r.summary}
                    </Td>
                    <TdNum className="border-black/10 text-ink">{money(r.ledger_amount)}</TdNum>
                    <TdNum className="border-black/10 text-ink">{money(r.verified_amount)}</TdNum>
                    <TdNum
                      className={cn(
                        'border-black/10 font-medium',
                        hasDiscrepancy ? 'text-risk-critical' : 'text-ink-muted'
                      )}
                    >
                      {money(r.discrepancy)}
                    </TdNum>
                    <Td className="border-black/10">
                      {hasDiscrepancy ? (
                        <Status tone="critical">{r.audit_conclusion}</Status>
                      ) : (
                        <span className="text-ink-muted">{r.audit_conclusion}</span>
                      )}
                    </Td>
                    <Td
                      className="border-black/10 max-w-[160px] truncate text-ink-muted"
                      title={r.evidence_trace}
                    >
                      {r.evidence_trace}
                    </Td>
                  </tr>
                )
              })}
            </tbody>
          </DataTable>
        </Panel>
      </Reveal>

      {/* Proposed adjusting entries and their effect on the statements. */}
      {report.adjustments?.entries?.length ? (
        <Reveal index={2} className="px-5 pt-5 sm:px-6">
          <Panel
            title="拟定审计调整分录（AJE）"
            note="仅对确定性程序锚定到具体凭证的发现项编制，借贷平衡；须经注册会计师与管理层沟通后确定。"
          >
            {report.adjustments.impact && report.adjustments.impact.comparable === false ? (
              <p className="px-5 pt-4 text-small text-risk-medium">{report.adjustments.impact.caveat}</p>
            ) : report.adjustments.impact ? (
              <div className="grid grid-cols-1 gap-4 px-5 pt-4 sm:grid-cols-3">
                {([
                  ['营业收入', report.adjustments.impact.revenue_before, report.adjustments.impact.revenue_after],
                  ['营业成本', report.adjustments.impact.cost_before, report.adjustments.impact.cost_after],
                  ['净利润（近似）', report.adjustments.impact.profit_before, report.adjustments.impact.profit_after],
                ] as [string, number, number][]).map(([label, before, after]) => (
                  <div key={label}>
                    <div className="text-label text-fg-muted">{label}</div>
                    <div className="mt-1 text-body tabular-nums text-fg">
                      {(before / 1e8).toFixed(2)} 亿 → <span className={after < before ? 'text-risk-critical' : ''}>{(after / 1e8).toFixed(2)} 亿</span>
                    </div>
                  </div>
                ))}
                {report.adjustments.impact.turns_to_loss ? (
                  <div className="sm:col-span-3">
                    <Status tone="critical">调整后由盈转亏</Status>
                  </div>
                ) : null}
                <p className="text-label text-fg-faint sm:col-span-3">{report.adjustments.impact.caveat}</p>
              </div>
            ) : null}
            <DataTable>
              <thead>
                <tr>
                  <Th>分录</Th>
                  <Th>科目</Th>
                  <Th className="text-right">借方</Th>
                  <Th className="text-right">贷方</Th>
                  <Th>说明</Th>
                </tr>
              </thead>
              <tbody>
                {report.adjustments.entries.flatMap((a: any) =>
                  a.lines.map((l: any, i: number) => (
                    <tr key={`${a.aje_id}-${i}`}>
                      <Td className="tabular-nums text-fg-muted">{i === 0 ? a.aje_id : ''}</Td>
                      <Td className={l.credit ? 'pl-8 text-fg' : 'text-fg'}>
                        {l.account_code} {l.account_name}
                      </Td>
                      <TdNum>{l.debit ? `¥${l.debit.toLocaleString('zh-CN')}` : ''}</TdNum>
                      <TdNum>{l.credit ? `¥${l.credit.toLocaleString('zh-CN')}` : ''}</TdNum>
                      <Td className="text-small text-fg-muted">{i === 0 ? a.description : ''}</Td>
                    </tr>
                  ))
                )}
              </tbody>
            </DataTable>
          </Panel>
        </Reveal>
      ) : null}

      {/* Back in the room: the human who answers for the sheet. */}
      <Reveal index={2} className="px-5 py-5 sm:px-6">
        <Panel
          title="注册会计师终审签章与责任伦理机制"
          note="遵循《中国注册会计师职业道德守则》：AI 辅助初筛，终审结论由执业注会独立复核并签名确认。"
          meta={
            cpaReceipt ? (
              <Status tone="clear">已完成数字签章生效</Status>
            ) : (
              <span className="text-label text-fg-faint">防算法独裁 · 终局负责</span>
            )
          }
        >
          {cpaReceipt ? (
            <div className="bg-field-raised2 px-5 py-5">
              <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="text-label text-fg-muted">签字注册会计师</dt>
                  <dd className="mt-1 text-body font-medium text-fg">{cpaReceipt.auditor_name}</dd>
                </div>
                <div>
                  <dt className="text-label text-fg-muted">执业证书编号</dt>
                  <dd className="mt-1 text-body font-medium tabular-nums text-fg">
                    {cpaReceipt.cert_no}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-label text-fg-muted">终审防伪哈希</dt>
                  <dd
                    className="mt-1 truncate text-small text-fg-muted"
                    title={cpaReceipt.verification_hash}
                  >
                    {cpaReceipt.verification_hash}
                  </dd>
                </div>
                <div>
                  <dt className="text-label text-fg-muted">签章时间</dt>
                  <dd className="mt-1 text-body font-medium tabular-nums text-fg">
                    {cpaReceipt.sign_timestamp}
                  </dd>
                </div>
              </dl>
              <p className="mt-5 max-w-[75ch] text-body text-fg">
                <span className="text-label text-fg-faint">伦理承诺 · </span>
                {cpaReceipt.ethical_declaration}
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-3">
                <label className="block">
                  <span className="text-label text-fg-muted">签字注册会计师</span>
                  <input
                    type="text"
                    value={auditorName}
                    onChange={(e) => setAuditorName(e.target.value)}
                    className="mt-1.5 w-full border border-white/10 bg-field px-3 py-2 text-small text-fg focus:border-seal"
                  />
                </label>
                <label className="block">
                  <span className="text-label text-fg-muted">CPA执业证书编号</span>
                  <input
                    type="text"
                    value={certNo}
                    onChange={(e) => setCertNo(e.target.value)}
                    className="mt-1.5 w-full border border-white/10 bg-field px-3 py-2 text-small tabular-nums text-fg focus:border-seal"
                  />
                </label>
                <label className="block">
                  <span className="text-label text-fg-muted">初拟审计意见类型</span>
                  <input
                    type="text"
                    value={opinionType}
                    onChange={(e) => setOpinionType(e.target.value)}
                    className="mt-1.5 w-full border border-white/10 bg-field px-3 py-2 text-small text-fg focus:border-seal"
                  />
                </label>
              </div>
              {report.findings && report.findings.length > 0 ? (
                <div className="space-y-2 border-t border-white/10 pt-4">
                  <div className="text-label text-fg-muted">逐项审计发现复核处置意见（随签章写入底稿）</div>
                  <div className="space-y-2">
                    {report.findings.map((f: any) => (
                      <div key={f.finding_id} className="flex flex-wrap items-center justify-between gap-3 bg-field-raised2 px-3 py-2 text-small">
                        <span className="truncate text-fg">{f.finding_id} · {f.title}</span>
                        <select
                          aria-label={`复核处置 ${f.finding_id}`}
                          value={findingDispositions[f.finding_id] || '已复核采纳'}
                          onChange={(e) =>
                            setFindingDispositions((prev) => ({ ...prev, [f.finding_id]: e.target.value }))
                          }
                          className="border border-white/10 bg-field px-2.5 py-1 text-small text-fg"
                        >
                          <option value="已复核采纳">已复核采纳</option>
                          <option value="修正后采纳">修正后采纳</option>
                          <option value="排除误报">排除误报</option>
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              <div className="flex justify-end">
                <Btn variant="solid" size="md" disabled={signing} onClick={handleSignOff}>
                  {signing ? '签名存证中…' : '执业注会终审签章'}
                </Btn>
              </div>
            </div>
          )}
        </Panel>
      </Reveal>
    </div>
  )
}
