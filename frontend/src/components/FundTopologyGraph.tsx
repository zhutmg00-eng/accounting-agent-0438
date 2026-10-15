import React, { useState } from 'react'
import {
  Building2,
  Users,
  Landmark,
  FileText,
  RefreshCw,
  Info,
  ShieldCheck,
  Sparkles
} from 'lucide-react'
import {
  Chip,
  DataTable,
  Panel,
  Status,
  Surface,
  Td,
  TdNum,
  Th,
  Verdict,
  cn
} from '../ui/primitives'
import { Reveal, useAnimatedNumber } from '../ui/motion'

/* ===========================================================================
   Beat 2 · 穿透 — 资金体外拓扑.

   The screen tells one story: how money leaves the listed company and runs a
   loop outside it. The graph is the lit evidence; everything drawn on it is a
   quiet greyscale step except the paths judged to be out-of-book, which carry
   the risk hue and are therefore the only thing that stands out.

   Presentation layer only: node coordinates, curve control points, link
   topology, labels and amounts are unchanged from the audited figure. The one
   move kept here is `animate-fund-flow`, because the dash encodes the
   DIRECTION of money movement, which is information and not decoration.
   =========================================================================== */

interface FundTopologyGraphProps {
  currentCase: any
}

interface NodeData {
  id: string
  name: string
  subText: string
  role: string
  x: number
  y: number
  stroke: string
  icon: string
  amount?: string
  warning?: string
}

interface LinkData {
  source: string
  target: string
  x1: number
  y1: number
  x2: number
  y2: number
  cx: number
  cy: number
  label: string
  amount?: string
  stroke: string
}

/* ---------------------------------------------------------------------------
   Canvas palette. The field is the room; the graph is the thing lit inside it.
   Quiet paths are the greyscale step, out-of-book paths carry risk-critical.
   --------------------------------------------------------------------------- */
const STROKE_QUIET = 'var(--fg-faint)'
const STROKE_STRONG = 'var(--fg-muted)'
const STROKE_CRITICAL = 'var(--risk-critical)'
const STROKE_CLEAR = 'var(--risk-clear)'

const CANVAS_BG = 'var(--field-sunken)'
const CANVAS_LABEL_BG = 'var(--field-raised-2)'
const NODE_BODY_BG = 'var(--field-raised)'

const NODE_ICONS: Record<string, React.ElementType> = {
  company: Building2,
  bank: Landmark,
  pool: Users,
  channel: FileText,
  recycle: RefreshCw
}

