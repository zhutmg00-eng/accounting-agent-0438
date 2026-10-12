import React, { useState } from 'react'
import {
  Network,
  AlertCircle,
  ShieldCheck,
  Activity,
  Layers,
  ArrowRight,
  Sparkles,
  Building2,
  Landmark,
  Share2,
  RefreshCw,
  Info
} from 'lucide-react'

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
  color: string
  glowColor: string
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
  color: string
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

  // Dynamic Nodes
  const nodes: NodeData[] = isClean
    ? [
        {
          id: 'node-clean-1',
          name: companyName,
          subText: '核心受审主体',
          role: '实体生产经营与财务归集中心',
          x: 480,
          y: 90,
          color: '#00F2FE',
          glowColor: 'rgba(0, 242, 254, 0.5)',
          icon: '🏢'
        },
        {
          id: 'node-clean-2',
          name: '战略核心客户/主机厂',
          subText: '真实业务回款',
          role: '终端销售与真实商业现金流输入',
          x: 770,
          y: 250,
          color: '#10B981',
          glowColor: 'rgba(16, 185, 129, 0.5)',
          icon: '🤝'
        },
        {
          id: 'node-clean-3',
          name: '主要合格供应商',
          subText: '物料真实交割',
          role: '原辅材料采购与增值税真实抵扣',
          x: 480,
          y: 400,
          color: '#38BDF8',
          glowColor: 'rgba(56, 189, 248, 0.5)',
          icon: '📦'
        },
        {
          id: 'node-clean-4',
          name: '基本存款账户(银企直连)',
          subText: '资金直连存管',
          role: '受央行与商业银行系统实时监管',
          x: 190,
          y: 250,
          color: '#A855F7',
          glowColor: 'rgba(168, 85, 247, 0.5)',
          icon: '🏦'
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
          color: '#00F2FE',
          glowColor: 'rgba(0, 242, 254, 0.6)',
          icon: '🏢',
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
          color: '#EF4444',
          glowColor: 'rgba(239, 68, 68, 0.6)',
          icon: '🏦',
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
          color: '#A855F7',
          glowColor: 'rgba(168, 85, 247, 0.6)',
          icon: '💰',
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
          color: '#F59E0B',
          glowColor: 'rgba(245, 158, 11, 0.6)',
          icon: '📑',
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
          color: '#38BDF8',
          glowColor: 'rgba(56, 189, 248, 0.6)',
          icon: '🔄',
          amount: fraudAmount,
          warning: '伪装成正常销售回款，闭环掩盖虚增营收'
        }
      ]

  // Dynamic Directed Links
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
          color: '#10B981'
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
          color: '#38BDF8'
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
          color: '#A855F7'
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
          color: '#EF4444'
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
          color: '#A855F7'
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
          color: '#F59E0B'
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
          color: '#38BDF8'
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
          color: '#00F2FE'
        }
      ]

  const activeNode = nodes.find((n) => n.id === (selectedNodeId || hoveredNodeId))

  return (
    <div className="flex-1 min-w-0 w-full overflow-y-auto p-6 space-y-6">
      <div className="glass-panel rounded-2xl p-6 border border-white/10 relative overflow-hidden">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 mb-1">
              <Network className="w-4 h-4" />
              <span>资金体外循环与关联方穿透拓扑 (Interactive Cyber Topology Matrix)</span>
            </div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <span>{companyName}</span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/10 text-slate-300 font-normal">
                {isClean ? '正常商业直连结算网络' : '体外涉案资金池闭环网络'}
              </span>
            </h2>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-xs text-slate-400 font-mono flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${isClean ? 'bg-emerald-400' : 'bg-rose-500 animate-ping'}`} />
              <span className={isClean ? 'text-emerald-300' : 'text-rose-300 font-bold'}>
                {isClean ? '合规直连网络·零体外循环' : '已捕获体外资金空转自循环回路'}
              </span>
            </div>
          </div>
        </div>

        {/* SVG Interactive Topology Canvas */}
        <div className="w-full mt-4 rounded-2xl bg-gradient-to-b from-[#060912] to-[#0A0F1D] border border-white/5 relative overflow-hidden shadow-inner p-2">
          {/* Background Ambient Cyber Grid */}
          <div className="absolute inset-0 bg-grid-pattern opacity-40 pointer-events-none" />

          {/* SVG Diagram */}
          <svg
            viewBox="0 0 960 480"
            className="w-full h-auto min-h-[460px] relative z-10 select-none"
          >
            <defs>
              {/* Arrow Markers */}
              <marker id="arrow-cyan" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#00F2FE" />
              </marker>
              <marker id="arrow-rose" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#EF4444" />
              </marker>
              <marker id="arrow-purple" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#A855F7" />
              </marker>
              <marker id="arrow-amber" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#F59E0B" />
              </marker>
              <marker id="arrow-sky" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#38BDF8" />
              </marker>
              <marker id="arrow-emerald" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#10B981" />
              </marker>

              {/* Node Glow Filters */}
              <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="0" stdDeviation="8" floodColor="#00F2FE" floodOpacity="0.8" />
              </filter>
              <filter id="glow-rose" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="0" stdDeviation="8" floodColor="#EF4444" floodOpacity="0.8" />
              </filter>
            </defs>

            {/* 1. Curved Flow Links */}
            {links.map((link, idx) => {
              const pathD = `M ${link.x1} ${link.y1} Q ${link.cx} ${link.cy} ${link.x2} ${link.y2}`
              return (
                <g key={idx}>
                  {/* Background Glow Path */}
                  <path
                    d={pathD}
                    fill="none"
                    stroke={link.color}
                    strokeWidth="5"
                    strokeOpacity="0.2"
                  />
                  {/* Foreground Animated Dashed Flow Path */}
                  <path
                    d={pathD}
                    fill="none"
                    stroke={link.color}
                    strokeWidth="2.5"
                    strokeDasharray="8 8"
                    className="animate-fund-flow"
                    markerEnd={`url(#arrow-${link.color === '#EF4444' ? 'rose' : link.color === '#A855F7' ? 'purple' : link.color === '#F59E0B' ? 'amber' : link.color === '#10B981' ? 'emerald' : link.color === '#38BDF8' ? 'sky' : 'cyan'})`}
                  />
                  {/* Edge Label Pill Badge */}
                  <g transform={`translate(${link.cx}, ${link.cy})`}>
                    <rect
                      x="-70"
                      y="-12"
                      width="140"
                      height="24"
                      rx="12"
                      fill="#0B132B"
                      stroke={link.color}
                      strokeWidth="1.2"
                      opacity="0.95"
                    />
                    <text
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill="#F1F5F9"
                      fontSize="10"
                      fontFamily="JetBrains Mono, monospace"
                      fontWeight="bold"
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
              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  className="cursor-pointer transition-transform duration-200"
                  onClick={() => setSelectedNodeId(node.id)}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                >
                  {/* Concentric Glow Pulse Ring */}
                  <circle
                    r={isSelected ? 42 : 36}
                    fill={node.glowColor}
                    opacity="0.3"
                    className="transition-all duration-300"
                  />
                  <circle
                    r={isSelected ? 36 : 30}
                    fill="#0F172A"
                    stroke={node.color}
                    strokeWidth={isSelected ? 3.5 : 2.5}
                    style={{ filter: `drop-shadow(0 0 12px ${node.color})` }}
                  />

                  {/* Icon or Symbol inside */}
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="18"
                    y="-1"
                  >
                    {node.icon}
                  </text>

                  {/* Text Label Below Node */}
                  <g transform="translate(0, 44)">
                    <rect
                      x="-85"
                      y="-11"
                      width="170"
                      height="22"
                      rx="6"
                      fill="#060912"
                      stroke={node.color}
                      strokeWidth="1"
                      opacity="0.95"
                    />
                    <text
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill="#FFFFFF"
                      fontSize="11"
                      fontWeight="bold"
                    >
                      {node.name.length > 12 ? `${node.name.substring(0, 11)}…` : node.name}
                    </text>
                  </g>

                  {/* Subtext Label Below */}
                  <text
                    x="0"
                    y="68"
                    textAnchor="middle"
                    fill="#94A3B8"
                    fontSize="10"
                    fontFamily="JetBrains Mono, monospace"
                  >
                    {node.subText}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        {/* Selected Node Details Inspection Card */}
        {activeNode && (
          <div className="mt-4 p-4 rounded-xl bg-slate-900/90 border border-cyan-500/40 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs font-mono animate-fade-in shadow-xl">
            <div className="flex items-center gap-3">
              <span className="text-2xl p-2 rounded-lg bg-black/40 border border-white/10">
                {activeNode.icon}
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">{activeNode.name}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold" style={{ backgroundColor: `${activeNode.color}25`, color: activeNode.color }}>
                    {activeNode.subText}
                  </span>
                  {activeNode.amount && (
                    <span className="text-rose-300 font-bold bg-rose-950/60 px-2 py-0.5 rounded border border-rose-500/30">
                      涉案规模: {activeNode.amount}
                    </span>
                  )}
                </div>
                <div className="text-slate-400 mt-1 flex items-center gap-1.5 font-sans">
                  <Info className="w-3.5 h-3.5 text-cyan-400" />
                  <span>{activeNode.role}</span>
                </div>
              </div>
            </div>

            {activeNode.warning && (
              <div className="text-rose-300 bg-rose-950/40 p-2.5 rounded-lg border border-rose-500/30 text-xs max-w-md">
                <span className="font-bold">【疑点定性】: </span>
                {activeNode.warning}
              </div>
            )}
          </div>
        )}

        {/* 5-Step Money Loop Breakdown Cards */}
        <div className="mt-5 pt-4 border-t border-white/10 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="font-bold text-white flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-cyan-400" />
              <span>全链路资金穿透流转明细 (Five-Step Fund Traceability Matrix)</span>
            </span>
            <span className="text-cyan-400 font-bold">{isClean ? '正常货物流与资金流一致' : '检出闭环无商业实质资金自循环'}</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-2.5 text-xs font-mono">
            {isClean ? (
              <>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-cyan-500/30 space-y-1">
                  <div className="text-cyan-400 font-bold">1. 企业主体</div>
                  <div className="text-white text-[11px] truncate">{companyName}</div>
                  <div className="text-slate-400 text-[10px]">生产制造与经营核心</div>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-emerald-500/30 space-y-1">
                  <div className="text-emerald-400 font-bold">2. 核心客户</div>
                  <div className="text-white text-[11px]">战略主机厂/客户</div>
                  <div className="text-slate-400 text-[10px]">真实销售与现汇回款</div>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-blue-500/30 space-y-1">
                  <div className="text-blue-400 font-bold">3. 合格供应商</div>
                  <div className="text-white text-[11px]">主要物料供应商</div>
                  <div className="text-slate-400 text-[10px]">真实采购货物交割</div>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-purple-500/30 space-y-1">
                  <div className="text-purple-400 font-bold">4. 银企直连</div>
                  <div className="text-white text-[11px]">开户银行监管户</div>
                  <div className="text-slate-400 text-[10px]">全额资金直连存管</div>
                </div>
                <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 space-y-1 flex flex-col justify-center text-center">
                  <div className="text-emerald-300 font-bold">5. 审计结论</div>
                  <div className="text-emerald-400 text-[11px] font-bold">勾稽完全一致</div>
                  <div className="text-slate-400 text-[10px]">无体外自循环</div>
                </div>
              </>
            ) : (
              <>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-cyan-500/30 space-y-1">
                  <div className="text-cyan-400 font-bold">1. 资金划出</div>
                  <div className="text-white text-[11px] truncate">{node1Name}</div>
                  <div className="text-rose-400 text-[10px]">{fraudAmount}</div>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-rose-500/30 space-y-1">
                  <div className="text-rose-400 font-bold">2. 虚假账户</div>
                  <div className="text-white text-[11px] truncate">{node2Name}</div>
                  <div className="text-slate-400 text-[10px]">伪造存单/联动池</div>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-purple-500/30 space-y-1">
                  <div className="text-purple-400 font-bold">3. 体外过桥</div>
                  <div className="text-white text-[11px]">实控人资金池</div>
                  <div className="text-slate-400 text-[10px]">隐瞒关联方占用</div>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-amber-500/30 space-y-1">
                  <div className="text-amber-400 font-bold">4. 虚假购销</div>
                  <div className="text-white text-[11px] truncate">{node3Name}</div>
                  <div className="text-slate-400 text-[10px]">无商业实质冲账</div>
                </div>
                <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/40 space-y-1 flex flex-col justify-center text-center">
                  <div className="text-rose-300 font-bold">5. 资金回流</div>
                  <div className="text-rose-400 text-[11px] font-bold">完成造假自循环</div>
                  <div className="text-slate-400 text-[10px]">虚构收入与资产</div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Pedagogical Explanation Footer */}
        <div className="mt-4 p-4 rounded-xl bg-slate-950/70 border border-white/5 text-xs text-slate-300 space-y-1.5 font-mono">
          <div className={`${isClean ? 'text-emerald-400' : 'text-cyan-400'} font-semibold flex items-center gap-1.5`}>
            <AlertCircle className="w-4 h-4" />
            <span>【数智审计专家穿透提示】:</span>
          </div>
          <p className="text-slate-300 leading-relaxed font-sans">
            {isClean
              ? '本拓扑图反映受审企业与主机厂客户、合格供应商及开户银行之间的真实交易结算路径。资金进出均具有真实货物购销背景与银企直连流水印证，无异常关联方闭环与体外过桥回流特征。'
              : '本拓扑图由 DeepSeek-AuditMind 智能分析引擎结合银行流水附言、关联方披露及发票价税合计自动推演构建。通过对“预付采购-资金池归集-体外过桥-虚假销售回款”四步闭环特征识别，精准锁定无实质商业背景的资金空转回路。'}
          </p>
        </div>
      </div>
    </div>
  )
}
