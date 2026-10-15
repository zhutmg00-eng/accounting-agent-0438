import React, { useEffect, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { Btn, DataValue, EmptyState, Panel, StatRow, Surface, toneOfVerdict } from '../ui/primitives'
import { Reveal } from '../ui/motion'

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

  const streamRef = useRef<HTMLPreElement | null>(null)

  const handleCopy = () => {
    if (!reasoningContent) return
    navigator.clipboard.writeText(reasoningContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const hasReasoning = Boolean(reasoningContent)

  const totalTokens = tokenUsage?.total ?? 0
  const elapsedSeconds = executionTime ?? 0

  const modeText = String(executionMode || '').toLowerCase()
  const isLiveMode = modeText.includes('live') || modeText.includes('real') || modeText.includes('api')

  // The stream is the one move this screen has: it follows its own tail.
  useEffect(() => {
    const el = streamRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [reasoningContent])

  // Copy path keeps the payload as plain text; the view marks each line
  // instead of re-wrapping the reasoning in terminal chrome.
  const formatCoT = (text: string) => {
    if (!text) return ''

    // Split paragraphs
    return text.split('\n').map((line, idx) => (
      <div key={idx} className="flex gap-3 py-0.5">
        <span className="shrink-0 select-none text-fg-faint">&gt;</span>
        <span className="min-w-0 whitespace-pre-wrap break-words text-fg">{line}</span>
      </div>
    ))
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto px-4 py-5 sm:px-6 sm:py-8">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
        <Reveal index={0}>
          <Panel
            title="思维链演播 · Chain-of-Thought"
            note="DeepSeek 推理原始载荷，逐字到达并停在此处，不做改写。"
            meta={
              hasReasoning ? (
                <span className="inline-flex items-center gap-2 text-fg-muted">
                  <span aria-hidden className="inline-block h-2 w-2 shrink-0 bg-seal" />
                  推理流接收中
                </span>
              ) : (
                <span className="text-fg-faint">推理流未开始</span>
              )
            }
            bare
          >
            <StatRow>
              <DataValue
                label="Token 用量"
                value={totalTokens > 0 ? totalTokens.toLocaleString('zh-CN') : '0'}
                unit="tokens"
                tone={toneOfVerdict(hasReasoning ? 'clear' : '')}
                size="display"
              />
              <DataValue
                label="执行耗时"
                value={elapsedSeconds > 0 ? Math.round(elapsedSeconds * 1000) : 0}
                unit="ms"
                size="body"
              />
              <DataValue label="执行引擎" value={isLiveMode ? '真实 API' : 'MOCK 启发式'} size="body" />
              <DataValue
                label="推理行数"
                value={hasReasoning ? reasoningContent.split('\n').length : 0}
                unit="行"
                size="body"
              />
            </StatRow>
          </Panel>
        </Reveal>

        <Reveal index={1}>
          <Panel
            title="推理原文载荷"
            note="这是模型给出的字面代码，因此它是全站唯一使用等宽字体的区块。"
            meta={
              <Btn size="sm" onClick={handleCopy} disabled={hasReasoning ? undefined : true}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? '已复制' : '复制原文'}
              </Btn>
            }
            bare
          >
            {hasReasoning ? (
              <pre
                ref={streamRef}
                role="log"
                aria-live="polite"
                aria-label="模型推理原文"
                className="m-0 max-h-[min(560px,70svh)] overflow-y-auto bg-field-sunken px-5 pb-5 text-label leading-relaxed"
              >
                <code className="block">
                  <span className="block bg-field-sunken pb-3 pt-4 text-label text-fg-faint">
                    [DEEPSEEK_AGENT_SESSION] model: deepseek-reasoner · mode: {isLiveMode ? 'live' : 'mock'} · payload: reasoning_content
                  </span>
                  {formatCoT(reasoningContent)}
                </code>
              </pre>
            ) : (
              <EmptyState
                title="还没有可回看的推理流"
                body="运行审计后，模型的推理过程会在这里逐字展开：先落款识别，再逐条穿透凭证、发票与流水。在指挥舱执行「启动智能穿透研判」后回到本页即可回看。"
              />
            )}
          </Panel>
        </Reveal>

        <Reveal index={2}>
          <Surface level="raised2" className="px-5 pb-5 pt-5">
            <h3 className="text-title font-semibold text-fg">思维链透明度与可解释性</h3>
            <p className="mt-2 max-w-[75ch] text-body text-fg">
              区别于传统「黑盒」模型，DeepSeek-AuditMind 完整输出了对于记账凭证摘要、发票税率偏差及银行存单真伪的逐步推理证据。评委可随时调阅大模型如何援引《企业会计准则第14号——收入》五步法模型及中国证监会行政处罚先例做出审慎定性。
            </p>
          </Surface>
        </Reveal>
      </div>
    </div>
  )
}
