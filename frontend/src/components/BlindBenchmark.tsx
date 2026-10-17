import React, { useState } from 'react'
import {
  Btn,
  DataTable,
  DataValue,
  EmptyState,
  Panel,
  SkeletonRows,
  StatRow,
  Status,
  Surface,
  Td,
  TdNum,
  Th,
  cn
} from '../ui/primitives'
import { Reveal } from '../ui/motion'

/* External blind benchmarks.  Every figure on this screen comes from a live
   offline run of /api/benchmark/blind, or from an online-mode snapshot that is
   labelled with the time it was produced.  Nothing is pre-filled. */

interface BlindLayerProps {
  layer: 'v3' | 'v2' | 'v1' | 'synthetic'
  data?: any
  running: boolean
  onRun: () => void
}

const pct = (n?: number) => (typeof n === 'number' ? `${(n * 100).toFixed(1)}%` : '—')

const Summary: React.FC<{ title: string; d: any; note?: string }> = ({ title, d, note }) => (
  <Surface paper className="px-6 py-5">
    <div className="flex flex-wrap items-baseline justify-between gap-3">
      <div className="text-label text-ink-muted">{title}</div>
      {note ? <div className="text-label text-ink-muted">{note}</div> : null}
    </div>
    <div className="mt-3 grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-4">
      <div>
        <div className="text-label text-ink-muted">舞弊公司被标出</div>
        <div className="text-title font-semibold tabular-nums text-ink">
          {d.fraud_cases_flagged} / {d.fraud_cases}
        </div>
      </div>
      <div>
        <div className="text-label text-ink-muted">真值事项命中（证据锚点）</div>
        <div className="text-title font-semibold tabular-nums text-ink">
          {d.truth_items_hit_by_agent} / {d.truth_items}
        </div>
      </div>
      <div>
        <div className="text-label text-ink-muted">金额误差 ≤1%</div>
        <div className="text-title font-semibold tabular-nums text-ink">
          {d.truth_items_amount_within_1pct} / {d.truth_items}
        </div>
      </div>
      <div>
        <div className="text-label text-ink-muted">合规对照误报</div>
        <div className="text-title font-semibold tabular-nums text-ink">
          {d.clean_cases_flagged} / {d.clean_cases}
        </div>
      </div>
    </div>
  </Surface>
)

