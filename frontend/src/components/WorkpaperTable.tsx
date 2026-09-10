import React, { useState } from 'react'
import { FileSpreadsheet, FileText, Download, CheckCircle2, AlertCircle, Share2, Layers } from 'lucide-react'
import { AnalysisReportResult, WorkpaperData } from '../types'

interface WorkpaperTableProps {
  report: AnalysisReportResult | null
  currentCase: any
}

export const WorkpaperTable: React.FC<WorkpaperTableProps> = ({ report, currentCase }) => {
  const [downloading, setDownloading] = useState<string | null>(null)

  if (!report || !report.workpapers || report.workpapers.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto p-6 flex items-center justify-center text-slate-500 text-xs">
        暂无审计底稿数据。请先在指挥舱完成该案例的智能穿透研判。
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
            审定金额合计: ¥{wp.total_audited_amount.toLocaleString('zh-CN', { minimumFractionDigits: 2 })} | 
            差异金额: <span className="text-rose-400 font-bold">¥{wp.abnormal_amount.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</span>
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
                const hasDiscrepancy = Math.abs(r.discrepancy) > 0.01
                return (
                  <tr key={i} className="hover:bg-white/5 transition-colors">
                    <td className="p-3 font-bold text-cyan-400">{r.voucher_no}</td>
                    <td className="p-3 text-slate-400">{r.date}</td>
                    <td className="p-3 text-white max-w-xs truncate">{r.summary}</td>
                    <td className="p-3 text-right">¥{r.ledger_amount.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</td>
                    <td className="p-3 text-right">¥{r.verified_amount.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</td>
                    <td className={`p-3 text-right font-bold ${hasDiscrepancy ? 'text-rose-400' : 'text-emerald-400'}`}>
                      ¥{r.discrepancy.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
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
    </div>
  )
}
