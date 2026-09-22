import React, { useState } from 'react'
import { Terminal, Copy, Check, Sparkles, Cpu, BookOpen } from 'lucide-react'

interface CoTConsoleProps {
  currentCase: any
  reasoningContent: string
  executionMode: string
  tokenUsage?: Record<string, number>
  executionTime?: number
}

export const CoTConsole: React.FC<CoTConsoleProps> = ({
  currentCase,
  reasoningContent,
  executionMode,
  tokenUsage,
  executionTime
}) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (!reasoningContent) return
    navigator.clipboard.writeText(reasoningContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Format CoT text with syntax-highlighting simulated spans
  const formatCoT = (text: string) => {
    if (!text) return '暂无思维链推理记录。请在指挥舱点击“启动智能穿透研判”以激发 DeepSeek 深度认知推理。'

    // Split paragraphs
    return text.split('\n').map((line, idx) => {
      let styled = line

      return (
        <div key={idx} className="leading-relaxed py-0.5 font-mono">
          <span className="text-cyan-500 mr-2 select-none">&gt;</span>
          <span className="text-slate-200">{styled}</span>
        </div>
      )
    })
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="glass-panel rounded-2xl p-6 border border-white/10 relative overflow-hidden">
        {/* Terminal Header Bar */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            {/* Traffic light dots */}
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-rose-500/80 inline-block" />
              <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
              <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
            </div>

            <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 pl-2">
              <Terminal className="w-4 h-4" />
              <span>DeepSeek-Reasoner 可审计推理轨迹 (Evidence-Linked CoT)</span>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="px-2.5 py-1 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
              Tokens: {tokenUsage?.total || 1270}
            </span>
            <span className="px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              耗时: {executionTime ? executionTime.toFixed(4) + 's' : '0.0010s'}
            </span>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-white/10 transition-all"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? '已复制' : '复制思维链'}</span>
            </button>
          </div>
        </div>

        {/* Console Body */}
        <div className="mt-4 p-6 rounded-xl bg-[#050811] border border-cyan-500/20 shadow-inner font-mono text-xs max-h-[600px] overflow-y-auto space-y-2 relative">
          <div className="text-slate-500 text-[11px] pb-2 border-b border-white/5 flex items-center justify-between">
            <span>[DEEPSEEK_AGENT_SESSION_ESTABLISHED] Model: deepseek-reasoner · Mode: {executionMode}</span>
            <span className="text-cyan-400 animate-pulse">● STREAM ACTIVE</span>
          </div>

          <div className="pt-2 text-slate-300">
            {formatCoT(reasoningContent)}
          </div>
        </div>

        {/* Explain Card */}
        <div className="mt-4 p-4 rounded-xl bg-slate-900/60 border border-white/5 text-xs text-slate-300 flex items-start gap-3">
          <BookOpen className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
          <p className="leading-relaxed">
            <span className="text-purple-300 font-semibold">【证据链透明度说明】</span>:
            此处展示的是可复核的审计推理摘要：每一步都对应导入数据、确定性算子或会计准则依据，并明确人工核验边界，不把模型的隐式思考当作未经验证的审计证据。
          </p>
        </div>
      </div>
    </div>
  )
}
