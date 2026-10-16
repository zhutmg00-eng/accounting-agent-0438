import React, { useState, useRef, useEffect } from 'react'
import { RefreshCw, Play, ChevronDown, ChevronUp, RotateCw } from 'lucide-react'
import {
  AgentMessage,
  AgentToolCall,
  AgentGoalStep,
  DeepSeekModelsResponse,
  AccountingVoucher,
  BankFlowRecord
} from '../types'
import {
  Panel,
  PanelHeader,
  Surface,
  Btn,
  Chip,
  Status,
  StatusMark,
  DataTable,
  Th,
  Td,
  TdNum,
  EmptyState,
  SkeletonRows,
  cn,
  type Tone
} from '../ui/primitives'
import { StageRail, Reveal, usePrefersReducedMotion } from '../ui/motion'

interface AgentWorkbenchProps {
  currentCase: any
  executionMode: string
  modelInfo: DeepSeekModelsResponse | null
  onOpenModelModal: () => void
}

/**
 * Beat 2 "穿透": the agent is working.
 *
 * One lit surface carries the case being penetrated and the size of the
 * evidence set the agent is working through. Everything else sits on the dark
 * field: colour steps separate the panels, and the only accent in the room is
 * the single primary action.
 */
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
  const reducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' })
  }, [messages, isGenerating, goalSteps, reducedMotion])

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
          tool_routing: replyData.tool_routing,
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
          content: `**智能体交互异常**：${e.message}\n请检查网络连接、API 状态或切换为 MOCK 模式重试。`,
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
        `自主目标执行完成（耗时 ${data.elapsed_seconds}s | ${data.model_name}）\n` +
        `识别风险发现：${data.report?.findings?.length || 0} 项，生成标准工作底稿：${data.report?.workpapers?.length || 0} 份。`
      )

      // Add summary message into conversation
      setMessages((prev) => [
        ...prev,
        {
          id: `goal-${Date.now()}`,
          role: 'assistant',
          content: `### 自主审计目标执行完成 (/goal)\n\n**审计意见概要**：\n${data.report?.executive_summary || '已完成端到端审计。'}\n\n` +
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
      setGoalSummary(`目标执行失败: ${e.message}`)
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

  /* --------------------------------------------------------------------- */
  /* Figures                                                                 */
  /* --------------------------------------------------------------------- */

  const voucherCount = currentCase?.vouchers?.length || 0
  const invoiceCount = currentCase?.invoices?.length || 0
  const flowCount = currentCase?.bank_flows?.length || 0
  const evidenceTotal = voucherCount + invoiceCount + flowCount
  const loadedKinds = [voucherCount, invoiceCount, flowCount].filter((n) => n > 0).length
  const activeModel = modelInfo?.active_model || 'deepseek-flash'

  /** The four mounted operators, with the exact instruction each one sends. */
  const operators: { name: string; label: string; detail: string; prompt: string }[] = [
    {
      name: 'calculate_beneish_m_score',
      label: 'Beneish M-Score 模型',
      detail: 'DSRI, GMI, AQI, SGI 8 维指标刚性测算',
      prompt: '请立即调用 calculate_beneish_m_score 算子计算当前案例的 8 因子操纵指数'
    },
    {
      name: 'perform_three_way_reconciliation',
      label: '三单穿透勾稽核对',
      detail: '凭证 vs 合同 vs 发票 vs 银行流水闭环',
      prompt: '请立即调用 perform_three_way_reconciliation 算子执行业财三单穿透勾稽核对'
    },
    {
      name: 'search_accounting_vouchers',
      label: '记账凭证多维检索',
      detail: '快速排查异常分录与无原始凭据单据',
      prompt: '请检索本案例所有大额记账凭证并分析分录科目借贷平衡情况'
    },
    {
      name: 'trace_bank_flow_counterparties',
      label: '银行流水穿透排查',
      detail: '识别关联方资金占用与闭环空转',
      prompt: '请检索分析本案例银行对账单大额流水与交易对手方关联性'
    }
  ]

  const goalRailState = (status: string): 'pending' | 'running' | 'done' | 'failed' => {
    const s = String(status || '').toLowerCase()
    if (s === 'completed' || s === 'done' || s === 'success') return 'done'
    if (s === 'running' || s === 'active') return 'running'
    if (s === 'failed' || s === 'error') return 'failed'
    return 'pending'
  }

  const goalTone = (state: 'pending' | 'running' | 'done' | 'failed'): Tone =>
    state === 'done' ? 'clear' : state === 'failed' ? 'critical' : state === 'running' ? 'neutral' : 'neutral'

  const goalStateText = (state: 'pending' | 'running' | 'done' | 'failed') =>
    state === 'done' ? '已完成' : state === 'failed' ? '失败' : state === 'running' ? '进行中' : '待执行'

  const toolTone = (status: unknown): Tone => {
    const s = String(status || '').toLowerCase()
    if (s === 'failed' || s === 'error') return 'critical'
    if (s === 'running' || s === 'pending') return 'medium'
    return 'clear'
  }

  const shortOperator = (name: string) => {
    if (name === 'calculate_beneish_m_score') return 'Beneish M-Score'
    if (name === 'perform_three_way_reconciliation') return '三单勾稽核对'
    if (name === 'journal_entry_testing') return '全量分录测试'
    if (name === 'detect_fund_round_trips') return '资金往返识别'
    if (name === 'benford_first_digit_test') return 'Benford 检验'
    if (name === 'search_vouchers') return '凭证检索'
    if (name === 'search_bank_flows') return '流水检索'
    return name
  }

  /** One row per operator call: mark, name, then the figure the call returned. */
  const renderToolCall = (tc: AgentToolCall, idx: number) => {
    const o = tc.tool_output
    let figure: React.ReactNode = null

    if (tc.tool_name === 'calculate_beneish_m_score' && o?.is_calculable) {
      const manipulator = Boolean(o?.is_manipulator)
      figure = (
        <span className="flex flex-wrap items-baseline justify-end gap-x-3 gap-y-1">
          <span className={cn('tabular-nums text-body font-semibold', manipulator ? 'text-risk-critical' : 'text-fg')}>
            M = {typeof o?.m_score === 'number' ? o.m_score.toFixed(2) : '---'}
          </span>
          <Status tone={manipulator ? 'critical' : 'clear'}>
            {manipulator ? '高危财务操纵' : '未触发操纵阈值'}
          </Status>
        </span>
      )
    } else if (tc.tool_name === 'perform_three_way_reconciliation') {
      figure = (
        <span className="flex flex-wrap items-baseline justify-end gap-x-3 gap-y-1">
          <span className="tabular-nums text-body font-semibold text-fg">
            {(o?.total_discrepancies_count || 0).toLocaleString()} 处勾稽异常
          </span>
          <span className="tabular-nums text-small text-fg-muted">
            涉及错报金额 ¥{(o?.total_abnormal_amount || 0).toLocaleString()}
          </span>
        </span>
      )
    } else if (tc.tool_name === 'journal_entry_testing' && o?.applicable) {
      figure = (
        <span className="tabular-nums text-body text-fg">
          {o.population} 张凭证全量测试 · 风险标识 {o.flagged_count} 张 · 高风险 {o.high_risk_count} 张
        </span>
      )
    } else if (tc.tool_name === 'detect_fund_round_trips' && o) {
      figure = (
        <span className="tabular-nums text-body text-fg">
          {o.loop_count ? `检出 ${o.loop_count} 组资金往返 · ¥${(o.loop_amount || 0).toLocaleString()}` : '未发现资金往返'}
        </span>
      )
    } else if (tc.tool_name === 'benford_first_digit_test' && o) {
      figure = (
        <span className="text-body text-fg">
          {o.applicable ? `${o.verdict} · MAD ${o.mad} · 样本 ${o.sample_size}` : '样本不足，不适用'}
        </span>
      )
    } else if (o !== undefined && o !== null) {
      figure = <span className="text-body text-fg">{typeof o?.matched === 'number' ? `命中 ${o.matched} 条` : '已返回结构化结果'}</span>
    } else {
      figure = <span className="text-small text-fg-faint">无返回值</span>
    }

    const tone = toolTone(tc.status)

    return (
      <div key={idx} className="bg-field-raised2 px-4 py-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <span className="text-small font-medium text-fg">
            {shortOperator(tc.tool_name)}
            <span className="ml-3 text-label text-fg-faint">{tc.tool_name}</span>
            {tc.tool_input && Object.keys(tc.tool_input).length && tc.decided_by === 'model' ? (
              <span className="ml-3 text-label tabular-nums text-fg-faint">
                参数 {JSON.stringify(tc.tool_input)}
              </span>
            ) : null}
          </span>
          <Status tone={tone}>
            {tone === 'critical' ? '执行失败' : tone === 'medium' ? '执行中' : '执行成功'}
          </Status>
        </div>
        <div className="mt-1.5">{figure}</div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col lg:flex-row overflow-hidden bg-field">
      {/* ------------------------------------------------------------------ */}
      {/* Left rail: the case on paper, then the goal hub and the operators.  */}
      {/* ------------------------------------------------------------------ */}
      <aside
        aria-label="被审计单位与证据装载"
        className="w-full lg:w-[23rem] lg:shrink-0 overflow-y-auto bg-field-sunken"
      >
        <Reveal index={0} className="h-full">
          <Surface
            paper
            className="px-5 pb-6 pt-5"
            aria-label="当前被审计单位与已装入证据规模"
          >
            <div className="text-label text-ink-muted">当前被审计单位</div>
            <div className="mt-1 text-title font-semibold text-ink">
              {currentCase?.company_name || '未选定案例'}
            </div>
            <div className="mt-1 text-small text-ink-muted">
              <span className="tabular-nums">{currentCase?.stock_code || '---'}</span>
              {' · '}
              {currentCase?.industry || '行业未标注'}
            </div>

            <div className="mt-5 text-label text-ink-muted">已装载证据</div>
            <div
              className="mt-1 tabular-nums text-display font-semibold text-ink"
              aria-label="当前案例已装载证据总量"
            >
              {evidenceTotal.toLocaleString()}
            </div>
            <div className="mt-1 text-small text-ink-muted">
              凭证 <span className="tabular-nums">{voucherCount}</span> 笔 · 发票{' '}
              <span className="tabular-nums">{invoiceCount}</span> 张 · 流水{' '}
              <span className="tabular-nums">{flowCount}</span> 笔
            </div>
            <div className="mt-3 text-label text-ink-muted">
              {loadedKinds > 0
                ? `已覆盖 ${loadedKinds} / 3 类业务凭证，等待智能体逐条穿透`
                : '账套尚未装载证据，请先在左侧案例栏选择或导入账套'}
            </div>
          </Surface>

          <Panel
            title="自主审计目标"
            note="目标规划、算子调度、CAS 研判与底稿合成为一次连续编排。"
            meta={<Chip tone="neutral">/goal</Chip>}
            className="bg-transparent px-0 pb-5 pt-2"
          >
            <div className="px-5">
              <Btn
                variant="primary"
                size="lg"
                className="w-full"
                onClick={handleRunGoal}
                disabled={isRunningGoal || !currentCase}
                icon={isRunningGoal ? <RefreshCw className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              >
                {isRunningGoal ? '自主目标执行中' : '执行自主审计目标'}
              </Btn>

              {goalSteps.length > 0 ? (
                <ol className="mt-5 space-y-4">
                  {goalSteps.map((s) => {
                    const state = goalRailState(s.status)
                    return (
                      <li key={s.step} className="space-y-2">
                        <div className="flex items-baseline justify-between gap-3">
                          <span className="text-body font-medium text-fg">{s.title}</span>
                          <Status tone={goalTone(state)}>{goalStateText(state)}</Status>
                        </div>
                        <StageRail state={state} />
                        <div className="text-label text-fg-faint">{s.detail}</div>
                      </li>
                    )
                  })}
                </ol>
              ) : (
                <EmptyState
                  className="px-0 pb-0 pt-6"
                  title="尚未启动自主审计"
                  body="点击上方按钮后，智能体会依次点亮四道审计阶段：账套画像、算子调度、准则研判与底稿合成。"
                />
              )}

              {goalSummary ? (
                <p className="mt-5 whitespace-pre-line bg-field-raised2 px-4 py-3 text-body text-fg">
                  {goalSummary}
                </p>
              ) : null}
            </div>
          </Panel>

          <Panel
            title="审计算子工具箱"
            note="点击任一行即把该算子交予智能体执行。"
            meta={<span className="tabular-nums">{operators.length} 项已挂载</span>}
            className="bg-transparent px-0 pb-5 pt-2"
          >
            <div className="px-5">
              <DataTable className="min-w-0">
                <caption className="sr-only">
                  审计算子工具箱：可挂载的算子、覆盖的证据面与执行方式
                </caption>
                <thead>
                  <tr>
                    <Th>审计算子</Th>
                    <Th>覆盖的证据面</Th>
                    <Th className="text-right">操作</Th>
                  </tr>
                </thead>
                <tbody>
                  {operators.map((op) => (
                    <tr
                      key={op.name}
                      tabIndex={0}
                      role="button"
                      aria-label={`调用算子 ${op.label}`}
                      onClick={() => handleSendMessage(op.prompt)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          handleSendMessage(op.prompt)
                        }
                      }}
                      className={cn(
                        'row-hover cursor-pointer',
                        isGenerating && 'cursor-not-allowed opacity-40'
                      )}
                    >
                      <Td>
                        <span className="block text-body font-medium text-fg">{op.label}</span>
                        <span className="mt-0.5 block text-label text-fg-faint">{op.name}</span>
                      </Td>
                      <Td className="text-fg-muted">{op.detail}</Td>
                      <Td className="text-right">
                        <span className="text-label font-medium text-seal-soft">执行</span>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            </div>
          </Panel>

          <Reveal index={1} className="px-5 pb-6">
            <Panel
              title="推理模型"
              note="模型探测结果决定准则推理的运行路径。"
              className="bg-transparent px-0"
            >
              <div className="px-5">
                <div className="flex flex-wrap items-end justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-label text-fg-muted">当前装载模型</div>
                    <div className="mt-1 truncate text-body font-semibold text-fg">{activeModel}</div>
                    <div className="mt-1 text-label text-fg-faint">
                      {modelInfo?.latency_ms !== undefined && modelInfo?.latency_ms !== null
                        ? `探测延迟 ${modelInfo.latency_ms}ms`
                        : '尚未探测'}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Chip tone="neutral">运行模式 {executionMode}</Chip>
                    <Btn size="sm" onClick={onOpenModelModal} icon={<RotateCw className="h-3.5 w-3.5" />}>
                      重新探测
                    </Btn>
                  </div>
                </div>
              </div>
            </Panel>
          </Reveal>
        </Reveal>
      </aside>

      {/* ------------------------------------------------------------------ */}
      {/* Main canvas: the conversation, top bar, prompts and the input.      */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden bg-field">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-6 py-4">
          <div className="min-w-0">
            <h2 className="text-title font-semibold text-fg">智能体会话</h2>
            <p className="mt-1 text-body text-fg">
              算子调用、思考链与审计意见在同一条时间线上逐条留下痕迹。
            </p>
          </div>
          <label className="flex cursor-pointer select-none items-center gap-3 text-small text-fg-muted">
            <input
              type="checkbox"
              name="tools-enabled"
              checked={toolsEnabled}
              onChange={(e) => setToolsEnabled(e.target.checked)}
              className="rounded-none border border-white/[0.08] bg-field-sunken text-seal accent-seal"
            />
            <span>启用审计算子调度 (Tools)</span>
          </label>
        </div>

        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <div className="max-w-4xl space-y-6 pt-2">
            {messages.map((m, mi) => {
              const isUser = m.role === 'user'
              const hasCoT = Boolean(m.reasoning_content)
              const hasTools = Boolean(m.tool_calls && m.tool_calls.length > 0)
              const isCoTExpanded = expandedCoT[m.id]

              return (
                <Reveal
                  key={m.id}
                  index={Math.min(mi, 8)}
                  className={cn('flex', isUser ? 'justify-end' : 'justify-start')}
                >
                  <div className={cn('w-full space-y-3', isUser ? 'max-w-[46rem] sm:w-auto' : 'max-w-[52rem]')}>
                    <div
                      className={cn(
                        'flex items-baseline gap-3 text-label',
                        isUser ? 'justify-end' : 'justify-start'
                      )}
                    >
                      <span className={isUser ? 'text-fg-faint' : 'text-fg-muted'}>
                        {isUser ? '审计员' : 'DeepSeek-AuditMind'}
                      </span>
                      <span className="tabular-nums text-fg-faint">{m.timestamp}</span>
                    </div>

                    {hasTools ? (
                      <div className="space-y-px">
                        {m.tool_routing ? (
                          <div className="px-1 pb-1 text-label text-fg-faint">
                            {m.tool_routing === 'model_function_calling'
                              ? `DeepSeek 自主决定调用 ${m.tool_calls!.length} 个审计算子（原生函数调用）`
                              : '离线模式：按关键词路由到审计算子'}
                          </div>
                        ) : null}
                        {m.tool_calls!.map(renderToolCall)}
                      </div>
                    ) : null}

                    {hasCoT ? (
                      <div className="bg-field-raised">
                        <button
                          type="button"
                          onClick={() => toggleCoT(m.id)}
                          aria-expanded={isCoTExpanded}
                          className="row-hover flex w-full items-center justify-between gap-4 px-4 py-3 text-left"
                        >
                          <span className="flex items-center gap-3">
                            <StatusMark tone="neutral" />
                            <span className="text-body font-medium text-fg">思考链原文</span>
                            <Chip tone="neutral">CoT</Chip>
                          </span>
                          {isCoTExpanded ? (
                            <ChevronUp className="h-4 w-4 shrink-0 text-fg-muted" />
                          ) : (
                            <ChevronDown className="h-4 w-4 shrink-0 text-fg-muted" />
                          )}
                        </button>

                        {isCoTExpanded ? (
                          <pre className="max-h-96 overflow-auto whitespace-pre-wrap bg-field-sunken px-4 py-4 text-small text-fg-muted">
                            {m.reasoning_content}
                          </pre>
                        ) : null}
                      </div>
                    ) : null}

                    <div
                      className={cn(
                        'px-5 py-4 text-body',
                        isUser ? 'bg-field-raised3 text-fg' : 'bg-field-raised text-fg'
                      )}
                    >
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    </div>
                  </div>
                </Reveal>
              )
            })}

            {isGenerating ? (
              <div role="status" aria-live="polite" className="max-w-[52rem] space-y-3">
                <div className="flex items-baseline gap-3 text-label">
                  <span className="text-fg-muted">DeepSeek-AuditMind</span>
                  <span className="text-fg-faint">正在演绎</span>
                </div>
                <SkeletonRows rows={3} />
              </div>
            ) : null}

            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 px-6 py-3">
          <span className="text-label text-fg-faint">快捷提问</span>
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSendMessage(p)}
              disabled={isGenerating}
              className="press rounded-none px-3 py-2 text-left text-small text-fg-muted hover:bg-field-raised2 hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
            >
              {p}
            </button>
          ))}
        </div>

        <div className="px-6 py-5">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSendMessage()
            }}
            className="flex flex-wrap items-center gap-3"
          >
            <input
              type="text"
              name="agent-prompt"
              aria-label="向 DeepSeek 审计智能体提问"
              autoComplete="off"
              spellCheck={false}
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              placeholder="向 DeepSeek 审计智能体提问（例如：请根据 CAS 14 准则核查发票与凭证金额差异，或输入 /goal 启动自主审计）…"
              disabled={isGenerating}
              className="min-w-[16rem] flex-1 bg-field-sunken px-4 py-3 text-body text-fg placeholder:text-fg-faint border border-white/[0.08]"
            />
            <Btn
              type="submit"
              variant="solid"
              size="lg"
              disabled={!inputPrompt.trim() || isGenerating}
            >
              发送
            </Btn>
          </form>
        </div>
      </div>
    </div>
  )
}
