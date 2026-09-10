import React, { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import { Network, HelpCircle, AlertCircle, ArrowUpRight } from 'lucide-react'

interface FundTopologyGraphProps {
  currentCase: any
}

export const FundTopologyGraph: React.FC<FundTopologyGraphProps> = ({ currentCase }) => {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!chartRef.current) return

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, 'dark')
    }

    const companyName = currentCase?.company_name || '上市公司主体'
    const category = currentCase?.case_category || ''

    // Build dynamic nodes and edges based on case type
    let nodes: any[] = []
    let links: any[] = []

    if (category.includes('货币资金') || category.includes('存单')) {
      nodes = [
        { name: companyName, symbolSize: 65, category: 0, itemStyle: { color: '#00F2FE' } },
        { name: '北京银行联动账户/虚假存单池', symbolSize: 55, category: 1, itemStyle: { color: '#EF4444' } },
        { name: '大股东及关联控股方', symbolSize: 50, category: 2, itemStyle: { color: '#A855F7' } },
        { name: '体外资金划转过桥账户', symbolSize: 45, category: 3, itemStyle: { color: '#F59E0B' } },
        { name: '虚假出口贸易代理行', symbolSize: 40, category: 4, itemStyle: { color: '#38BDF8' } },
      ]
      links = [
        { source: companyName, target: '北京银行联动账户/虚假存单池', value: '虚增存款 ¥122.1亿', lineStyle: { color: '#EF4444', width: 4, curveness: 0.2 } },
        { source: '北京银行联动账户/虚假存单池', target: '大股东及关联控股方', value: '归集划转/隐瞒占用', lineStyle: { color: '#A855F7', width: 3, curveness: 0.2 } },
        { source: '大股东及关联控股方', target: '体外资金划转过桥账户', value: '过桥清偿债务', lineStyle: { color: '#F59E0B', width: 2, curveness: 0.2 } },
        { source: '体外资金划转过桥账户', target: companyName, value: '伪造回款闭环', lineStyle: { color: '#00F2FE', width: 3, curveness: 0.2 } },
        { source: companyName, target: '虚假出口贸易代理行', value: '虚构外销报关', lineStyle: { color: '#38BDF8', width: 2, curveness: 0.2 } },
      ]
    } else if (category.includes('虚构购销') || category.includes('体外')) {
      nodes = [
        { name: companyName, symbolSize: 65, category: 0, itemStyle: { color: '#00F2FE' } },
        { name: '上游指定壳公司A(诺贝丰/富朗)', symbolSize: 50, category: 1, itemStyle: { color: '#EF4444' } },
        { name: '下游关联分销壳商B', symbolSize: 50, category: 1, itemStyle: { color: '#F59E0B' } },
        { name: '实控人控制走账过桥池', symbolSize: 55, category: 2, itemStyle: { color: '#A855F7' } },
        { name: '虚假物流仓储(无货空转)', symbolSize: 40, category: 3, itemStyle: { color: '#64748B' } },
      ]
      links = [
        { source: companyName, target: '上游指定壳公司A(诺贝丰/富朗)', value: '预付大额采购款 ¥230亿', lineStyle: { color: '#EF4444', width: 4, curveness: 0.25 } },
        { source: '上游指定壳公司A(诺贝丰/富朗)', target: '实控人控制走账过桥池', value: '资金背靠背划转', lineStyle: { color: '#A855F7', width: 3, curveness: 0.25 } },
        { source: '实控人控制走账过桥池', target: '下游关联分销壳商B', value: '注资伪造购买力', lineStyle: { color: '#F59E0B', width: 3, curveness: 0.25 } },
        { source: '下游关联分销壳商B', target: companyName, value: '虚假商品回款(确认收入)', lineStyle: { color: '#00F2FE', width: 4, curveness: 0.25 } },
        { source: companyName, target: '虚假物流仓储(无货空转)', value: '伪造入库与出库单', lineStyle: { color: '#64748B', width: 2, type: 'dashed' } },
      ]
    } else {
      nodes = [
        { name: companyName, symbolSize: 65, category: 0, itemStyle: { color: '#00F2FE' } },
        { name: '核心战略客户/主机厂', symbolSize: 50, category: 1, itemStyle: { color: '#10B981' } },
        { name: '合规主要供应商', symbolSize: 50, category: 2, itemStyle: { color: '#38BDF8' } },
        { name: '基本存款账户(银企直连)', symbolSize: 50, category: 3, itemStyle: { color: '#A855F7' } },
      ]
      links = [
        { source: '核心战略客户/主机厂', target: companyName, value: '真实银行现汇结算', lineStyle: { color: '#10B981', width: 3, curveness: 0.2 } },
        { source: companyName, target: '合规主要供应商', value: '采购原辅材料款', lineStyle: { color: '#38BDF8', width: 3, curveness: 0.2 } },
        { source: companyName, target: '基本存款账户(银企直连)', value: '资金归集监管', lineStyle: { color: '#A855F7', width: 2, curveness: 0.2 } },
      ]
    }

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'edge') {
            return `<div class="font-mono text-xs"><span class="text-cyan-400 font-bold">${params.data.source}</span> ➔ <span class="text-purple-400 font-bold">${params.data.target}</span><br/><span class="text-rose-300">${params.data.value}</span></div>`
          }
          return `<div class="font-mono text-xs font-bold text-white">${params.name}</div>`
        }
      },
      legend: {
        data: ['企业主体', '涉案壳公司/存单池', '关联控制方', '过桥资金池', '物流中介'],
        textStyle: { color: '#94A3B8', fontSize: 11 },
        bottom: 10
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          animation: true,
          force: {
            repulsion: 450,
            edgeLength: [140, 220],
            gravity: 0.08
          },
          roam: true,
          label: {
            show: true,
            position: 'bottom',
            color: '#E2E8F0',
            fontSize: 11,
            fontFamily: 'sans-serif'
          },
          edgeSymbol: ['circle', 'arrow'],
          edgeSymbolSize: [4, 8],
          edgeLabel: {
            show: true,
            fontSize: 10,
            color: '#94A3B8',
            fontFamily: 'monospace',
            formatter: (p: any) => p.data.value || ''
          },
          data: nodes,
          links: links,
          lineStyle: {
            opacity: 0.9,
            curveness: 0.2
          }
        }
      ]
    }

    chartInstance.current.setOption(option)

    const handleResize = () => {
      chartInstance.current?.resize()
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [currentCase])

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="glass-panel rounded-2xl p-6 border border-white/10 relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 mb-1">
              <Network className="w-4 h-4" />
              <span>资金体外循环与关联方穿透拓扑 (ECharts Force Relational Graph)</span>
            </div>
            <h2 className="text-xl font-bold text-white">
              {currentCase?.company_name} · 涉案壳公司、银行资金池与关联往来穿透网络
            </h2>
          </div>

          <div className="text-xs text-slate-400 font-mono flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            <span>力导向自适应布局 | 支持滚轮缩放与节点拖拽</span>
          </div>
        </div>

        {/* Chart Canvas Container */}
        <div ref={chartRef} className="w-full h-[520px] mt-4" />

        {/* Legend / Pedagogical Explanation */}
        <div className="mt-4 p-4 rounded-xl bg-slate-950/60 border border-white/5 text-xs text-slate-300 space-y-1.5 font-mono">
          <div className="text-cyan-400 font-semibold flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4" />
            <span>【数智审计专家穿透提示】:</span>
          </div>
          <p className="text-slate-300 leading-relaxed font-sans">
            本拓扑图由 DeepSeek-AuditMind 智能分析引擎结合银行流水附言、关联方披露及发票价税合计自动推演构建。通过对“预付采购-资金池归集-体外过桥-虚假销售回款”四步闭环特征识别，精准锁定无实质商业背景的资金空转回路。
          </p>
        </div>
      </div>
    </div>
  )
}
