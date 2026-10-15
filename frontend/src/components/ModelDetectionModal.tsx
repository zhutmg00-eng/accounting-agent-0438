import React, { useId, useRef, useState } from 'react'
import { X, CheckCircle2, RefreshCw } from 'lucide-react'
import { DeepSeekModelsResponse, DeepSeekModelProfile } from '../types'
import { useFocusTrap } from '../lib/useFocusTrap'
import {
  Btn,
  Chip,
  DataTable,
  DataValue,
  ErrorNote,
  Status,
  Surface,
  Td,
  TdNum,
  Th
} from '../ui/primitives'

interface ModelDetectionModalProps {
  isOpen: boolean
  onClose: () => void
  modelInfo: DeepSeekModelsResponse | null
  onRefreshModels: () => void
  onUpdateConfig: (modelName: string, apiKey?: string, apiBase?: string) => Promise<void>
}

/** A field row on the raised surface: same geometry as a table cell. */
const FIELD_CLASS =
  'min-h-[40px] w-full border border-white/10 bg-field-sunken px-3 text-small text-fg placeholder:text-fg-faint'

export const ModelDetectionModal: React.FC<ModelDetectionModalProps> = ({
  isOpen,
  onClose,
  modelInfo,
  onRefreshModels,
  onUpdateConfig
}) => {
  const [selectedModel, setSelectedModel] = useState<string>(modelInfo?.active_model || 'deepseek-v4.1-flash')
  const [apiKey, setApiKey] = useState<string>('')
  const [apiBase, setApiBase] = useState<string>(modelInfo?.api_base || 'https://api.deepseek.com')
  const [isTesting, setIsTesting] = useState<boolean>(false)
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null)

  const panelRef = useRef<HTMLDivElement>(null)
  const dialogTitleId = useId()

  // Same overlay contract as the other two modals: focus in, Tab wrapped,
  // Escape closes, focus back on 模型探测.
  useFocusTrap(isOpen, onClose, { dialogRef: panelRef, panelRef })

  if (!isOpen) return null

  const handleTestAndDetect = async () => {
    setIsTesting(true)
    setFeedbackMsg(null)
    try {
      const resp = await fetch('/api/deepseek/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey.trim() || undefined,
          api_base: apiBase.trim() || undefined
        })
      })
      const data = await resp.json()
      if (data.detected_model) {
        setSelectedModel(data.detected_model)
      }
      setFeedbackMsg(data.message || '检测完成')
      onRefreshModels()
    } catch (e: any) {
      setFeedbackMsg(`检测异常: ${e.message}`)
    } finally {
      setIsTesting(false)
    }
  }

  const handleApply = async () => {
    setIsTesting(true)
    try {
      await onUpdateConfig(selectedModel, apiKey.trim() || undefined, apiBase.trim() || undefined)
      setFeedbackMsg(`已切换当前模型为: ${selectedModel}`)
      setTimeout(() => {
        onClose()
      }, 700)
    } catch (e: any) {
      setFeedbackMsg(`应用失败: ${e.message}`)
    } finally {
      setIsTesting(false)
    }
  }

  const activeProfile = modelInfo?.models_detail?.find((m) => m.id === selectedModel) || modelInfo?.active_model_profile

  const models: DeepSeekModelProfile[] = modelInfo?.models_detail || []
  const latency = modelInfo?.latency_ms

  const isMock = Boolean(modelInfo?.is_mock)
  const isOffline = !modelInfo
  const busyDetect = isTesting ? true : undefined
  const busyApply = isTesting ? true : undefined

  const feedbackIsFailure = Boolean(feedbackMsg && /异常|失败|错误/.test(feedbackMsg))
  const capabilityText = activeProfile?.has_thinking_mode ? '原生内置 CoT' : '标准输出'

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
        className="flex max-h-[92svh] w-full max-w-4xl flex-col overflow-hidden overscroll-contain bg-field-raised shadow-overlay"
      >
        <div className="flex items-start justify-between gap-6 px-5 pt-5 pb-4">
          <div className="min-w-0">
            <h2 id={dialogTitleId} className="text-title font-semibold text-fg">
              DeepSeek 接口与模型自适应识别
            </h2>
            <p className="mt-1 max-w-[68ch] text-body text-fg">
              探测 GET /models 端点，识别当前生效模型、推理特性与实际响应延迟。
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭模型诊断浮层"
            className="press -mr-2 -mt-1 shrink-0 p-2 text-fg-muted hover:bg-field-raised2 hover:text-fg"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-5 pb-5">
          {/* The reading this screen is about: how fast the endpoint answers. */}
          <DataValue
            label="探测响应延迟"
            value={isOffline ? '—' : latency ?? '—'}
            unit={isOffline || latency === undefined ? undefined : 'ms'}
            size="display"
            tone={isMock ? 'medium' : 'clear'}
            className="bg-field-raised2 px-5 py-4"
          />

          <div className="grid gap-4 sm:grid-cols-3">
            <DataValue
              label="连接状态"
              value={
                <Status tone={isOffline ? 'neutral' : isMock ? 'medium' : 'clear'}>
                  {isOffline ? '未探测' : isMock ? 'MOCK 启发式' : 'ONLINE 在线'}
                </Status>
              }
              size="body"
            />
            <DataValue
              label="当前激活模型"
              value={modelInfo?.active_model || selectedModel}
              size="body"
            />
            <DataValue label="可用模型" value={models.length} unit="个" size="body" />
          </div>

          {activeProfile ? (
            <Surface level="raised2" className="px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
                <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
                  <h3 className="text-title font-semibold text-fg">{activeProfile.display_name}</h3>
                  <Chip>{activeProfile.series}</Chip>
                  {activeProfile.is_latest_2026 ? <Chip tone="clear">2026 推荐</Chip> : null}
                </div>
                <span className="text-label text-fg-faint">{activeProfile.id}</span>
              </div>
              <p className="mt-2 max-w-[75ch] text-body text-fg">{activeProfile.description}</p>
              <div className="mt-4 grid gap-4 sm:grid-cols-4">
                <DataValue label="Thinking 思维链" value={capabilityText} size="body" />
                <DataValue
                  label="算子工具调用"
                  value={activeProfile.supports_tools ? '原生优化' : '仅对话'}
                  size="body"
                />
                <DataValue label="吞吐速度" value={activeProfile.throughput_tier} size="body" />
                <DataValue label="上下文窗口" value={activeProfile.context_window} size="body" />
              </div>
            </Surface>
          ) : null}

          <div>
            <div className="mb-2 flex items-baseline justify-between gap-4">
              <h3 className="text-label text-fg-muted">可选模型与架构</h3>
              <span className="text-label text-fg-faint">点击一行切换候选模型</span>
            </div>

            {models.length ? (
              <DataTable>
                <thead>
                  <tr>
                    <Th className="w-20">选中</Th>
                    <Th className="w-56">模型</Th>
                    <Th>定位与推荐场景</Th>
                    <Th className="w-36">推理特性</Th>
                    <Th className="w-28">上下文</Th>
                    <Th className="w-24 text-right">吞吐</Th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m) => {
                    const isSel = selectedModel === m.id
                    return (
                      <tr
                        key={m.id}
                        tabIndex={0}
                        aria-selected={isSel}
                        onClick={() => setSelectedModel(m.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            setSelectedModel(m.id)
                          }
                        }}
                        className={isSel ? 'bg-field-raised2' : 'hover:bg-field-raised2'}
                      >
                        <Td>
                          <Status tone={isSel ? 'clear' : 'neutral'}>{isSel ? '当前' : '未选'}</Status>
                        </Td>
                        <Td>
                          <div className="font-medium text-fg">{m.display_name}</div>
                          <div className="text-label text-fg-faint">{m.id}</div>
                        </Td>
                        <Td className="text-fg-muted">{m.recommended_scenario}</Td>
                        <Td className="text-fg-muted">{m.has_thinking_mode ? 'CoT 深度思考' : '极速响应'}</Td>
                        <Td className="tabular-nums text-fg-muted">{m.context_window}</Td>
                        <TdNum className="text-fg-muted">{m.throughput_tier}</TdNum>
                      </tr>
                    )
                  })}
                </tbody>
              </DataTable>
            ) : (
              <Surface level="raised2" className="px-5 py-4">
                <p className="text-body text-fg-muted">
                  尚未取得模型清单。点左下角「重新探测」从当前端点拉取一次。
                </p>
              </Surface>
            )}
          </div>

          <div className="space-y-4 bg-field-raised2 px-5 py-4">
            <div>
              <label htmlFor="deepseek-api-base" className="mb-1.5 block text-label text-fg-muted">
                API 端点 Base URL
              </label>
              <input
                id="deepseek-api-base"
                name="deepseek-api-base"
                type="text"
                inputMode="url"
                autoComplete="off"
                spellCheck={false}
                value={apiBase}
                onChange={(e) => setApiBase(e.target.value)}
                placeholder="https://api.deepseek.com"
                className={FIELD_CLASS}
              />
            </div>

            <div>
              <label htmlFor="deepseek-api-key" className="mb-1.5 block text-label text-fg-muted">
                DeepSeek API Key（选填，留空则保持当前配置）
              </label>
              <input
                id="deepseek-api-key"
                name="deepseek-api-key"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-…"
                autoComplete="off"
                spellCheck={false}
                className={FIELD_CLASS}
              />
              <p className="mt-1.5 text-label text-fg-faint">
                密钥只随本次请求发出，不写回界面，也不在此处回显。
              </p>
            </div>
          </div>

          {/* Stays mounted so the detection result is announced when it lands. */}
          <div aria-live="polite">
            {feedbackMsg ? (
              feedbackIsFailure ? (
                <ErrorNote title="模型配置未生效" detail={feedbackMsg} />
              ) : (
                <Surface level="raised2" className="px-5 py-4">
                  <p className="text-body text-fg">{feedbackMsg}</p>
                </Surface>
              )
            ) : null}
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 bg-field-raised px-5 py-4">
          <Btn onClick={handleTestAndDetect} disabled={busyDetect}>
            <RefreshCw aria-hidden className={`h-4 w-4 ${isTesting ? 'animate-spin' : ''}`} />
            重新探测
          </Btn>

          <div className="flex items-center gap-3">
            <Btn variant="ghost" onClick={onClose}>
              取消
            </Btn>
            <Btn
              variant="primary"
              onClick={handleApply}
              disabled={busyApply}
              icon={<CheckCircle2 className="h-4 w-4" />}
            >
              应用当前模型
            </Btn>
          </div>
        </div>
      </div>
    </div>
  )
}
