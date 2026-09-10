import React, { useState } from 'react'
import { X, UploadCloud, FileSpreadsheet, Receipt, Landmark, CheckCircle2, AlertCircle } from 'lucide-react'

interface CustomUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onCaseImported: (caseData: any) => void
}

export const CustomUploadModal: React.FC<CustomUploadModalProps> = ({
  isOpen,
  onClose,
  onCaseImported
}) => {
  const [companyName, setCompanyName] = useState('企业实战账套抽样')
  const [stockCode, setStockCode] = useState('CUSTOM-888')
  const [industry, setIndustry] = useState('高端制造与智能硬件')

  const [vouchersFile, setVouchersFile] = useState<File | null>(null)
  const [invoicesFile, setInvoicesFile] = useState<File | null>(null)
  const [bankFlowsFile, setBankFlowsFile] = useState<File | null>(null)

  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setUploading(true)
    setUploadError(null)

    const formData = new FormData()
    formData.append('company_name', companyName)
    formData.append('stock_code', stockCode)
    formData.append('industry', industry)

    if (vouchersFile) formData.append('vouchers_file', vouchersFile)
    if (invoicesFile) formData.append('invoices_file', invoicesFile)
    if (bankFlowsFile) formData.append('bank_flows_file', bankFlowsFile)

    try {
      const resp = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      })

      if (resp.ok) {
        const data = await resp.json()
        onCaseImported(data.case)
        onClose()
      } else {
        const err = await resp.json()
        setUploadError(err.detail || '导入解析失败，请检查文件格式是否符合规范模板。')
      }
    } catch (e: any) {
      setUploadError(e.message || '网络连接异常，无法上传。')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
      <div className="glass-panel w-full max-w-2xl rounded-2xl p-6 border border-white/10 shadow-2xl relative">
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-cyan-400" />
            <h3 className="text-base font-bold text-white">导入真实企业财务文件 (Excel / CSV)</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {uploadError && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[11px] text-slate-400 block mb-1">受审公司全称</label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-slate-800 border border-white/10 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="text-[11px] text-slate-400 block mb-1">股票代码 / 账套编号</label>
              <input
                type="text"
                value={stockCode}
                onChange={(e) => setStockCode(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-slate-800 border border-white/10 text-white focus:outline-none focus:border-cyan-500 font-mono"
              />
            </div>

            <div>
              <label className="text-[11px] text-slate-400 block mb-1">所属行业领域</label>
              <input
                type="text"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-slate-800 border border-white/10 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          {/* 3 File Inputs */}
          <div className="space-y-3 pt-2">
            {/* Vouchers File */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileSpreadsheet className="w-5 h-5 text-cyan-400" />
                <div>
                  <div className="text-xs font-bold text-white">1. 企业记账凭证表 (Excel: .xlsx)</div>
                  <div className="text-[11px] text-slate-400">必填列: 凭证号、记账日期、科目编码、科目名称、借方金额、贷方金额</div>
                </div>
              </div>
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setVouchersFile(e.target.files?.[0] || null)}
                className="text-xs text-slate-300 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:bg-cyan-500/20 file:text-cyan-300 hover:file:bg-cyan-500/30 cursor-pointer"
              />
            </div>

            {/* Invoices File */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Receipt className="w-5 h-5 text-purple-400" />
                <div>
                  <div className="text-xs font-bold text-white">2. 增值税发票清单 (CSV: .csv)</div>
                  <div className="text-[11px] text-slate-400">必填列: 发票号码、开票日期、购买方名称、销售方名称、价税合计</div>
                </div>
              </div>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setInvoicesFile(e.target.files?.[0] || null)}
                className="text-xs text-slate-300 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:bg-purple-500/20 file:text-purple-300 hover:file:bg-purple-500/30 cursor-pointer"
              />
            </div>

            {/* Bank Flows File */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Landmark className="w-5 h-5 text-blue-400" />
                <div>
                  <div className="text-xs font-bold text-white">3. 银行对账单明细 (CSV: .csv)</div>
                  <div className="text-[11px] text-slate-400">必填列: 交易流水号、交易时间、对手方户名、交易金额、附言</div>
                </div>
              </div>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setBankFlowsFile(e.target.files?.[0] || null)}
                className="text-xs text-slate-300 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:bg-blue-500/20 file:text-blue-300 hover:file:bg-blue-500/30 cursor-pointer"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/10">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={uploading}
              className="px-5 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/25 active:scale-95 transition-all"
            >
              {uploading ? '解析校验中...' : '提交并加载账套'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
