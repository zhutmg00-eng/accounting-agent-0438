import React, { useId, useRef, useState } from 'react'
import { X, FileSpreadsheet, Receipt, Landmark, Download } from 'lucide-react'
import { Btn, ErrorNote, Surface } from '../ui/primitives'
import { useFocusTrap } from '../lib/useFocusTrap'

interface CustomUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onCaseImported: (caseData: any) => void
}

/** The three upload slots, described by the columns the parser actually needs. */
const SLOTS = [
  {
    key: 'vouchers' as const,
    order: '凭证',
    title: '企业记账凭证表',
    accept: '.xlsx,.xls',
    hint: '必填列：凭证号、记账日期、科目编码、科目名称、借方金额、贷方金额',
    Icon: FileSpreadsheet
  },
  {
    key: 'invoices' as const,
    order: '发票',
    title: '增值税发票清单',
    accept: '.csv',
    hint: '必填列：发票号码、开票日期、购买方名称、销售方名称、价税合计',
    Icon: Receipt
  },
  {
    key: 'bank_flows' as const,
    order: '流水',
    title: '银行对账单明细',
    accept: '.csv',
    hint: '必填列：交易流水号、交易时间、对手方户名、交易金额、附言',
    Icon: Landmark
  }
]

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

  const panelRef = useRef<HTMLDivElement>(null)
  const dialogTitleId = useId()

  // The overlay owes a keyboard user the same contract the whitepaper modal
  // keeps: focus enters the panel, Tab stays inside it, Escape closes it and
  // focus goes back to 导入实测账套.
  useFocusTrap(isOpen, onClose, { dialogRef: panelRef, panelRef })

  const handleDownloadTemplate = (type: 'vouchers' | 'invoices' | 'bank_flows') => {
    window.open(`/api/templates/download/${type}`, '_blank')
  }

  if (!isOpen) return null

  const selectedFiles: Record<'vouchers' | 'invoices' | 'bank_flows', File | null> = {
    vouchers: vouchersFile,
    invoices: invoicesFile,
    bank_flows: bankFlowsFile
  }

  const selectFile = (type: 'vouchers' | 'invoices' | 'bank_flows', file: File | null) => {
    if (type === 'vouchers') setVouchersFile(file)
    if (type === 'invoices') setInvoicesFile(file)
    if (type === 'bank_flows') setBankFlowsFile(file)
  }

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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={dialogTitleId}
        tabIndex={-1}
        className="flex max-h-[92svh] w-full max-w-2xl flex-col overflow-hidden overscroll-contain bg-field-raised shadow-overlay"
      >
        <div className="flex items-start justify-between gap-6 px-5 pt-5 pb-4">
          <div className="min-w-0">
            <h2 id={dialogTitleId} className="text-title font-semibold text-fg">
              导入真实企业财务文件
            </h2>
            <p className="mt-1 max-w-[60ch] text-body text-fg">
              三张表齐备时穿透最完整。缺一张也能导入，对应算子会在穿透阶段标记为无数据。
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭导入浮层"
            className="press -mr-2 -mt-1 shrink-0 p-2 text-fg-muted hover:bg-field-raised2 hover:text-fg"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex min-h-0 flex-col">
          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-5 pb-5">
            {uploadError ? <ErrorNote title="导入失败" detail={uploadError} /> : null}

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label htmlFor="upload-company-name" className="mb-1.5 block text-label text-fg-muted">
                  受审公司全称
                </label>
                <input
                  id="upload-company-name"
                  name="company-name"
                  type="text"
                  autoComplete="off"
                  spellCheck={false}
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="min-h-[40px] w-full border border-white/10 bg-field-sunken px-3 text-small text-fg placeholder:text-fg-faint"
                />
              </div>

              <div>
                <label htmlFor="upload-stock-code" className="mb-1.5 block text-label text-fg-muted">
                  股票代码 / 账套编号
                </label>
                <input
                  id="upload-stock-code"
                  name="stock-code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  spellCheck={false}
                  value={stockCode}
                  onChange={(e) => setStockCode(e.target.value)}
                  className="min-h-[40px] w-full border border-white/10 bg-field-sunken px-3 text-small tabular-nums text-fg placeholder:text-fg-faint"
                />
              </div>

              <div>
                <label htmlFor="upload-industry" className="mb-1.5 block text-label text-fg-muted">
                  所属行业领域
                </label>
                <input
                  id="upload-industry"
                  name="industry"
                  type="text"
                  autoComplete="off"
                  spellCheck={false}
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  className="min-h-[40px] w-full border border-white/10 bg-field-sunken px-3 text-small text-fg placeholder:text-fg-faint"
                />
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-baseline justify-between gap-4">
                <h3 className="text-label text-fg-muted">待导入文件</h3>
                <span className="text-label text-fg-faint">支持 .xlsx / .xls / .csv</span>
              </div>

              {SLOTS.map((slot) => {
                const chosen = selectedFiles[slot.key]
                return (
                  <Surface key={slot.key} level="raised2" className="px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
                      <div className="flex min-w-0 items-start gap-3">
                        <slot.Icon aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-fg-muted" />
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                            <span className="text-small font-semibold text-fg">
                              {slot.order} · {slot.title}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleDownloadTemplate(slot.key)}
                              className="inline-flex items-center gap-1 text-label text-fg-muted underline decoration-white/20 underline-offset-4 hover:text-seal"
                            >
                              <Download aria-hidden className="h-3.5 w-3.5" />
                              下载标准模板
                            </button>
                          </div>
                          <p className="mt-1 max-w-[52ch] text-label text-fg-muted">{slot.hint}</p>
                          <p className="mt-1 text-label text-fg-faint">
                            {chosen ? `已选择：${chosen.name}` : '尚未选择文件'}
                          </p>
                        </div>
                      </div>

                      <input
                        type="file"
                        name={`${slot.key}-files`}
                        aria-label={`选择${slot.title}文件`}
                        accept={slot.accept}
                        onChange={(e) => selectFile(slot.key, e.target.files?.[0] || null)}
                        className="cursor-pointer text-label text-fg-muted file:mr-3 file:cursor-pointer file:border-0 file:bg-field-raised3 file:px-3 file:py-2 file:text-label file:font-medium file:text-fg hover:file:bg-field-raised"
                      />
                    </div>
                  </Surface>
                )
              })}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 bg-field-raised px-5 py-4">
            <Btn type="button" variant="ghost" onClick={onClose}>
              取消
            </Btn>
            <Btn type="submit" variant="primary" disabled={uploading ? true : undefined}>
              {uploading ? '解析校验中…' : '提交并加载账套'}
            </Btn>
          </div>
        </form>
      </div>
    </div>
  )
}
