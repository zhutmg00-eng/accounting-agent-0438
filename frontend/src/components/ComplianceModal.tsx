import React, { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { Btn, Chip, StatusMark, cn } from '../ui/primitives'
import { useFocusTrap } from '../lib/useFocusTrap'
import { ComplianceManifest, CpaApprovalReceipt } from '../types'

interface ComplianceModalProps {
  isOpen: boolean
  onClose: () => void
  currentCaseId?: string
  onCaseSanitized?: () => void
}

/**
 * The same sign-off the workpaper sheet performs, repeated for one case: same
 * signer, same certificate number, same declared basis, so the modal and the
 * workpaper sheet quote one CPA rather than two.
 */
const SIGNER = {
  auditor_name: '',
  cert_no: '',
  audit_firm: '数智会计联合审计项目组',
  opinion_type: '保留意见/拟追加外部银行函证',
  professional_skepticism_notes:
    '已秉持职业怀疑态度，全面复核确定性算子三单倒挂天数与Beneish操纵指数，认可智能体证据链，拟针对可疑关联方实施外部独立银行函证。',
  compliance_confirmed: true
}

interface Notice {
  text: string
  bad: boolean
}

const Field: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="min-w-0">
    <div className="text-label text-fg-muted">{label}</div>
    <div className="mt-1 text-body text-fg">{value}</div>
  </div>
)

/**
 * The whitepaper overlay. A real overlay, so it carries `shadow-overlay` and a
 * flat scrim - nothing else: the panel is square, the room stays dark, and the
 * surface that holds ink is the paper band of legal bases. The one accent is
 * the sign-off that turns the paper into a case record.
 */
