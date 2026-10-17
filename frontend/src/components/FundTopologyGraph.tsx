import React, { useEffect, useState } from 'react'
import {
  DataTable,
  EmptyState,
  Panel,
  SkeletonRows,
  Status,
  Td,
  TdNum,
  Th,
  Verdict
} from '../ui/primitives'
import { Reveal } from '../ui/motion'

/* ===========================================================================
   Beat 2 · 穿透 — 资金拓扑与业财单据链.

   Everything drawn here comes from /api/topology/{case_id}: bank flows summed
   by counterparty, and the flows that deterministic operators flagged (fund
   round-trips, suspicious remarks, third-party receipts, restricted cash,
   post-period installation payments).  Nothing is templated per case and no
   ground-truth field is read.  A case without a fund loop shows the document
   chain view instead, so the picture always matches the case.
   =========================================================================== */

interface FundTopologyGraphProps {
  currentCase: any
}

const STROKE_QUIET = 'var(--fg-faint, #8c8c8c)'
const STROKE_RISK = 'var(--risk-critical, #d92b21)'

const money = (v: number) =>
  Math.abs(v) >= 1e8 ? `¥${(v / 1e8).toFixed(2)}亿` : Math.abs(v) >= 1e4 ? `¥${(v / 1e4).toFixed(1)}万` : `¥${v.toFixed(0)}`

