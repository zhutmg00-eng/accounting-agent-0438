import React, { useMemo, useState } from 'react'
import { AlertTriangle, ArrowRight, Check, Copy, Play, RotateCw } from 'lucide-react'
import { AnalysisReportResult } from '../types'
import {
  Btn,
  Chip,
  cn,
  EmptyState,
  Panel,
  Status,
  Surface,
  Verdict,
  toneOfVerdict
} from '../ui/primitives'
import { Reveal, StageRail, useAnimatedNumber } from '../ui/motion'
import { count, growthLabel, moneyParts, pct } from '../lib/format'
import { AnalyticsPanel } from './AnalyticsPanel'

interface AuditCockpitProps {
  currentCase: any
  report: AnalysisReportResult | null
  isRunning: boolean
  onRunAudit: () => void
  currentStage: number
  stageLogs: { stage: number; title: string; status: string; detail: string }[]
  onSelectCase?: (caseId: string) => void
}

/** The five audit operators, in the order the pipeline runs them. */
const STAGES = [
  { num: 1, name: '数据解析与字段校验', note: '凭证 / 发票 / 合同 / 流水结构化' },
  { num: 2, name: '确定性算子矩阵扫描', note: 'Beneish M-Score 等确定性算子' },
  { num: 3, name: '三单业财勾稽穿透', note: '凭证 ↔ 发票 ↔ 合同 ↔ 流水' },
  { num: 4, name: 'DeepSeek 准则推理', note: '准则条款与处罚先例对齐' },
  { num: 5, name: '审计底稿与结论合成', note: '底稿、结论、复核留痕' }
]

/** Cases the demo walks through; kept because the live demo depends on them. */
const SHOWCASE = [
  { id: 'REAL_CSRC_001', code: '600518', name: '康美药业', tag: '虚增货币 299.44 亿 / 伪造存单' },
  { id: 'REAL_CSRC_002', code: '002450', name: '康得新', tag: '虚增存款 122 亿 / 联动池闭环' },
  { id: 'REAL_CSRC_003', code: '600781', name: '辅仁药业', tag: '非经营性占用 / 违规担保' },
  { id: 'REAL_CSRC_014', code: '002069', name: '獐子岛', tag: '底播存货核销 / 异常灭失' },
  { id: 'REAL_CLEAN_027', code: '600660', name: '福耀玻璃', tag: '合规基准对照 · 零误报' }
]

const RISK_LABEL: Record<string, string> = {
  CRITICAL: '存在重大舞弊迹象',
  HIGH: '存在高度舞弊风险',
  MEDIUM: '存在中度错报风险',
  LOW: '风险可控，需持续关注',
  CLEAN: '未发现舞弊迹象'
}

/** The largest single amount a finding rests on. */
const findingMagnitude = (f: any): number =>
  Math.abs(Number(f?.impact_amount ?? f?.abnormal_amount ?? f?.suspicious_amount ?? 0)) || 0

/** A figure and its unit, where only the figure is display size. */
const Figure: React.FC<{ amount: number; tone?: 'ink' | 'muted' }> = ({ amount, tone = 'ink' }) => {
  const { value, unit } = moneyParts(amount)
  return (
    <>
      {value}
      <span
        className={cn(
          'ml-2 text-title font-medium',
          tone === 'ink' ? 'text-ink/60' : 'text-fg-muted'
        )}
      >
        {unit}
      </span>
    </>
  )
}

const Row: React.FC<{
  label: React.ReactNode
  children: React.ReactNode
  emphasis?: boolean
}> = ({ label, children, emphasis }) => (
  <div
    className={cn(
      'flex items-baseline justify-between gap-4 px-4 py-2.5',
      emphasis ? 'bg-field-raised2/60' : 'odd:bg-field-raised2/30'
    )}
  >
    <dt className="text-small text-fg-muted">{label}</dt>
    <dd className="text-right text-small tabular-nums text-fg">{children}</dd>
  </div>
)

