import React, { useState } from 'react'
import { X, Sparkles, Cpu, Zap, BrainCircuit, CheckCircle2, AlertCircle, RefreshCw, Server, Key } from 'lucide-react'
import { DeepSeekModelsResponse, DeepSeekModelProfile } from '../types'

interface ModelDetectionModalProps {
  isOpen: boolean
  onClose: () => void
  modelInfo: DeepSeekModelsResponse | null
  onRefreshModels: () => void
  onUpdateConfig: (modelName: string, apiKey?: string, apiBase?: string) => Promise<void>
}

export const ModelDetectionModal: React.FC<ModelDetectionModalProps> = ({
  isOpen,
  onClose,
  modelInfo,
  onRefreshModels,
  onUpdateConfig
}) => {
  if (!isOpen) return null

  const [selectedModel, setSelectedModel] = useState<string>(modelInfo?.active_model || 'deepseek-v4.1-flash')
  const [apiKey, setApiKey] = useState<string>('')
  const [apiBase, setApiBase] = useState<string>(modelInfo?.api_base || 'https://api.deepseek.com')
  const [isTesting, setIsTesting] = useState<boolean>(false)
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null)

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-2xl bg-[#0B101B] border border-cyan-500/30 rounded-2xl shadow-2xl shadow-cyan-500/10 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-slate-900/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>DeepSeek 接口与模型自适应识别</span>
                <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                  2026 前沿架构
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                实时探测 GET /models 端点，毫秒级自适应识别当前模型类型与推理特性
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto custom-scrollbar">
          {/* Status Banner */}
          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 rounded-xl bg-slate-900/80 border border-white/5 flex flex-col justify-between">
              <span className="text-xs text-slate-400 flex items-center gap-1.5">
                <Server className="w-3.5 h-3.5 text-blue-400" /> 连接状态
              </span>
              <div className="flex items-center gap-2 mt-2">
                <span className={`w-2 h-2 rounded-full ${modelInfo?.is_mock ? 'bg-amber-400' : 'bg-emerald-400 animate-pulse'}`} />
                <span className="text-sm font-semibold font-mono text-white">
                  {modelInfo?.is_mock ? 'MOCK 启发式' : 'ONLINE 在线'}
                </span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-white/5 flex flex-col justify-between">
              <span className="text-xs text-slate-400 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-amber-400" /> 探测响应延迟
              </span>
              <div className="flex items-baseline gap-1 mt-2">
                <span className="text-lg font-bold font-mono text-cyan-300">
                  {modelInfo?.latency_ms ?? '--'}
                </span>
                <span className="text-xs text-slate-400 font-mono">ms</span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-900/80 border border-white/5 flex flex-col justify-between">
              <span className="text-xs text-slate-400 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-purple-400" /> 当前激活模型
              </span>
              <span className="text-xs font-bold font-mono text-purple-300 truncate mt-2">
                {modelInfo?.active_model || selectedModel}
              </span>
            </div>
          </div>

          {/* Active Profile Card */}
          {activeProfile && (
            <div className="p-4 rounded-xl bg-gradient-to-br from-cyan-950/40 via-blue-950/20 to-slate-900 border border-cyan-500/30">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <BrainCircuit className="w-4 h-4 text-cyan-400" />
                  <span className="text-sm font-bold text-white font-mono">{activeProfile.display_name}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-mono">
                    {activeProfile.series}
                  </span>
                </div>
                {activeProfile.is_latest_2026 && (
                  <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30">
                    2026推荐
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-300 mb-3">{activeProfile.description}</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="bg-black/30 p-2 rounded border border-white/5">
                  <div className="text-slate-400 text-[10px]">Thinking 思维链</div>
                  <div className="font-semibold text-white mt-0.5">
                    {activeProfile.has_thinking_mode ? '🟢 原生内置 CoT' : '⚪ 标准输出'}
                  </div>
                </div>
                <div className="bg-black/30 p-2 rounded border border-white/5">
                  <div className="text-slate-400 text-[10px]">算子工具调用</div>
                  <div className="font-semibold text-white mt-0.5">
                    {activeProfile.supports_tools ? '🟢 原生优化' : '⚪ 仅对话'}
                  </div>
                </div>
                <div className="bg-black/30 p-2 rounded border border-white/5">
                  <div className="text-slate-400 text-[10px]">吞吐速度</div>
                  <div className="font-semibold text-cyan-300 mt-0.5 font-mono">{activeProfile.throughput_tier}</div>
                </div>
                <div className="bg-black/30 p-2 rounded border border-white/5">
                  <div className="text-slate-400 text-[10px]">上下文窗口</div>
                  <div className="font-semibold text-purple-300 mt-0.5 font-mono">{activeProfile.context_window}</div>
                </div>
              </div>
            </div>
          )}

          {/* Model Selection List */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-2">
              可选模型与架构列表 (点击选择)
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {(modelInfo?.models_detail || []).map((m) => {
                const isSel = selectedModel === m.id
                return (
                  <div
                    key={m.id}
                    onClick={() => setSelectedModel(m.id)}
                    className={`cursor-pointer p-3 rounded-xl border transition-all ${
                      isSel
                        ? 'bg-cyan-500/10 border-cyan-400/80 shadow-md shadow-cyan-500/10'
                        : 'bg-slate-900/60 border-white/5 hover:border-white/20'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold font-mono text-white">{m.display_name}</span>
                      {isSel && <CheckCircle2 className="w-4 h-4 text-cyan-400" />}
                    </div>
                    <div className="text-[11px] text-slate-400 truncate mt-1">{m.recommended_scenario}</div>
                    <div className="flex items-center gap-2 mt-2 text-[10px] font-mono text-slate-400">
                      <span>{m.throughput_tier}</span>
                      <span>·</span>
                      <span>{m.has_thinking_mode ? 'CoT 深度思考' : '极速响应'}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* API Key & Endpoint Configuration */}
          <div className="space-y-3 pt-2 border-t border-white/10">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1 flex items-center gap-1.5">
                <Server className="w-3.5 h-3.5 text-slate-400" />
                API 端点 (Base URL)
              </label>
              <input
                type="text"
                value={apiBase}
                onChange={(e) => setApiBase(e.target.value)}
                placeholder="https://api.deepseek.com"
                className="w-full px-3 py-2 text-xs font-mono bg-slate-900/90 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/60"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-slate-400" />
                DeepSeek API Key (选填，留空则保持当前配置)
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full px-3 py-2 text-xs font-mono bg-slate-900/90 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/60"
              />
            </div>
          </div>

          {/* Feedback message */}
          {feedbackMsg && (
            <div className="text-xs p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span>{feedbackMsg}</span>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-white/10 bg-slate-900/80">
          <button
            onClick={handleTestAndDetect}
            disabled={isTesting}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-medium rounded-lg bg-white/5 hover:bg-white/10 text-slate-200 border border-white/10 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : ''}`} />
            <span>自动识别与测试 (Auto-Detect)</span>
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3.5 py-2 text-xs font-medium rounded-lg text-slate-400 hover:text-white transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleApply}
              disabled={isTesting}
              className="flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white shadow-lg shadow-cyan-500/20 border border-cyan-400/30 transition-all disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>应用当前模型</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