export const FundTopologyGraph: React.FC<FundTopologyGraphProps> = ({ currentCase }) => {
  const [topo, setTopo] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const caseId = currentCase?.case_id

  useEffect(() => {
    if (!caseId) return
    let alive = true
    setLoading(true)
    setError(null)
    fetch(`/api/topology/${encodeURIComponent(caseId)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => alive && setTopo(d))
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [caseId])

  if (!currentCase) {
    return (
      <div className="flex-1 p-6">
        <EmptyState title="未选择案例" body="在左侧案例清单中选择一个案例后查看资金拓扑。" />
      </div>
    )
  }
  if (loading || !topo) {
    return (
      <div className="flex-1 p-6">
        {error ? <EmptyState title="拓扑加载失败" body={error} /> : <SkeletonRows rows={8} />}
      </div>
    )
  }

  const parties: any[] = topo.parties || []
  const flaggedTotal = parties.reduce((s, p) => s + (p.flagged_amount || 0), 0)
  const hasLoops = (topo.loops || []).length > 0
  const anyFlag = flaggedTotal > 0 || hasLoops
  const brokenChains = (topo.chains || []).filter((c: any) => !c.contract || !c.invoice || !c.bank_flow || c.doc_ref_exists === false)

  // Radial layout: the audited company in the centre, counterparties around it.
  const n = Math.max(parties.length, 1)
  const W = 960
  const H = n <= 2 ? 320 : 460
  const cx = W / 2
  const cy = H / 2
  const ry = n <= 2 ? 115 : 175
  const placed = parties.map((p, i) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n
    return { ...p, x: cx + Math.cos(a) * 360, y: cy + Math.sin(a) * ry }
  })

  const conclusion = hasLoops
    ? `检出 ${topo.loops.length} 组资金往返，合计 ${money(topo.loop_amount || 0)}`
    : flaggedTotal > 0
      ? `算子标记的异常资金流向 ${parties.filter((p) => p.flagged_amount > 0).length} 个对手方`
      : topo.has_bank_flows
        ? '未检出异常资金流向'
        : '本案例未提供银行流水，以下仅展示业财单据链'

  return (
    <div className="flex-1 overflow-y-auto">
      <Reveal index={0} className="px-5 pt-6 pb-5 sm:px-6">
        <Verdict
          conclusion={conclusion}
          figure={anyFlag ? money(hasLoops ? topo.loop_amount : flaggedTotal) : undefined}
          figureLabel={anyFlag ? (hasLoops ? '资金往返金额' : '被标记流水金额') : undefined}
          tone={anyFlag ? 'critical' : 'clear'}
          basis={topo.method}
        />
      </Reveal>

      {topo.has_bank_flows && parties.length > 0 ? (
        <Reveal index={1} className="px-5 sm:px-6">
          <Panel title="资金拓扑" note={`${topo.company} 与主要对手方的银行收付（按对手方汇总，最多 8 个）`}>
            <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="资金拓扑图">
              <defs>
                <marker id="arr-q" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                  <path d="M0,0 L10,5 L0,10 z" fill={STROKE_QUIET} />
                </marker>
                <marker id="arr-r" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                  <path d="M0,0 L10,5 L0,10 z" fill={STROKE_RISK} />
                </marker>
              </defs>
              {placed.map((p) => {
                const risky = p.flagged_amount > 0
                const stroke = risky ? STROKE_RISK : STROKE_QUIET
                const marker = risky ? 'url(#arr-r)' : 'url(#arr-q)'
                const dim = hover && hover !== p.name ? 0.25 : 1
                const dx = p.x - cx
                const dy = p.y - cy
                const len = Math.hypot(dx, dy) || 1
                const ux = dx / len
                const uy = dy / len
                const nx = -uy * 10
                const ny = ux * 10
                const s = { x: cx + ux * 70, y: cy + uy * 34 }
                const e = { x: p.x - ux * 80, y: p.y - uy * 26 }
                return (
                  <g key={p.name} opacity={dim}>
                    {p.outflow > 0 ? (
                      <line x1={s.x + nx} y1={s.y + ny} x2={e.x + nx} y2={e.y + ny} stroke={stroke}
                        strokeWidth={risky ? 2.4 : 1.4} markerEnd={marker} className={risky ? 'animate-fund-flow' : ''}
                        strokeDasharray={risky ? '6 4' : undefined} />
                    ) : null}
                    {p.inflow > 0 ? (
                      <line x1={e.x - nx} y1={e.y - ny} x2={s.x - nx} y2={s.y - ny} stroke={stroke}
                        strokeWidth={risky ? 2.4 : 1.4} markerEnd={marker} className={risky ? 'animate-fund-flow' : ''}
                        strokeDasharray={risky ? '6 4' : undefined} />
                    ) : null}
                    <text x={(s.x + e.x) / 2 + (Math.abs(ux) < 0.3 ? 16 : nx * 2.2)} y={(s.y + e.y) / 2 + (Math.abs(ux) < 0.3 ? 4 : ny * 2.2)} fontSize="12" textAnchor={Math.abs(ux) < 0.3 ? 'start' : 'middle'}
                      fill={risky ? STROKE_RISK : 'currentColor'} className="tabular-nums">
                      {p.outflow > 0 ? `出 ${money(p.outflow)}` : ''}{p.outflow > 0 && p.inflow > 0 ? ' · ' : ''}{p.inflow > 0 ? `入 ${money(p.inflow)}` : ''}
                    </text>
                  </g>
                )
              })}
              <g>
                <rect x={cx - 92} y={cy - 30} width={184} height={60} fill="var(--paper, #efefef)" stroke="currentColor" />
                <text x={cx} y={cy - 4} textAnchor="middle" fontSize="14" fontWeight={600} fill="var(--ink, #14151a)">
                  {topo.company.length > 12 ? topo.company.slice(0, 12) + '…' : topo.company}
                </text>
                <text x={cx} y={cy + 16} textAnchor="middle" fontSize="11" fill="var(--ink-muted, #5a5c63)">被审计单位</text>
              </g>
              {placed.map((p) => (
                <g key={`n-${p.name}`} onMouseEnter={() => setHover(p.name)} onMouseLeave={() => setHover(null)} style={{ cursor: 'default' }}>
                  <rect x={p.x - 82} y={p.y - 24} width={164} height={48} fill="transparent"
                    stroke={p.flagged_amount > 0 ? STROKE_RISK : STROKE_QUIET} strokeWidth={p.flagged_amount > 0 ? 2 : 1} />
                  <text x={p.x} y={p.y - 3} textAnchor="middle" fontSize="12" fill="currentColor">
                    {p.name.length > 12 ? p.name.slice(0, 12) + '…' : p.name}
                  </text>
                  <text x={p.x} y={p.y + 14} textAnchor="middle" fontSize="10.5" fill={p.flagged_amount > 0 ? STROKE_RISK : STROKE_QUIET}>
                    {p.flagged_amount > 0 ? `算子标记 ${money(p.flagged_amount)}` : `${p.count} 笔流水`}{p.related_party ? ' · 关联方' : ''}
                  </text>
                </g>
              ))}
            </svg>
          </Panel>
        </Reveal>
      ) : null}

      {hasLoops ? (
        <Reveal index={2} className="px-5 pt-5 sm:px-6">
          <Panel bare title="资金往返明细">
            <DataTable>
              <thead>
                <tr>
                  <Th>流出流水</Th>
                  <Th>对手方</Th>
                  <Th className="text-right">流出</Th>
                  <Th>流入流水</Th>
                  <Th className="text-right">流入</Th>
                  <Th className="text-right">间隔</Th>
                </tr>
              </thead>
              <tbody>
                {topo.loops.map((l: any) => (
                  <tr key={l.out_id + l.in_id}>
                    <Td className="tabular-nums">{l.out_id}</Td>
                    <Td>{l.out_party}</Td>
                    <TdNum>{money(l.out_amount)}</TdNum>
                    <Td className="tabular-nums">{l.in_id}</Td>
                    <TdNum>{money(l.in_amount)}</TdNum>
                    <TdNum>{l.days} 天</TdNum>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </Panel>
        </Reveal>
      ) : null}

      <Reveal index={3} className="px-5 py-5 sm:px-6">
        <Panel bare title="业财单据链" note="算子指向的凭证逐张核对：合同 → 发票 → 记账凭证 → 银行流水，断点标红">
          {(topo.chains || []).length === 0 ? (
            <EmptyState title="没有需要穿透的凭证" body="三单勾稽与专项程序均未指向异常凭证。" />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <Th>业务合同</Th>
                  <Th>增值税发票</Th>
                  <Th>记账凭证</Th>
                  <Th>银行流水</Th>
                  <Th>判定</Th>
                </tr>
              </thead>
              <tbody>
                {topo.chains.map((c: any) => {
                  const cell = (id: string | null) =>
                    id ? <span className="tabular-nums text-fg">{id}</span> : <span className="text-risk-critical">缺失</span>
                  const broken = !c.contract || !c.invoice || !c.bank_flow || c.doc_ref_exists === false
                  return (
                    <tr key={c.voucher_id}>
                      <Td>{cell(c.contract)}</Td>
                      <Td>{cell(c.invoice)}</Td>
                      <Td>
                        <div className="tabular-nums text-fg">{c.voucher_id}</div>
                        <div className="text-label text-fg-muted">{c.date} · {money(c.amount)}{c.party ? ` · ${c.party}` : ''}</div>
                        {c.doc_ref_exists === false ? (
                          <div className="text-label text-risk-critical">引用单据 {c.doc_ref} 不存在</div>
                        ) : null}
                      </Td>
                      <Td>{cell(c.bank_flow)}</Td>
                      <Td>{broken ? <Status tone="critical">链条断裂</Status> : <Status tone="medium">链条完整·金额/时点存疑</Status>}</Td>
                    </tr>
                  )
                })}
              </tbody>
            </DataTable>
          )}
          {brokenChains.length ? (
            <p className="px-5 pb-4 pt-3 text-small text-fg-muted">
              {brokenChains.length} 张凭证的单据链存在断点。链条完整不等于业务真实：截止、背靠背与第三方回款类问题，往往单据齐全而时点或资金来源异常。
            </p>
          ) : null}
        </Panel>
      </Reveal>
    </div>
  )
}