export const AuditCockpit: React.FC<AuditCockpitProps> = ({
  currentCase,
  report,
  isRunning,
  onRunAudit,
  currentStage,
  stageLogs,
  onSelectCase
}) => {
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Hooks run before the empty-state return so the hook order is stable.
  const findings = useMemo(() => report?.findings ?? [], [report])

  const heroFinding = useMemo(
    () => [...findings].sort((a, b) => findingMagnitude(b) - findingMagnitude(a))[0],
    [findings]
  )

  const heroAmount = heroFinding
    ? Number(
        heroFinding.impact_amount ?? heroFinding.abnormal_amount ?? heroFinding.suspicious_amount ?? 0
      )
    : 0

  const reconciliation = currentCase?.reconciliation
  const auditedScope = Number(reconciliation?.total_audited_amount ?? 0)

  // Before the audit runs, the screen is about how much money is under review.
  // After it runs, it is about the largest problem found.
  const displayAmount = report ? heroAmount : auditedScope
  const animatedAmount = useAnimatedNumber(displayAmount)

  const stageState = (index: number): 'pending' | 'running' | 'done' | 'failed' => {
    if (report) return 'done'
    if (!isRunning) return 'pending'
    const n = index + 1
    if (n < currentStage) return 'done'
    if (n === currentStage) return 'running'
    return 'pending'
  }

  const handleCopyFinding = (text: string, id: string) => {
    navigator.clipboard?.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  if (!currentCase) {
    return (
      <EmptyState
        className="m-6 bg-field-raised"
        title="还没有选择案件"
        body="从左侧案例库中挑一个真实处罚案例，或者点下面的答辩经典案例直接进入。选定之后，这一屏会显示案件事实、审计流水线和最终研判结论。"
        action={
          onSelectCase ? (
            <div className="flex flex-wrap gap-2">
              {SHOWCASE.slice(0, 3).map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => onSelectCase(p.id)}
                  className="press flex items-center gap-2 bg-field-raised2 px-3 py-2 text-small text-fg hover:bg-field-raised3"
                >
                  <span className="tabular-nums text-fg-faint">{p.code}</span>
                  {p.name}
                  <ArrowRight className="h-3.5 w-3.5 text-fg-faint" />
                </button>
              ))}
            </div>
          ) : undefined
        }
      />
    )
  }

  const fin = currentCase.financial_summary ?? {}
  const prior = currentCase.prior_financial_summary ?? {}
  const rating = String(report?.overall_risk_rating ?? '').toUpperCase()
  const isClean = rating === 'CLEAN'

  const inventory = [
    { label: '记账凭证', value: currentCase.vouchers?.length ?? 0 },
    { label: '税务发票', value: currentCase.invoices?.length ?? 0 },
    { label: '业务合同', value: currentCase.contracts?.length ?? 0 },
    { label: '银行流水', value: currentCase.bank_flows?.length ?? 0 },
    { label: '勾稽异常', value: reconciliation?.discrepancies?.length ?? 0 },
    { label: '风险线索', value: currentCase.ground_truth_risks?.length ?? 0 }
  ]

  const revenueGrowth = growthLabel(fin.revenue, prior.revenue)
  const cashNegative = Number(fin.operating_cash_flow) < 0

  return (
    <div className="space-y-5 p-4 sm:p-6">
      {/* ---- 清点: what case is open, and on whose authority ---- */}
      <Reveal>
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-small tabular-nums font-medium text-seal-soft">
                {currentCase.stock_code}
              </span>
              <h2 className="text-title font-semibold text-fg">{currentCase.company_name}</h2>
              <span className="text-label text-fg-faint">{currentCase.case_id}</span>
            </div>
            <p className="mt-1.5 text-body text-fg">
              {currentCase.industry} · 审计期间 {currentCase.audit_period} ·{' '}
              {currentCase.penalty_decision_no}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Chip>{currentCase.case_category}</Chip>
            {report ? (
              <Status tone={toneOfVerdict(rating)}>
                {RISK_LABEL[rating] ?? report.overall_risk_rating}
              </Status>
            ) : (
              <Status tone="neutral">待研判</Status>
            )}
          </div>
        </div>
      </Reveal>

      {/* ---- 定谳: the conclusion, on the one lit surface ----
          Deliberately NOT wrapped in <Reveal>. The finding is the point of the
          screen, so it is on the paper at first paint; a conclusion that fades
          in is a conclusion you might miss. */}
      {report ? (
          <Verdict
            conclusion={RISK_LABEL[rating] ?? `风险等级 ${report.overall_risk_rating}`}
            tone={toneOfVerdict(rating)}
            figure={<Figure amount={animatedAmount} />}
            figureLabel={heroFinding ? `最大单项问题金额 · ${heroFinding.title}` : '本次穿透未量化出问题金额'}
            action={
              <Btn
                variant="solid"
                onClick={onRunAudit}
                disabled={isRunning}
                icon={<RotateCw className={cn('h-4 w-4', isRunning && 'animate-spin')} />}
              >
                {isRunning ? `研判进行中 · 阶段 ${currentStage} / 5` : '重新研判'}
              </Btn>
            }
            basis={report.executive_summary}
          />
        ) : (
          <Verdict
            conclusion="本案尚未出具数智穿透结论"
            tone="neutral"
            figure={<Figure amount={animatedAmount} />}
            figureLabel="受审资金规模"
            action={
              <Btn
                variant="primary"
                size="lg"
                onClick={onRunAudit}
                disabled={isRunning}
                icon={<Play className="h-4 w-4" />}
              >
                {isRunning ? `研判进行中 · 阶段 ${currentStage} / 5` : '执行数智穿透研判'}
              </Btn>
            }
            basis={currentCase.csrc_summary ?? '—'}
          />
      )}

      {/* ---- 穿透: the pipeline, the product's signature move ---- */}
      <Reveal index={2}>
        <Panel
          title="审计流水线"
          note="五道审计算子依次执行，全部结果可追溯到底稿"
          meta={
            <span role="status" aria-live="polite" className="tabular-nums">
              阶段 {Math.min(currentStage || 1, 5)} / 5 ·{' '}
              {report ? '已完成' : isRunning ? '执行中' : '待执行'}
            </span>
          }
          bare
        >
          <div className="grid gap-px bg-field-raised2 sm:grid-cols-2 lg:grid-cols-5">
            {STAGES.map((s, i) => {
              const state = stageState(i)
              return (
                <div key={s.num} className="flex flex-col bg-field-raised px-4 py-4">
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={cn(
                        'text-label tabular-nums font-medium',
                        state === 'done' && 'text-risk-clear',
                        state === 'running' && 'text-seal',
                        state === 'failed' && 'text-risk-critical',
                        state === 'pending' && 'text-fg-faint'
                      )}
                    >
                      {s.num}
                    </span>
                    {state === 'done' ? <Check className="h-3.5 w-3.5 text-risk-clear" /> : null}
                  </div>
                  <div
                    className={cn(
                      'mt-2 text-small font-medium',
                      state === 'pending' ? 'text-fg-faint' : 'text-fg'
                    )}
                  >
                    {s.name}
                  </div>
                  <div className="mt-1 flex-1 text-label text-fg-faint">{s.note}</div>
                  <div className="mt-3">
                    <StageRail state={state} />
                  </div>
                </div>
              )
            })}
          </div>
        </Panel>
      </Reveal>

      {/* ---- 清点: material on hand, and the numbers that frame it ---- */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Reveal index={3}>
          <Panel
            title="已载入证据"
            note="本案件由处罚决定书还原的全部原始资料"
            className="h-full"
          >
            <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
              {inventory.map((item) => (
                <div key={item.label}>
                  <div className="text-label text-fg-muted">{item.label}</div>
                  <div
                    className={cn(
                      'mt-0.5 text-title font-semibold tabular-nums',
                      item.value === 0 ? 'text-fg-faint' : 'text-fg'
                    )}
                  >
                    {count(item.value)}
                  </div>
                </div>
              ))}
            </div>

            {currentCase.description ? (
              <p className="mt-5 max-w-[70ch] text-body text-fg">{currentCase.description}</p>
            ) : null}
          </Panel>
        </Reveal>

        <Reveal index={4}>
          <Panel
            title="财务快照"
            note={
              fin.period
                ? `${fin.period} · 与上年同期对比 · ${
                    fin.provenance === 'reported_original'
                      ? '摘自当年年报原始发布版'
                      : fin.provenance === 'reported' && !(fin.estimated_fields ?? []).length
                        ? '年报披露数'
                        : '部分字段为结构化重构，仅演示算法'
                  }`
                : undefined
            }
            className="h-full"
          >
            <dl className="-mx-4">
              <Row label="营业收入">
                {moneyParts(fin.revenue).value} {moneyParts(fin.revenue).unit}
                {revenueGrowth ? (
                  <span className="ml-2 text-label text-fg-faint">{revenueGrowth}</span>
                ) : null}
              </Row>
              <Row label="净利润">
                {moneyParts(fin.net_profit).value} {moneyParts(fin.net_profit).unit}
              </Row>
              <Row label="经营活动现金流" emphasis>
                <span className={cashNegative ? 'text-risk-critical' : 'text-fg'}>
                  {moneyParts(fin.operating_cash_flow).value}{' '}
                  {moneyParts(fin.operating_cash_flow).unit}
                </span>
              </Row>
              <Row label="毛利率">{pct(fin.gross_margin)}</Row>
              <Row label="总资产">
                {moneyParts(fin.total_assets).value} {moneyParts(fin.total_assets).unit}
              </Row>
            </dl>
            {fin.source_url ? (
              <a
                href={fin.source_url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-block text-label text-fg-faint underline-offset-2 hover:text-fg hover:underline"
              >
                查看年报原文
              </a>
            ) : null}

            {revenueGrowth && cashNegative ? (
              <p className="mt-4 max-w-[70ch] text-body text-fg">
                营业收入同比增长 <span className="text-fg">{revenueGrowth}</span>，经营活动现金流却为
                <span className="text-risk-critical"> 净流出</span>
                —— 利润在增长，现金在流出，这两件事同时成立本身就是需要解释的异常。
              </p>
            ) : null}
          </Panel>
        </Reveal>
      </div>

      {/* ---- 定谳的支撑: the findings the conclusion rests on ---- */}
      {report ? (
        <Reveal index={5}>
          <Panel
            title="穿透核查发现备忘录"
            meta={
              <span className="tabular-nums">
                {findings.length} 项 · 耗时{' '}
                {report.execution_time_seconds !== undefined
                  ? `${report.execution_time_seconds.toFixed(3)} s`
                  : '—'}{' '}
                · {report.execution_mode}
                {report.verification ? (
                  <>
                    {' '}· 证据锚定 {report.verification.grounded}/{report.verification.findings_total}
                    {report.verification.amount_unverified
                      ? ` · 金额待复核 ${report.verification.amount_unverified}`
                      : ''}
                    {report.verification.calibration?.recalibrated?.length
                      ? ` · 定级校准 ${report.verification.calibration.recalibrated.length}`
                      : ''}
                    {report.verification.reflection?.triggered
                      ? ` · 自我修正 ${report.verification.reflection.issues_before ?? '?'}→${report.verification.reflection.issues_after ?? '?'}${report.verification.reflection.adopted ? '（已采纳）' : '（保留初稿）'}`
                      : ''}
                    {report.substantive?.materiality
                      ? ` · 实际执行重要性 ¥${(report.substantive.materiality.performance_materiality / 1e4).toFixed(0)}万`
                      : ''}
                  </>
                ) : null}
              </span>
            }
          >
            {findings.length === 0 ? (
              <EmptyState
                title="未检出舞弊迹象"
                body="全部确定性算子与准则推理均未命中异常。此结论与案件的真实合规基准一致。"
              />
            ) : (
              <ul className="space-y-3">
                {findings.map((f, idx) => {
                  const amount = findingMagnitude(f)
                  const evidenceText = [
                    f.title,
                    f.suspected_mechanism ? `机制：${f.suspected_mechanism}` : '',
                    f.audit_evidence ? `证据：${f.audit_evidence}` : '',
                    amount ? `金额：${moneyParts(amount).value} ${moneyParts(amount).unit}` : ''
                  ]
                    .filter(Boolean)
                    .join('\n')
                  return (
                    <li key={f.finding_id ?? idx}>
                      <Surface level="raised" className="px-5 py-4">
                        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
                          <div className="flex min-w-0 items-baseline gap-3">
                            <h3 className="text-body font-medium text-fg">{f.title}</h3>
                          </div>
                          <div className="flex shrink-0 items-center gap-3">
                            {amount ? (
                              <span className="text-body tabular-nums font-semibold text-risk-critical">
                                {moneyParts(amount).value}{' '}
                                <span className="text-small font-normal text-fg-muted">
                                  {moneyParts(amount).unit}
                                </span>
                              </span>
                            ) : null}
                            {f.grounded === false ? (
                              <Status tone="medium">证据未锚定</Status>
                            ) : f.cited_refs?.length ? (
                              <Status tone="clear">已锚定 {f.cited_refs.length} 张单据</Status>
                            ) : null}
                            <Status tone={toneOfVerdict(f.risk_level)}>{f.risk_level}</Status>
                            <button
                              type="button"
                              onClick={() => handleCopyFinding(evidenceText, f.finding_id ?? String(idx))}
                              className="press flex h-8 w-8 items-center justify-center text-fg-faint hover:bg-field-raised2 hover:text-fg"
                              aria-label={`复制发现 ${idx + 1}`}
                            >
                              {copiedId === (f.finding_id ?? String(idx)) ? (
                                <Check className="h-4 w-4 text-risk-clear" />
                              ) : (
                                <Copy className="h-4 w-4" />
                              )}
                            </button>
                          </div>
                        </div>

                        {f.suspected_mechanism ? (
                          <p className="mt-3 max-w-[85ch] text-body text-fg">
                            <span className="text-fg-faint">机制 </span>
                            {f.suspected_mechanism}
                          </p>
                        ) : null}

                        {f.audit_evidence ? (
                          <p className="mt-2 max-w-[85ch] text-body text-fg">
                            <span className="text-fg-faint">证据 </span>
                            {f.audit_evidence}
                          </p>
                        ) : null}

                        {f.verification_note ? (
                          <p className="mt-2 max-w-[85ch] text-small text-fg-muted">
                            <span className="text-fg-faint">校验 </span>
                            {f.cited_refs?.length ? `${f.cited_refs.join('、')} · ` : ''}
                            {f.verification_note}
                          </p>
                        ) : null}

                        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-label text-fg-faint">
                          {f.accounting_standard ? <span>准则 {f.accounting_standard}</span> : null}
                          {f.csrc_standard_clause ? <span>依据 {f.csrc_standard_clause}</span> : null}
                          {f.confidence_score !== undefined ? (
                            <span className="tabular-nums">
                              置信度 {pct(f.confidence_score, 0)}
                            </span>
                          ) : null}
                          {f.suggested_procedure ? (
                            <span className="max-w-[60ch]">建议程序 {f.suggested_procedure}</span>
                          ) : null}
                        </div>
                      </Surface>
                    </li>
                  )
                })}
              </ul>
            )}
          </Panel>
        </Reveal>
      ) : null}

      {/* ---- 全量分析程序 ---- */}
      {report?.analytics ? (
        <Reveal index={6}>
          <AnalyticsPanel analytics={report.analytics} />
        </Reveal>
      ) : null}

      {/* ---- 执行日志 ---- */}
      {stageLogs.length > 0 ? (
        <Reveal index={6}>
          <Panel title="执行日志" meta={<span className="tabular-nums">{stageLogs.length} 条</span>}>
            <ol className="space-y-2">
              {stageLogs.map((log, i) => (
                <li key={`${log.stage}-${i}`} className="flex items-start gap-4 py-1.5">
                  <span className="w-20 shrink-0 text-label tabular-nums text-fg-faint">
                    阶段 {log.stage}
                  </span>
                  <span className="w-56 shrink-0 text-small text-fg">{log.title}</span>
                  <span className="min-w-0 flex-1 text-small text-fg-muted">{log.detail}</span>
                </li>
              ))}
            </ol>
          </Panel>
        </Reveal>
      ) : null}

      {/* ---- 答辩经典案例 quick jump ---- */}
      {onSelectCase ? (
        <Reveal index={7}>
          <Panel title="答辩经典案例" note="现场演示按此顺序推进">
            <div className="flex flex-wrap gap-2">
              {SHOWCASE.map((p) => {
                const isCurrent = currentCase.case_id === p.id
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => onSelectCase(p.id)}
                    className={cn(
                      'press flex min-w-[240px] flex-1 flex-col items-start gap-1 px-4 py-3 text-left',
                      isCurrent
                        ? 'bg-field-raised3'
                        : 'bg-field-raised2 hover:bg-field-raised3'
                    )}
                  >
                    <span className="flex items-baseline gap-2">
                      <span className="text-label tabular-nums text-seal-soft">{p.code}</span>
                      <span className="text-small font-medium text-fg">{p.name}</span>
                    </span>
                    <span className="text-label text-fg-muted">{p.tag}</span>
                  </button>
                )
              })}
              <button
                type="button"
                onClick={async () => {
                  const r = await fetch('/api/demo/population', { method: 'POST' })
                  if (r.ok) {
                    const data = await r.json()
                    onSelectCase(data.case_id)
                  }
                }}
                className={cn(
                  'press flex min-w-[240px] flex-1 flex-col items-start gap-1 px-4 py-3 text-left',
                  currentCase.case_id === 'DEMO-POPULATION-2025'
                    ? 'bg-field-raised3'
                    : 'bg-field-raised2 hover:bg-field-raised3'
                )}
              >
                <span className="flex items-baseline gap-2">
                  <span className="text-label tabular-nums text-seal-soft">DEMO</span>
                  <span className="text-small font-medium text-fg">全量演示账套</span>
                </span>
                <span className="text-label text-fg-muted">合成数据 · 535 张凭证 · 已知注入异常</span>
              </button>
            </div>
          </Panel>
        </Reveal>
      ) : null}

      {isRunning && !report ? (
        <p className="flex items-center gap-2 text-body text-fg">
          <AlertTriangle className="h-4 w-4 text-risk-medium" />
          审计算子运行中，请勿切换案件，否则本轮流式结果会中断。
        </p>
      ) : null}

      {isClean && report ? (
        <p className="flex items-center gap-2 text-body text-fg">
          <Check className="h-4 w-4 text-risk-clear" />
          本案为合规对照组，未检出舞弊迹象，可用于说明误报率。
        </p>
      ) : null}
    </div>
  )
}