export const BlindLayer: React.FC<BlindLayerProps> = ({ layer, data, running, onRun }) => {
  const [tableSource, setTableSource] = useState<'offline' | 'online'>('offline')

  const intro =
    layer === 'v3'
      ? '第三批盲测：10 家舞弊公司 + 6 家合规对照，出题方看不到代码、v1 与 v2。案例在算法冻结后运行，支持离线确定性实时重跑与 DeepSeek 在线快照逐案对比。'
      : layer === 'v2'
      ? '第二批盲测：在 v2.3 冻结后首次运行（结果为 v2.3 的严格盲测成绩）。v2.4/v2.5 强化职业判断与勾稽算子后，支持离线现场重跑与历史快照对照。'
      : layer === 'v1'
        ? '第一批盲测：10 家舞弊 + 4 家合规。它的结果曾用于发现并修复缺陷、并在设计专项算子时被参考，因此只作开发后验证，不再作为严格盲测引用。'
        : '独立随机生成器造账套：随机注入正例，并放入"像但不该报"的负例（调休上班日记账、有发票现销、60 天后才回款等）。满分只说明规则按设计工作。'

  const hasOnline = Boolean(data?.online_snapshot?.per_case?.length)
  const activeDataset =
    tableSource === 'online' && hasOnline ? data.online_snapshot : data?.offline

  return (
    <div>
      <Reveal index={1} className="px-5 sm:px-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <p className="max-w-[78ch] text-body text-fg">{intro}</p>
          <Btn variant="primary" disabled={running} onClick={onRun} className="shrink-0">
            {running ? '正在运行…' : '离线模式现场重跑'}
          </Btn>
        </div>
      </Reveal>

      <div className="px-5 py-5 sm:px-6">
        {running ? (
          <SkeletonRows rows={6} />
        ) : !data ? (
          <Panel bare>
            <EmptyState title="尚未运行" body="点击右上角按钮，在本机离线模式下重跑该层评测；在线模式结果为历史快照，会单独标注运行时间。" />
          </Panel>
        ) : layer === 'synthetic' ? (
          <SyntheticView d={data.synthetic} />
        ) : (
          <div className="space-y-5">
            <Summary title="离线确定性模式 · 现场运行 (v2.5)" d={data.offline} />
            {data.online_snapshot ? (
              <Summary
                title={`DeepSeek 在线模式 · 历史快照`}
                note={`运行于 ${data.online_snapshot.snapshot_time} · 算法 ${data.online_snapshot.algorithm_version ?? "v2.4"}`}
                d={data.online_snapshot}
              />
            ) : null}
            {data.beneish_reported ? (
              <StatRow className="sm:grid-cols-3 lg:grid-cols-3">
                <DataValue
                  label="Beneish · 年报原值 · 舞弊组检出"
                  value={`${data.beneish_reported.fraud_flagged} / ${data.beneish_reported.fraud_cases}`}
                />
                <DataValue
                  label="Beneish · 合规组误报"
                  value={`${data.beneish_reported.clean_false_positive} / ${data.beneish_reported.clean_cases}`}
                />
                <DataValue label="检出率" value={pct(data.beneish_reported.detection_rate)} />
              </StatRow>
            ) : null}
            {hasOnline ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-small text-fg-muted">
                  逐案明细视图切换：可对比实时离线规则推理与 DeepSeek 在线快照的逐案检出差异
                </span>
                <div className="inline-flex border border-white/10 bg-field-sunken p-0.5">
                  <button
                    type="button"
                    onClick={() => setTableSource('offline')}
                    className={cn(
                      'px-3 py-1.5 text-small transition-colors',
                      tableSource === 'offline' ? 'bg-field-raised2 font-medium text-fg' : 'text-fg-muted hover:text-fg'
                    )}
                  >
                    离线确定性模式（现场运行）
                  </button>
                  <button
                    type="button"
                    onClick={() => setTableSource('online')}
                    className={cn(
                      'px-3 py-1.5 text-small transition-colors',
                      tableSource === 'online' ? 'bg-field-raised2 font-medium text-fg' : 'text-fg-muted hover:text-fg'
                    )}
                  >
                    DeepSeek 在线模式（历史快照）
                  </button>
                </div>
              </div>
            ) : null}
            <Panel bare>
              <DataTable>
                <thead>
                  <tr>
                    <Th>标的</Th>
                    <Th>真值事项</Th>
                    <Th>{tableSource === 'online' && hasOnline ? '系统发现（DeepSeek 在线快照）' : '系统发现（离线现场运行）'}</Th>
                    <Th>判定</Th>
                  </tr>
                </thead>
                <tbody>
                  {(activeDataset?.per_case || []).map((r: any) => (
                    <tr key={r.case_id} className="row-hover align-top">
                      <Td>
                        <div className="text-fg">{r.company}</div>
                        <div className="text-label text-fg-muted">{r.group === 'clean' ? '合规对照' : r.case_id}</div>
                      </Td>
                      <Td className="max-w-[40ch] text-small text-fg-muted">
                        {r.truth.length === 0
                          ? '—'
                          : r.truth.map((t: any, i: number) => (
                              <div key={i}>
                                {t.agent_hit ? '✓ ' : '✗ '}
                                {t.finding_type}
                              </div>
                            ))}
                      </Td>
                      <Td className="max-w-[44ch] text-small text-fg-muted">
                        {r.findings.length === 0 ? '无' : r.findings.map((f: string, i: number) => <div key={i}>{f.replace('RiskLevel.', '')}</div>)}
                      </Td>
                      <Td>
                        {r.group === 'clean' ? (
                          r.case_flagged ? <Status tone="high">误报</Status> : <Status tone="clear">零误报</Status>
                        ) : r.case_flagged ? (
                          <Status tone="critical">已标出</Status>
                        ) : (
                          <Status tone="medium">漏检</Status>
                        )}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            </Panel>
          </div>
        )}
      </div>
    </div>
  )
}

const SyntheticView: React.FC<{ d: any }> = ({ d }) => (
  <div className="space-y-5">
    <StatRow className="sm:grid-cols-3 lg:grid-cols-3">
      <DataValue label="账套数（随机种子）" value={`${d.ledgers}`} />
      <DataValue label="每套基础凭证" value={`${d.ledger_size_base_vouchers}`} />
      <DataValue label="Benford 区分编造账套准确率" value={pct(d.benford?.accuracy)} />
    </StatRow>
    <Panel bare>
      <DataTable>
        <thead>
          <tr>
            <Th>异常类型</Th>
            <Th>规则</Th>
            <Th className="text-right">查全率</Th>
            <Th className="text-right">查准率</Th>
            <Th className="text-right">负例误报率</Th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(d.rules || {}).map(([k, r]: [string, any]) => (
            <tr key={k} className="row-hover">
              <Td className="text-fg">{LABELS[k] || k}</Td>
              <Td className="text-fg-muted">{r.rule}</Td>
              <TdNum>{pct(r.recall)}</TdNum>
              <TdNum>{pct(r.precision)}</TdNum>
              <TdNum className="text-fg-muted">{r.decoy_false_positive_rate == null ? '—' : pct(r.decoy_false_positive_rate)}</TdNum>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </Panel>
    <p className="text-small text-fg-muted">{d.protocol}</p>
  </div>
)

const LABELS: Record<string, string> = {
  offday_posting: '非工作日记账（含调休）',
  segregation_of_duties: '职责分离缺失',
  no_attachment: '无附件凭证',
  revenue_cash_no_doc: '收入直连货币资金且无单据',
  phantom_document: '引用不存在的单据',
  round_trip: '资金往返'
}
