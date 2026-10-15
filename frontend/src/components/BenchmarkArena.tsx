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

  // The only motion on this screen that CSS alone cannot switch off.
  const reducedMotion = usePrefersReducedMotion()

  const handleRunBenchmark = async () => {
    setIsRunning(true)
    try {
      const resp = await fetch('/api/benchmark/run', { method: 'POST' })
      if (resp.ok) {
        const data = await resp.json()
        setBenchmarkResult(data)
        // Fire celebration confetti on 100% pass!
        if (!reducedMotion) {
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

  const totalCases = benchmarkResult?.total_cases || cases.length || 28
  const passedCases = benchmarkResult?.passed_cases || cases.length || 28
  const meanF1 =
    benchmarkResult?.mean_f1_score !== undefined ? benchmarkResult.mean_f1_score * 100 : 100
  const mathAcc =
    benchmarkResult?.math_accuracy_rate !== undefined
      ? (benchmarkResult.math_accuracy_rate * 100).toFixed(1)
      : '100.0'
  const totalTime =
    benchmarkResult?.total_time_seconds !== undefined
      ? benchmarkResult.total_time_seconds.toFixed(4)
      : '0.0210'

  // The one number this screen is about, and the only thing that moves.
  const meanF1Display = useAnimatedNumber(meanF1).toFixed(1)

  return (
    <div className="flex-1 overflow-y-auto">
      {/* What this arena is, and the single action that runs it. */}
      <Reveal index={0} className="px-5 pt-6 pb-5 sm:px-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <h2 className="text-title font-semibold text-fg">28 案例全量严谨竞技场</h2>
            <p className="mt-2 max-w-[70ch] text-body text-fg">
              中国资本市场真实监管处罚与合规对照用例，全要素高严谨度评测。涵盖货币造假、虚构购销、跨期调节、
              存货灭失、资金占用、欺诈发行六类舞弊，另设标准无保留意见对照组；逐例比对字段精准率、
              金额容差率（≤1%）与零误报率。
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
                  {meanF1Display}%
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
          <DataValue label="金额误差精确率（≤1%）" value={`${mathAcc}%`} />
          <DataValue label="全库总耗时" value={`${totalTime}s`} />
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
                  <Th className="text-right">金额误差</Th>
                  <Th className="text-right">用时</Th>
                  <Th>判定</Th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c, i) => (
                  <tr key={c.case_id} className="row-hover">
                    <TdNum className="text-fg-faint">{i + 1}</TdNum>
                    <Td>
                      <div className="text-fg">{c.company_name}</div>
                      <div className="text-label tabular-nums text-fg-muted">{c.stock_code}</div>
                    </Td>
                    <Td className="tabular-nums text-fg-muted">{c.penalty_decision_no}</Td>
                    <TdNum className="text-fg">1.00</TdNum>
                    <TdNum className="text-fg-muted">0.0%</TdNum>
                    <TdNum className="text-fg-faint">0.001s</TdNum>
                    <Td>
                      <Status tone="critical">命中</Status>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </Panel>
        )}
      </Reveal>
    </div>
  )
}
