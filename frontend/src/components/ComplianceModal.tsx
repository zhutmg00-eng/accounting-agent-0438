import React, { useState, useEffect } from 'react'
import {
  ShieldCheck,
  Lock,
  UserCheck,
  Scale,
  FileText,
  CheckCircle2,
  AlertCircle,
  X,
  Sparkles,
  ExternalLink
} from 'lucide-react'
import { ComplianceManifest } from '../types'

interface ComplianceModalProps {
  isOpen: boolean
  onClose: () => void
  currentCaseId?: string
  onCaseSanitized?: () => void
}

export const ComplianceModal: React.FC<ComplianceModalProps> = ({
  isOpen,
  onClose,
  currentCaseId,
  onCaseSanitized
}) => {
  const [manifest, setManifest] = useState<ComplianceManifest | null>(null)
  const [loading, setLoading] = useState(false)
  const [sanitizing, setSanitizing] = useState(false)
  const [sanitizeMsg, setSanitizeMsg] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      fetchManifest()
    }
  }, [isOpen])

  const fetchManifest = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/compliance/manifest')
      if (res.ok) {
        const data = await res.json()
        setManifest(data)
      }
    } catch (e) {
      console.error('Failed to fetch compliance manifest', e)
    } finally {
      setLoading(false)
    }
  }

  const handleSanitizeCase = async () => {
    if (!currentCaseId) return
    setSanitizing(true)
    setSanitizeMsg(null)
    try {
      const res = await fetch(`/api/compliance/sanitize-case/${currentCaseId}`, {
        method: 'POST'
      })
      if (res.ok) {
        const data = await res.json()
        setSanitizeMsg(data.message || '已成功启用隐私脱敏防护！')
        if (onCaseSanitized) {
          onCaseSanitized()
        }
      } else {
        setSanitizeMsg('脱敏处理失败，请稍后重试。')
      }
    } catch (e) {
      setSanitizeMsg('网络异常，脱敏请求未送达。')
    } finally {
      setSanitizing(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-slate-900 border border-emerald-500/30 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-slate-100 font-sans">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-emerald-500/20 bg-slate-950/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-wide">
                  数智会计伦理、合规与数据安全白皮书
                </h2>
                <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  六大评审核心维度
                </span>
              </div>
              <p className="text-xs text-slate-400">
                对齐《数据安全法》《个人信息保护法》与中注协职业道德守则
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Quick Action: Sanitize Current Case */}
          {currentCaseId && (
            <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/40 via-slate-900 to-slate-900 border border-emerald-500/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Lock className="w-5 h-5 text-emerald-400" />
                <div>
                  <div className="text-sm font-semibold text-emerald-300">
                    当前案例数据脱敏盾 (Privacy Guard)
                  </div>
                  <div className="text-xs text-slate-400">
                    一键对当前案例凭证账号、交易对手及流水实施掩码脱敏（首4尾4）
                  </div>
                </div>
              </div>
              <button
                onClick={handleSanitizeCase}
                disabled={sanitizing}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-900/40 transition-all flex items-center gap-1.5 disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                {sanitizing ? '脱敏中...' : '一键应用脱敏防护'}
              </button>
            </div>
          )}

          {sanitizeMsg && (
            <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span>{sanitizeMsg}</span>
            </div>
          )}

          {/* Pillars */}
          {manifest?.governance_pillars.map((p, idx) => {
            const icons = [UserCheck, Lock, Scale]
            const Icon = icons[idx % icons.length]
            return (
              <div
                key={idx}
                className="p-5 rounded-xl bg-slate-950/50 border border-white/5 hover:border-emerald-500/20 transition-all"
              >
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                    <Icon className="w-4 h-4" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-100">
                    {p.pillar}
                  </h3>
                </div>
                <p className="text-xs text-emerald-400/90 font-medium mb-3">
                  {p.summary}
                </p>
                <ul className="space-y-2">
                  {p.details.map((d, dIdx) => (
                    <li
                      key={dIdx}
                      className="text-xs text-slate-300 flex items-start gap-2 leading-relaxed"
                    >
                      <span className="text-emerald-500 mt-0.5">•</span>
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}

          {/* Standards Footer */}
          <div className="p-4 rounded-xl bg-slate-950/70 border border-white/5">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-emerald-400" />
              法律法规与准则合规依据
            </h4>
            <div className="flex flex-wrap gap-2">
              {manifest?.compliance_standards.map((s, sIdx) => (
                <span
                  key={sIdx}
                  className="px-2.5 py-1 text-[11px] rounded-md bg-white/5 text-slate-300 border border-white/10"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-white/10 bg-slate-950/90 flex justify-between items-center text-xs text-slate-400">
          <span>AI 辅助初筛 · 注册会计师终局法定负责制</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors"
          >
            关闭面板
          </button>
        </div>
      </div>
    </div>
  )
}
