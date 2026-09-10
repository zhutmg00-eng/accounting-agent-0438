import React, { useState, useEffect } from 'react'
import { 
  Play, RotateCw, AlertTriangle, CheckCircle2, FileText, ArrowRight, 
  TrendingUp, Scale, Building, ShieldCheck, Sparkles, BookOpen, AlertOctagon, Info
} from 'lucide-react'
import { AnalysisReportResult, CaseListItem } from '../types'

interface AuditCockpitProps {
  currentCase: any
  report: AnalysisReportResult | null
  isRunning: boolean
  onRunAudit: () => void
  currentStage: number
  stageLogs: { stage: number; title: string; status: string; detail: string }[]
}

export const AuditCockpit: React.FC<AuditCockpitProps> = ({
  currentCase,
  report,
  isRunning,
  onRunAudit,
  currentStage,
  stageLogs
}) => {
  if (!currentCase) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 text-slate-500">
        请在左侧侧边栏中选择一个真实审计案例开始研判。
      </div>
    )
  }

  const stages = [
    { num: 1, name: '数据解析与时序校验' },
    { num: 2, name: '确定性算子矩阵扫描' },
    { num: 3, name: '三单业财勾稽穿透' },
    { num: 4, name: 'DeepSeek 准则推理' },
    { num: 5, name: '审计底稿与结论合成' },
  ]

  const mScoreData = report?.tool_outputs?.beneish_m_score || {}
  const reconData = report?.tool_outputs?.three_way_reconciliation || {}

  const getRiskColor = (rating: string = 'CLEAN') => {
    switch (rating.toUpperCase()) {
      case 'CRITICAL':
        return 'text-rose-400 bg-rose-950/40 border-rose-500/50 shadow-rose-500/20'
      case 'HIGH':
        return 'text-amber-400 bg-amber-950/40 border-amber-500/50 shadow-amber-500/20'
      case 'MEDIUM':
        return 'text-yellow-400 bg-yellow-950/40 border-yellow-500/50 shadow-yellow-500/20'
      case 'LOW':
        return 'text-blue-400 bg-blue-950/40 border-blue-500/50 shadow-blue-500/20'
      case 'CLEAN':
      default:
        return 'text-emerald-400 bg-emerald-950/40 border-emerald-500/50 shadow-emerald-500/20'
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* 1. Executive Case Banner */}
      <div className="glass-panel rounded-2xl p-6 relative overflow-hidden">
        {/* Ambient background glow */}
        <div className="absolute -right-20 -top-20 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -left-20 -bottom-20 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2 max-w-3xl">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="px-2.5 py-1 rounded-md bg-cyan-500/20 text-cyan-300 font-mono text-xs font-bold border border-cyan-400/40 shadow-sm">
                代码 {currentCase.stock_code}
              </span>
              <span className="px-2.5 py-1 rounded-md bg-white/10 text-slate-300 text-xs font-medium">
                行业: {currentCase.industry}
              </span>
              <span className="px-2.5 py-1 rounded-md bg-purple-500/20 text-purple-300 text-xs font-mono border border-purple-500/30">
                {currentCase.audit_period}
              </span>
              <span className="px-2.5 py-1 rounded-md bg-rose-500/15 text-rose-300 text-xs font-mono border border-rose-500/30">
                {currentCase.penalty_decision_no}
              </span>
            </div>

            <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
              <span>{currentCase.company_name}</span>
              <span className="text-xs font-mono font-normal px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-white/10">
                {currentCase.case_id}
              </span>
            </h2>

            <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/50 p-3.5 rounded-xl border border-white/5 font-sans">
              <span className="text-cyan-400 font-semibold">【官方监管通报摘要】</span> {currentCase.csrc_summary}
            </p>
          </div>

          {/* Action Trigger Button */}
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <button
              disabled={isRunning}
              onClick={onRunAudit}
              className={`flex items-center gap-2.5 px-6 py-3.5 rounded-xl font-semibold text-sm transition-all shadow-xl active:scale-95 border ${
                isRunning
                  ? 'bg-slate-800 text-slate-400 border-white/10 cursor-not-allowed'
                  : 'bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white border-cyan-400/50 shadow-cyan-500/25 animate-pulse-glow'
              }`}
            >
              {isRunning ? (
                <>
                  <RotateCw className="w-5 h-5 animate-spin text-cyan-400" />
                  <span>多模态穿透研判中...</span>
                </>
              ) : (
                <>
                  <Play className="w-5 h-5 fill-current text-cyan-200" />
                  <span>启动智能穿透研判</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* 2. Five-Stage Animated Pipeline */}
        <div className="mt-8 pt-6 border-t border-white/10">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-3">
            <span className="font-semibold text-slate-200 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span>五步多模态智能审计流水线 (Multi-Stage Audit Pipeline)</span>
            </span>
            <span className="font-mono text-cyan-400">
              阶段 {currentStage} / 5 {isRunning ? '进行中...' : report ? '已完成' : '待运行'}
            </span>
          </div>

          <div className="grid grid-cols-5 gap-2">
            {stages.map((st) => {
              const isDone = st.num < currentStage || (report && !isRunning)
              const isCurrent = st.num === currentStage && isRunning
              return (
                <div
                  key={st.num}
                  className={`p-2.5 rounded-xl border text-center transition-all ${
                    isDone
                      ? 'bg-emerald-950/20 border-emerald-500/40 text-emerald-300'
                      : isCurrent
                      ? 'bg-cyan-950/40 border-cyan-400 text-cyan-200 ring-2 ring-cyan-500/20 shadow-lg shadow-cyan-500/20'
                      : 'bg-slate-900/40 border-white/5 text-slate-500'
                  }`}
                >
                  <div className="flex items-center justify-center gap-1.5 text-xs font-mono font-bold mb-1">
                    {isDone ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : isCurrent ? (
                      <RotateCw className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                    ) : (
                      <span className="w-3.5 h-3.5 flex items-center justify-center rounded-full bg-slate-800 text-[10px]">
                        {st.num}
                      </span>
                    )}
                    <span>阶段 {st.num}</span>
                  </div>
                  <div className="text-[11px] truncate">{st.name}</div>
                </div>
              )
            })}
          </div>

          {/* Current Stage Status Log Banner */}
          {isRunning && stageLogs.length > 0 && (
            <div className="mt-3 p-2.5 rounded-lg bg-slate-950/80 border border-cyan-500/30 text-xs text-cyan-300 font-mono flex items-center gap-2 animate-pulse">
              <RotateCw className="w-3.5 h-3.5 animate-spin text-cyan-400 flex-shrink-0" />
              <span className="truncate">{stageLogs[stageLogs.length - 1].detail}</span>
            </div>
          )}
        </div>
      </div>

      {/* 3. Core Scorecard Cards */}
      {report && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Overall Rating */}
          <div className={`glass-panel rounded-2xl p-5 border shadow-xl ${getRiskColor(report.overall_risk_rating)}`}>
            <div className="flex items-center justify-between text-xs font-medium mb-3">
              <span className="flex items-center gap-1.5 text-slate-300">
                <ShieldCheck className="w-4 h-4" />
                <span>综合舞弊风险等级</span>
              </span>
              <span className="font-mono text-xs opacity-80">Execution: {report.execution_mode}</span>
            </div>
            <div className="text-3xl font-extrabold tracking-tight font-mono mb-2">
              {report.overall_risk_rating}
            </div>
            <p className="text-xs text-slate-300 line-clamp-2">
              {report.executive_summary}
            </p>
          </div>

          {/* Beneish M-Score Card */}
          <div className="glass-panel rounded-2xl p-5 border border-white/10 shadow-xl">
            <div className="flex items-center justify-between text-xs font-medium mb-3 text-slate-300">
              <span className="flex items-center gap-1.5">
                <Scale className="w-4 h-4 text-purple-400" />
                <span>Beneish M-Score (8因子算子)</span>
              </span>
              <span className="font-mono text-xs text-purple-400">阈值: -1.78</span>
            </div>
            <div className="flex items-baseline gap-3 mb-2">
              <span className={`text-3xl font-extrabold font-mono ${
                mScoreData.is_manipulator ? 'text-rose-400 glow-crimson' : 'text-emerald-400 glow-emerald'
              }`}>
                {mScoreData.m_score !== undefined ? mScoreData.m_score.toFixed(2) : '--'}
              </span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-white/10 text-slate-300">
                {mScoreData.is_manipulator ? '高危操纵' : '正常无异常'}
              </span>
            </div>
            <div className="text-xs text-slate-400 grid grid-cols-2 gap-1 font-mono pt-2 border-t border-white/5">
              <span>DSRI(应收): {mScoreData.dsri?.toFixed(2) || '1.00'}</span>
              <span>GMI(毛利): {mScoreData.gmi?.toFixed(2) || '1.00'}</span>
              <span>AQI(资产): {mScoreData.aqi?.toFixed(2) || '1.00'}</span>
              <span>SGI(增长): {mScoreData.sgi?.toFixed(2) || '1.00'}</span>
            </div>
          </div>

          {/* 3-Way Reconciliation Card */}
          <div className="glass-panel rounded-2xl p-5 border border-white/10 shadow-xl">
            <div className="flex items-center justify-between text-xs font-medium mb-3 text-slate-300">
              <span className="flex items-center gap-1.5">
                <TrendingUp className="w-4 h-4 text-cyan-400" />
                <span>三单勾稽穿透核对</span>
              </span>
              <span className="font-mono text-xs text-cyan-400">
                异常数: {reconData.total_discrepancies_count || 0}
              </span>
            </div>
            <div className="text-2xl font-extrabold font-mono text-white mb-2 truncate">
              ¥ {(reconData.total_abnormal_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-slate-400 pt-2 border-t border-white/5 flex items-center justify-between">
              <span>受审金额: ¥{((reconData.total_audited_amount || 0) / 100000000).toFixed(2)} 亿元</span>
              <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                reconData.reconciliation_clean ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
              }`}>
                {reconData.reconciliation_clean ? '勾稽完全一致' : '存在严重错报'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 4. Structured Risk Findings List */}
      {report && report.findings && report.findings.length > 0 && (
        <div className="glass-panel rounded-2xl p-6 border border-white/10 space-y-4 shadow-xl">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <AlertOctagon className="w-5 h-5 text-rose-400" />
              <span>审计穿透核查发现 (Audit Findings: {report.findings.length} 项)</span>
            </h3>
            <span className="text-xs font-mono text-slate-400">
              推理耗时: {report.execution_time_seconds.toFixed(4)}s
            </span>
          </div>

          <div className="space-y-4">
            {report.findings.map((f, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-slate-900/60 border border-white/10 hover:border-cyan-500/30 transition-all space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 flex items-center justify-center rounded-lg bg-rose-500/20 text-rose-400 font-mono font-bold text-xs border border-rose-500/40">
                      {idx + 1}
                    </span>
                    <h4 className="text-sm font-bold text-white tracking-wide">{f.title}</h4>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-rose-950/60 text-rose-300 border border-rose-500/40">
                      {f.risk_level}
                    </span>
                    <span className="text-xs font-mono font-semibold text-cyan-300 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-500/30">
                      涉案金额: ¥{f.abnormal_amount.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>

                {/* Evidence & Details */}
                <div className="text-xs text-slate-300 bg-black/40 p-3 rounded-lg border border-white/5 space-y-2">
                  <div className="flex items-start gap-2">
                    <span className="text-slate-400 font-semibold flex-shrink-0">【客观事实证据】:</span>
                    <span>{f.audit_evidence}</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-cyan-400 font-semibold flex-shrink-0">【违反应计准则】:</span>
                    <span className="text-cyan-200 font-mono">{f.csrc_standard_clause}</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-purple-400 font-semibold flex-shrink-0">【建议追加程序】:</span>
                    <span>{f.audit_procedure_recommendation}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
