import React, { useState, useRef, useEffect } from 'react'
import {
  Bot,
  Send,
  Sparkles,
  Zap,
  Terminal,
  Layers,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  Play,
  RefreshCw,
  Search,
  Landmark,
  ChevronDown,
  ChevronUp,
  Cpu,
  BrainCircuit,
  CornerDownLeft
} from 'lucide-react'
import {
  AgentMessage,
  AgentToolCall,
  AgentGoalStep,
  DeepSeekModelsResponse,
  AccountingVoucher,
  BankFlowRecord
} from '../types'

interface AgentWorkbenchProps {
  currentCase: any
  executionMode: string
  modelInfo: DeepSeekModelsResponse | null
  onOpenModelModal: () => void
}

export const AgentWorkbench: React.FC<AgentWorkbenchProps> = ({
  currentCase,
  executionMode,
  modelInfo,
  onOpenModelModal
}) => {
  const [messages, setMessages] = useState<AgentMessage[]>([
    {
      id: 'msg-init',
      role: 'assistant',
      content: `您好！我是由 **DeepSeek-AuditMind** 驱动的数智会计与舞弊穿透智能体（中国注册会计师 / 资深数智审计专家）。\n\n已成功载入被审计单位 **${currentCase?.company_name || '企业账套'} (${currentCase?.stock_code || '---'})**。\n我可以直接调用底层的 **Beneish M-Score 8 因子操纵模型**、**业财三单勾稽穿透核对** 以及 **凭证流水多维检索算子**，帮助您穿透核实经济业务实质。请随时向我提问，或点击左侧的审计算子与自主目标！`,
      timestamp: new Date().toLocaleTimeString()
    }
  ])

  const [inputPrompt, setInputPrompt] = useState('')
  const [toolsEnabled, setToolsEnabled] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [expandedCoT, setExpandedCoT] = useState<Record<string, boolean>>({})

  // Goal Mode State (/goal)
  const [isRunningGoal, setIsRunningGoal] = useState(false)
  const [goalSteps, setGoalSteps] = useState<AgentGoalStep[]>([])
  const [goalSummary, setGoalSummary] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isGenerating, goalSteps])

  // Reset messages when case changes
  useEffect(() => {
    if (!currentCase) return
    setMessages([
      {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: `已切换被审计单位为 **${currentCase.company_name} (${currentCase.stock_code})**。\n当前已解析记账凭证 ${currentCase.vouchers?.length || 0} 笔、发票 ${currentCase.invoices?.length || 0} 张、银行流水 ${currentCase.bank_flows?.length || 0} 笔。\n您可以让我执行全套业财三单勾稽、测算 Beneish 指数，或自主执行端到端舞弊穿透目标！`,
        timestamp: new Date().toLocaleTimeString()
      }
    ])
    setGoalSteps([])
    setGoalSummary(null)
  }, [currentCase?.case_id])

  const handleSendMessage = async (customText?: string) => {
    const text = (customText || inputPrompt).trim()
    if (!text || isGenerating || !currentCase) return

    const userMsgId = `user-${Date.now()}`
    const newMessages: AgentMessage[] = [
      ...messages,
      {
        id: userMsgId,
        role: 'user',
        content: text,
        timestamp: new Date().toLocaleTimeString()
      }
    ]

    setMessages(newMessages)
    setInputPrompt('')
    setIsGenerating(true)

    // Build chat history for backend
    const apiMessages = newMessages.map((m) => ({
      role: m.role,
      content: m.content
    }))

    try {
      const resp = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: currentCase.case_id,
          messages: apiMessages,
          tools_enabled: toolsEnabled,
          mode: executionMode,
          temperature: 0.2
        })
      })

      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || `请求失败 (${resp.status})`)
      }

      const replyData = await resp.json()
      const assistantMsgId = `asst-${Date.now()}`

      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          role: 'assistant',
          content: replyData.content || '未返回有效意见',
          reasoning_content: replyData.reasoning_content,
          tool_calls: replyData.tool_calls || [],
          timestamp: new Date().toLocaleTimeString()
        }
      ])

      if (replyData.reasoning_content) {
        setExpandedCoT((prev) => ({ ...prev, [assistantMsgId]: true }))
      }
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ **智能体交互异常**：${e.message}\n请检查网络连接、API 状态或切换为 MOCK 模式重试。`,
          timestamp: new Date().toLocaleTimeString()
        }
      ])
    } finally {
      setIsGenerating(false)
    }
  }

  // Trigger Autonomous Goal (/goal)
  const handleRunGoal = async () => {
    if (isRunningGoal || !currentCase) return
    setIsRunningGoal(true)
    setGoalSteps([
      { step: 1, title: '审计目标规划与全模态账套画像', status: 'running', detail: '正在分析目标，构建凭证与流水图谱...' },
      { step: 2, title: '确定性审计算子矩阵调度', status: 'pending', detail: '等待调度 Beneish 与三单勾稽算子...' },
      { step: 3, title: 'DeepSeek 大模型准则深度定性', status: 'pending', detail: '等待 CAS 准则比对...' },
      { step: 4, title: '三层证据审计底稿与结论合成', status: 'pending', detail: '等待底稿生成...' },
    ])

    try {
      const resp = await fetch('/api/agent/goal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: currentCase.case_id,
          goal: '执行端到端全量舞弊穿透审计与底稿生成',
          mode: executionMode
        })
      })

      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || '目标执行失败')
      }

      const data = await resp.json()
      setGoalSteps(data.steps || [])
      setGoalSummary(
        `🎯 **自主目标执行完成**（耗时 ${data.elapsed_seconds}s | ${data.model_name}）\n` +
        `识别风险发现：${data.report?.findings?.length || 0} 项，生成标准工作底稿：${data.report?.workpapers?.length || 0} 份。`
      )

      // Add summary message into conversation
      setMessages((prev) => [
        ...prev,
        {
          id: `goal-${Date.now()}`,
          role: 'assistant',
          content: `### 🎯 自主审计目标执行完成 (/goal)\n\n**审计意见概要**：\n${data.report?.executive_summary || '已完成端到端审计。'}\n\n` +
            `**综合风险评级**：\`${data.report?.overall_risk_rating || 'CLEAN'}\`\n\n` +
            `可前往【审计指挥舱】或【底稿与成果导出】标签页查看完整底稿并导出 Excel / PDF。`,
          reasoning_content: data.report?.reasoning_content,
          tool_calls: [
            {
              tool_name: 'calculate_beneish_m_score',
              tool_input: { case_id: currentCase.case_id },
              tool_output: data.tool_outputs?.beneish_m_score,
              status: 'success'
            },
            {
              tool_name: 'perform_three_way_reconciliation',
              tool_input: { case_id: currentCase.case_id },
              tool_output: data.tool_outputs?.three_way_reconciliation,
              status: 'success'
            }
          ],
          timestamp: new Date().toLocaleTimeString()
        }
      ])
    } catch (e: any) {
      setGoalSummary(`❌ 目标执行失败: ${e.message}`)
    } finally {
      setIsRunningGoal(false)
    }
  }

  const toggleCoT = (msgId: string) => {
    setExpandedCoT((prev) => ({ ...prev, [msgId]: !prev[msgId] }))
  }

  const quickPrompts = [
    '测算 Beneish M-Score 指数并分析操纵预警',
    '执行全套业财三单穿透勾稽，排查异常单据',
    '抽查大额记账凭证并核查分录借贷平衡',
    '核查银行流水大额对手方，排查关联方资金占用',
    '依据 CAS 14 准则编制收入确认现场核查程序建议'
  ]

  return (
    <div className="flex-1 flex overflow-hidden bg-[#080C14]">
      {/* Left Column: Domain Tools & Autonomous Goal Hub */}
      <div className="w-80 border-r border-white/10 bg-slate-950/70 flex flex-col justify-between overflow-y-auto custom-scrollbar p-4 space-y-4">
        <div className="space-y-4">
          {/* Current Case Overview Card */}
          <div className="p-3.5 rounded-xl bg-gradient-to-br from-slate-900 to-slate-900/60 border border-white/10 shadow-sm">
            <div className="text-[11px] font-medium text-slate-400 mb-1">当前被审计单位</div>
            <div className="text-sm font-bold text-white truncate font-mono">
              {currentCase?.company_name || '未选定案例'}
            </div>
            <div className="text-xs text-cyan-400 font-mono mt-0.5">
              {currentCase?.stock_code || '---'} · {currentCase?.industry || '---'}
            </div>

            <div className="grid grid-cols-3 gap-1.5 mt-3 pt-3 border-t border-white/5 text-center font-mono text-xs">
              <div className="p-1.5 rounded bg-white/5">
                <div className="text-[10px] text-slate-400">凭证</div>
                <div className="font-semibold text-slate-200">{currentCase?.vouchers?.length || 0}</div>
              </div>
              <div className="p-1.5 rounded bg-white/5">
                <div className="text-[10px] text-slate-400">发票</div>
                <div className="font-semibold text-slate-200">{currentCase?.invoices?.length || 0}</div>
              </div>
              <div className="p-1.5 rounded bg-white/5">
                <div className="text-[10px] text-slate-400">流水</div>
                <div className="font-semibold text-slate-200">{currentCase?.bank_flows?.length || 0}</div>
              </div>
            </div>
          </div>

          {/* Autonomous Goal Hub (/goal) */}
          <div className="p-3.5 rounded-xl bg-gradient-to-br from-purple-950/30 via-slate-900 to-slate-900/80 border border-purple-500/30 shadow-lg shadow-purple-500/5">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <BrainCircuit className="w-4 h-4 text-purple-400" />
                <span className="text-xs font-bold text-white font-mono">自主审计目标 (/goal)</span>
              </div>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 font-mono">
                dsh 原生升级
              </span>
            </div>
            <p className="text-[11px] text-slate-300 mb-3">
              一键触发端到端多步自主审计编排：目标规划 ➔ 算子调度 ➔ CAS 研判 ➔ 底稿生成。
            </p>

            <button
              onClick={handleRunGoal}
              disabled={isRunningGoal || !currentCase}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 text-xs font-semibold rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-md shadow-purple-500/20 border border-purple-400/30 transition-all disabled:opacity-50 active:scale-95"
            >
              {isRunningGoal ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>自主目标执行中...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>执行自主审计目标 (/goal)</span>
                </>
              )}
            </button>

            {/* Goal Steps Progress */}
            {goalSteps.length > 0 && (
              <div className="mt-3 space-y-1.5 pt-2 border-t border-white/10 text-xs font-mono">
                {goalSteps.map((s) => (
                  <div key={s.step} className="flex items-start gap-2 p-1.5 rounded bg-black/20 text-[11px]">
                    <div className="mt-0.5">
                      {s.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                      {s.status === 'running' && <RefreshCw className="w-3.5 h-3.5 text-cyan-400 animate-spin" />}
                      {s.status === 'pending' && <span className="w-3.5 h-3.5 inline-block rounded-full border border-slate-600" />}
                    </div>
                    <div className="flex-1 truncate">
                      <div className="font-medium text-slate-200">{s.title}</div>
                      <div className="text-[10px] text-slate-400 truncate">{s.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Domain Tools Matrix */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-white/10 space-y-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-white flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                审计算子工具箱
              </span>
              <span className="text-[10px] text-emerald-400 font-mono">4 项已挂载</span>
            </div>

            <button
              onClick={() => handleSendMessage('请立即调用 calculate_beneish_m_score 算子计算当前案例的 8 因子操纵指数')}
              disabled={isGenerating}
              className="w-full text-left p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 hover:border-cyan-500/30 transition-all text-xs group"
            >
              <div className="font-semibold text-slate-200 group-hover:text-cyan-300 flex items-center justify-between">
                <span>Beneish M-Score 模型</span>
                <span className="text-[10px] font-mono text-cyan-400">调用算子 ➔</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">DSRI, GMI, AQI, SGI 8 维指标刚性测算</div>
            </button>

            <button
              onClick={() => handleSendMessage('请立即调用 perform_three_way_reconciliation 算子执行业财三单穿透勾稽核对')}
              disabled={isGenerating}
              className="w-full text-left p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 hover:border-cyan-500/30 transition-all text-xs group"
            >
              <div className="font-semibold text-slate-200 group-hover:text-cyan-300 flex items-center justify-between">
                <span>三单穿透勾稽核对</span>
                <span className="text-[10px] font-mono text-cyan-400">调用算子 ➔</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">凭证 vs 合同 vs 发票 vs 银行流水闭环</div>
            </button>

            <button
              onClick={() => handleSendMessage('请检索本案例所有大额记账凭证并分析分录科目借贷平衡情况')}
              disabled={isGenerating}
              className="w-full text-left p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 hover:border-cyan-500/30 transition-all text-xs group"
            >
              <div className="font-semibold text-slate-200 group-hover:text-cyan-300 flex items-center justify-between">
                <span>记账凭证多维检索</span>
                <span className="text-[10px] font-mono text-cyan-400">调用算子 ➔</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">快速排查异常分录与无原始凭据单据</div>
            </button>

            <button
              onClick={() => handleSendMessage('请检索分析本案例银行对账单大额流水与交易对手方关联性')}
              disabled={isGenerating}
              className="w-full text-left p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 hover:border-cyan-500/30 transition-all text-xs group"
            >
              <div className="font-semibold text-slate-200 group-hover:text-cyan-300 flex items-center justify-between">
                <span>银行流水穿透排查</span>
                <span className="text-[10px] font-mono text-cyan-400">调用算子 ➔</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">识别关联方资金占用与闭环空转</div>
            </button>
          </div>
        </div>

        {/* DeepSeek Model Inspector Trigger Button */}
        <div className="pt-3 border-t border-white/10">
          <button
            onClick={onOpenModelModal}
            className="w-full flex items-center justify-between p-2.5 rounded-xl bg-cyan-950/30 hover:bg-cyan-900/40 border border-cyan-500/30 text-xs text-slate-300 transition-all group"
          >
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400 group-hover:rotate-12 transition-transform" />
              <div className="text-left font-mono">
                <div className="text-[10px] text-slate-400">自适应模型探测器</div>
                <div className="font-bold text-cyan-300 truncate max-w-[150px]">
                  {modelInfo?.active_model || 'deepseek-v4.1-flash'}
                </div>
              </div>
            </div>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
              {modelInfo?.latency_ms ? `${modelInfo.latency_ms}ms` : '探测'}
            </span>
          </button>
        </div>
      </div>

      {/* Main Conversation & CoT Reasoning Canvas */}
      <div className="flex-1 flex flex-col overflow-hidden bg-slate-950/40">
        {/* Top Mini Bar */}
        <div className="flex items-center justify-between px-6 py-2.5 border-b border-white/10 bg-slate-900/40 text-xs">
          <div className="flex items-center gap-2 font-mono">
            <Bot className="w-4 h-4 text-cyan-400" />
            <span className="font-bold text-white">DeepSeek-AuditMind Agent 对话工作台</span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-400">
              运行模式: <strong className="text-cyan-300">{executionMode}</strong>
            </span>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 cursor-pointer select-none text-xs text-slate-300">
              <input
                type="checkbox"
                checked={toolsEnabled}
                onChange={(e) => setToolsEnabled(e.target.checked)}
                className="rounded bg-slate-900 border-white/20 text-cyan-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
              />
              <span>启用审计算子调度 (Tools)</span>
            </label>
          </div>
        </div>

        {/* Message Feed */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-6">
          {messages.map((m) => {
            const isUser = m.role === 'user'
            const hasCoT = Boolean(m.reasoning_content)
            const hasTools = Boolean(m.tool_calls && m.tool_calls.length > 0)
            const isCoTExpanded = expandedCoT[m.id]

            return (
              <div
                key={m.id}
                className={`flex gap-4 max-w-4xl ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
              >
                {/* Avatar */}
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 border shadow-md ${
                    isUser
                      ? 'bg-blue-600/30 text-blue-300 border-blue-500/40'
                      : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-cyan-500/10'
                  }`}
                >
                  {isUser ? <Terminal className="w-4 h-4" /> : <Bot className="w-5 h-5" />}
                </div>

                {/* Message Body */}
                <div className={`space-y-2 max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
                  {/* Tool Call Cards */}
                  {hasTools && (
                    <div className="space-y-2">
                      {m.tool_calls!.map((tc, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-xl bg-slate-900/90 border border-cyan-500/30 text-xs font-mono shadow-md"
                        >
                          <div className="flex items-center justify-between text-cyan-400 font-bold mb-1">
                            <span className="flex items-center gap-1.5">
                              <Zap className="w-3.5 h-3.5 text-amber-400" />
                              算子调用: {tc.tool_name}
                            </span>
                            <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/30">
                              执行成功
                            </span>
                          </div>
                          {tc.tool_name === 'calculate_beneish_m_score' && tc.tool_output?.is_calculable && (
                            <div className="text-slate-300 mt-1">
                              测算得分: <strong className="text-rose-400">{tc.tool_output.m_score?.toFixed(2)}</strong> (
                              {tc.tool_output.is_manipulator ? '⚠️ 高危财务操纵' : '正常无操纵'})
                            </div>
                          )}
                          {tc.tool_name === 'perform_three_way_reconciliation' && (
                            <div className="text-slate-300 mt-1">
                              检出三单勾稽异常:{' '}
                              <strong className="text-amber-400">
                                {tc.tool_output?.total_discrepancies_count || 0} 处
                              </strong>
                              ，涉及错报金额: ¥
                              {(tc.tool_output?.total_abnormal_amount || 0).toLocaleString()} 元
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* CoT Thinking Drawer */}
                  {hasCoT && (
                    <div className="rounded-xl border border-purple-500/30 bg-purple-950/20 overflow-hidden text-xs">
                      <button
                        onClick={() => toggleCoT(m.id)}
                        className="w-full flex items-center justify-between px-3 py-2 bg-purple-950/40 hover:bg-purple-900/40 text-purple-300 font-mono transition-colors"
                      >
                        <span className="flex items-center gap-1.5">
                          <BrainCircuit className="w-3.5 h-3.5 text-purple-400" />
                          DeepSeek CoT 深度思考链推演
                        </span>
                        {isCoTExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>

                      {isCoTExpanded && (
                        <div className="p-3 font-mono text-[11px] text-purple-200/90 whitespace-pre-wrap leading-relaxed border-t border-purple-500/20 bg-black/40">
                          {m.reasoning_content}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Main Bubble Content */}
                  <div
                    className={`p-4 rounded-2xl text-xs leading-relaxed ${
                      isUser
                        ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-lg shadow-blue-500/10'
                        : 'bg-slate-900/90 text-slate-200 border border-white/10 shadow-xl'
                    }`}
                  >
                    <div className="prose prose-invert prose-xs max-w-none whitespace-pre-wrap">
                      {m.content}
                    </div>
                    <div
                      className={`text-[10px] mt-2 font-mono ${
                        isUser ? 'text-blue-200' : 'text-slate-500'
                      } text-right`}
                    >
                      {m.timestamp}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}

          {/* Loading Indicator */}
          {isGenerating && (
            <div className="flex gap-4 mr-auto max-w-4xl animate-pulse">
              <div className="w-9 h-9 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center justify-center">
                <Bot className="w-5 h-5 animate-spin" />
              </div>
              <div className="p-4 rounded-2xl bg-slate-900/90 border border-cyan-500/30 text-xs text-slate-400 font-mono flex items-center gap-2">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                <span>DeepSeek 智能体正在调阅账套并深度演绎审计准则...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Prompt Chips */}
        <div className="px-6 py-2 bg-slate-950/60 border-t border-white/5 flex items-center gap-2 overflow-x-auto custom-scrollbar">
          <span className="text-[11px] text-slate-500 whitespace-nowrap font-mono flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-cyan-400" /> 快捷提问:
          </span>
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(p)}
              disabled={isGenerating}
              className="text-[11px] px-2.5 py-1 rounded-full bg-slate-900 hover:bg-cyan-500/10 text-slate-300 hover:text-cyan-300 border border-white/10 hover:border-cyan-500/30 whitespace-nowrap transition-all"
            >
              {p}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-slate-900/80 border-t border-white/10">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSendMessage()
            }}
            className="flex items-center gap-3"
          >
            <div className="relative flex-1">
              <input
                type="text"
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                placeholder="向 DeepSeek 审计智能体提问（例如：请根据 CAS 14 准则核查发票与凭证金额差异，或输入 /goal 启动自主审计）..."
                disabled={isGenerating}
                className="w-full px-4 py-3 bg-slate-950/90 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 font-sans shadow-inner pr-10"
              />
              <button
                type="submit"
                disabled={!inputPrompt.trim() || isGenerating}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white disabled:opacity-40 transition-all shadow-md shadow-cyan-500/20"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>

            <button
              type="button"
              onClick={handleRunGoal}
              disabled={isRunningGoal || isGenerating}
              className="hidden sm:flex items-center gap-1.5 px-3.5 py-3 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/40 text-xs font-mono font-medium transition-all shadow-md shadow-purple-500/10 whitespace-nowrap"
            >
              <BrainCircuit className="w-3.5 h-3.5" />
              <span>/goal 自主审计</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
