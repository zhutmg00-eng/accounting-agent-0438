import React, { useState } from 'react'
import confetti from 'canvas-confetti'
import {
  Btn,
  DataTable,
  DataValue,
  EmptyState,
  Panel,
  Skeleton,
  StatRow,
  Status,
  Surface,
  Td,
  TdNum,
  Th
} from '../ui/primitives'
import { Reveal, useAnimatedNumber, usePrefersReducedMotion } from '../ui/motion'
import { BlindLayer } from './BlindBenchmark'

interface BenchmarkArenaProps {
  cases: any[]
}

/**
 * Beat 5 - 对战. Twenty-eight cases scored side by side.
 *
 * That is tabular data by nature, so it is a real table rather than a grid of
 * score cards. The screen is dark and continuous; the one lit surface carries
 * the single figure the whole arena exists to produce - the mean score.
 */
export const BenchmarkArena: React.FC<BenchmarkArenaProps> = ({ cases }) => {
  const [isRunning, setIsRunning] = useState(false)
  const [benchmarkResult, setBenchmarkResult] = useState<any | null>(null)
  const [layer, setLayer] = useState<'dev' | 'v3' | 'v2' | 'v1' | 'synthetic'>('dev')
  const [blindResult, setBlindResult] = useState<Record<string, any>>({})
  const [blindRunning, setBlindRunning] = useState(false)

  const runBlind = async (which: 'v3' | 'v2' | 'v1' | 'synthetic') => {
    setBlindRunning(true)
    try {
      const resp = await fetch(`/api/benchmark/blind?layer=${which}`, { method: 'POST' })
      if (resp.ok) {
        const data = await resp.json()
        setBlindResult((prev) => ({ ...prev, [which]: data }))
      }
    } catch (e) {
      console.error('Failed to run blind benchmark', e)
    } finally {
      setBlindRunning(false)
    }
  }
  const scoreByCaseId = new Map<string, any>(
    (benchmarkResult?.case_scores ?? []).map((sc: any) => [sc.case_id, sc])
  )

  // The only motion on this screen that CSS alone cannot switch off.
  const reducedMotion = usePrefersReducedMotion()

  const handleRunBenchmark = async () => {
    setIsRunning(true)
    try {
      const resp = await fetch('/api/benchmark/run', { method: 'POST' })
      if (resp.ok) {
        const data = await resp.json()
        setBenchmarkResult(data)
        // Celebrate only a genuinely clean sweep.
        if (!reducedMotion && data.passed_cases === data.total_cases) {
          confetti({
            particleCount: 80,
            spread: 70,
            origin: { y: 0.6 }
          })
        }
      }
    } catch (e) {
      console.error('Failed to run benchmark', e)
    } finally {
      setIsRunning(false)
    }
  }

  // Nothing is shown as a score until the benchmark has actually run.
  const hasRun = !!benchmarkResult
  const totalCases = benchmarkResult?.total_cases ?? cases.length
  const passedCases = hasRun ? benchmarkResult.passed_cases : '—'
  const meanF1 = hasRun ? benchmarkResult.mean_f1_score * 100 : 0
  const mathAcc = hasRun && benchmarkResult.mean_amount_accuracy !== undefined
    ? (benchmarkResult.mean_amount_accuracy * 100).toFixed(1)
    : '—'
  const totalTime = hasRun && benchmarkResult.mean_latency !== undefined
    ? (benchmarkResult.mean_latency * benchmarkResult.total_cases).toFixed(3)
    : '—'

  // The one number this screen is about, and the only thing that moves.
  const meanF1Display = useAnimatedNumber(meanF1).toFixed(1)

  return (
    <div className="flex-1 overflow-y-auto">
      {/* What this arena is, and the single action that runs it. */}
      <Reveal index={0} className="px-5 pt-6 pb-5 sm:px-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <h2 className="text-title font-semibold text-fg">三层评测：开发集 · 外部盲测 · 合成账套</h2>
            <p className="mt-2 max-w-[70ch] text-body text-fg">
              开发集是团队自建的 28 例（25 例处罚案例 + 3 例合规对照），用于回归；外部盲测由看不到代码的独立出题方
              依据处罚决定书编写，每批都在算法冻结后才首次运行，最新一批是对外引用的口径；合成账套用独立随机生成器检验规则的查全与查准。
            </p>
          </div>
          <Btn
            variant="primary"
            size="lg"
            disabled={isRunning}
            onClick={handleRunBenchmark}
            className="shrink-0"
          >
            {isRunning ? '正在逐例评测…' : '一键执行全库 28 案例评测'}
          </Btn>
        </div>
      </Reveal>

      <div className="flex flex-wrap gap-2 px-5 pb-4 sm:px-6" role="tablist" aria-label="评测层级">
        {([
          ['dev', '开发集 28 例'],
          ['v3', '外部盲测 v3（严格）'],
          ['v2', '盲测 v2（v2.3 严格）'],
          ['v1', '盲测 v1（已用于开发）'],
          ['synthetic', '合成随机账套'],
        ] as const).map(([k, label]) => (
          <button
            key={k}
            role="tab"
            aria-selected={layer === k}
            onClick={() => setLayer(k)}
            className={
              'px-3 py-1.5 text-small transition-colors ' +
              (layer === k ? 'bg-paper font-semibold text-ink' : 'text-fg-muted hover:text-fg')
            }
          >
            {label}
          </button>
        ))}
      </div>

      {layer !== 'dev' ? (
        <BlindLayer layer={layer} data={blindResult[layer]} running={blindRunning} onRun={() => runBlind(layer)} />
      ) : (
      <>
      {/* The lit artifact: the score the whole screen is about. */}
      <Reveal index={1} className="px-5 sm:px-6">
        <Surface paper className="px-6 py-6">
          <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-5">
            <div>
              <div className="text-label text-ink-muted">全库平均 F1 得分 · {totalCases} 例</div>
              {isRunning ? (
                <Skeleton className="mt-2 h-11 w-44" />
              ) : (
                <div className="mt-1 text-display font-semibold tabular-nums text-ink">
                  {hasRun ? `${meanF1Display}%` : '待运行'}
                </div>
              )}
            </div>
            <p className="max-w-[44ch] text-small text-ink-muted">
              判定口径：字段精准率与金额容差率（≤1%）同时满足记为命中；任一不满足即判未命中，并计入误报。
            </p>
          </div>
          <p className="mt-5 bg-paper-deep px-4 py-3 text-small text-ink-muted">
            用例来源为中国证监会公开行政处罚决定书，逐例复核智能体输出的舞弊类型、涉案金额与凭证指向。
          </p>
        </Surface>
      </Reveal>

      {/* Secondary readings: separated by tone and space, not by cards. */}
      <Reveal index={2} className="px-5 pt-5 sm:px-6">
        <StatRow className="sm:grid-cols-3 lg:grid-cols-3">
          <DataValue label="案例通过率" value={`${passedCases} / ${totalCases}`} />
          <DataValue label="金额误差≤1% 的比例" value={mathAcc === '—' ? '—' : `${mathAcc}%`} />
          <DataValue label="全库总耗时" value={totalTime === '—' ? '—' : `${totalTime}s`} />
        </StatRow>
      </Reveal>

      {/* Twenty-eight cases: a real table, with its rules. */}
      <Reveal index={3} className="px-5 py-5 sm:px-6">
        {cases.length === 0 ? (
          <Panel bare>
            <EmptyState
              title="尚未载入评测案例集"
              body="竞技场按左侧清单的类别取用例。先在案例清单中选择一个类别，再回到本页执行全量评测。"
            />
          </Panel>
        ) : (
          <Panel bare>
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 px-5 pt-5 pb-4">
              <h2 className="text-title font-semibold text-fg">全量案例单例表现</h2>
              <span className="text-small text-fg-muted">
                {cases.length} 例 · 逐例 F1 得分、金额误差与用时
              </span>
            </div>
            <DataTable>
              <thead>
                <tr>
                  <Th className="w-14 text-right">序</Th>
                  <Th>标的</Th>
                  <Th>处罚决定书</Th>
                  <Th className="text-right">F1 得分</Th>
                  <Th className="text-right">金额准确</Th>
                  <Th className="text-right">用时</Th>
                  <Th>判定</Th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c, i) => {
                  const sc = scoreByCaseId.get(c.case_id)
                  const isClean = String(c.case_id).startsWith('REAL_CLEAN') || c.is_clean
                  return (
                    <tr key={c.case_id} className="row-hover">
                      <TdNum className="text-fg-faint">{i + 1}</TdNum>
                      <Td>
                        <div className="text-fg">{c.company_name}</div>
                        <div className="text-label tabular-nums text-fg-muted">{c.stock_code}</div>
                      </Td>
                      <Td className="tabular-nums text-fg-muted">{c.penalty_decision_no || (isClean ? '合规对照' : '—')}</Td>
                      <TdNum className="text-fg">{sc ? sc.f1_score.toFixed(2) : '—'}</TdNum>
                      <TdNum className="text-fg-muted">{sc ? `${(sc.amount_accuracy_rate * 100).toFixed(0)}%` : '—'}</TdNum>
                      <TdNum className="text-fg-faint">{sc ? `${sc.latency_seconds.toFixed(3)}s` : '—'}</TdNum>
                      <Td>
                        {!sc ? (
                          <Status tone="neutral">待运行</Status>
                        ) : isClean ? (
                          sc.false_positive_count === 0 ? (
                            <Status tone="clear">零误报通过</Status>
                          ) : (
                            <Status tone="high">误报 {sc.false_positive_count}</Status>
                          )
                        ) : sc.passed ? (
                          <Status tone="clear">通过</Status>
                        ) : (
                          <Status tone="medium">
                            未通过{sc.recall > 0 ? ' · 已识别' : ''}
                          </Status>
                        )}
                      </Td>
                    </tr>
                  )
                })}
              </tbody>
            </DataTable>
          </Panel>
        )}
      </Reveal>
      </>
      )}
    </div>
  )
}