export const FundTopologyGraph: React.FC<FundTopologyGraphProps> = ({ currentCase }) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)

  const companyName = currentCase?.company_name || '上市公司主体'
  const category = currentCase?.case_category || ''
  const isClean = Boolean(
    currentCase?.is_clean ||
    category.includes('对照') ||
    category.includes('合规') ||
    (currentCase?.ground_truth_findings && currentCase.ground_truth_findings.length === 0)
  )

  const bankCounterparty = currentCase?.bank_flows?.[0]?.counterparty_name ||
    (category.includes('存单') || category.includes('货币') ? '涉案银行联动专户/存单池' : '涉案指定走账账户')
  const contractCounterparty = currentCase?.contracts?.[0]?.customer_or_vendor ||
    (category.includes('购销') ? '上游指定过桥壳公司' : '关联方中介公司')

  const rawFraudAmt = currentCase?.ground_truth_findings?.[0]?.expected_amount ??
    (currentCase?.bank_flows?.[0]?.amount ? Math.abs(currentCase.bank_flows[0].amount) : 0)
  const fraudAmount = rawFraudAmt > 0 ? `¥${(rawFraudAmt / 100000000).toFixed(1)}亿` : '涉案资金池'

  const rawContractAmt = currentCase?.contracts?.[0]?.total_amount ?? rawFraudAmt
  const contractAmount = rawContractAmt > 0 ? `¥${(rawContractAmt / 100000000).toFixed(1)}亿` : fraudAmount

  const node1Name = companyName
  const node2Name = bankCounterparty === node1Name ? `${bankCounterparty}(专户池)` : bankCounterparty
  const node3Name = contractCounterparty === node1Name || contractCounterparty === node2Name ? `${contractCounterparty}(结算通道)` : contractCounterparty

  /* The only figure this screen counts up to: the money judged to sit outside
     the books. The graph itself shows the un-animated amount per node. */
  const animatedFraudAmt = useAnimatedNumber(rawFraudAmt > 0 ? rawFraudAmt / 100000000 : 0)
  const verdictFigure = rawFraudAmt > 0 ? `¥${animatedFraudAmt.toFixed(1)}亿` : fraudAmount

  // Dynamic Nodes — same ids, same coordinates, same copy.
  const nodes: NodeData[] = isClean
    ? [
        {
          id: 'node-clean-1',
          name: companyName,
          subText: '核心受审主体',
          role: '实体生产经营与财务归集中心',
          x: 480,
          y: 90,
          stroke: STROKE_STRONG,
          icon: 'company'
        },
        {
          id: 'node-clean-2',
          name: '战略核心客户/主机厂',
          subText: '真实业务回款',
          role: '终端销售与真实商业现金流输入',
          x: 770,
          y: 250,
          stroke: STROKE_QUIET,
          icon: 'channel'
        },
        {
          id: 'node-clean-3',
          name: '主要合格供应商',
          subText: '物料真实交割',
          role: '原辅材料采购与增值税真实抵扣',
          x: 480,
          y: 400,
          stroke: STROKE_QUIET,
          icon: 'channel'
        },
        {
          id: 'node-clean-4',
          name: '基本存款账户(银企直连)',
          subText: '资金直连存管',
          role: '受央行与商业银行系统实时监管',
          x: 190,
          y: 250,
          stroke: STROKE_QUIET,
          icon: 'bank'
        }
      ]
    : [
        {
          id: 'node-fraud-1',
          name: node1Name,
          subText: '上市公司主体',
          role: '发端实体 / 资金划出与虚构资产方',
          x: 480,
          y: 75,
          stroke: STROKE_CRITICAL,
          icon: 'company',
          amount: fraudAmount,
          warning: '账面存巨额货币资金，实则已遭体外抽逃划转'
        },
        {
          id: 'node-fraud-2',
          name: node2Name,
          subText: '涉案联动账户/存单池',
          role: '虚假银行凭证开具与资金中转',
          x: 790,
          y: 190,
          stroke: STROKE_CRITICAL,
          icon: 'bank',
          amount: fraudAmount,
          warning: '配合伪造银行对账单，出具无真实资金定存证明'
        },
        {
          id: 'node-fraud-3',
          name: '大股东及实控人走账过桥池',
          subText: '体外资金隐匿池',
          role: '非经营性占用归集与拆借过桥',
          x: 670,
          y: 405,
          stroke: STROKE_CRITICAL,
          icon: 'pool',
          amount: fraudAmount,
          warning: '资金沉淀用于还贷、投资或流向关联私户'
        },
        {
          id: 'node-fraud-4',
          name: node3Name,
          subText: '关联过桥/购销通道',
          role: '虚构购销合同与假发票过桥主体',
          x: 290,
          y: 405,
          stroke: STROKE_CRITICAL,
          icon: 'channel',
          amount: contractAmount,
          warning: '无真实货物移转，通过签订阴阳合同过账'
        },
        {
          id: 'node-fraud-5',
          name: '无商业实质空转回流节点',
          subText: '洗白回款中介',
          role: '以客户名义将资金回流上市公司',
          x: 170,
          y: 190,
          stroke: STROKE_CRITICAL,
          icon: 'recycle',
          amount: fraudAmount,
          warning: '伪装成正常销售回款，闭环掩盖虚增营收'
        }
      ]

  // Dynamic Directed Links — same endpoints and same control points.
  const links: LinkData[] = isClean
    ? [
        {
          source: 'node-clean-2',
          target: 'node-clean-1',
          x1: 770,
          y1: 250,
          x2: 480,
          y2: 90,
          cx: 660,
          cy: 140,
          label: '真实销售现汇结算',
          stroke: STROKE_QUIET
        },
        {
          source: 'node-clean-1',
          target: 'node-clean-3',
          x1: 480,
          y1: 90,
          x2: 480,
          y2: 400,
          cx: 560,
          cy: 245,
          label: '采购货款公对公划转',
          stroke: STROKE_QUIET
        },
        {
          source: 'node-clean-1',
          target: 'node-clean-4',
          x1: 480,
          y1: 90,
          x2: 190,
          y2: 250,
          cx: 300,
          cy: 140,
          label: '银企直连实时对账',
          stroke: STROKE_QUIET
        }
      ]
    : [
        {
          source: 'node-fraud-1',
          target: 'node-fraud-2',
          x1: 480,
          y1: 75,
          x2: 790,
          y2: 190,
          cx: 670,
          cy: 100,
          label: `异常划出 ${fraudAmount}`,
          stroke: STROKE_CRITICAL
        },
        {
          source: 'node-fraud-2',
          target: 'node-fraud-3',
          x1: 790,
          y1: 190,
          x2: 670,
          y2: 405,
          cx: 770,
          cy: 310,
          label: '资金归集/隐匿占用',
          stroke: STROKE_CRITICAL
        },
        {
          source: 'node-fraud-3',
          target: 'node-fraud-4',
          x1: 670,
          y1: 405,
          x2: 290,
          y2: 405,
          cx: 480,
          cy: 440,
          label: `注资过桥 ${contractAmount}`,
          stroke: STROKE_QUIET
        },
        {
          source: 'node-fraud-4',
          target: 'node-fraud-5',
          x1: 290,
          y1: 405,
          x2: 170,
          y2: 190,
          cx: 190,
          cy: 310,
          label: '无商业实质购销冲账',
          stroke: STROKE_QUIET
        },
        {
          source: 'node-fraud-5',
          target: 'node-fraud-1',
          x1: 170,
          y1: 190,
          x2: 480,
          y2: 75,
          cx: 290,
          cy: 100,
          label: '销售回款闭环自循环',
          stroke: STROKE_CRITICAL
        }
      ]

  const activeNode = nodes.find((n) => n.id === (selectedNodeId || hoveredNodeId))
  const isNodeCritical = (node: NodeData) => node.stroke === STROKE_CRITICAL

  return (
    <div
      className={cn(
        'flex-1 min-w-0 w-full overflow-y-auto bg-field',
        'px-5 pt-5 pb-8 space-y-5 sm:px-8 sm:pt-8'
      )}
    >
      <Panel
        bare
        title={companyName}
        note="资金体外循环与关联方穿透拓扑：从受审主体出发，沿银行流水、关联方披露与发票价税合计逐条追下去。"
        meta={
          isClean ? (
            <Status tone="clear">合规直连网络 · 零体外循环</Status>
          ) : (
            <Status tone="critical">已捕获体外资金空转自循环回路</Status>
          )
        }
      >
        <Reveal index={0} className="px-5 pb-5">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 bg-field-raised2 px-5 py-4">
            <div className="flex items-center gap-2 text-body text-fg">
              <span
                aria-hidden
                className="inline-block h-[3px] w-8"
                style={{ backgroundColor: STROKE_QUIET }}
              />
              <span>正常结算路径</span>
            </div>
            <div className="flex items-center gap-2 text-body text-fg">
              <span
                aria-hidden
                className="inline-block h-[3px] w-8"
                style={{ backgroundColor: STROKE_CRITICAL }}
              />
              <span>{isClean ? '—' : '判定为体外 / 异常的路径'}</span>
            </div>
            <div className="flex items-center gap-2 text-body text-fg">
              <span
                aria-hidden
                className="inline-block h-0 w-8 border-t-2 border-dashed"
                style={{ borderColor: STROKE_STRONG }}
              />
              <span>虚线方向即资金流向</span>
            </div>
          </div>
        </Reveal>

        {/* The lit evidence: the canvas itself, drawn on the sunken field. */}
        <Reveal index={1} className="px-5 pb-5">
          <div className="w-full overflow-hidden bg-field-sunken p-2 sm:p-4">
            <svg
              viewBox="0 0 960 480"
              role="img"
              aria-label={`${companyName} 资金往来拓扑：正常结算路径与判定为体外的资金路径`}
              className="w-full h-auto min-h-[460px] select-none"
            >
              <defs>
                {/* One arrowhead. It takes the colour of the path it closes. */}
                <marker
                  id="fund-arrow"
                  viewBox="0 0 10 10"
                  refX="28"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                  markerUnits="strokeWidth"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="context-stroke" />
                </marker>
              </defs>

              {/* 1. Curved Flow Links */}
              {links.map((link, idx) => {
                const pathD = `M ${link.x1} ${link.y1} Q ${link.cx} ${link.cy} ${link.x2} ${link.y2}`
                const isCritical = link.stroke === STROKE_CRITICAL
                return (
                  <g key={idx}>
                    {/* Resting stroke: one quiet weight step, no bloom */}
                    <path
                      d={pathD}
                      fill="none"
                      stroke={link.stroke}
                      strokeWidth={isCritical ? 3 : 2}
                      strokeOpacity={isCritical ? 0.28 : 0.16}
                    />
                    {/* Directed, animated dashed flow. The dash IS the direction
                        of the money and is the only motion on this screen. */}
                    <path
                      d={pathD}
                      fill="none"
                      stroke={link.stroke}
                      strokeWidth={isCritical ? 3 : 1.8}
                      strokeLinecap="square"
                      strokeDasharray="8 8"
                      className="animate-fund-flow"
                      markerEnd="url(#fund-arrow)"
                    />
                    {/* Edge Label */}
                    <g transform={`translate(${link.cx}, ${link.cy})`}>
                      <rect
                        x="-92"
                        y="-15"
                        width="184"
                        height="30"
                        rx="0"
                        fill={CANVAS_LABEL_BG}
                      />
                      <text
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fill={isCritical ? STROKE_CRITICAL : STROKE_QUIET}
                        fontSize="14"
                        fontWeight="500"
                      >
                        {link.label}
                      </text>
                    </g>
                  </g>
                )
              })}

              {/* 2. Interactive Nodes */}
              {nodes.map((node) => {
                const isSelected = selectedNodeId === node.id || hoveredNodeId === node.id
                const Icon = NODE_ICONS[node.icon] ?? Building2
                const critical = isNodeCritical(node)
                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y})`}
                    className="cursor-pointer transition-opacity duration-200 ease-out hover:opacity-90"
                    onClick={() => setSelectedNodeId(node.id)}
                    onMouseEnter={() => setHoveredNodeId(node.id)}
                    onMouseLeave={() => setHoveredNodeId(null)}
                  >
                    {/* Selection halo: a tone step, never a glow */}
                    <circle
                      r={isSelected ? 42 : 36}
                      fill={critical ? STROKE_CRITICAL : STROKE_STRONG}
                      opacity={isSelected ? 0.16 : 0.06}
                    />
                    <circle
                      r={isSelected ? 36 : 30}
                      fill={NODE_BODY_BG}
                      stroke={node.stroke}
                      strokeWidth={isSelected ? 3 : 2}
                    />

                    {/* Role mark inside the node */}
                    <Icon
                      x={-11}
                      y={-11}
                      width={22}
                      height={22}
                      strokeWidth={1.75}
                      color={critical ? STROKE_CRITICAL : STROKE_STRONG}
                    />

                    {/* Name plate below the node */}
                    <g transform="translate(0, 44)">
                      <rect
                        x="-92"
                        y="-13"
                        width="184"
                        height="26"
                        rx="0"
                        fill={CANVAS_LABEL_BG}
                      />
                      <text
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fill={critical ? STROKE_CRITICAL : STROKE_STRONG}
                        fontSize="14"
                        fontWeight="500"
                      >
                        {node.name.length > 12 ? `${node.name.substring(0, 11)}…` : node.name}
                      </text>
                    </g>

                    {/* Role sub-label below */}
                    <text
                      x="0"
                      y="68"
                      textAnchor="middle"
                      fill={STROKE_QUIET}
                      fontSize="13"
                    >
                      {node.subText}
                    </text>
                  </g>
                )
              })}
            </svg>
          </div>
        </Reveal>

        {/* Inspected counterparty. Real data, so it keeps its own surface. */}
        {activeNode ? (
          <Reveal index={2} className="px-5 pb-5">
            <Surface
              level="raised2"
              className="flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-start lg:justify-between"
            >
              <div className="flex min-w-0 items-start gap-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center bg-field-raised3">
                  {(() => {
                    const Icon = NODE_ICONS[activeNode.icon] ?? Building2
                    return (
                      <Icon
                        size={20}
                        strokeWidth={1.75}
                        className={isNodeCritical(activeNode) ? 'text-risk-critical' : 'text-fg-muted'}
                      />
                    )
                  })()}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-body font-semibold text-fg">{activeNode.name}</span>
                    <Chip tone="neutral">{activeNode.subText}</Chip>
                    {activeNode.amount ? (
                      <Chip tone="critical">涉案规模 {activeNode.amount}</Chip>
                    ) : (
                      <Chip tone="clear">未标注涉案金额</Chip>
                    )}
                  </div>
                  <p className="mt-2 flex items-start gap-2 text-body text-fg">
                    <Info size={16} strokeWidth={1.75} className="mt-0.5 shrink-0 text-fg-faint" />
                    <span>{activeNode.role}</span>
                  </p>
                </div>
              </div>

              {activeNode.warning ? (
                <div className="max-w-[52ch] bg-field-raised3 px-4 py-3">
                  <div className="text-label text-risk-critical">疑点定性</div>
                  <p className="mt-1 text-body text-fg">{activeNode.warning}</p>
                </div>
              ) : (
                <div className="max-w-[52ch] bg-field-raised3 px-4 py-3">
                  <div className="text-label text-risk-clear">疑点定性</div>
                  <p className="mt-1 text-body text-fg">该主体处于真实货物与资金对流路径，未发现体外占用特征。</p>
                </div>
              )}
            </Surface>
          </Reveal>
        ) : null}

        {/* Full-chain traceability: a real table, so it keeps its rules. */}
        <Reveal index={3} className="px-5 pb-5">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
            <h3 className="text-title font-semibold text-fg">全链路资金穿透明细</h3>
            <span className={cn('text-small', isClean ? 'text-risk-clear' : 'text-risk-critical')}>
              {isClean ? '货物流与资金流一致' : '检出无商业实质的资金自循环'}
            </span>
          </div>

          <DataTable>
            <thead>
              <tr>
                <Th className="w-[72px]">步骤</Th>
                <Th>主体</Th>
                <Th>性质</Th>
                <Th className="w-[160px] text-right">金额</Th>
              </tr>
            </thead>
            <tbody>
              {isClean ? (
                <>
                  <tr>
                    <Td className="text-fg-faint">1</Td>
                    <Td>{companyName}</Td>
                    <Td className="text-fg-muted">生产制造与经营核心</Td>
                    <TdNum className="text-fg-faint">—</TdNum>
                  </tr>
                  <tr>
                    <Td className="text-fg-faint">2</Td>
                    <Td>战略主机厂/客户</Td>
                    <Td className="text-fg-muted">真实销售与现汇回款</Td>
                    <TdNum className="text-fg-faint">—</TdNum>
                  </tr>
                  <tr>
                    <Td className="text-fg-faint">3</Td>
                    <Td>主要物料供应商</Td>
                    <Td className="text-fg-muted">真实采购货物交割</Td>
                    <TdNum className="text-fg-faint">—</TdNum>
                  </tr>
                  <tr>
                    <Td className="text-fg-faint">4</Td>
                    <Td>开户银行监管户</Td>
                    <Td className="text-fg-muted">全额资金直连存管</Td>
                    <TdNum className="text-fg-faint">—</TdNum>
                  </tr>
                  <tr>
                    <Td className="text-fg-faint">5</Td>
                    <Td>审计结论</Td>
                    <Td className="text-risk-clear">勾稽完全一致，无体外自循环</Td>
                    <TdNum className="text-fg-faint">—</TdNum>
                  </tr>
                </>
              ) : (
                <>
                  <tr>
                    <Td className="text-fg-faint">1</Td>
                    <Td>{node1Name}</Td>
                    <Td className="text-fg-muted">资金划出，账面资产被体外抽逃</Td>
                    <TdNum className="text-risk-critical">{fraudAmount}</TdNum>
                  </tr>
                  <tr>
                    <Td className="text-fg-faint">2</Td>
                    <Td>{node2Name}</Td>
                    <Td className="text-fg-muted">伪造存单与联动池，资金中转</Td>
                    <TdNum className="text-risk-critical">{fraudAmount}</TdNum>
                  </tr>
                  <tr>
                    <Td className="text-fg-faint">3</Td>
                    <Td>实控人资金池</Td>
                    <Td className="text-fg-muted">隐瞒关联方非经营性占用</Td>
                    <TdNum className="text-risk-critical">{fraudAmount}</TdNum>
                  </tr>
                  <tr>
                    <Td className="text-fg-faint">4</Td>
                    <Td>{node3Name}</Td>
                    <Td className="text-fg-muted">无商业实质冲账，阴阳合同过桥</Td>
                    <TdNum className="text-fg-muted">{contractAmount}</TdNum>
                  </tr>
                  <tr>
                    <Td className="text-fg-faint">5</Td>
                    <Td>回流上市公司</Td>
                    <Td className="text-risk-critical">完成造假自循环，虚构收入与资产</Td>
                    <TdNum className="text-risk-critical">{fraudAmount}</TdNum>
                  </tr>
                </>
              )}
            </tbody>
          </DataTable>
        </Reveal>

        {/* The one lit surface on the screen: the conclusion. */}
        <Reveal index={4} className="px-5 pb-5">
          <Verdict
            conclusion={isClean ? '未发现体外循环' : '存在体外资金循环'}
            figureLabel={isClean ? '涉案金额' : '体外循环资金规模'}
            figure={isClean ? '—' : verdictFigure}
            tone={isClean ? 'clear' : 'critical'}
            basis={
              isClean
                ? '判定依据：资金进出均具真实货物购销背景，银企直连流水与发票价税合计逐笔勾稽一致。'
                : '判定依据：银行流水附言、关联方披露与发票价税合计三方勾稽，检出“预付采购—资金池归集—体外过桥—虚假销售回款”四步闭环。'
            }
          />
        </Reveal>

        {/* Why the machine reads the loop this way. */}
        <Reveal index={5} className="px-5 pb-5">
          <div className="bg-field-raised2 px-5 py-4">
            <div className="flex items-center gap-2 text-label text-fg-muted">
              <Sparkles size={16} strokeWidth={1.75} className="text-seal" />
              <span>穿透提示</span>
            </div>
            <p className="mt-2 max-w-[80ch] text-body text-fg">
              {isClean
                ? '本拓扑图反映受审企业与主机厂客户、合格供应商及开户银行之间的真实交易结算路径。资金进出均具有真实货物购销背景与银企直连流水印证，无异常关联方闭环与体外过桥回流特征。'
                : '本拓扑图由 DeepSeek-AuditMind 智能分析引擎结合银行流水附言、关联方披露及发票价税合计自动推演构建。通过对“预付采购-资金池归集-体外过桥-虚假销售回款”四步闭环特征识别，精准锁定无实质商业背景的资金空转回路。'}
            </p>
          </div>
        </Reveal>

        <Reveal index={6} className="px-5 pb-5">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-small text-fg-faint">
            <span className="flex items-center gap-2">
              <ShieldCheck size={16} strokeWidth={1.75} />
              <span>数据源：银行流水 / 关联方披露 / 发票价税合计</span>
            </span>
            <span>
              拓扑节点 {nodes.length} 个，资金路径 {links.length} 条
            </span>
          </div>
        </Reveal>
      </Panel>
    </div>
  )
}
