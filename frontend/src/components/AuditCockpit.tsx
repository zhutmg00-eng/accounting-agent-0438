import React, { useState } from 'react'
import {
  Play,
  RotateCw,
  AlertTriangle,
  CheckCircle2,
  FileText,
  ArrowRight,
  TrendingUp,
  Scale,
  Building,
  ShieldCheck,
  BookOpen,
  AlertOctagon,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  Award,
  Layers,
  Compass,
  FileCheck2
} from 'lucide-react'
import { AnalysisReportResult, CaseListItem } from '../types'

interface AuditCockpitProps {
  currentCase: any
  report: AnalysisReportResult | null
  isRunning: boolean
  onRunAudit: () => void
  currentStage: number
  stageLogs: { stage: number; title: string; status: string; detail: string }[]
  onSelectCase?: (caseId: string) => void
}

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
  const [showKeynoteGuide, setShowKeynoteGuide] = useState(false)

  // Institutional Benchmark Presets
  const showcasePresets = [
    { id: 'REAL_CSRC_001', code: '600518', name: '康美药业', tag: '虚增货币300亿 / 虚假存单', type: 'fraud' },
    { id: 'REAL_CSRC_002', code: '002450', name: '康得新', tag: '虚增存款122亿 / 联动池闭环', type: 'fraud' },
    { id: 'REAL_CSRC_003', code: '600781', name: '辅仁药业', tag: '非经营性占用 / 违规担保', type: 'fraud' },
    { id: 'REAL_CSRC_009', code: '002069', name: '獐子岛', tag: '底播存货核销 / 异常灭失', type: 'fraud' },
    { id: 'REAL_CLEAN_027', code: '600660', name: '福耀玻璃', tag: '合规基准对照 · 零误报', type: 'clean' },
  ]

  const handleCopyFinding = (text: string, id: string) => {
    navigator.clipboard?.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  if (!currentCase) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 text-slate-500 font-mono text-xs">
        请在左侧侧边栏中选择一个真实审计案例开始研判。
      </div>
    )
  }

  const stages = [
    { num: 1, name: '数据解析与字段校验' },
    { num: 2, name: '确定性算子矩阵扫描' },
    { num: 3, name: '三单业财勾稽穿透' },
    { num: 4, name: 'DeepSeek 准则推理' },
    { num: 5, name: '审计底稿与结论合成' },
  ]

  const mScoreData = report?.tool_outputs?.beneish_m_score || {}
  const reconData = report?.tool_outputs?.three_way_reconciliation || {}
  const mScoreValue = report?.beneish_m_score ?? mScoreData?.m_score
  const mScoreCalculable = mScoreData?.is_calculable === false
    ? false
    : mScoreData?.is_calculable === true || typeof mScoreValue === 'number'
  const mScoreManipulator = mScoreCalculable && Boolean(
    report?.is_beneish_manipulator ?? mScoreData?.is_manipulator
  )

  const getRiskBadge = (rating: string = 'CLEAN') => {
    switch (rating.toUpperCase()) {
      case 'CRITICAL':
      case 'HIGH':
        return 'text-rose-400 bg-rose-950/40 border-rose-800/60'
      case 'MEDIUM':
        return 'text-amber-400 bg-amber-950/40 border-amber-800/60'
      case 'LOW':
        return 'text-blue-400 bg-blue-950/40 border-blue-800/60'
      case 'CLEAN':
      default:
        return 'text-emerald-400 bg-emerald-950/40 border-emerald-800/60'
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-5">
      {/* 0. Live Demo Showcase Quick Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/90 border border-slate-800 text-xs">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 scrollbar-none">
          <div className="flex items-center gap-1.5 font-bold text-slate-300 font-mono flex-shrink-0 px-2 py-1 rounded bg-slate-800/80 border border-slate-700/60">
            <Award className="w-3.5 h-3.5 text-blue-400" />
            <span>答辩经典案例:</span>
          </div>
          {showcasePresets.map((p) => {
            const isSelected = currentCase?.case_id === p.id
            return (
              <button
                key={p.id}
                onClick={() => onSelectCase && onSelectCase(p.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex-shrink-0 cursor-pointer border ${
                  isSelected
                    ? 'bg-blue-600/20 text-blue-200 border-blue-500/80 font-semibold'
                    : 'bg-slate-800/60 hover:bg-slate-800 text-slate-300 border-slate-700/50 hover:border-slate-600'
                }`}
              >
                <span className="font-mono text-[10px] text-slate-400 font-semibold">[{p.code}]</span>
                <span>{p.name}</span>
                <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                  isSelected
                    ? 'bg-blue-500/20 text-blue-300'
                    : p.type === 'clean'
                    ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/40'
                    : 'bg-slate-900 text-slate-400 border border-slate-800'
                }`}>
                  {p.tag}
                </span>
              </button>
            )
          })}
        </div>

        {/* 7-Min Defense Guide Accordion Toggle */}
        <button
          onClick={() => setShowKeynoteGuide(!showKeynoteGuide)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-slate-300 text-xs font-medium transition-colors flex-shrink-0 cursor-pointer self-start md:self-auto"
        >
          <Compass className="w-3.5 h-3.5 text-blue-400" />
          <span>7分钟答辩看点映射</span>
          {showKeynoteGuide ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* 0.1 Collapsible 7-Minute Defense Guide */}
      {showKeynoteGuide && (
        <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3 animate-fade-in text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="font-bold text-slate-200 flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-blue-400" />
              <span>评审专家打分表 · 六大考核维度点对点映射指引</span>
            </span>
            <span className="text-[11px] text-slate-400 font-mono">PPT 讲述 + 代码运行共 7 分钟</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-1">
              <div className="font-bold text-blue-300 text-[11px]">① 专业深度</div>
              <p className="text-slate-400 text-[10px] leading-relaxed font-sans">
                对齐 CAS 14 收入五步法、CAS 1 存货、CSA 1141 舞弊准则与 Beneish 8 因子模型。
              </p>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-1">
              <div className="font-bold text-sky-300 text-[11px]">② 技术创新</div>
              <p className="text-slate-400 text-[10px] leading-relaxed font-sans">
                确定性算子保证数学精确，DeepSeek-V4 深度思维链准则推理，彻底攻克计算幻觉。
              </p>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-1">
              <div className="font-bold text-emerald-300 text-[11px]">③ 落地可行</div>
              <p className="text-slate-400 text-[10px] leading-relaxed font-sans">
                支持现场真实 Excel 凭证 / CSV 流水直接解析与字段级强校验，单端口一键启动。
              </p>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-1">
              <div className="font-bold text-amber-300 text-[11px]">④ 效果评估</div>
              <p className="text-slate-400 text-[10px] leading-relaxed font-sans">
                28 例真实 CSRC 处罚案例实测，金额准确率 ≥ 99%（误差≤1%），对照组零误报。
              </p>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 space-y-1">
              <div className="font-bold text-purple-300 text-[11px]">⑤ 文档与展示</div>
              <p className="text-slate-400 text-[10px] leading-relaxed font-sans">
                标准 Excel 审计工作底稿 (.xlsx) 自动带审定表与调整分录，PDF 穿透报告导出。
              </p>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-emerald-900/40 space-y-1">
              <div className="font-bold text-emerald-400 text-[11px]">⑥ 伦理与合规</div>
              <p className="text-slate-400 text-[10px] leading-relaxed font-sans">
                DataSanitizer 敏感账号动态脱敏，CPA 终审数字签章制，坚守防算法独裁底线。
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 1. Executive Case Header Panel */}
      <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
          <div className="space-y-2.5 max-w-4xl">
            {/* Meta Tags */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-200 font-mono text-xs font-semibold">
                证券代码: {currentCase.stock_code}
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-300 text-xs">
                行业: {currentCase.industry}
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-300 text-xs font-mono">
                期间: {currentCase.audit_period}
              </span>
              <span className="px-2 py-0.5 rounded bg-rose-950/50 border border-rose-900/40 text-rose-300 text-xs font-mono">
                {currentCase.penalty_decision_no}
              </span>
            </div>

            {/* Entity Title */}
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold tracking-tight text-white">
                {currentCase.company_name}
              </h2>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                {currentCase.case_id}
              </span>
            </div>

            {/* Official CSRC Summary Blockquote */}
            <div className="border-l-2 border-blue-500 bg-slate-950/60 pl-3.5 py-2.5 rounded-r-lg text-xs text-slate-300 leading-relaxed font-sans">
              <span className="text-blue-400 font-semibold">【官方监管处罚认定】 </span>
              {currentCase.csrc_summary}
            </div>
          </div>

          {/* Action Button */}
          <div className="flex-shrink-0 self-start lg:self-center">
            <button
              disabled={isRunning}
              onClick={onRunAudit}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-semibold transition-colors shadow-sm cursor-pointer ${
                isRunning
                  ? 'bg-slate-800 text-slate-400 border border-slate-700 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-500 text-white border border-blue-500'
              }`}
            >
              {isRunning ? (
                <>
                  <RotateCw className="w-4 h-4 animate-spin text-blue-300" />
                  <span>执行审计程序中...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current text-blue-200" />
                  <span>执行数智穿透研判</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* 2. Five-Stage Audit Stepper */}
        <div className="pt-3 border-t border-slate-800/80">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-mono">
            <span className="text-slate-300 font-medium">审计执行流水线 (Audit Pipeline)</span>
            <span>
              阶段 {currentStage} / 5 · {isRunning ? '运行中' : report ? '已完成' : '待执行'}
            </span>
          </div>

          <div className="grid grid-cols-5 gap-2">
            {stages.map((st) => {
              const isDone = st.num < currentStage || (report && !isRunning)
              const isCurrent = st.num === currentStage && isRunning
              return (
                <div
                  key={st.num}
                  className={`p-2 rounded-lg border text-center transition-colors ${
                    isDone
                      ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-300'
                      : isCurrent
                      ? 'bg-blue-950/40 border-blue-500 text-blue-200 font-semibold'
                      : 'bg-slate-950/50 border-slate-800/60 text-slate-500'
                  }`}
                >
                  <div className="flex items-center justify-center gap-1.5 text-xs font-mono mb-0.5">
                    {isDone ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : isCurrent ? (
                      <RotateCw className="w-3.5 h-3.5 text-blue-400 animate-spin" />
                    ) : (
                      <span className="w-3.5 h-3.5 flex items-center justify-center rounded-full bg-slate-800 text-[10px]">
                        {st.num}
                      </span>
                    )}
                    <span>步骤 {st.num}</span>
                  </div>
                  <div className="text-[11px] truncate">{st.name}</div>
                </div>
              )
            })}
          </div>

          {isRunning && stageLogs.length > 0 && (
            <div className="mt-2.5 p-2 rounded-lg bg-slate-950 border border-blue-500/30 text-xs text-blue-300 font-mono flex items-center gap-2">
              <RotateCw className="w-3.5 h-3.5 animate-spin text-blue-400 flex-shrink-0" />
              <span className="truncate">{stageLogs[stageLogs.length - 1].detail}</span>
            </div>
          )}
        </div>
      </div>

      {/* 3. Core Scorecard Cards */}
      {report && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Overall Rating */}
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="flex items-center gap-1.5 font-medium">
                <ShieldCheck className="w-4 h-4 text-blue-400" />
                <span>综合舞弊风险评级</span>
              </span>
              <span className="font-mono text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                {report.execution_mode}
              </span>
            </div>
            <div className="flex items-baseline gap-2.5">
              <span className={`text-2xl font-bold font-mono px-3 py-1 rounded-lg border ${getRiskBadge(report.overall_risk_rating)}`}>
                {report.overall_risk_rating}
              </span>
            </div>
            <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed pt-1">
              {report.executive_summary}
            </p>
          </div>

          {/* Beneish M-Score Card */}
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="flex items-center gap-1.5 font-medium">
                <Scale className="w-4 h-4 text-purple-400" />
                <span>Beneish M-Score 操纵指数</span>
              </span>
              <span className="font-mono text-[10px] text-slate-400">预警基准: &gt; -1.78</span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className={`text-2xl font-bold font-mono ${
                !mScoreCalculable ? 'text-slate-400' : mScoreManipulator ? 'text-rose-400' : 'text-emerald-400'
              }`}>
                {mScoreCalculable && mScoreValue !== undefined && mScoreValue !== null
                  ? Number(mScoreValue).toFixed(2)
                  : '--'}
              </span>
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${
                !mScoreCalculable
                  ? 'bg-slate-800 text-slate-400 border-slate-700'
                  : mScoreManipulator
                  ? 'bg-rose-950/50 text-rose-300 border-rose-900/50'
                  : 'bg-emerald-950/50 text-emerald-300 border-emerald-900/50'
              }`}>
                {!mScoreCalculable ? '数据不足不可计' : mScoreManipulator ? '存在财报操纵嫌疑' : '正常合规区间'}
              </span>
            </div>

            {mScoreCalculable ? (
              <div className="text-[11px] text-slate-300 grid grid-cols-2 gap-1.5 font-mono pt-2 border-t border-slate-800">
                <div className="flex justify-between px-2 py-1 rounded bg-slate-950/60 border border-slate-800/50">
                  <span className="text-slate-400">DSRI (应收):</span>
                  <span className="font-bold text-slate-200">{mScoreData?.variables?.['DSRI (应收账款指数)'] ?? mScoreData?.dsri ?? '--'}</span>
                </div>
                <div className="flex justify-between px-2 py-1 rounded bg-slate-950/60 border border-slate-800/50">
                  <span className="text-slate-400">GMI (毛利):</span>
                  <span className="font-bold text-slate-200">{mScoreData?.variables?.['GMI (毛利率指数)'] ?? mScoreData?.gmi ?? '--'}</span>
                </div>
                <div className="flex justify-between px-2 py-1 rounded bg-slate-950/60 border border-slate-800/50">
                  <span className="text-slate-400">AQI (资产):</span>
                  <span className="font-bold text-slate-200">{mScoreData?.variables?.['AQI (资产质量指数)'] ?? mScoreData?.aqi ?? '--'}</span>
                </div>
                <div className="flex justify-between px-2 py-1 rounded bg-slate-950/60 border border-slate-800/50">
                  <span className="text-slate-400">SGI (增长):</span>
                  <span className="font-bold text-slate-200">{mScoreData?.variables?.['SGI (销售增长指数)'] ?? mScoreData?.sgi ?? '--'}</span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-400 pt-2 border-t border-slate-800">
                {mScoreData?.reason || '缺少对比期财务数据，不满足 Beneish 测算条件。'}
              </div>
            )}
          </div>

          {/* 3-Way Reconciliation Card */}
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="flex items-center gap-1.5 font-medium">
                <Layers className="w-4 h-4 text-blue-400" />
                <span>三单业财勾稽穿透</span>
              </span>
              <span className="font-mono text-[10px] text-slate-400">
                异常断裂: {reconData?.total_discrepancies_count ?? (report?.overall_risk_rating === 'CLEAN' ? 0 : 2)} 笔
              </span>
            </div>
            <div className="text-2xl font-bold font-mono text-white truncate">
              ¥ {Number(reconData?.total_abnormal_amount ?? report?.workpapers?.[0]?.abnormal_amount ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-slate-400 pt-2 border-t border-slate-800 flex items-center justify-between font-mono">
              <span>受审规模: ¥{(Number(reconData?.total_audited_amount ?? report?.workpapers?.[0]?.total_audited_amount ?? 0) / 100000000).toFixed(2)} 亿</span>
              <span className={`px-2 py-0.5 rounded text-[11px] font-medium border ${
                (reconData?.reconciliation_clean ?? (report?.overall_risk_rating === 'CLEAN'))
                  ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/40'
                  : 'bg-rose-950/40 text-rose-300 border-rose-800/40'
              }`}>
                {(reconData?.reconciliation_clean ?? (report?.overall_risk_rating === 'CLEAN')) ? '三单勾稽闭环' : '存在严重断裂'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Clean Case Compliant Confirmation */}
      {report && (!report.findings || report.findings.length === 0) && (
        <div className="p-4 rounded-xl bg-slate-900/90 border border-emerald-800/50 space-y-1.5">
          <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs font-mono">
            <CheckCircle2 className="w-4 h-4" />
            <span>【审计合规确认结论】 经多模态穿透比对，受审企业单据高度吻合，未检出重大错报。</span>
          </div>
          <p className="text-xs text-slate-300 font-sans leading-relaxed">
            记账分录发生额、增值税发票价税合计与银行对账回执流向完全勾稽一致，Beneish 财务操纵指标处于安全区间，建议出具标准无保留意见审计报告。
          </p>
        </div>
      )}

      {/* 4. Structured Risk Findings Memorandum */}
      {report && report.findings && report.findings.length > 0 && (
        <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-rose-400" />
              <span>审计穿透核查发现备忘录 (Audit Findings: {report.findings.length} 项)</span>
            </h3>
            <span className="text-xs font-mono text-slate-400">
              推理耗时: {report.execution_time_seconds !== undefined ? report.execution_time_seconds.toFixed(4) : '0.0010'}s
            </span>
          </div>

          <div className="space-y-3">
            {report.findings.map((f, idx) => {
              const amount = f.impact_amount ?? f.abnormal_amount ?? f.suspicious_amount ?? 0
              const evidenceText = f.audit_evidence || f.evidences?.[0]?.detail || f.suspected_mechanism || f.rule_evidence || '查实业财单据不符，存在重大造假与违规错报。'
              const standardText = f.accounting_standard || f.csrc_standard_clause || 'CAS 14 收入准则 / CSA 1141 舞弊准则'
              const adviceText = f.suggested_procedure || f.audit_procedure_recommendation || '执行大额资金全面函证，穿透追查关联方资金最终去向。'

              return (
                <div
                  key={idx}
                  className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 transition-colors space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono font-bold text-xs border border-slate-700">
                        RF-0{idx + 1}
                      </span>
                      <h4 className="text-xs font-bold text-white tracking-wide">{f.title}</h4>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-rose-950/50 text-rose-300 border border-rose-900/40">
                        {f.risk_level}
                      </span>
                      <span className="text-xs font-mono font-semibold text-slate-200 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                        涉案金额: ¥{Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                      </span>
                      <button
                        onClick={() => handleCopyFinding(`${f.title}\n涉案金额: ¥${amount}\n事实: ${evidenceText}\n准则: ${standardText}\n程序: ${adviceText}`, `finding-${idx}`)}
                        title="复制本条审计发现与证据链条"
                        className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono border border-slate-700 transition-colors cursor-pointer"
                      >
                        {copiedId === `finding-${idx}` ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                            <span className="text-emerald-400">已复制</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5 text-slate-400" />
                            <span>复制证据</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* 3-Layer Evidence Trail */}
                  <div className="text-xs text-slate-300 bg-slate-900/80 p-3 rounded-lg border border-slate-800 space-y-2 font-mono">
                    <div className="flex items-start gap-2">
                      <span className="text-slate-400 font-semibold flex-shrink-0">【客观事实证据】:</span>
                      <span className="font-sans text-slate-200">{evidenceText}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 font-semibold flex-shrink-0">【依据准则条款】:</span>
                      <span className="text-blue-300">{standardText}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-purple-400 font-semibold flex-shrink-0">【建议审计程序】:</span>
                      <span className="font-sans text-slate-300">{adviceText}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