export const ComplianceModal: React.FC<ComplianceModalProps> = ({
  isOpen,
  onClose,
  currentCaseId,
  onCaseSanitized
}) => {
  const [manifest, setManifest] = useState<ComplianceManifest | null>(null)
  const [loading, setLoading] = useState(false)
  const [receipt, setReceipt] = useState<CpaApprovalReceipt | null>(null)
  const [signing, setSigning] = useState(false)
  const [signNotice, setSignNotice] = useState<Notice | null>(null)
  const [sanitizing, setSanitizing] = useState(false)
  const [sanitizeNotice, setSanitizeNotice] = useState<Notice | null>(null)

  const panelRef = useRef<HTMLDivElement>(null)

  // A receipt names exactly one case; switching case retires the old one.
  useEffect(() => {
    setReceipt(null)
    setSignNotice(null)
  }, [currentCaseId])

  const fetchManifest = async () => {
    setLoading(true)
    try {
      const resp = await fetch('/api/compliance/manifest')
      if (resp.ok) {
        setManifest(await resp.json())
      }
    } catch (error) {
      console.error('Failed to load compliance manifest', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSignOff = async () => {
    if (!currentCaseId) return
    setSigning(true)
    setSignNotice(null)
    try {
      const resp = await fetch('/api/compliance/cpa-approval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: currentCaseId, ...SIGNER })
      })
      if (!resp.ok) {
        setSignNotice({ text: `签章服务返回 ${resp.status}，本案例回执未签发。`, bad: true })
        return
      }
      setReceipt(await resp.json())
    } catch (error) {
      console.error('CPA sign-off failed', error)
      setSignNotice({ text: '签章服务未响应，本案例回执未签发。', bad: true })
    } finally {
      setSigning(false)
    }
  }

  const handleSanitizeCase = async () => {
    if (!currentCaseId) return
    setSanitizing(true)
    setSanitizeNotice(null)
    try {
      const resp = await fetch(`/api/compliance/sanitize-case/${currentCaseId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      if (resp.ok) {
        const data = await resp.json()
        setSanitizeNotice({ text: data.message || '脱敏完成：账号、对手与流水已掩码。', bad: false })
        onCaseSanitized?.()
      } else {
        setSanitizeNotice({ text: `脱敏请求被拒绝（${resp.status}）。`, bad: true })
      }
    } catch (error) {
      console.error('Sanitize request failed', error)
      setSanitizeNotice({ text: '脱敏请求未送达，网络异常。', bad: true })
    } finally {
      setSanitizing(false)
    }
  }

  useEffect(() => {
    if (isOpen) fetchManifest()
  }, [isOpen])

  // Real overlay, real focus handling: focus moves into the panel on open, Tab
  // cycles inside it, Escape closes, and focus returns to the trigger on close.
  useFocusTrap(isOpen, onClose, { dialogRef: panelRef, panelRef })

  if (!isOpen) return null

  const footerStatus = receipt
    ? `回执 ${receipt.receipt_id} · 签署于 ${receipt.sign_timestamp}`
    : currentCaseId
      ? `待签收 · 签字人 ${SIGNER.auditor_name} · 执业证书 ${SIGNER.cert_no}`
      : '未选定案卷，回执按案卷逐份签发'

  return (
    <div
      className="fixed inset-0 z-modal flex items-start justify-center bg-black/70 p-3 sm:items-center sm:p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="compliance-modal-title"
        tabIndex={-1}
        className="flex max-h-[88svh] w-full max-w-5xl flex-col overflow-hidden overscroll-contain bg-field-raised shadow-overlay"
      >
        <header className="flex items-start justify-between gap-6 bg-field-raised2 px-6 py-5">
          <h2 id="compliance-modal-title" className="text-title font-semibold text-fg">
            {manifest ? manifest.title : '数智会计伦理、合规与数据安全白皮书'}
          </h2>
          <div className="flex shrink-0 items-center gap-3">
            {manifest ? (
              <span className="hidden text-small text-fg-muted lg:inline">版本 {manifest.version}</span>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭面板"
              className="press -mt-1 -mr-1 p-2 text-fg-muted hover:bg-field-raised3 hover:text-fg"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto overscroll-contain">
          {loading && !manifest ? (
            <p role="status" aria-live="polite" className="max-w-[70ch] px-6 py-8 text-body text-fg-muted">
              正在读取白皮书内容…
            </p>
          ) : (
            <>
              <section className="px-6 pt-6 pb-8">
                <h3 className="text-body font-semibold text-fg">治理支柱</h3>
                <ul className="mt-5 space-y-10">
                  {manifest?.governance_pillars.map((pillar, index) => (
                    <li key={index} className="max-w-[70ch]">
                      <h4 className="text-title font-semibold text-fg">{pillar.pillar}</h4>
                      <p className="mt-2 text-body text-fg">{pillar.summary}</p>
                      <ul className="mt-3 space-y-2.5">
                        {pillar.details.map((detail, detailIndex) => (
                          <li key={detailIndex} className="flex gap-3">
                            <span aria-hidden className="mt-[9px] h-1.5 w-1.5 shrink-0 bg-fg-faint" />
                            <span className="text-body text-fg">{detail}</span>
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="bg-paper text-ink">
                <div className="flex flex-wrap items-baseline justify-between gap-4 px-6 pt-6">
                  <h3 className="text-body font-semibold text-ink">合规依据与执业准则</h3>
                  <span className="text-small text-ink-muted tabular-nums">
                    {manifest ? `${manifest.compliance_standards.length} 项` : ''}
                  </span>
                </div>
                <ol className="mt-4 pb-6">
                  {manifest?.compliance_standards.map((standard, index) => (
                    <li
                      key={index}
                      className={cn('flex gap-4 px-6 py-4', index % 2 === 1 && 'bg-paper-deep')}
                    >
                      <span className="w-5 shrink-0 text-small text-ink-muted tabular-nums">
                        {index + 1}
                      </span>
                      <span className="text-body text-ink">{standard}</span>
                    </li>
                  ))}
                </ol>
              </section>

              <section className="bg-field-raised2 px-6 py-6">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <h3 className="text-body font-semibold text-fg">CPA 电子签收回执</h3>
                  {receipt ? (
                    <Chip filled tone={receipt.status === 'APPROVED_BY_CPA' ? 'clear' : 'medium'}>
                      {receipt.status}
                    </Chip>
                  ) : (
                    <Chip>尚未签发</Chip>
                  )}
                </div>

                {receipt ? (
                  <>
                    <div className="mt-5 max-w-[70ch]">
                      <div className="text-small text-fg-muted">签字注册会计师</div>
                      <div className="mt-1 text-title font-semibold text-fg">{receipt.auditor_name}</div>
                      <div className="mt-1 text-small text-fg-muted">
                        执业证书编号 {receipt.cert_no} · {receipt.audit_firm}
                      </div>
                    </div>

                    <div className="mt-5 grid gap-x-8 gap-y-4 sm:grid-cols-2">
                      <Field label="回执编号" value={receipt.receipt_id} />
                      <Field label="案卷编号" value={receipt.case_id} />
                      <Field label="签署时间" value={receipt.sign_timestamp} />
                      <Field label="审计意见类型" value={receipt.opinion_type} />
                    </div>

                    <div className="mt-5 bg-field-sunken px-5 py-4">
                      <div className="text-label text-fg-muted">验证摘要 · SHA-256 前 24 位</div>
                      <code className="mt-2 block break-all font-mono text-body text-fg">
                        {receipt.verification_hash}
                      </code>
                      <p className="mt-2 text-body text-fg">
                        回执编号由该摘要前 8 位与签发日期派生，可在签章服务中复核。
                      </p>
                    </div>

                    <div className="mt-5 max-w-[70ch]">
                      <div className="text-label text-fg-muted">职业道德与独立性声明</div>
                      <p className="mt-2 text-body text-fg">{receipt.ethical_declaration}</p>
                    </div>
                  </>
                ) : (
                  <div className="mt-4 max-w-[70ch]">
                    <p className="text-body text-fg">
                      本案例尚未签发 CPA 电子签收回执。签署后由合规签章服务按案卷标识生成验证摘要，摘要一经签发即固定。
                    </p>
                    <div aria-live="polite">
                      {signNotice ? (
                        <p className="mt-3 flex items-center gap-2.5 text-body text-fg">
                          <StatusMark tone={signNotice.bad ? 'high' : 'clear'} />
                          {signNotice.text}
                        </p>
                      ) : null}
                    </div>
                  </div>
                )}
              </section>

              {currentCaseId ? (
                <section className="bg-field-sunken px-6 py-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="max-w-[70ch]">
                      <h3 className="text-body font-semibold text-fg">本案数据脱敏</h3>
                      <p className="mt-1 text-body text-fg">
                        对案卷 {currentCaseId} 的凭证账号、交易对手与流水按首 4 位、尾 4 位掩码脱敏。
                      </p>
                    </div>
                    <Btn variant="quiet" disabled={sanitizing} onClick={handleSanitizeCase}>
                      {sanitizing ? '脱敏处理中…' : '一键应用脱敏防护'}
                    </Btn>
                  </div>
                  <div aria-live="polite">
                    {sanitizeNotice ? (
                      <p className="mt-3 flex items-center gap-2.5 text-body text-fg">
                        <StatusMark tone={sanitizeNotice.bad ? 'high' : 'clear'} />
                        {sanitizeNotice.text}
                      </p>
                    ) : null}
                  </div>
                </section>
              ) : null}
            </>
          )}
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-4 bg-field-raised2 px-6 py-4">
          <p className="flex items-center gap-2.5 text-body text-fg">
            <StatusMark tone={receipt ? 'clear' : 'neutral'} />
            {footerStatus}
          </p>
          {receipt || !currentCaseId ? (
            <Btn variant="quiet" onClick={onClose}>
              关闭白皮书
            </Btn>
          ) : (
            <Btn variant="primary" disabled={signing} onClick={handleSignOff}>
              {signing ? '签发处理中…' : '确认伦理声明并签署回执'}
            </Btn>
          )}
        </footer>
      </div>
    </div>
  )
}
