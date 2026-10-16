import React from 'react'
import { DataTable, Panel, Status, Td, TdNum, Th, cn } from '../ui/primitives'
import { count, moneyParts } from '../lib/format'

/**
 * 全量分析程序：分录测试 / 资金往返 / Benford。
 * All numbers here come from deterministic operators (no model involved), so
 * the panel is the "full population" counterpart to the sampled findings.
 */
export const AnalyticsPanel: React.FC<{ analytics?: Record<string, any> | null }> = ({ analytics }) => {
  if (!analytics || !analytics.journal_entry_testing) return null
  const je = analytics.journal_entry_testing ?? {}
  const rt = analytics.fund_round_trips ?? {}
  const bf = analytics.benford ?? {}
  const rules: Record<string, string> = je.rules ?? {}
  const hits: Record<string, number> = je.rule_hits ?? {}
  const maxHit = Math.max(1, ...Object.values(hits).map(Number))

  return (
    <Panel
      title="全量分析程序"
      note="不抽样：每一张凭证、每一笔流水都过一遍确定性规则，不经过大模型"
      meta={
        je.applicable ? (
          <span className="tabular-nums">
            凭证 {count(je.population)} 张 · 覆盖 100% · 风险标识 {count(je.flagged_count)} 张
          </span>
        ) : undefined
      }
    >
      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        {/* Rule hits */}
        <div>
          <div className="text-small font-medium text-fg">会计分录测试 · 规则命中</div>
          {je.applicable ? (
            <ul className="mt-3 space-y-1.5">
              {Object.entries(rules).map(([code, name]) => {
                const n = Number(hits[code] ?? 0)
                return (
                  <li key={code} className="grid grid-cols-[3rem_minmax(0,1fr)_3rem] items-center gap-3">
                    <span className="text-label tabular-nums text-fg-faint">{code}</span>
                    <div className="min-w-0">
                      <div className={cn('truncate text-small', n ? 'text-fg' : 'text-fg-faint')}>{name}</div>
                      <div className="mt-1 h-1 bg-field-raised2">
                        <div
                          className={cn('h-1', n ? 'bg-risk-high' : 'bg-transparent')}
                          style={{ width: `${(n / maxHit) * 100}%` }}
                        />
                      </div>
                    </div>
                    <span className={cn('text-right text-small tabular-nums', n ? 'text-fg' : 'text-fg-faint')}>
                      {n}
                    </span>
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="mt-3 text-small text-fg-muted">{je.reason}</p>
          )}
        </div>

        {/* Top flagged vouchers */}
        <div className="min-w-0">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-small font-medium text-fg">风险分最高的凭证</span>
            {je.high_risk_count ? (
              <span className="text-label tabular-nums text-risk-high">高风险（≥5 分）{je.high_risk_count} 张</span>
            ) : null}
          </div>
          {je.flagged?.length ? (
            <DataTable className="mt-3">
              <thead>
                <tr>
                  <Th>凭证号</Th>
                  <Th>日期</Th>
                  <Th className="text-right">金额</Th>
                  <Th className="text-right">风险分</Th>
                  <Th>命中规则</Th>
                </tr>
              </thead>
              <tbody>
                {je.flagged.slice(0, 6).map((f: any) => (
                  <tr key={f.voucher_id}>
                    <Td className="tabular-nums">{f.voucher_id}</Td>
                    <Td className="tabular-nums text-fg-muted">{f.date}</Td>
                    <TdNum>
                      {moneyParts(f.amount).value} {moneyParts(f.amount).unit}
                    </TdNum>
                    <TdNum className={f.score >= 5 ? 'text-risk-high' : ''}>{f.score}</TdNum>
                    <Td className="text-fg-muted">{(f.rules ?? []).join(' · ')}</Td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          ) : (
            <p className="mt-3 text-small text-fg-muted">没有凭证命中风险标识。</p>
          )}
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* Round trips */}
        <div>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-small font-medium text-fg">资金往返识别</span>
            {rt.applicable ? (
              <span className="text-label tabular-nums text-fg-faint">
                流水 {count(rt.population)} 笔 · 筛查 ≥10 万元 {count(rt.screened)} 笔
              </span>
            ) : null}
          </div>
          {rt.loop_count ? (
            <ul className="mt-3 space-y-2">
              {rt.loops.slice(0, 5).map((l: any) => (
                <li key={l.out_id} className="bg-field-raised2/50 px-3 py-2 text-small">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="tabular-nums text-fg">
                      {l.out_id} → {l.in_id}
                    </span>
                    <span className="tabular-nums text-risk-high">
                      {moneyParts(l.out_amount).value} {moneyParts(l.out_amount).unit}
                    </span>
                  </div>
                  <div className="mt-0.5 text-label text-fg-muted">
                    {l.out_party}：流出后 {l.days} 天流回 · {l.pattern}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-small text-fg-muted">
              {rt.applicable ? '未发现窗口期内金额相近的资金往返。' : '本案没有银行流水。'}
            </p>
          )}
        </div>

        {/* Benford */}
        <div>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-small font-medium text-fg">Benford 首位数字检验</span>
            {bf.applicable ? (
              <Status tone={bf.conforms ? 'clear' : 'high'}>
                {bf.verdict} · MAD {bf.mad}
              </Status>
            ) : null}
          </div>
          {bf.applicable ? (
            <div className="mt-3 flex h-24 items-end gap-1.5">
              {Object.keys(bf.expected ?? {}).map((d) => {
                const obs = Number(bf.observed?.[d] ?? 0)
                const exp = Number(bf.expected?.[d] ?? 0)
                const spike = (bf.spike_digits ?? []).includes(Number(d))
                return (
                  <div key={d} className="flex flex-1 flex-col items-center gap-1">
                    <div className="relative flex h-20 w-full items-end justify-center">
                      <div
                        className={cn('w-3/5', spike ? 'bg-risk-high' : 'bg-fg-muted/60')}
                        style={{ height: `${(obs / 0.32) * 100}%` }}
                        title={`实际 ${(obs * 100).toFixed(1)}%`}
                      />
                      <div
                        className="absolute left-0 right-0 border-t border-dashed border-seal-soft"
                        style={{ bottom: `${(exp / 0.32) * 100}%` }}
                        title={`理论 ${(exp * 100).toFixed(1)}%`}
                      />
                    </div>
                    <span className="text-label tabular-nums text-fg-faint">{d}</span>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="mt-3 text-small text-fg-muted">{bf.reason}</p>
          )}
          {bf.applicable ? (
            <p className="mt-2 text-label text-fg-faint">
              柱：实际占比 · 虚线：Benford 理论值 · 样本 {count(bf.sample_size)} 个金额
            </p>
          ) : null}
        </div>
      </div>
    </Panel>
  )
}
