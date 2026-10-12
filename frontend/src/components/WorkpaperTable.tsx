import React, { useState } from 'react'
import { FileSpreadsheet, FileText, Download, CheckCircle2, AlertCircle, Share2, Layers, Play, RotateCw, UserCheck, ShieldCheck, Stamp } from 'lucide-react'
import { AnalysisReportResult, WorkpaperData, CpaApprovalReceipt } from '../types'

interface WorkpaperTableProps {
  report: AnalysisReportResult | null
  currentCase: any
  onRunAudit?: () => void
  isRunning?: boolean
}

export const WorkpaperTable: React.FC<WorkpaperTableProps> = ({ report, currentCase, onRunAudit, isRunning }) => {
  const [downloading, setDownloading] = useState<string | null>(null)

  const [cpaReceipt, setCpaReceipt] = useState<CpaApprovalReceipt | null>(null)
  const [signing, setSigning] = useState(false)
  const [auditorName, setAuditorName] = useState('张宇 (执业CPA)')
  const [certNo, setCertNo] = useState('110000240982')
  const [opinionType, setOpinionType] = useState('保留意见/拟追加外部银行函证')

  const handleSignOff = async () => {
    if (!report) return
    setSigning(true)
    try {
      const resp = await fetch('/api/compliance/cpa-approval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: report.case_id,
          auditor_name: auditorName,
          cert_no: certNo,
          opinion_type: opinionType,
          audit_firm: '数智会计联合审计项目组',
          professional_skepticism_notes: '已秉持职业怀疑态度，全面复核确定性算子三单倒挂天数与Beneish操纵指数，认可智能体证据链，拟针对可疑关联方实施外部独立银行函证。',
          compliance_confirmed: true
        })
      })
      if (resp.ok) {
        const receipt = await resp.json()
        setCpaReceipt(receipt)
      }
    } catch (e) {
      console.error('Sign-off failed', e)
    } finally {
      setSigning(false)
    }
  }
  if (!report || !report.workpapers || report.workpapers.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto p-12 flex flex-col items-center justify-center text-center space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center shadow-lg shadow-cyan-500/10">
          <FileSpreadsheet className="w-8 h-8 text-cyan-400" />
        </div>
        <div className="space-y-1.5 max-w-md">
          <h3 className="text-base font-bold text-white">暂未生成受审企业审计工作底稿</h3>
          <p className="text-xs text-slate-400">
            底稿需要结合业财三单比对、Beneish 8 因子刚性测算以及大模型准则定性自动合成。当前选定案例【{currentCase?.company_name || '未选定'}】尚未执行穿透研判。
          </p>
        </div>
        {onRunAudit && (
          <button
            onClick={onRunAudit}
            disabled={isRunning}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-lg shadow-cyan-500/25 active:scale-95 transition-all cursor-pointer"
          >
            {isRunning ? (
              <>
                <RotateCw className="w-4 h-4 animate-spin" />
                <span>正在生成审计工作底稿...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>立即对当前案例一键生成底稿</span>
              </>
            )}
          </button>
        )}
      </div>
    )
  }

  const wp: WorkpaperData = report.workpapers[0]

  const handleExport = async (format: 'excel' | 'pdf' | 'json') => {
    setDownloading(format)
    try {
      const resp = await fetch(`/api/export/${format}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report)
      })

      if (resp.ok) {
        const blob = await resp.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `AuditMind_${report.company_name}_${format.toUpperCase()}.${format === 'excel' ? 'xlsx' : format}`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      }
    } catch (e) {
      console.error('Export failed', e)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header & Export Action Controls */}
      <div className="glass-panel rounded-2xl p-6 border border-white/10 relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 mb-1">
              <FileSpreadsheet className="w-4 h-4" />
              <span>注册会计师标准审计工作底稿 (Substantive Workpaper: {wp.workpaper_id})</span>
            </div>
            <h2 className="text-xl font-bold text-white">
              {wp.title} · {report.company_name}
            </h2>
            <p className="text-xs text-slate-400 mt-1 font-mono">
              编制人: {wp.prepared_by} | 复核日期: {wp.review_date} | 抽样样本量: {wp.sample_count} 笔
            </p>
          </div>

          {/* Export Buttons */}
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => handleExport('excel')}
              disabled={downloading === 'excel'}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 transition-all shadow-md active:scale-95"
            >
              <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
              <span>{downloading === 'excel' ? '正在导出...' : '导出 Excel 底稿 (.xlsx)'}</span>
            </button>

            <button
              onClick={() => handleExport('pdf')}
              disabled={downloading === 'pdf'}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 transition-all shadow-md active:scale-95"
            >
              <FileText className="w-4 h-4 text-rose-400" />
              <span>{downloading === 'pdf' ? '正在排版...' : '导出 PDF 报告 (.pdf)'}</span>
            </button>

            <button
              onClick={() => handleExport('json')}
              disabled={downloading === 'json'}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/40 transition-all shadow-md active:scale-95"
            >
              <Download className="w-4 h-4 text-cyan-400" />
              <span>{downloading === 'json' ? '打包中...' : '导出 JSON 数据包'}</span>
            </button>
          </div>
        </div>

        {/* Audit Opinion Summary */}
        <div className="mt-4 p-3.5 rounded-xl bg-slate-950/60 border border-white/5 text-xs text-slate-300 font-mono">
          <span className="text-cyan-400 font-bold">【底稿复核综合意见】: </span>
          <span>{wp.audit_opinion_summary}</span>
        </div>
      </div>

      {/* Substantive Workpaper Table Grid */}
      <div className="glass-panel rounded-2xl p-6 border border-white/10 space-y-4 overflow-hidden">
        <div className="flex items-center justify-between border-b border-white/10 pb-4 text-xs font-mono text-slate-400">
          <span className="font-bold text-white text-sm">核查样本明细行 ({wp.rows.length} 笔)</span>
          <span>
            审定金额合计: ¥{Number(wp.total_audited_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })} | 
            差异金额: <span className="text-rose-400 font-bold">¥{Number(wp.abnormal_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</span>
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-white/10 text-slate-400 bg-white/5">
                <th className="p-3">凭证号</th>
                <th className="p-3">业务日期</th>
                <th className="p-3">摘要</th>
                <th className="p-3 text-right">账面金额</th>
                <th className="p-3 text-right">审定金额</th>
                <th className="p-3 text-right">差异金额</th>
                <th className="p-3">审计结论</th>
                <th className="p-3">佐证底单</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {wp.rows.map((r, i) => {
                const hasDiscrepancy = Math.abs(Number(r.discrepancy || 0)) > 0.01
                return (
                  <tr key={i} className="hover:bg-white/5 transition-colors">
                    <td className="p-3 font-bold text-cyan-400">{r.voucher_no}</td>
                    <td className="p-3 text-slate-400">{r.date}</td>
                    <td className="p-3 text-white max-w-xs truncate">{r.summary}</td>
                    <td className="p-3 text-right">¥{Number(r.ledger_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</td>
                    <td className="p-3 text-right">¥{Number(r.verified_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</td>
                    <td className={`p-3 text-right font-bold ${hasDiscrepancy ? 'text-rose-400' : 'text-emerald-400'}`}>
                      ¥{Number(r.discrepancy || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                        hasDiscrepancy ? 'bg-rose-500/20 text-rose-300' : 'bg-emerald-500/20 text-emerald-300'
                      }`}>
                        {r.audit_conclusion}
                      </span>
                    </td>
                    <td className="p-3 text-purple-300 truncate max-w-[140px]">{r.evidence_trace}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* CPA Lead Auditor Sign-off & Ethics Declaration Card */}
      <div className="glass-panel rounded-2xl p-6 border border-emerald-500/20 bg-gradient-to-br from-slate-950/80 via-slate-900/90 to-emerald-950/20 space-y-4">
        <div className="flex items-center justify-between border-b border-emerald-500/20 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                注册会计师终审签章与责任伦理机制 (CPA Sign-off & Ethics)
                <span className="px-2 py-0.5 text-[10px] rounded bg-emerald-500/20 text-emerald-300 font-mono border border-emerald-500/30">
                  防算法独裁 · CPA终局负责
                </span>
              </h4>
              <p className="text-xs text-slate-400">
                遵循《中国注册会计师职业道德守则》：AI 辅助初筛，终审结论由执业注会独立复核并签名确认
              </p>
            </div>
          </div>
          {cpaReceipt ? (
            <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-mono font-bold">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>已完成数字签章生效</span>
            </div>
          ) : (
            <button
              onClick={handleSignOff}
              disabled={signing}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-950/50 transition-all cursor-pointer disabled:opacity-50"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>{signing ? '签名存证中...' : '执业注会终审签章'}</span>
            </button>
          )}
        </div>

        {cpaReceipt ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-950/60 border border-emerald-500/30 font-mono text-xs">
            <div>
              <span className="text-slate-500 block">签字注册会计师</span>
              <span className="text-emerald-300 font-bold">{cpaReceipt.auditor_name}</span>
            </div>
            <div>
              <span className="text-slate-500 block">执业证书编号</span>
              <span className="text-slate-300">{cpaReceipt.cert_no}</span>
            </div>
            <div>
              <span className="text-slate-500 block">终审防伪哈希</span>
              <span className="text-cyan-400 font-mono truncate block" title={cpaReceipt.verification_hash}>
                {cpaReceipt.verification_hash}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">签章时间</span>
              <span className="text-slate-300">{cpaReceipt.sign_timestamp}</span>
            </div>
            <div className="col-span-1 md:col-span-4 mt-2 pt-2 border-t border-white/5 text-[11px] text-slate-400">
              <span className="text-emerald-400 font-semibold">【伦理承诺】: </span>
              {cpaReceipt.ethical_declaration}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div>
              <label className="text-slate-400 text-[11px] block mb-1">签字注册会计师</label>
              <input
                type="text"
                value={auditorName}
                onChange={(e) => setAuditorName(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="text-slate-400 text-[11px] block mb-1">CPA执业证书编号</label>
              <input
                type="text"
                value={certNo}
                onChange={(e) => setCertNo(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="text-slate-400 text-[11px] block mb-1">初拟审计意见类型</label>
              <input
                type="text"
                value={opinionType}
                onChange={(e) => setOpinionType(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 rounded-lg px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
